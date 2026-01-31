"""Application bootstrap and dependency injection setup."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from audiobook_ripper.core.container import Container
from audiobook_ripper.core.interfaces import (
    ICDDrive,
    IEncoder,
    IMetadataService,
    IMusicBrainzService,
    IRipper,
)
from audiobook_ripper.services.cd_drive import CDDriveService
from audiobook_ripper.services.encoder import EncoderService
from audiobook_ripper.services.metadata import MetadataService
from audiobook_ripper.services.musicbrainz import MusicBrainzService
from audiobook_ripper.services.ripper import FFmpegRipper
from audiobook_ripper.ui.main_window import MainWindow
from audiobook_ripper.utils.ffmpeg import check_ffmpeg


def create_container() -> Container:
    """Create and configure the dependency injection container."""
    container = Container()

    # Register services
    container.register(ICDDrive, CDDriveService())
    container.register(IRipper, FFmpegRipper())
    container.register(IEncoder, EncoderService())
    container.register(IMetadataService, MetadataService())
    container.register(IMusicBrainzService, MusicBrainzService())

    return container


def check_prerequisites() -> list[str]:
    """Check for required external dependencies.

    Returns:
        List of error messages for missing dependencies
    """
    errors = []

    if not check_ffmpeg():
        errors.append(
            "FFmpeg is not installed or not in PATH.\n"
            "Please install FFmpeg and ensure it's accessible from the command line."
        )

    return errors


def create_app() -> QApplication:
    """Create and initialize the Qt application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Audiobook CD Ripper")
    app.setApplicationVersion("0.1.0")

    # Check prerequisites
    errors = check_prerequisites()
    if errors:
        QMessageBox.critical(
            None,
            "Missing Dependencies",
            "\n\n".join(errors),
        )
        # Continue anyway - some features may work

    # Create container and main window
    container = create_container()
    window = MainWindow(container)
    window.show()

    # Store window reference on app to prevent garbage collection
    app._main_window = window

    return app
