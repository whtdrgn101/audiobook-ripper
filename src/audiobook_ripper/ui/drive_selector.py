"""Drive selection widget."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from audiobook_ripper.core.interfaces import ICDDrive
from audiobook_ripper.core.models import DriveInfo


class DriveSelector(QWidget):
    """Widget for selecting a CD drive."""

    drive_changed = Signal(str)  # Emits drive letter
    refresh_requested = Signal()

    def __init__(
        self,
        cd_drive_service: ICDDrive | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cd_drive_service = cd_drive_service
        self._drives: list[DriveInfo] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(200)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self._combo)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self._refresh_btn)

        self._eject_btn = QPushButton("Eject")
        self._eject_btn.clicked.connect(self._on_eject_clicked)
        layout.addWidget(self._eject_btn)

    def set_service(self, service: ICDDrive) -> None:
        """Set the CD drive service."""
        self._cd_drive_service = service

    def refresh(self) -> None:
        """Refresh the list of available drives."""
        if not self._cd_drive_service:
            return

        self._combo.blockSignals(True)
        current_letter = self.current_drive()

        self._drives = self._cd_drive_service.list_drives()
        self._combo.clear()

        selected_index = -1
        for i, drive in enumerate(self._drives):
            self._combo.addItem(str(drive), drive.letter)
            if drive.letter == current_letter:
                selected_index = i

        if selected_index >= 0:
            self._combo.setCurrentIndex(selected_index)
        elif self._drives:
            self._combo.setCurrentIndex(0)

        self._combo.blockSignals(False)

        # Emit signal if selection changed
        new_letter = self.current_drive()
        if new_letter != current_letter:
            self.drive_changed.emit(new_letter)

    def current_drive(self) -> str:
        """Get the currently selected drive letter."""
        index = self._combo.currentIndex()
        if index >= 0 and index < len(self._drives):
            return self._drives[index].letter
        return ""

    def set_drive(self, letter: str) -> None:
        """Set the selected drive by letter."""
        for i, drive in enumerate(self._drives):
            if drive.letter == letter:
                self._combo.setCurrentIndex(i)
                break

    def _on_selection_changed(self, index: int) -> None:
        if index >= 0 and index < len(self._drives):
            self.drive_changed.emit(self._drives[index].letter)

    def _on_refresh_clicked(self) -> None:
        self.refresh()
        self.refresh_requested.emit()

    def _on_eject_clicked(self) -> None:
        drive = self.current_drive()
        if drive and self._cd_drive_service:
            self._cd_drive_service.eject(drive)
            self.refresh()
