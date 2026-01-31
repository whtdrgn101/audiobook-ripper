"""MP3 encoding service using FFmpeg."""

import re
import subprocess
import threading
from pathlib import Path
from typing import Callable


class EncoderService:
    """Service for encoding audio files to MP3 using FFmpeg."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._lock = threading.Lock()

    def encode_to_mp3(
        self,
        input_path: Path,
        output_path: Path,
        bitrate: int = 192,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Encode a WAV file to MP3.

        Args:
            input_path: Path to input WAV file
            output_path: Path for output MP3 file
            bitrate: MP3 bitrate in kbps (default 192)
            progress_callback: Optional callback for progress updates (0.0-1.0)

        Raises:
            FileNotFoundError: If input file doesn't exist
            RuntimeError: If encoding fails or is cancelled
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        self._cancelled = False
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(input_path),
            "-codec:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            "-q:a", "2",  # VBR quality
            "-progress", "pipe:1",
            str(output_path),
        ]

        # Use local variable for process to support parallel encoding
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Discard stderr to avoid deadlock
            text=True,
        )

        # Track process for cancellation (but use local var for operations)
        with self._lock:
            self._process = process

        try:
            total_duration = self._get_duration(input_path)

            # Parse progress output
            if process.stdout:
                current_time = 0.0
                for line in process.stdout:
                    if self._cancelled:
                        break

                    if line.startswith("out_time_ms="):
                        try:
                            ms = int(line.split("=")[1].strip())
                            current_time = ms / 1_000_000  # Convert to seconds
                            if total_duration > 0 and progress_callback:
                                progress_callback(min(current_time / total_duration, 1.0))
                        except ValueError:
                            pass

            process.wait()

            if self._cancelled:
                if output_path.exists():
                    output_path.unlink()
                raise RuntimeError("Encoding cancelled")

            if process.returncode != 0:
                raise RuntimeError("FFmpeg encoding failed")

            if progress_callback:
                progress_callback(1.0)

        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

    def _get_duration(self, file_path: Path) -> float:
        """Get the duration of an audio file in seconds."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(file_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, ValueError):
            pass

        return 0.0

    def cancel(self) -> None:
        """Cancel the current encoding operation."""
        self._cancelled = True
        with self._lock:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is available on the system."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
