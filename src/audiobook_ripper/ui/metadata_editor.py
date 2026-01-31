"""Metadata editing dialog."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audiobook_ripper.core.models import AudiobookMetadata


class MetadataEditorDialog(QDialog):
    """Dialog for editing track metadata."""

    def __init__(
        self,
        metadata: AudiobookMetadata,
        batch_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the metadata editor.

        Args:
            metadata: Initial metadata to edit
            batch_mode: If True, show batch editing options
            parent: Parent widget
        """
        super().__init__(parent)
        self._metadata = metadata
        self._batch_mode = batch_mode
        self._cover_art_data: bytes | None = metadata.cover_art
        self._cover_art_mime: str = metadata.cover_art_mime

        self._setup_ui()
        self._load_metadata()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Edit Metadata")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Standard fields
        standard_group = QGroupBox("Standard Information")
        standard_layout = QFormLayout(standard_group)

        self._title_edit = QLineEdit()
        if not self._batch_mode:
            standard_layout.addRow("Title:", self._title_edit)

        self._artist_edit = QLineEdit()
        standard_layout.addRow("Author:", self._artist_edit)

        self._album_edit = QLineEdit()
        standard_layout.addRow("Book Title:", self._album_edit)

        # Track number row (not shown in batch mode)
        track_layout = QHBoxLayout()
        self._track_spin = QSpinBox()
        self._track_spin.setRange(0, 999)
        track_layout.addWidget(self._track_spin)
        track_layout.addWidget(QLabel("of"))
        self._total_tracks_spin = QSpinBox()
        self._total_tracks_spin.setRange(0, 999)
        track_layout.addWidget(self._total_tracks_spin)
        track_layout.addStretch()
        if not self._batch_mode:
            standard_layout.addRow("Track:", track_layout)

        self._year_spin = QSpinBox()
        self._year_spin.setRange(0, 2100)
        self._year_spin.setSpecialValueText("None")
        standard_layout.addRow("Year:", self._year_spin)

        self._genre_edit = QLineEdit()
        standard_layout.addRow("Genre:", self._genre_edit)

        layout.addWidget(standard_group)

        # Audiobook-specific fields
        audiobook_group = QGroupBox("Audiobook Information")
        audiobook_layout = QFormLayout(audiobook_group)

        self._narrator_edit = QLineEdit()
        audiobook_layout.addRow("Narrator:", self._narrator_edit)

        self._series_edit = QLineEdit()
        audiobook_layout.addRow("Series:", self._series_edit)

        self._series_number_edit = QLineEdit()
        self._series_number_edit.setMaximumWidth(100)
        audiobook_layout.addRow("Series #:", self._series_number_edit)

        layout.addWidget(audiobook_group)

        # Cover art
        cover_group = QGroupBox("Cover Art")
        cover_layout = QHBoxLayout(cover_group)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(150, 150)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        cover_layout.addWidget(self._cover_label)

        cover_buttons = QVBoxLayout()
        self._load_cover_btn = QPushButton("Load Image...")
        self._load_cover_btn.clicked.connect(self._on_load_cover)
        cover_buttons.addWidget(self._load_cover_btn)

        self._clear_cover_btn = QPushButton("Clear")
        self._clear_cover_btn.clicked.connect(self._on_clear_cover)
        cover_buttons.addWidget(self._clear_cover_btn)

        cover_buttons.addStretch()
        cover_layout.addLayout(cover_buttons)
        cover_layout.addStretch()

        layout.addWidget(cover_group)

        # Batch mode info
        if self._batch_mode:
            info_label = QLabel(
                "Batch editing mode: Changes will be applied to all selected tracks.\n"
                "Leave fields empty to keep existing values."
            )
            info_label.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(info_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_metadata(self) -> None:
        """Load metadata into the form fields."""
        self._title_edit.setText(self._metadata.title)
        self._artist_edit.setText(self._metadata.artist)
        self._album_edit.setText(self._metadata.album)
        self._track_spin.setValue(self._metadata.track_number)
        self._total_tracks_spin.setValue(self._metadata.total_tracks)
        self._year_spin.setValue(self._metadata.year or 0)
        self._genre_edit.setText(self._metadata.genre)
        self._narrator_edit.setText(self._metadata.narrator)
        self._series_edit.setText(self._metadata.series)
        self._series_number_edit.setText(self._metadata.series_number)

        self._update_cover_preview()

    def _update_cover_preview(self) -> None:
        """Update the cover art preview."""
        if self._cover_art_data:
            pixmap = QPixmap()
            pixmap.loadFromData(self._cover_art_data)
            scaled = pixmap.scaled(
                150, 150,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._cover_label.setPixmap(scaled)
        else:
            self._cover_label.setText("No cover")

    def _on_load_cover(self) -> None:
        """Load cover art from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            "",
            "Images (*.jpg *.jpeg *.png *.gif *.bmp)",
        )
        if file_path:
            path = Path(file_path)
            self._cover_art_data = path.read_bytes()

            # Determine MIME type
            suffix = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
            }
            self._cover_art_mime = mime_map.get(suffix, "image/jpeg")
            self._update_cover_preview()

    def _on_clear_cover(self) -> None:
        """Clear the cover art."""
        self._cover_art_data = None
        self._update_cover_preview()

    def get_metadata(self) -> AudiobookMetadata:
        """Get the edited metadata."""
        return AudiobookMetadata(
            title=self._title_edit.text(),
            artist=self._artist_edit.text(),
            album=self._album_edit.text(),
            track_number=self._track_spin.value(),
            total_tracks=self._total_tracks_spin.value(),
            year=self._year_spin.value() or None,
            genre=self._genre_edit.text() or "Audiobook",
            narrator=self._narrator_edit.text(),
            series=self._series_edit.text(),
            series_number=self._series_number_edit.text(),
            cover_art=self._cover_art_data,
            cover_art_mime=self._cover_art_mime,
        )

    def get_batch_updates(self) -> dict[str, str | int | bytes | None]:
        """Get only the fields that should be updated in batch mode.

        Returns fields that have non-empty values.
        """
        updates: dict[str, str | int | bytes | None] = {}

        if self._album_edit.text():
            updates["album"] = self._album_edit.text()
        if self._artist_edit.text():
            updates["artist"] = self._artist_edit.text()
        if self._genre_edit.text():
            updates["genre"] = self._genre_edit.text()
        if self._narrator_edit.text():
            updates["narrator"] = self._narrator_edit.text()
        if self._series_edit.text():
            updates["series"] = self._series_edit.text()
        if self._series_number_edit.text():
            updates["series_number"] = self._series_number_edit.text()
        if self._year_spin.value():
            updates["year"] = self._year_spin.value()
        if self._cover_art_data:
            updates["cover_art"] = self._cover_art_data
            updates["cover_art_mime"] = self._cover_art_mime

        return updates
