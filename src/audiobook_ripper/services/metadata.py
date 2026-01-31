"""Metadata service for reading and writing MP3 tags."""

from pathlib import Path

from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT1,
    TIT2,
    TPE1,
    TPE2,
    TRCK,
)
from mutagen.mp3 import MP3

from audiobook_ripper.core.models import AudiobookMetadata


class MetadataService:
    """Service for reading and writing MP3 metadata using mutagen."""

    def read_metadata(self, file_path: Path) -> AudiobookMetadata:
        """Read metadata from an MP3 file.

        Args:
            file_path: Path to the MP3 file

        Returns:
            AudiobookMetadata populated from the file's tags

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        audio = MP3(file_path)
        tags = audio.tags

        if tags is None:
            return AudiobookMetadata()

        metadata = AudiobookMetadata(
            title=self._get_text_tag(tags, "TIT2"),
            artist=self._get_text_tag(tags, "TPE1"),
            album=self._get_text_tag(tags, "TALB"),
            genre=self._get_text_tag(tags, "TCON") or "Audiobook",
            narrator=self._get_text_tag(tags, "TPE2"),
        )

        # Parse track number
        track_str = self._get_text_tag(tags, "TRCK")
        if track_str:
            if "/" in track_str:
                num, total = track_str.split("/", 1)
                metadata.track_number = int(num) if num.isdigit() else 0
                metadata.total_tracks = int(total) if total.isdigit() else 0
            elif track_str.isdigit():
                metadata.track_number = int(track_str)

        # Parse year
        year_str = self._get_text_tag(tags, "TDRC")
        if year_str:
            try:
                metadata.year = int(str(year_str)[:4])
            except ValueError:
                pass

        # Parse series info from grouping
        series_info = self._get_text_tag(tags, "TIT1")
        if series_info:
            if " #" in series_info:
                metadata.series, metadata.series_number = series_info.rsplit(" #", 1)
            else:
                metadata.series = series_info

        # Get cover art
        for key in tags:
            if key.startswith("APIC"):
                apic = tags[key]
                metadata.cover_art = apic.data
                metadata.cover_art_mime = apic.mime
                break

        return metadata

    def _get_text_tag(self, tags: ID3, key: str) -> str:
        """Extract text from an ID3 tag."""
        if key in tags:
            tag = tags[key]
            if hasattr(tag, "text") and tag.text:
                return str(tag.text[0])
        return ""

    def write_metadata(self, file_path: Path, metadata: AudiobookMetadata) -> None:
        """Write metadata to an MP3 file.

        Args:
            file_path: Path to the MP3 file
            metadata: Metadata to write

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        audio = MP3(file_path)

        # Create ID3 tags if they don't exist
        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags

        # Clear existing tags we'll be setting
        for key in ["TIT2", "TPE1", "TALB", "TRCK", "TCON", "TDRC", "TPE2", "TIT1"]:
            if key in tags:
                del tags[key]

        # Remove existing cover art
        keys_to_remove = [k for k in tags if k.startswith("APIC")]
        for key in keys_to_remove:
            del tags[key]

        # Set standard tags
        if metadata.title:
            tags.add(TIT2(encoding=3, text=metadata.title))

        if metadata.artist:
            tags.add(TPE1(encoding=3, text=metadata.artist))

        if metadata.album:
            tags.add(TALB(encoding=3, text=metadata.album))

        # Track number
        if metadata.track_number:
            if metadata.total_tracks:
                track_str = f"{metadata.track_number}/{metadata.total_tracks}"
            else:
                track_str = str(metadata.track_number)
            tags.add(TRCK(encoding=3, text=track_str))

        if metadata.genre:
            tags.add(TCON(encoding=3, text=metadata.genre))

        if metadata.year:
            tags.add(TDRC(encoding=3, text=str(metadata.year)))

        # Audiobook-specific: narrator as album artist
        if metadata.narrator:
            tags.add(TPE2(encoding=3, text=metadata.narrator))

        # Series info as grouping
        if metadata.series:
            series_info = metadata.series
            if metadata.series_number:
                series_info += f" #{metadata.series_number}"
            tags.add(TIT1(encoding=3, text=series_info))

        # Cover art
        if metadata.cover_art:
            tags.add(APIC(
                encoding=3,
                mime=metadata.cover_art_mime,
                type=3,  # Cover (front)
                desc="Cover",
                data=metadata.cover_art,
            ))

        audio.save()

    def copy_metadata(self, source: Path, dest: Path) -> None:
        """Copy metadata from one MP3 file to another."""
        metadata = self.read_metadata(source)
        self.write_metadata(dest, metadata)
