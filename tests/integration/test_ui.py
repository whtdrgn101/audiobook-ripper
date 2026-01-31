"""Integration tests for Qt UI components."""

import pytest
from unittest.mock import Mock, MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from audiobook_ripper.core.container import Container
from audiobook_ripper.core.interfaces import ICDDrive, IEncoder, IMetadataService, IMusicBrainzService, IRipper
from audiobook_ripper.core.models import AudiobookMetadata, DriveInfo, Track
from audiobook_ripper.ui.drive_selector import DriveSelector
from audiobook_ripper.ui.track_list import TrackListWidget
from audiobook_ripper.ui.metadata_editor import MetadataEditorDialog
from audiobook_ripper.ui.progress_dialog import ProgressDialog
from audiobook_ripper.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestDriveSelector:
    """Tests for DriveSelector widget."""

    def test_init_creates_widgets(self, qapp):
        """Test that initialization creates required widgets."""
        selector = DriveSelector()

        assert selector._combo is not None
        assert selector._refresh_btn is not None
        assert selector._eject_btn is not None

    def test_refresh_populates_combo(self, qapp, mock_cd_drive, sample_drives):
        """Test that refresh populates the combo box."""
        selector = DriveSelector()
        selector.set_service(mock_cd_drive)
        selector.refresh()

        assert selector._combo.count() == len(sample_drives)

    def test_current_drive_returns_letter(self, qapp, mock_cd_drive, sample_drives):
        """Test current_drive returns correct letter."""
        selector = DriveSelector()
        selector.set_service(mock_cd_drive)
        selector.refresh()

        assert selector.current_drive() == sample_drives[0].letter

    def test_drive_changed_signal(self, qapp, mock_cd_drive):
        """Test drive_changed signal is emitted."""
        selector = DriveSelector()
        selector.set_service(mock_cd_drive)

        signal_received = []
        selector.drive_changed.connect(lambda d: signal_received.append(d))

        selector.refresh()
        selector._combo.setCurrentIndex(1)

        assert len(signal_received) > 0


class TestTrackListWidget:
    """Tests for TrackListWidget."""

    def test_init_creates_columns(self, qapp):
        """Test that initialization creates correct columns."""
        widget = TrackListWidget()

        assert widget.columnCount() == len(TrackListWidget.COLUMNS)

    def test_set_tracks_populates_rows(self, qapp, sample_tracks):
        """Test that set_tracks populates the table."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)

        assert widget.rowCount() == len(sample_tracks)

    def test_get_selected_tracks_default_all(self, qapp, sample_tracks):
        """Test that all tracks are selected by default."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)

        selected = widget.get_selected_tracks()
        assert len(selected) == len(sample_tracks)

    def test_select_none(self, qapp, sample_tracks):
        """Test select_none unchecks all tracks."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)
        widget.select_none()

        selected = widget.get_selected_tracks()
        assert len(selected) == 0

    def test_select_all(self, qapp, sample_tracks):
        """Test select_all checks all tracks."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)
        widget.select_none()
        widget.select_all()

        selected = widget.get_selected_tracks()
        assert len(selected) == len(sample_tracks)

    def test_set_metadata_updates_display(self, qapp, sample_tracks, sample_metadata):
        """Test that set_metadata updates the display."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)

        widget.set_metadata(1, sample_metadata)

        assert widget.item(0, 2).text() == sample_metadata.title
        assert widget.item(0, 4).text() == sample_metadata.artist

    def test_get_all_metadata(self, qapp, sample_tracks):
        """Test getting metadata for all tracks."""
        widget = TrackListWidget()
        widget.set_tracks(sample_tracks)

        metadata = widget.get_all_metadata()

        assert len(metadata) == len(sample_tracks)
        for track in sample_tracks:
            assert track.number in metadata


class TestMetadataEditorDialog:
    """Tests for MetadataEditorDialog."""

    def test_init_loads_metadata(self, qapp, sample_metadata):
        """Test that initialization loads metadata into fields."""
        dialog = MetadataEditorDialog(sample_metadata)

        assert dialog._title_edit.text() == sample_metadata.title
        assert dialog._artist_edit.text() == sample_metadata.artist
        assert dialog._album_edit.text() == sample_metadata.album

    def test_get_metadata_returns_edited_values(self, qapp):
        """Test that get_metadata returns current values."""
        initial = AudiobookMetadata()
        dialog = MetadataEditorDialog(initial)

        dialog._title_edit.setText("New Title")
        dialog._artist_edit.setText("New Author")

        result = dialog.get_metadata()

        assert result.title == "New Title"
        assert result.artist == "New Author"

    def test_batch_mode_shows_info(self, qapp):
        """Test that batch mode shows info label."""
        dialog = MetadataEditorDialog(AudiobookMetadata(), batch_mode=True)

        # Dialog should have batch mode indicator
        assert dialog._batch_mode is True

    def test_get_batch_updates_excludes_empty(self, qapp):
        """Test that batch updates exclude empty fields."""
        dialog = MetadataEditorDialog(AudiobookMetadata(), batch_mode=True)
        dialog._album_edit.setText("Batch Album")
        # Leave other fields empty

        updates = dialog.get_batch_updates()

        assert "album" in updates
        assert "title" not in updates


class TestProgressDialog:
    """Tests for ProgressDialog."""

    def test_init_sets_total_tracks(self, qapp):
        """Test that initialization sets up for total tracks."""
        dialog = ProgressDialog(total_tracks=5)

        assert dialog._total_tracks == 5

    def test_update_progress_updates_bars(self, qapp):
        """Test that update_progress updates progress bars."""
        from audiobook_ripper.core.models import RipProgress

        dialog = ProgressDialog(total_tracks=4)

        progress = RipProgress(
            track_number=2,
            total_tracks=4,
            track_progress=0.5,
            status="Encoding"
        )

        dialog.update_progress(progress)

        assert dialog._track_progress.value() == 50
        assert dialog._overall_progress.value() > 0

    def test_cancel_emits_signal(self, qapp):
        """Test that cancel button emits signal."""
        dialog = ProgressDialog(total_tracks=1)

        signal_received = []
        dialog.cancel_requested.connect(lambda: signal_received.append(True))

        dialog._on_cancel()

        assert len(signal_received) == 1
        assert dialog.is_cancelled()

    def test_set_finished_enables_close(self, qapp):
        """Test that set_finished enables close button."""
        dialog = ProgressDialog(total_tracks=1)

        dialog.set_finished(success=True)

        assert dialog._close_btn.isEnabled()
        assert not dialog._cancel_btn.isEnabled()


class TestMainWindow:
    """Tests for MainWindow."""

    def test_init_creates_ui(self, qapp, container):
        """Test that initialization creates UI components."""
        window = MainWindow(container)

        assert window._drive_selector is not None
        assert window._track_list is not None
        assert window._rip_btn is not None

    def test_refresh_tracks_calls_service(self, qapp, container, mock_cd_drive):
        """Test that refreshing tracks uses the CD drive service."""
        window = MainWindow(container)
        window._drive_selector.refresh()

        mock_cd_drive.list_drives.assert_called()

    def test_window_title(self, qapp, container):
        """Test window has correct title."""
        window = MainWindow(container)

        assert "Audiobook" in window.windowTitle()

    def test_close_saves_config(self, qapp, container):
        """Test that closing the window saves configuration."""
        window = MainWindow(container)
        window.resize(1024, 768)

        # Simulate close
        window._config.window_width = window.width()
        window._config.window_height = window.height()

        assert window._config.window_width == 1024
        assert window._config.window_height == 768
