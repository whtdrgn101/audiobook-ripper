"""Tests for the FFmpeg ripper service."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from audiobook_ripper.services.ripper import FFmpegRipper


class TestFFmpegRipper:
    """Tests for FFmpegRipper."""

    @pytest.fixture
    def ripper(self):
        """Create a FFmpegRipper instance."""
        return FFmpegRipper()

    @patch("audiobook_ripper.services.ripper.subprocess")
    def test_rip_track_success(self, mock_subprocess, ripper, tmp_path):
        """Test successful track ripping."""
        output_path = tmp_path / "track01.wav"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_subprocess.Popen.return_value = mock_process

        progress_values = []
        ripper.rip_track("D", 1, output_path, lambda p: progress_values.append(p))

        assert mock_subprocess.Popen.called
        assert 1.0 in progress_values

    @patch("audiobook_ripper.services.ripper.subprocess")
    def test_rip_track_failure(self, mock_subprocess, ripper, tmp_path):
        """Test handling of ripping failure."""
        output_path = tmp_path / "track01.wav"

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("", "Error: No disc")
        mock_subprocess.Popen.return_value = mock_process

        with pytest.raises(RuntimeError) as exc_info:
            ripper.rip_track("D", 1, output_path)

        assert "FFmpeg failed" in str(exc_info.value)

    @patch("audiobook_ripper.services.ripper.subprocess")
    def test_rip_track_creates_parent_dir(self, mock_subprocess, ripper, tmp_path):
        """Test that parent directories are created."""
        output_path = tmp_path / "subdir" / "deep" / "track01.wav"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_subprocess.Popen.return_value = mock_process

        ripper.rip_track("D", 1, output_path)

        assert output_path.parent.exists()

    @patch("audiobook_ripper.services.ripper.subprocess")
    def test_cancel_terminates_process(self, mock_subprocess, ripper):
        """Test that cancel terminates the running process."""
        mock_process = MagicMock()
        mock_subprocess.Popen.return_value = mock_process

        # Simulate a running process
        ripper._process = mock_process
        ripper.cancel()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()

    def test_cancel_no_process(self, ripper):
        """Test cancel when no process is running."""
        # Should not raise
        ripper.cancel()
        assert ripper._cancelled is True
