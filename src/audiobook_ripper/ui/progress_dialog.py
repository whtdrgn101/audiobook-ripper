"""Progress dialog for ripping operations."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audiobook_ripper.core.models import RipProgress


class ProgressDialog(QDialog):
    """Dialog showing progress of ripping operation."""

    cancel_requested = Signal()

    def __init__(self, total_tracks: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total_tracks = total_tracks
        self._cancelled = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Ripping Progress")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self.setModal(True)

        # Prevent closing via X button during operation
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)

        # Current track info
        self._current_label = QLabel("Preparing...")
        self._current_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._current_label)

        # Overall progress
        overall_layout = QHBoxLayout()
        overall_layout.addWidget(QLabel("Overall:"))
        self._overall_progress = QProgressBar()
        self._overall_progress.setRange(0, 100)
        overall_layout.addWidget(self._overall_progress)
        layout.addLayout(overall_layout)

        # Status label
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Log output
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(150)
        layout.addWidget(self._log_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self._cancel_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        button_layout.addWidget(self._close_btn)

        layout.addLayout(button_layout)

    def update_progress(self, progress: RipProgress) -> None:
        """Update the dialog with new progress information."""
        # Update labels
        self._current_label.setText(
            f"Track {progress.track_number} of {progress.total_tracks}: {progress.status}"
        )

        if progress.current_file:
            self._status_label.setText(f"Output: {progress.current_file.name}")

        # Update progress bar
        self._overall_progress.setValue(int(progress.overall_progress * 100))

        # Log errors
        if progress.error:
            self.log(f"Error: {progress.error}")

    def log(self, message: str) -> None:
        """Add a message to the log output."""
        self._log_text.append(message)
        # Scroll to bottom
        scrollbar = self._log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_finished(self, success: bool = True) -> None:
        """Mark the operation as finished."""
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

        if success:
            self._current_label.setText("Ripping complete!")
            self._overall_progress.setValue(100)
        else:
            self._current_label.setText("Ripping cancelled or failed")

        # Re-enable close button
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowCloseButtonHint
        )

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._current_label.setText("Cancelling...")
        self.cancel_requested.emit()
