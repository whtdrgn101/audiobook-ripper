"""Track listing widget with metadata display."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from audiobook_ripper.core.models import AudiobookMetadata, Track


class TrackListWidget(QTableWidget):
    """Widget for displaying and selecting CD tracks."""

    selection_changed = Signal(list)  # Emits list of selected track numbers
    metadata_edited = Signal(int, str, str)  # track_number, field, value

    COLUMNS = ["", "#", "Title", "Duration", "Artist", "Album"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._metadata: dict[int, AudiobookMetadata] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)

        # Configure selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Configure header
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # Track #
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Title
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # Duration
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # Artist
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  # Album

        self.setColumnWidth(0, 30)
        self.setColumnWidth(1, 40)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(4, 150)
        self.setColumnWidth(5, 150)

        # Enable editing for certain columns
        self.itemChanged.connect(self._on_item_changed)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_tracks(
        self,
        tracks: list[Track],
        metadata: dict[int, AudiobookMetadata] | None = None,
    ) -> None:
        """Set the track list.

        Args:
            tracks: List of Track objects
            metadata: Optional dict mapping track numbers to metadata
        """
        self.blockSignals(True)
        self.setRowCount(0)

        self._tracks = tracks
        self._metadata = metadata or {}

        for track in tracks:
            self._add_track_row(track)

        self.blockSignals(False)

    def _add_track_row(self, track: Track) -> None:
        row = self.rowCount()
        self.insertRow(row)

        meta = self._metadata.get(track.number, AudiobookMetadata(
            title=track.title,
            artist=track.artist,
            track_number=track.number,
        ))

        # Checkbox
        checkbox = QTableWidgetItem()
        checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checkbox.setCheckState(Qt.CheckState.Checked)
        self.setItem(row, 0, checkbox)

        # Track number (read-only)
        num_item = QTableWidgetItem(str(track.number))
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 1, num_item)

        # Title (editable)
        title_item = QTableWidgetItem(meta.title or track.title)
        self.setItem(row, 2, title_item)

        # Duration (read-only)
        duration_item = QTableWidgetItem(track.duration_formatted)
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 3, duration_item)

        # Artist (editable)
        artist_item = QTableWidgetItem(meta.artist or track.artist)
        self.setItem(row, 4, artist_item)

        # Album (editable)
        album_item = QTableWidgetItem(meta.album)
        self.setItem(row, 5, album_item)

    def get_selected_tracks(self) -> list[int]:
        """Get list of checked track numbers."""
        selected = []
        for row in range(self.rowCount()):
            checkbox = self.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.CheckState.Checked:
                selected.append(self._tracks[row].number)
        return selected

    def get_highlighted_tracks(self) -> list[int]:
        """Get list of highlighted (selected in UI) track numbers."""
        rows = set(item.row() for item in self.selectedItems())
        return [self._tracks[row].number for row in rows if row < len(self._tracks)]

    def select_all(self) -> None:
        """Check all tracks."""
        for row in range(self.rowCount()):
            checkbox = self.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.CheckState.Checked)

    def select_none(self) -> None:
        """Uncheck all tracks."""
        for row in range(self.rowCount()):
            checkbox = self.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.CheckState.Unchecked)

    def get_metadata(self, track_number: int) -> AudiobookMetadata | None:
        """Get metadata for a specific track, reading current values from the table."""
        # Find the row for this track
        for row, track in enumerate(self._tracks):
            if track.number == track_number:
                # Get or create metadata
                if track_number not in self._metadata:
                    self._metadata[track_number] = AudiobookMetadata(track_number=track_number)

                meta = self._metadata[track_number]
                # Update from current table values
                meta.title = self.item(row, 2).text()
                meta.artist = self.item(row, 4).text()
                meta.album = self.item(row, 5).text()
                return meta

        return self._metadata.get(track_number)

    def set_metadata(self, track_number: int, metadata: AudiobookMetadata) -> None:
        """Set metadata for a specific track and update display."""
        self._metadata[track_number] = metadata

        # Find row for this track
        for row, track in enumerate(self._tracks):
            if track.number == track_number:
                self.blockSignals(True)
                self.item(row, 2).setText(metadata.title)
                self.item(row, 4).setText(metadata.artist)
                self.item(row, 5).setText(metadata.album)
                self.blockSignals(False)
                break

    def get_all_metadata(self) -> dict[int, AudiobookMetadata]:
        """Get metadata dictionary for all tracks."""
        # Update metadata from table contents
        for row, track in enumerate(self._tracks):
            if track.number not in self._metadata:
                self._metadata[track.number] = AudiobookMetadata(track_number=track.number)

            meta = self._metadata[track.number]
            meta.title = self.item(row, 2).text()
            meta.artist = self.item(row, 4).text()
            meta.album = self.item(row, 5).text()
            meta.total_tracks = len(self._tracks)

        return self._metadata

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        row = item.row()
        col = item.column()

        if row >= len(self._tracks):
            return

        track_number = self._tracks[row].number
        field_map = {2: "title", 4: "artist", 5: "album"}

        if col in field_map:
            field = field_map[col]
            value = item.text()
            self.metadata_edited.emit(track_number, field, value)

    def _on_selection_changed(self) -> None:
        selected = self.get_highlighted_tracks()
        self.selection_changed.emit(selected)
