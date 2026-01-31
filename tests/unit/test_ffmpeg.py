"""Tests for FFmpeg utilities."""

import subprocess as sp
import pytest
from unittest.mock import patch, MagicMock

from audiobook_ripper.utils.ffmpeg import (
    check_ffmpeg,
    get_ffmpeg_version,
    check_libcdio,
    check_lame_encoder,
)


class TestCheckFFmpeg:
    """Tests for check_ffmpeg function."""

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_ffmpeg_available(self, mock_subprocess):
        """Test when FFmpeg is available."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_ffmpeg() is True

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_ffmpeg_not_found(self, mock_subprocess):
        """Test when FFmpeg is not installed."""
        mock_subprocess.run.side_effect = FileNotFoundError()
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_ffmpeg() is False

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_ffmpeg_timeout(self, mock_subprocess):
        """Test timeout handling."""
        mock_subprocess.run.side_effect = sp.TimeoutExpired("ffmpeg", 10)
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_ffmpeg() is False

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_ffmpeg_os_error(self, mock_subprocess):
        """Test OS error handling."""
        mock_subprocess.run.side_effect = OSError("Permission denied")
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_ffmpeg() is False


class TestGetFFmpegVersion:
    """Tests for get_ffmpeg_version function."""

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_version_parsing(self, mock_subprocess):
        """Test version string parsing."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 6.0-full_build Copyright (c) 2000-2023"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        version = get_ffmpeg_version()

        assert version == "6.0-full_build"

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_version_not_available(self, mock_subprocess):
        """Test when FFmpeg is not available."""
        mock_subprocess.run.side_effect = FileNotFoundError()
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        version = get_ffmpeg_version()

        assert version is None

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_version_parse_failure(self, mock_subprocess):
        """Test when version string can't be parsed."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="unexpected output format"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        version = get_ffmpeg_version()

        assert version is None


class TestCheckLibcdio:
    """Tests for check_libcdio function."""

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_libcdio_available(self, mock_subprocess):
        """Test when libcdio is available."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="D libcdio          libcdio CD Audio input device"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_libcdio() is True

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_libcdio_not_available(self, mock_subprocess):
        """Test when libcdio is not available."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="D other_demuxer    Some other demuxer"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_libcdio() is False

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_libcdio_ffmpeg_not_found(self, mock_subprocess):
        """Test when FFmpeg is not installed."""
        mock_subprocess.run.side_effect = FileNotFoundError()
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_libcdio() is False


class TestCheckLameEncoder:
    """Tests for check_lame_encoder function."""

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_lame_available(self, mock_subprocess):
        """Test when LAME encoder is available."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="A..... libmp3lame       libmp3lame MP3 (MPEG audio layer 3)"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_lame_encoder() is True

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_lame_not_available(self, mock_subprocess):
        """Test when LAME encoder is not available."""
        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="A..... other_encoder    Some other encoder"
        )
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_lame_encoder() is False

    @patch("audiobook_ripper.utils.ffmpeg.subprocess")
    def test_lame_ffmpeg_not_found(self, mock_subprocess):
        """Test when FFmpeg is not installed."""
        mock_subprocess.run.side_effect = FileNotFoundError()
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_lame_encoder() is False
