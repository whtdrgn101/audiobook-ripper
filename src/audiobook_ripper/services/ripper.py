"""FFmpeg-based CD ripping service."""

import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable


class FFmpegRipper:
    """Service for ripping CD tracks using FFmpeg."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._lock = threading.Lock()
        self._chapter_cache: dict[str, list[dict]] = {}

    def _get_chapters(self, drive: str) -> list[dict]:
        """Get chapter information from the CD.

        Returns list of dicts with 'start_time' and 'end_time' for each track.
        """
        if drive in self._chapter_cache:
            return self._chapter_cache[drive]

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_chapters",
            "-of", "json",
            "-f", "libcdio",
            "-i", f"{drive}:",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                chapters = []
                for chapter in data.get("chapters", []):
                    chapters.append({
                        "start_time": float(chapter.get("start_time", 0)),
                        "end_time": float(chapter.get("end_time", 0)),
                    })
                self._chapter_cache[drive] = chapters
                return chapters
        except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
            pass

        return []

    def get_chapters(self, drive: str) -> list[dict]:
        """Get chapter information from the CD (public interface).

        Returns list of dicts with 'start_time' and 'end_time' for each track.
        """
        return self._get_chapters(drive)

    def get_disc_duration(self, drive: str) -> float:
        """Get total disc duration in seconds."""
        chapters = self._get_chapters(drive)
        if chapters:
            return chapters[-1]["end_time"]
        return 0.0

    def rip_disc(
        self,
        drive: str,
        output_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Rip entire disc to a single WAV file.

        Args:
            drive: Drive letter (e.g., 'D')
            output_path: Output file path for the WAV file
            progress_callback: Optional callback for progress updates (0.0-1.0)

        Raises:
            RuntimeError: If ripping fails or is cancelled
        """
        self._cancelled = False
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get total duration - needed to tell FFmpeg when to stop
        total_duration = self.get_disc_duration(drive)
        if total_duration <= 0:
            raise RuntimeError("Could not determine disc duration")

        # FFmpeg command to rip entire disc
        # Use -t to specify duration (libcdio needs explicit end point)
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f", "libcdio",
            "-i", f"{drive}:",
            "-t", str(total_duration),  # Must specify duration for libcdio
            "-map", "0:a:0",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]

        try:
            with self._lock:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            # Parse FFmpeg's stderr to monitor progress
            # FFmpeg outputs lines like: size=  756992KiB time=01:13:15.02 bitrate=...
            current_time = 0.0

            for line in self._process.stderr:
                if self._cancelled:
                    break

                # Parse time from FFmpeg output
                if "time=" in line:
                    try:
                        # Extract time=HH:MM:SS.ss
                        time_match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
                        if time_match:
                            h, m, s = time_match.groups()
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)

                            if progress_callback:
                                progress = min(current_time / total_duration, 0.99)
                                progress_callback(progress)

                            # Check if we've reached the end
                            if current_time >= total_duration - 1:  # Within 1 second of end
                                self._process.terminate()
                                break
                    except (ValueError, AttributeError):
                        pass

            # Wait for process to finish
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

            if self._cancelled:
                if output_path.exists():
                    output_path.unlink()
                raise RuntimeError("Ripping cancelled")

        finally:
            with self._lock:
                self._process = None

        # Verify the file was created
        if not output_path.exists():
            raise RuntimeError("Rip failed - output file not found")

        if progress_callback:
            progress_callback(1.0)

    def split_audio(
        self,
        input_path: Path,
        output_dir: Path,
        chapters: list[dict],
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[Path]:
        """Split a WAV file into tracks using chapter timestamps.

        Args:
            input_path: Path to the input WAV file
            output_dir: Directory for output WAV files
            chapters: List of dicts with 'start_time' and 'end_time' keys
            progress_callback: Optional callback for progress updates (0.0-1.0)

        Returns:
            List of output WAV file paths

        Raises:
            RuntimeError: If splitting fails or is cancelled
        """
        self._cancelled = False
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths: list[Path] = []

        for i, chapter in enumerate(chapters):
            if self._cancelled:
                raise RuntimeError("Splitting cancelled")

            output_path = output_dir / f"track_{i + 1:02d}.wav"
            start_time = chapter["start_time"]
            end_time = chapter["end_time"]

            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(input_path),
                "-ss", str(start_time),
                "-to", str(end_time),
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(output_path),
            ]

            try:
                with self._lock:
                    self._process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )

                _, stderr = self._process.communicate()

                if self._cancelled:
                    if output_path.exists():
                        output_path.unlink()
                    raise RuntimeError("Splitting cancelled")

                if self._process.returncode != 0:
                    raise RuntimeError(f"FFmpeg split failed: {stderr.decode() if stderr else 'Unknown error'}")

                output_paths.append(output_path)

                if progress_callback:
                    progress_callback((i + 1) / len(chapters))

            finally:
                with self._lock:
                    self._process = None

        return output_paths

    def rip_track(
        self,
        drive: str,
        track_number: int,
        output_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Rip a single track from CD to a WAV file.

        Args:
            drive: Drive letter (e.g., 'D')
            track_number: Track number to rip (1-based)
            output_path: Output file path for the WAV file
            progress_callback: Optional callback for progress updates (0.0-1.0)

        Raises:
            RuntimeError: If ripping fails or is cancelled
        """
        self._cancelled = False
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get chapter times for the track
        chapters = self._get_chapters(drive)
        if not chapters or track_number < 1 or track_number > len(chapters):
            raise RuntimeError(f"Track {track_number} not found on disc")

        chapter = chapters[track_number - 1]  # Convert to 0-based index
        start_time = chapter["start_time"]
        end_time = chapter["end_time"]
        duration = end_time - start_time

        # FFmpeg command to rip from CD using chapter times
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f", "libcdio",
            "-i", f"{drive}:",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-map", "0:a:0",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]

        try:
            with self._lock:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            # Wait for process to complete, consuming output to prevent deadlock
            _, stderr = self._process.communicate()

            if self._cancelled:
                if output_path.exists():
                    output_path.unlink()
                raise RuntimeError("Ripping cancelled")

            if self._process.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {stderr.decode() if stderr else 'Unknown error'}")

            if progress_callback:
                progress_callback(1.0)

        finally:
            with self._lock:
                self._process = None

    def cancel(self) -> None:
        """Cancel the current ripping operation."""
        self._cancelled = True
        with self._lock:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
