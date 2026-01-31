"""CD drive detection and information service."""

import ctypes
import json
import string
import subprocess
from pathlib import Path

from audiobook_ripper.core.models import DriveInfo, Track


class CDDriveService:
    """Service for detecting and interacting with CD drives on Windows."""

    def list_drives(self) -> list[DriveInfo]:
        """List all available CD/DVD drives on the system."""
        drives = []

        # Get logical drives bitmask
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()

        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                drive_path = f"{letter}:\\"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)

                # DRIVE_CDROM = 5
                if drive_type == 5:
                    has_disc = self._check_disc_present(letter)
                    name = self._get_drive_name(letter)
                    drives.append(DriveInfo(
                        letter=letter,
                        name=name,
                        has_disc=has_disc,
                    ))

        return drives

    def _check_disc_present(self, drive: str) -> bool:
        """Check if a disc is present in the drive."""
        drive_path = Path(f"{drive}:\\")
        try:
            # Try to access the drive
            return drive_path.exists() and any(drive_path.iterdir())
        except (OSError, PermissionError):
            return False

    def _get_drive_name(self, drive: str) -> str:
        """Get the volume name or drive model."""
        volume_name = ctypes.create_unicode_buffer(256)
        ctypes.windll.kernel32.GetVolumeInformationW(
            f"{drive}:\\",
            volume_name,
            256,
            None,
            None,
            None,
            None,
            0,
        )
        name = volume_name.value
        return name if name else "CD/DVD Drive"

    def get_tracks(self, drive: str) -> list[Track]:
        """Get track listing from a CD using discid library."""
        try:
            import discid
            disc = discid.read(f"{drive}:")
            tracks = []
            for i, track in enumerate(disc.tracks, start=1):
                duration = track.seconds
                tracks.append(Track(
                    number=i,
                    duration_seconds=duration,
                    title=f"Track {i:02d}",
                ))
            return tracks
        except Exception:
            # Fallback: try to detect tracks via FFmpeg
            return self._get_tracks_ffmpeg(drive)

    def _get_tracks_ffmpeg(self, drive: str) -> list[Track]:
        """Get track listing using FFmpeg as fallback."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_chapters",
                    "-of", "json",
                    "-f", "libcdio",
                    "-i", f"{drive}:",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []

            data = json.loads(result.stdout)
            chapters = data.get("chapters", [])

            tracks = []
            for chapter in chapters:
                track_num = chapter.get("id", 0) + 1  # chapters are 0-indexed
                start_time = float(chapter.get("start_time", 0))
                end_time = float(chapter.get("end_time", 0))
                duration = end_time - start_time
                title = chapter.get("tags", {}).get("title", f"Track {track_num:02d}")

                tracks.append(Track(
                    number=track_num,
                    duration_seconds=duration,
                    title=title,
                ))

            return tracks

        except (subprocess.TimeoutExpired, json.JSONDecodeError, subprocess.SubprocessError):
            return []

    def get_disc_id(self, drive: str) -> str | None:
        """Get the MusicBrainz disc ID for lookup."""
        try:
            import discid
            disc = discid.read(f"{drive}:")
            return disc.id
        except Exception:
            return None

    def eject(self, drive: str) -> None:
        """Eject the disc from the specified drive."""
        # Use Windows MCI command to eject
        ctypes.windll.winmm.mciSendStringW(
            f"open {drive}: type cdaudio alias cdrom",
            None, 0, None
        )
        ctypes.windll.winmm.mciSendStringW(
            "set cdrom door open",
            None, 0, None
        )
        ctypes.windll.winmm.mciSendStringW(
            "close cdrom",
            None, 0, None
        )
