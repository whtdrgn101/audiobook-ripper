"""Tests for the metadata service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from audiobook_ripper.services.metadata import MetadataService
from audiobook_ripper.core.models import AudiobookMetadata


class TestMetadataService:
    """Tests for MetadataService."""

    @pytest.fixture
    def service(self):
        """Create a MetadataService instance."""
        return MetadataService()

    def test_read_metadata_missing_file(self, service, tmp_path):
        """Test error when file doesn't exist."""
        file_path = tmp_path / "nonexistent.mp3"

        with pytest.raises(FileNotFoundError):
            service.read_metadata(file_path)

    def test_write_metadata_missing_file(self, service, tmp_path):
        """Test error when file doesn't exist."""
        file_path = tmp_path / "nonexistent.mp3"
        metadata = AudiobookMetadata(title="Test")

        with pytest.raises(FileNotFoundError):
            service.write_metadata(file_path, metadata)

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_read_metadata_no_tags(self, mock_mp3, service, tmp_path):
        """Test reading file with no tags."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio.tags = None
        mock_mp3.return_value = mock_audio

        metadata = service.read_metadata(file_path)

        assert metadata.title == ""
        assert metadata.artist == ""

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_read_metadata_basic_tags(self, mock_mp3, service, tmp_path):
        """Test reading basic ID3 tags."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_tags = MagicMock()
        mock_tags.__contains__ = lambda self, key: key in ["TIT2", "TPE1", "TALB"]
        mock_tags.__getitem__ = lambda self, key: MagicMock(text=["Value for " + key])

        mock_audio = MagicMock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio

        metadata = service.read_metadata(file_path)

        assert metadata.title == "Value for TIT2"
        assert metadata.artist == "Value for TPE1"
        assert metadata.album == "Value for TALB"

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_read_metadata_track_number_with_total(self, mock_mp3, service, tmp_path):
        """Test parsing track number with total."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_tags = MagicMock()
        mock_tags.__contains__ = lambda self, key: key == "TRCK"
        mock_tags.__getitem__ = lambda self, key: MagicMock(text=["5/10"])

        mock_audio = MagicMock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio

        metadata = service.read_metadata(file_path)

        assert metadata.track_number == 5
        assert metadata.total_tracks == 10

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_read_metadata_series_info(self, mock_mp3, service, tmp_path):
        """Test parsing series info from TIT1."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_tags = MagicMock()
        mock_tags.__contains__ = lambda self, key: key == "TIT1"
        mock_tags.__getitem__ = lambda self, key: MagicMock(text=["Harry Potter #3"])

        mock_audio = MagicMock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio

        metadata = service.read_metadata(file_path)

        assert metadata.series == "Harry Potter"
        assert metadata.series_number == "3"

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_write_metadata_basic(self, mock_mp3, service, tmp_path):
        """Test writing basic metadata."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_tags = MagicMock()
        mock_tags.__contains__ = lambda self, key: False
        mock_tags.__iter__ = lambda self: iter([])

        mock_audio = MagicMock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio

        metadata = AudiobookMetadata(
            title="Test Title",
            artist="Test Author",
            album="Test Book",
            track_number=1,
            total_tracks=10,
        )

        service.write_metadata(file_path, metadata)

        mock_audio.save.assert_called_once()
        # Verify tags were added
        assert mock_tags.add.called

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_write_metadata_with_cover_art(self, mock_mp3, service, tmp_path):
        """Test writing metadata with cover art."""
        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"ID3" + b"\x00" * 100)

        mock_tags = MagicMock()
        mock_tags.__contains__ = lambda self, key: False
        mock_tags.__iter__ = lambda self: iter([])

        mock_audio = MagicMock()
        mock_audio.tags = mock_tags
        mock_mp3.return_value = mock_audio

        metadata = AudiobookMetadata(
            title="Test",
            cover_art=b"\xff\xd8\xff\xe0" + b"\x00" * 100,  # Fake JPEG
            cover_art_mime="image/jpeg",
        )

        service.write_metadata(file_path, metadata)

        # Check that APIC frame was added
        add_calls = [str(call) for call in mock_tags.add.call_args_list]
        assert any("APIC" in str(call) for call in add_calls)

    @patch("audiobook_ripper.services.metadata.MP3")
    def test_copy_metadata(self, mock_mp3, service, tmp_path):
        """Test copying metadata between files."""
        source_path = tmp_path / "source.mp3"
        dest_path = tmp_path / "dest.mp3"
        source_path.write_bytes(b"ID3" + b"\x00" * 100)
        dest_path.write_bytes(b"ID3" + b"\x00" * 100)

        # Mock for source read
        mock_source_tags = MagicMock()
        mock_source_tags.__contains__ = lambda self, key: key == "TIT2"
        mock_source_tags.__getitem__ = lambda self, key: MagicMock(text=["Source Title"])
        mock_source_tags.__iter__ = lambda self: iter([])

        mock_source_audio = MagicMock()
        mock_source_audio.tags = mock_source_tags

        # Mock for dest write
        mock_dest_tags = MagicMock()
        mock_dest_tags.__contains__ = lambda self, key: False
        mock_dest_tags.__iter__ = lambda self: iter([])

        mock_dest_audio = MagicMock()
        mock_dest_audio.tags = mock_dest_tags

        mock_mp3.side_effect = [mock_source_audio, mock_dest_audio]

        service.copy_metadata(source_path, dest_path)

        mock_dest_audio.save.assert_called_once()
