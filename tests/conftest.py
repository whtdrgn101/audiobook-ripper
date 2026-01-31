"""Pytest fixtures and mock factories for testing."""

from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, Mock

import pytest

from audiobook_ripper.core.container import Container
from audiobook_ripper.core.interfaces import (
    ICDDrive,
    IEncoder,
    IMetadataService,
    IMusicBrainzService,
    IRipper,
)
from audiobook_ripper.core.models import AudiobookMetadata, DriveInfo, Track


@pytest.fixture
def sample_tracks() -> list[Track]:
    """Sample track list for testing."""
    return [
        Track(number=1, duration_seconds=180.0, title="Chapter 1", artist="Test Author"),
        Track(number=2, duration_seconds=240.0, title="Chapter 2", artist="Test Author"),
        Track(number=3, duration_seconds=300.0, title="Chapter 3", artist="Test Author"),
    ]


@pytest.fixture
def sample_drives() -> list[DriveInfo]:
    """Sample drive list for testing."""
    return [
        DriveInfo(letter="D", name="Test DVD Drive", has_disc=True),
        DriveInfo(letter="E", name="Test BD Drive", has_disc=False),
    ]


@pytest.fixture
def sample_metadata() -> AudiobookMetadata:
    """Sample metadata for testing."""
    return AudiobookMetadata(
        title="Test Chapter",
        artist="Test Author",
        album="Test Audiobook",
        track_number=1,
        total_tracks=10,
        year=2024,
        genre="Audiobook",
        narrator="Test Narrator",
        series="Test Series",
        series_number="1",
    )


@pytest.fixture
def mock_cd_drive(sample_drives, sample_tracks) -> Mock:
    """Mock CD drive service."""
    mock = Mock(spec=ICDDrive)
    mock.list_drives.return_value = sample_drives
    mock.get_tracks.return_value = sample_tracks
    mock.get_disc_id.return_value = "test_disc_id_123"
    return mock


@pytest.fixture
def mock_ripper() -> Mock:
    """Mock ripper service."""
    mock = Mock(spec=IRipper)

    def rip_track(drive, track_number, output_path, progress_callback=None):
        # Simulate ripping by creating the output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFF" + b"\x00" * 100)  # Fake WAV header
        if progress_callback:
            progress_callback(1.0)

    mock.rip_track.side_effect = rip_track
    return mock


@pytest.fixture
def mock_encoder() -> Mock:
    """Mock encoder service."""
    mock = Mock(spec=IEncoder)

    def encode_to_mp3(input_path, output_path, bitrate=192, progress_callback=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"ID3" + b"\x00" * 100)  # Fake MP3 header
        if progress_callback:
            progress_callback(1.0)

    mock.encode_to_mp3.side_effect = encode_to_mp3
    return mock


@pytest.fixture
def mock_metadata_service() -> Mock:
    """Mock metadata service."""
    mock = Mock(spec=IMetadataService)
    mock.read_metadata.return_value = AudiobookMetadata()
    return mock


@pytest.fixture
def mock_musicbrainz() -> Mock:
    """Mock MusicBrainz service."""
    mock = Mock(spec=IMusicBrainzService)
    mock.lookup_by_disc_id.return_value = {
        "title": "Test Album",
        "artist": "Test Artist",
        "year": 2024,
        "tracks": [
            {"number": 1, "title": "Track 1", "duration": 180},
            {"number": 2, "title": "Track 2", "duration": 240},
        ],
    }
    mock.search_release.return_value = []
    return mock


@pytest.fixture
def container(
    mock_cd_drive,
    mock_ripper,
    mock_encoder,
    mock_metadata_service,
    mock_musicbrainz,
) -> Container:
    """Pre-configured DI container with mocks."""
    container = Container()
    container.register(ICDDrive, mock_cd_drive)
    container.register(IRipper, mock_ripper)
    container.register(IEncoder, mock_encoder)
    container.register(IMetadataService, mock_metadata_service)
    container.register(IMusicBrainzService, mock_musicbrainz)
    return container


@pytest.fixture
def temp_dir(tmp_path) -> Path:
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def temp_mp3(tmp_path) -> Path:
    """Create a temporary MP3 file for testing."""
    # Create a minimal valid MP3 file with ID3 tags
    mp3_path = tmp_path / "test.mp3"

    # ID3v2 header (minimal)
    id3_header = bytes([
        0x49, 0x44, 0x33,  # "ID3"
        0x04, 0x00,        # Version 2.4.0
        0x00,              # Flags
        0x00, 0x00, 0x00, 0x00,  # Size (0)
    ])

    # Minimal MP3 frame (silence)
    mp3_frame = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MP3 frame header
    ] + [0x00] * 417)  # Frame data

    mp3_path.write_bytes(id3_header + mp3_frame * 10)
    return mp3_path
