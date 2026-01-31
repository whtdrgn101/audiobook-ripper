"""Tests for the CD drive service."""

import sys
import pytest
from unittest.mock import MagicMock, patch, Mock

from audiobook_ripper.services.cd_drive import CDDriveService
from audiobook_ripper.core.models import DriveInfo, Track


class TestCDDriveService:
    """Tests for CDDriveService."""

    @pytest.fixture
    def service(self):
        """Create a CDDriveService instance."""
        return CDDriveService()

    @patch("audiobook_ripper.services.cd_drive.ctypes")
    def test_list_drives_finds_cdrom(self, mock_ctypes):
        """Test that list_drives finds CD-ROM drives."""
        # Set up mock: drive D (bit 3) is a CD-ROM
        mock_ctypes.windll.kernel32.GetLogicalDrives.return_value = 0b1000  # D:
        mock_ctypes.windll.kernel32.GetDriveTypeW.return_value = 5  # DRIVE_CDROM

        mock_buffer = MagicMock()
        mock_buffer.value = "Test CD Drive"
        mock_ctypes.create_unicode_buffer.return_value = mock_buffer

        service = CDDriveService()

        with patch.object(service, "_check_disc_present", return_value=True):
            drives = service.list_drives()

        assert len(drives) == 1
        assert drives[0].letter == "D"
        assert drives[0].name == "Test CD Drive"
        assert drives[0].has_disc is True

    @patch("audiobook_ripper.services.cd_drive.ctypes")
    def test_list_drives_excludes_non_cdrom(self, mock_ctypes):
        """Test that list_drives excludes non-CD drives."""
        # Set up mock: drive C (bit 2) is a fixed drive (type 3)
        mock_ctypes.windll.kernel32.GetLogicalDrives.return_value = 0b0100  # C:
        mock_ctypes.windll.kernel32.GetDriveTypeW.return_value = 3  # DRIVE_FIXED

        service = CDDriveService()
        drives = service.list_drives()

        assert len(drives) == 0

    def test_get_tracks_with_discid(self):
        """Test get_tracks using discid library."""
        mock_track1 = Mock()
        mock_track1.seconds = 180
        mock_track2 = Mock()
        mock_track2.seconds = 240

        mock_disc = Mock()
        mock_disc.tracks = [mock_track1, mock_track2]

        mock_discid = MagicMock()
        mock_discid.read.return_value = mock_disc

        with patch.dict(sys.modules, {"discid": mock_discid}):
            service = CDDriveService()
            tracks = service.get_tracks("D")

        assert len(tracks) == 2
        assert tracks[0].number == 1
        assert tracks[0].duration_seconds == 180
        assert tracks[1].number == 2
        assert tracks[1].duration_seconds == 240

    def test_get_disc_id(self):
        """Test getting disc ID."""
        mock_disc = Mock()
        mock_disc.id = "test_disc_id_abc123"

        mock_discid = MagicMock()
        mock_discid.read.return_value = mock_disc

        with patch.dict(sys.modules, {"discid": mock_discid}):
            service = CDDriveService()
            disc_id = service.get_disc_id("D")

        assert disc_id == "test_disc_id_abc123"
        mock_discid.read.assert_called_once_with("D:")

    def test_get_disc_id_error_returns_none(self):
        """Test that errors return None for disc ID."""
        mock_discid = MagicMock()
        mock_discid.read.side_effect = Exception("No disc")

        with patch.dict(sys.modules, {"discid": mock_discid}):
            service = CDDriveService()
            disc_id = service.get_disc_id("D")

        assert disc_id is None

    @patch("audiobook_ripper.services.cd_drive.ctypes")
    def test_eject(self, mock_ctypes):
        """Test disc ejection."""
        service = CDDriveService()
        service.eject("D")

        # Verify MCI commands were sent
        calls = mock_ctypes.windll.winmm.mciSendStringW.call_args_list
        assert len(calls) == 3
        assert "open D:" in str(calls[0])
        assert "door open" in str(calls[1])
        assert "close" in str(calls[2])
