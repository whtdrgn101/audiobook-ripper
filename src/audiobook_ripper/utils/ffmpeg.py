"""FFmpeg utility functions."""

import re
import subprocess


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available on the system.

    Returns:
        True if FFmpeg is available and working
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def get_ffmpeg_version() -> str | None:
    """Get the FFmpeg version string.

    Returns:
        Version string (e.g., "6.0") or None if not available
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse version from first line: "ffmpeg version X.Y.Z ..."
            match = re.search(r"ffmpeg version (\S+)", result.stdout)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def check_libcdio() -> bool:
    """Check if FFmpeg has libcdio support for CD ripping.

    Returns:
        True if libcdio demuxer is available
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-demuxers"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "libcdio" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def check_lame_encoder() -> bool:
    """Check if FFmpeg has libmp3lame encoder support.

    Returns:
        True if libmp3lame encoder is available
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "libmp3lame" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
