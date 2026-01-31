"""Tests for the encoder service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from audiobook_ripper.services.encoder import EncoderService, check_ffmpeg_available


class TestEncoderService:
    """Tests for EncoderService."""

    @pytest.fixture
    def encoder(self):
        """Create an EncoderService instance."""
        return EncoderService()

    def test_encode_missing_input_file(self, encoder, tmp_path):
        """Test error when input file doesn't exist."""
        input_path = tmp_path / "nonexistent.wav"
        output_path = tmp_path / "output.mp3"

        with pytest.raises(FileNotFoundError):
            encoder.encode_to_mp3(input_path, output_path)

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_encode_success(self, mock_subprocess, encoder, tmp_path):
        """Test successful encoding."""
        input_path = tmp_path / "input.wav"
        input_path.write_bytes(b"RIFF" + b"\x00" * 100)
        output_path = tmp_path / "output.mp3"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout.__iter__ = Mock(return_value=iter([
            "out_time_ms=1000000\n",
            "out_time_ms=2000000\n",
        ]))
        mock_subprocess.Popen.return_value = mock_process
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="10.0")

        progress_values = []
        encoder.encode_to_mp3(input_path, output_path, progress_callback=lambda p: progress_values.append(p))

        assert mock_subprocess.Popen.called
        call_args = mock_subprocess.Popen.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-codec:a" in call_args
        assert "libmp3lame" in call_args

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_encode_with_custom_bitrate(self, mock_subprocess, encoder, tmp_path):
        """Test encoding with custom bitrate."""
        input_path = tmp_path / "input.wav"
        input_path.write_bytes(b"RIFF" + b"\x00" * 100)
        output_path = tmp_path / "output.mp3"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout.__iter__ = Mock(return_value=iter([]))
        mock_subprocess.Popen.return_value = mock_process
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="10.0")

        encoder.encode_to_mp3(input_path, output_path, bitrate=320)

        call_args = mock_subprocess.Popen.call_args[0][0]
        assert "320k" in call_args

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_encode_failure(self, mock_subprocess, encoder, tmp_path):
        """Test handling of encoding failure."""
        input_path = tmp_path / "input.wav"
        input_path.write_bytes(b"RIFF" + b"\x00" * 100)
        output_path = tmp_path / "output.mp3"

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout.__iter__ = Mock(return_value=iter([]))
        mock_process.stderr.read.return_value = "Encoding error"
        mock_subprocess.Popen.return_value = mock_process
        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="10.0")

        with pytest.raises(RuntimeError) as exc_info:
            encoder.encode_to_mp3(input_path, output_path)

        assert "FFmpeg encoding failed" in str(exc_info.value)

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_cancel_terminates_process(self, mock_subprocess, encoder):
        """Test that cancel terminates the running process."""
        mock_process = MagicMock()
        mock_subprocess.Popen.return_value = mock_process

        encoder._process = mock_process
        encoder.cancel()

        mock_process.terminate.assert_called_once()

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_get_duration(self, mock_subprocess, encoder, tmp_path):
        """Test getting file duration."""
        file_path = tmp_path / "test.wav"
        file_path.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_subprocess.run.return_value = MagicMock(
            returncode=0,
            stdout="123.456\n"
        )

        duration = encoder._get_duration(file_path)

        assert duration == 123.456


class TestCheckFFmpegAvailable:
    """Tests for check_ffmpeg_available function."""

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_ffmpeg_available(self, mock_subprocess):
        """Test detection when FFmpeg is available."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        assert check_ffmpeg_available() is True

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_ffmpeg_not_available(self, mock_subprocess):
        """Test detection when FFmpeg is not installed."""
        import subprocess as sp
        mock_subprocess.run.side_effect = FileNotFoundError()
        mock_subprocess.TimeoutExpired = sp.TimeoutExpired

        assert check_ffmpeg_available() is False

    @patch("audiobook_ripper.services.encoder.subprocess")
    def test_ffmpeg_timeout(self, mock_subprocess):
        """Test handling of FFmpeg timeout."""
        import subprocess
        mock_subprocess.run.side_effect = subprocess.TimeoutExpired("ffmpeg", 10)
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        assert check_ffmpeg_available() is False
