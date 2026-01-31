"""Tests for data models."""

import pytest

from audiobook_ripper.core.models import (
    AudiobookMetadata,
    DriveInfo,
    RipJob,
    RipProgress,
    Track,
)


class TestDriveInfo:
    """Tests for DriveInfo model."""

    def test_str_with_disc(self):
        """Test string representation with disc present."""
        drive = DriveInfo(letter="D", name="DVD Drive", has_disc=True)
        assert str(drive) == "D: DVD Drive (Ready)"

    def test_str_without_disc(self):
        """Test string representation without disc."""
        drive = DriveInfo(letter="E", name="BD Drive", has_disc=False)
        assert str(drive) == "E: BD Drive (Empty)"


class TestTrack:
    """Tests for Track model."""

    def test_duration_formatted_minutes_seconds(self):
        """Test duration formatting with minutes and seconds."""
        track = Track(number=1, duration_seconds=185.5)
        assert track.duration_formatted == "3:05"

    def test_duration_formatted_zero(self):
        """Test duration formatting for zero duration."""
        track = Track(number=1, duration_seconds=0)
        assert track.duration_formatted == "0:00"

    def test_duration_formatted_hour_plus(self):
        """Test duration formatting for long tracks."""
        track = Track(number=1, duration_seconds=3665)  # 61:05
        assert track.duration_formatted == "61:05"

    def test_default_values(self):
        """Test default values for optional fields."""
        track = Track(number=1, duration_seconds=100)
        assert track.title == ""
        assert track.artist == ""


class TestAudiobookMetadata:
    """Tests for AudiobookMetadata model."""

    def test_default_values(self):
        """Test default values."""
        meta = AudiobookMetadata()
        assert meta.genre == "Audiobook"
        assert meta.cover_art is None
        assert meta.year is None

    def test_to_id3_tags_basic(self):
        """Test ID3 tag conversion with basic fields."""
        meta = AudiobookMetadata(
            title="Test Title",
            artist="Test Author",
            album="Test Album",
            track_number=5,
            total_tracks=10,
        )
        tags = meta.to_id3_tags()

        assert tags["TIT2"] == "Test Title"
        assert tags["TPE1"] == "Test Author"
        assert tags["TALB"] == "Test Album"
        assert tags["TRCK"] == "5/10"
        assert tags["TCON"] == "Audiobook"

    def test_to_id3_tags_with_year(self):
        """Test ID3 tag conversion with year."""
        meta = AudiobookMetadata(year=2024)
        tags = meta.to_id3_tags()
        assert tags["TDRC"] == "2024"

    def test_to_id3_tags_with_narrator(self):
        """Test ID3 tag conversion with narrator."""
        meta = AudiobookMetadata(narrator="John Smith")
        tags = meta.to_id3_tags()
        assert tags["TPE2"] == "John Smith"

    def test_to_id3_tags_with_series(self):
        """Test ID3 tag conversion with series info."""
        meta = AudiobookMetadata(series="My Series", series_number="3")
        tags = meta.to_id3_tags()
        assert tags["TIT1"] == "My Series #3"

    def test_to_id3_tags_track_without_total(self):
        """Test ID3 tag conversion without total tracks."""
        meta = AudiobookMetadata(track_number=5, total_tracks=0)
        tags = meta.to_id3_tags()
        assert tags["TRCK"] == "5"


class TestRipProgress:
    """Tests for RipProgress model."""

    def test_overall_progress_empty(self):
        """Test overall progress with zero tracks."""
        progress = RipProgress(track_number=1, total_tracks=0, track_progress=0.5)
        assert progress.overall_progress == 0.0

    def test_overall_progress_first_track(self):
        """Test overall progress on first track."""
        progress = RipProgress(track_number=1, total_tracks=4, track_progress=0.5)
        # (0 completed + 0.5 current) / 4 = 0.125
        assert progress.overall_progress == 0.125

    def test_overall_progress_middle_track(self):
        """Test overall progress in middle of ripping."""
        progress = RipProgress(track_number=3, total_tracks=4, track_progress=0.5)
        # (2 completed + 0.5 current) / 4 = 0.625
        assert progress.overall_progress == 0.625

    def test_overall_progress_complete(self):
        """Test overall progress when complete."""
        progress = RipProgress(track_number=4, total_tracks=4, track_progress=1.0)
        # (3 completed + 1.0 current) / 4 = 1.0
        assert progress.overall_progress == 1.0
