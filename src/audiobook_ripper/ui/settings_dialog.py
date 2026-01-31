"""Settings dialog for application configuration."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audiobook_ripper.utils.config import Config


class SettingsDialog(QDialog):
    """Dialog for editing application settings."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)

        # Output directory
        dir_layout = QHBoxLayout()
        self._output_dir_edit = QLineEdit()
        dir_layout.addWidget(self._output_dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_output)
        dir_layout.addWidget(browse_btn)
        output_layout.addRow("Output Directory:", dir_layout)

        # Bitrate
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItems(["128", "160", "192", "224", "256", "320"])
        output_layout.addRow("MP3 Bitrate (kbps):", self._bitrate_combo)

        # Filename template
        self._filename_edit = QLineEdit()
        self._filename_edit.setPlaceholderText("{track:02d} - {title}")
        output_layout.addRow("Filename Template:", self._filename_edit)

        layout.addWidget(output_group)

        # Metadata defaults
        metadata_group = QGroupBox("Metadata Defaults")
        metadata_layout = QFormLayout(metadata_group)

        self._genre_edit = QLineEdit()
        metadata_layout.addRow("Default Genre:", self._genre_edit)

        self._artist_edit = QLineEdit()
        metadata_layout.addRow("Default Author:", self._artist_edit)

        self._narrator_edit = QLineEdit()
        metadata_layout.addRow("Default Narrator:", self._narrator_edit)

        layout.addWidget(metadata_group)

        # MusicBrainz settings
        mb_group = QGroupBox("MusicBrainz")
        mb_layout = QFormLayout(mb_group)

        self._auto_lookup_check = QCheckBox("Automatically look up disc info")
        mb_layout.addRow(self._auto_lookup_check)

        layout.addWidget(mb_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(button_box)

    def _load_config(self) -> None:
        """Load current config into form fields."""
        self._output_dir_edit.setText(self._config.output_directory)
        self._bitrate_combo.setCurrentText(str(self._config.default_bitrate))
        self._filename_edit.setText(self._config.filename_template)
        self._genre_edit.setText(self._config.default_genre)
        self._artist_edit.setText(self._config.default_artist)
        self._narrator_edit.setText(self._config.default_narrator)
        self._auto_lookup_check.setChecked(self._config.auto_lookup)

    def _save_config(self) -> None:
        """Save form values to config."""
        self._config.output_directory = self._output_dir_edit.text()
        self._config.default_bitrate = int(self._bitrate_combo.currentText())
        self._config.filename_template = self._filename_edit.text() or "{track:02d} - {title}"
        self._config.default_genre = self._genre_edit.text()
        self._config.default_artist = self._artist_edit.text()
        self._config.default_narrator = self._narrator_edit.text()
        self._config.auto_lookup = self._auto_lookup_check.isChecked()
        self._config.save()

    def _on_browse_output(self) -> None:
        """Browse for output directory."""
        current = self._output_dir_edit.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current,
        )
        if directory:
            self._output_dir_edit.setText(directory)

    def _on_ok(self) -> None:
        """Handle OK button."""
        self._save_config()
        self.accept()

    def _on_apply(self) -> None:
        """Handle Apply button."""
        self._save_config()

    def get_config(self) -> Config:
        """Get the updated config."""
        return self._config
