"""Tests for the MusicBrainz service."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from audiobook_ripper.services.musicbrainz import MusicBrainzService
from audiobook_ripper.core.models import AudiobookMetadata, Track


class TestMusicBrainzService:
    """Tests for MusicBrainzService."""

    @pytest.fixture
    def service(self):
        """Create a MusicBrainzService instance."""
        with patch("audiobook_ripper.services.musicbrainz.musicbrainzngs"):
            return MusicBrainzService()

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_init_sets_useragent(self, mock_mb):
        """Test that initialization sets user agent."""
        MusicBrainzService("TestApp", "1.0.0")

        mock_mb.set_useragent.assert_called_once_with("TestApp", "1.0.0")

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_lookup_by_disc_id_success(self, mock_mb, service):
        """Test successful disc ID lookup."""
        mock_mb.get_releases_by_discid.return_value = {
            "disc": {
                "release-list": [{
                    "title": "Test Album",
                    "date": "2024-01-15",
                    "artist-credit": [{"artist": {"name": "Test Artist"}}],
                    "medium-list": [{
                        "track-list": [
                            {
                                "number": "1",
                                "recording": {"title": "Track 1", "length": 180000}
                            },
                            {
                                "number": "2",
                                "recording": {"title": "Track 2", "length": 240000}
                            },
                        ]
                    }]
                }]
            }
        }

        result = service.lookup_by_disc_id("test_disc_id")

        assert result is not None
        assert result["title"] == "Test Album"
        assert result["artist"] == "Test Artist"
        assert result["year"] == 2024
        assert len(result["tracks"]) == 2
        assert result["tracks"][0]["title"] == "Track 1"

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_lookup_by_disc_id_not_found(self, mock_mb, service):
        """Test disc ID lookup when not found."""
        mock_mb.get_releases_by_discid.return_value = {}

        result = service.lookup_by_disc_id("unknown_disc_id")

        assert result is None

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_lookup_by_disc_id_network_error(self, mock_mb, service):
        """Test handling of network errors."""
        mock_mb.WebServiceError = Exception
        mock_mb.get_releases_by_discid.side_effect = mock_mb.WebServiceError()

        result = service.lookup_by_disc_id("test_disc_id")

        assert result is None

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_search_release_success(self, mock_mb, service):
        """Test successful release search."""
        mock_mb.search_releases.return_value = {
            "release-list": [
                {
                    "title": "Result 1",
                    "artist-credit": [{"artist": {"name": "Artist 1"}}],
                    "medium-list": []
                },
                {
                    "title": "Result 2",
                    "artist-credit": [{"artist": {"name": "Artist 2"}}],
                    "medium-list": []
                },
            ]
        }

        results = service.search_release("test query")

        assert len(results) == 2
        assert results[0]["title"] == "Result 1"
        assert results[1]["title"] == "Result 2"

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_search_release_empty(self, mock_mb, service):
        """Test search with no results."""
        mock_mb.search_releases.return_value = {"release-list": []}

        results = service.search_release("nonexistent album")

        assert results == []

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_search_release_network_error(self, mock_mb, service):
        """Test handling of network errors in search."""
        mock_mb.WebServiceError = Exception
        mock_mb.search_releases.side_effect = mock_mb.WebServiceError()

        results = service.search_release("test query")

        assert results == []

    def test_apply_to_tracks(self, service):
        """Test applying release info to tracks."""
        release_info = {
            "title": "Test Book",
            "artist": "Test Author",
            "year": 2024,
            "tracks": [
                {"number": 1, "title": "Chapter 1"},
                {"number": 2, "title": "Chapter 2"},
            ]
        }

        tracks = [
            Track(number=1, duration_seconds=180),
            Track(number=2, duration_seconds=240),
        ]

        result = service.apply_to_tracks(release_info, tracks)

        assert len(result) == 2
        assert result[1].album == "Test Book"
        assert result[1].artist == "Test Author"
        assert result[1].title == "Chapter 1"
        assert result[1].total_tracks == 2
        assert result[2].title == "Chapter 2"

    def test_apply_to_tracks_missing_track_info(self, service):
        """Test applying info when track titles are missing."""
        release_info = {
            "title": "Test Book",
            "artist": "Test Author",
            "year": 2024,
            "tracks": []  # No track info
        }

        tracks = [
            Track(number=1, duration_seconds=180, title="Original Title"),
        ]

        result = service.apply_to_tracks(release_info, tracks)

        # Should keep original title when not in release info
        assert result[1].title == "Original Title"

    @patch("audiobook_ripper.services.musicbrainz.musicbrainzngs")
    def test_parse_release_multiple_artists(self, mock_mb, service):
        """Test parsing release with multiple artists."""
        mock_mb.get_releases_by_discid.return_value = {
            "disc": {
                "release-list": [{
                    "title": "Collaboration",
                    "artist-credit": [
                        {"artist": {"name": "Artist A"}},
                        {"artist": {"name": "Artist B"}},
                    ],
                    "medium-list": []
                }]
            }
        }

        result = service.lookup_by_disc_id("test_disc_id")

        assert result["artist"] == "Artist A, Artist B"
