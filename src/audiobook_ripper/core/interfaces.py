"""Protocol interfaces for dependency injection."""

from pathlib import Path
from typing import Callable, Protocol

from audiobook_ripper.core.models import (
    AudiobookMetadata,
    DriveInfo,
    RipProgress,
    Track,
)


class ICDDrive(Protocol):
    """Interface for CD drive operations."""

    def list_drives(self) -> list[DriveInfo]:
        """List all available CD/DVD drives."""
        ...

    def get_tracks(self, drive: str) -> list[Track]:
        """Get track listing from a CD in the specified drive."""
        ...

    def get_disc_id(self, drive: str) -> str | None:
        """Get the MusicBrainz disc ID for lookup."""
        ...

    def eject(self, drive: str) -> None:
        """Eject the disc from the specified drive."""
        ...


class IRipper(Protocol):
    """Interface for CD ripping operations."""

    def rip_track(
        self,
        drive: str,
        track_number: int,
        output_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Rip a single track from CD to a WAV file."""
        ...

    def rip_disc(
        self,
        drive: str,
        output_path: Path,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Rip entire disc to a single WAV file."""
        ...

    def get_chapters(self, drive: str) -> list[dict]:
        """Get chapter/track timing information from the disc."""
        ...

    def cancel(self) -> None:
        """Cancel the current ripping operation."""
        ...


class IEncoder(Protocol):
    """Interface for audio encoding operations."""

    def encode_to_mp3(
        self,
        input_path: Path,
        output_path: Path,
        bitrate: int = 192,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Encode a WAV file to MP3."""
        ...

    def cancel(self) -> None:
        """Cancel the current encoding operation."""
        ...


class IMetadataService(Protocol):
    """Interface for metadata operations."""

    def read_metadata(self, file_path: Path) -> AudiobookMetadata:
        """Read metadata from an MP3 file."""
        ...

    def write_metadata(self, file_path: Path, metadata: AudiobookMetadata) -> None:
        """Write metadata to an MP3 file."""
        ...


class IMusicBrainzService(Protocol):
    """Interface for MusicBrainz lookup operations."""

    def lookup_by_disc_id(self, disc_id: str) -> dict | None:
        """Look up album information by disc ID."""
        ...

    def search_release(self, query: str) -> list[dict]:
        """Search for releases by text query."""
        ...


ProgressCallback = Callable[[RipProgress], None]
