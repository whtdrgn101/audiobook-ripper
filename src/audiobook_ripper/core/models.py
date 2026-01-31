"""Data models for the audiobook ripper."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DriveInfo:
    """Information about a CD drive."""

    letter: str
    name: str
    has_disc: bool = False

    def __str__(self) -> str:
        status = "Ready" if self.has_disc else "Empty"
        return f"{self.letter}: {self.name} ({status})"


@dataclass
class Track:
    """Represents a single CD track."""

    number: int
    duration_seconds: float
    title: str = ""
    artist: str = ""

    @property
    def duration_formatted(self) -> str:
        """Return duration as MM:SS format."""
        minutes = int(self.duration_seconds // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class AudiobookMetadata:
    """Metadata for an audiobook track."""

    # Standard fields
    title: str = ""
    artist: str = ""  # Author
    album: str = ""  # Book title
    track_number: int = 0
    total_tracks: int = 0
    year: int | None = None
    genre: str = "Audiobook"

    # Audiobook-specific
    narrator: str = ""
    series: str = ""
    series_number: str = ""
    disc_number: int | None = None
    total_discs: int | None = None

    # Cover art (binary data)
    cover_art: bytes | None = None
    cover_art_mime: str = "image/jpeg"

    def to_id3_tags(self) -> dict[str, str]:
        """Convert to ID3 tag dictionary."""
        tags = {
            "TIT2": self.title,
            "TPE1": self.artist,
            "TALB": self.album,
            "TRCK": f"{self.track_number}/{self.total_tracks}" if self.total_tracks else str(self.track_number),
            "TCON": self.genre,
        }
        if self.year:
            tags["TDRC"] = str(self.year)
        if self.narrator:
            tags["TPE2"] = self.narrator  # Use album artist for narrator
        if self.series:
            # Use grouping for series info
            series_info = self.series
            if self.series_number:
                series_info += f" #{self.series_number}"
            tags["TIT1"] = series_info
        if self.disc_number:
            if self.total_discs:
                tags["TPOS"] = f"{self.disc_number}/{self.total_discs}"
            else:
                tags["TPOS"] = str(self.disc_number)
        return tags


@dataclass
class RipProgress:
    """Progress information for a ripping operation."""

    track_number: int
    total_tracks: int
    track_progress: float  # 0.0 to 1.0
    current_file: Path | None = None
    status: str = "Ripping"
    error: str | None = None

    @property
    def overall_progress(self) -> float:
        """Calculate overall progress across all tracks."""
        if self.total_tracks == 0:
            return 0.0
        completed = self.track_number - 1
        return (completed + self.track_progress) / self.total_tracks


@dataclass
class RipJob:
    """A job to rip tracks from a CD."""

    drive: str
    tracks: list[int]
    output_dir: Path
    metadata: dict[int, AudiobookMetadata] = field(default_factory=dict)
    bitrate: int = 192
