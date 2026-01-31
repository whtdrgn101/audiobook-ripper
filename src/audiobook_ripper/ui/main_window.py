"""Main application window."""

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from audiobook_ripper.core.container import Container
from audiobook_ripper.core.interfaces import (
    ICDDrive,
    IEncoder,
    IMetadataService,
    IMusicBrainzService,
    IRipper,
)
from audiobook_ripper.core.models import AudiobookMetadata, RipProgress, Track
from audiobook_ripper.ui.drive_selector import DriveSelector
from audiobook_ripper.ui.metadata_editor import MetadataEditorDialog
from audiobook_ripper.ui.progress_dialog import ProgressDialog
from audiobook_ripper.ui.settings_dialog import SettingsDialog
from audiobook_ripper.ui.track_list import TrackListWidget
from audiobook_ripper.utils.config import Config


class ScanWorker(QThread):
    """Worker thread for scanning CD tracks."""

    finished = Signal(list)  # list of Track objects
    error = Signal(str)

    def __init__(self, cd_drive_service, drive: str) -> None:
        super().__init__()
        self._cd_drive_service = cd_drive_service
        self._drive = drive

    def run(self) -> None:
        try:
            tracks = self._cd_drive_service.get_tracks(self._drive)
            self.finished.emit(tracks)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit([])


class ScanningDialog(QDialog):
    """Modal dialog shown while scanning a CD."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scanning CD")
        self.setModal(True)
        self.setFixedSize(300, 100)

        layout = QVBoxLayout(self)

        self._label = QLabel("Reading disc contents...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self._progress)

    def set_message(self, message: str) -> None:
        self._label.setText(message)


class CombineOptionsDialog(QDialog):
    """Dialog for setting combined file options."""

    def __init__(
        self,
        default_title: str = "",
        default_disc: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Combined File Options")
        self.setModal(True)
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # Form layout for inputs
        form = QFormLayout()

        self._title_edit = QLineEdit(default_title)
        self._title_edit.setPlaceholderText("Enter filename (without extension)")
        form.addRow("Filename:", self._title_edit)

        self._disc_spin = QSpinBox()
        self._disc_spin.setRange(1, 99)
        self._disc_spin.setValue(default_disc)
        form.addRow("Disc Number:", self._disc_spin)

        self._total_discs_spin = QSpinBox()
        self._total_discs_spin.setRange(0, 99)
        self._total_discs_spin.setValue(0)
        self._total_discs_spin.setSpecialValueText("Unknown")
        form.addRow("Total Discs:", self._total_discs_spin)

        layout.addLayout(form)

        # Preview
        self._preview_label = QLabel()
        self._preview_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self._preview_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Update preview when inputs change
        self._title_edit.textChanged.connect(self._update_preview)
        self._disc_spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the filename preview."""
        filename = self.get_filename()
        self._preview_label.setText(f"File: {filename}")

    def get_filename(self) -> str:
        """Get the combined filename."""
        title = self._title_edit.text().strip()
        if not title:
            title = "audiobook"
        # Sanitize filename
        safe_title = "".join(c for c in title if c not in '<>:"/\\|?*')
        disc = self._disc_spin.value()
        return f"{safe_title} - Disc {disc:02d}.mp3"

    def get_title(self) -> str:
        """Get the title for metadata (Disc XX)."""
        disc = self._disc_spin.value()
        return f"Disc {disc:02d}"

    def get_disc_number(self) -> int:
        """Get the disc number."""
        return self._disc_spin.value()

    def get_total_discs(self) -> int | None:
        """Get total discs, or None if unknown."""
        value = self._total_discs_spin.value()
        return value if value > 0 else None


class RipWorker(QThread):
    """Worker thread for ripping and encoding tracks."""

    progress = Signal(RipProgress)
    finished = Signal(bool)  # success
    error = Signal(str)

    def __init__(
        self,
        ripper: IRipper,
        encoder: IEncoder,
        metadata_service: IMetadataService,
        drive: str,
        tracks: list[int],
        output_dir: Path,
        metadata: dict[int, AudiobookMetadata],
        bitrate: int,
        combine: bool = False,
        combined_filename: str = "audiobook.mp3",
    ) -> None:
        super().__init__()
        self._ripper = ripper
        self._encoder = encoder
        self._metadata_service = metadata_service
        self._drive = drive
        self._tracks = tracks
        self._output_dir = output_dir
        self._metadata = metadata
        self._bitrate = bitrate
        self._combine = combine
        self._combined_filename = combined_filename
        self._cancelled = False

    def run(self) -> None:
        """Execute the ripping process using single-pass disc ripping."""
        total_tracks = len(self._tracks)
        temp_dir = Path(tempfile.mkdtemp(prefix="audiobook_rip_"))

        try:
            if self._combine:
                self._run_combined_mode(temp_dir, total_tracks)
            else:
                self._run_split_mode(temp_dir, total_tracks)

            self.finished.emit(not self._cancelled)

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

        finally:
            # Clean up temp directory
            self._cleanup_temp_dir(temp_dir)

    def _run_combined_mode(self, temp_dir: Path, total_tracks: int) -> None:
        """Combined mode: rip disc → encode to single MP3 → write metadata."""
        full_disc_wav = temp_dir / "full_disc.wav"
        combined_path = self._output_dir / self._combined_filename

        # Step 1: Rip entire disc (progress 0-50%)
        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=1,
            track_progress=0.0,
            current_file=full_disc_wav,
            status="Ripping entire disc",
        ))

        try:
            self._ripper.rip_disc(
                self._drive,
                full_disc_wav,
                lambda p: self._emit_progress(1, 1, p * 0.5, full_disc_wav, "Ripping disc"),
            )
        except Exception as e:
            self.progress.emit(RipProgress(
                track_number=1,
                total_tracks=1,
                track_progress=0.0,
                status="Error",
                error=f"Ripping failed: {e}",
            ))
            raise

        if self._cancelled:
            return

        # Step 2: Encode to single MP3 (progress 50-95%)
        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=1,
            track_progress=0.5,
            current_file=combined_path,
            status="Encoding",
        ))

        try:
            self._encoder.encode_to_mp3(
                full_disc_wav,
                combined_path,
                self._bitrate,
                lambda p: self._emit_progress(1, 1, 0.5 + p * 0.45, combined_path, "Encoding"),
            )
        except Exception as e:
            self.progress.emit(RipProgress(
                track_number=1,
                total_tracks=1,
                track_progress=0.5,
                status="Error",
                error=f"Encoding failed: {e}",
            ))
            raise

        if self._cancelled:
            return

        # Step 3: Write metadata (progress 95-100%)
        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=1,
            track_progress=0.95,
            current_file=combined_path,
            status="Writing metadata",
        ))

        try:
            first_meta = self._metadata.get(self._tracks[0], AudiobookMetadata())
            # Use disc number as track number for combined files
            first_meta.track_number = first_meta.disc_number or 1
            first_meta.total_tracks = first_meta.total_discs or 1
            self._metadata_service.write_metadata(combined_path, first_meta)
        except Exception as e:
            self.progress.emit(RipProgress(
                track_number=1,
                total_tracks=1,
                track_progress=0.95,
                status="Warning",
                error=f"Metadata write failed: {e}",
            ))

        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=1,
            track_progress=1.0,
            current_file=combined_path,
            status="Complete",
        ))

    def _run_split_mode(self, temp_dir: Path, total_tracks: int) -> None:
        """Split mode: rip disc → split by chapters → parallel encode → metadata."""
        full_disc_wav = temp_dir / "full_disc.wav"

        # Step 1: Rip entire disc (progress 0-40%)
        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=total_tracks,
            track_progress=0.0,
            current_file=full_disc_wav,
            status="Ripping entire disc",
        ))

        try:
            self._ripper.rip_disc(
                self._drive,
                full_disc_wav,
                lambda p: self._emit_progress(1, total_tracks, p * 0.4, full_disc_wav, "Ripping disc"),
            )
        except Exception as e:
            self.progress.emit(RipProgress(
                track_number=1,
                total_tracks=total_tracks,
                track_progress=0.0,
                status="Error",
                error=f"Ripping failed: {e}",
            ))
            raise

        if self._cancelled:
            return

        # Step 2: Get chapters and split into track WAVs (progress 40-50%)
        self.progress.emit(RipProgress(
            track_number=1,
            total_tracks=total_tracks,
            track_progress=0.4,
            current_file=full_disc_wav,
            status="Splitting tracks",
        ))

        try:
            chapters = self._ripper.get_chapters(self._drive)
            # Filter chapters to only include selected tracks
            selected_chapters = [chapters[t - 1] for t in self._tracks if t <= len(chapters)]

            track_wavs = self._ripper.split_audio(
                full_disc_wav,
                temp_dir,
                selected_chapters,
                lambda p: self._emit_progress(1, total_tracks, 0.4 + p * 0.1, full_disc_wav, "Splitting"),
            )
        except Exception as e:
            self.progress.emit(RipProgress(
                track_number=1,
                total_tracks=total_tracks,
                track_progress=0.4,
                status="Error",
                error=f"Splitting failed: {e}",
            ))
            raise

        if self._cancelled:
            return

        # Clean up full disc WAV to save space
        if full_disc_wav.exists():
            full_disc_wav.unlink()

        # Step 3: Parallel encode all tracks (progress 50-95%)
        self._parallel_encode(track_wavs, total_tracks)

        if self._cancelled:
            return

        # Step 4: Write metadata to each MP3 (progress 95-100%)
        self._write_all_metadata(total_tracks)

    def _parallel_encode(self, track_wavs: list[Path], total_tracks: int) -> None:
        """Encode tracks in parallel using ThreadPoolExecutor."""
        completed_count = 0
        completed_lock = Lock()
        encode_errors: list[str] = []

        def encode_track(args: tuple[int, Path, int]) -> tuple[int, Path, str | None]:
            """Encode a single track. Returns (track_num, mp3_path, error)."""
            idx, wav_path, track_num = args
            meta = self._metadata.get(track_num, AudiobookMetadata(track_number=track_num))
            safe_title = "".join(c for c in meta.title if c not in '<>:"/\\|?*') or f"Track {track_num:02d}"
            mp3_path = self._output_dir / f"{track_num:02d} - {safe_title}.mp3"

            try:
                self._encoder.encode_to_mp3(
                    wav_path,
                    mp3_path,
                    self._bitrate,
                )
                return (track_num, mp3_path, None)
            except Exception as e:
                return (track_num, mp3_path, str(e))

        # Create work items: (index, wav_path, track_number)
        work_items = list(zip(range(len(track_wavs)), track_wavs, self._tracks))

        # Use up to 4 threads for encoding (or fewer if less tracks)
        max_workers = min(4, len(work_items))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(encode_track, item): item for item in work_items}

            for future in as_completed(futures):
                if self._cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return

                track_num, mp3_path, error = future.result()

                with completed_lock:
                    completed_count += 1
                    progress = 0.5 + (completed_count / total_tracks) * 0.45

                if error:
                    encode_errors.append(f"Track {track_num}: {error}")
                    self.progress.emit(RipProgress(
                        track_number=completed_count,
                        total_tracks=total_tracks,
                        track_progress=progress,
                        current_file=mp3_path,
                        status="Error",
                        error=error,
                    ))
                else:
                    self.progress.emit(RipProgress(
                        track_number=completed_count,
                        total_tracks=total_tracks,
                        track_progress=progress,
                        current_file=mp3_path,
                        status="Encoded",
                    ))

        # Clean up WAV files after encoding
        for wav_path in track_wavs:
            if wav_path.exists():
                wav_path.unlink()

    def _write_all_metadata(self, total_tracks: int) -> None:
        """Write metadata to all encoded MP3 files."""
        for i, track_num in enumerate(self._tracks, start=1):
            if self._cancelled:
                return

            meta = self._metadata.get(track_num, AudiobookMetadata(track_number=track_num))
            safe_title = "".join(c for c in meta.title if c not in '<>:"/\\|?*') or f"Track {track_num:02d}"
            mp3_path = self._output_dir / f"{track_num:02d} - {safe_title}.mp3"

            if not mp3_path.exists():
                continue

            progress = 0.95 + (i / total_tracks) * 0.05

            self.progress.emit(RipProgress(
                track_number=i,
                total_tracks=total_tracks,
                track_progress=progress,
                current_file=mp3_path,
                status="Writing metadata",
            ))

            try:
                self._metadata_service.write_metadata(mp3_path, meta)
            except Exception as e:
                self.progress.emit(RipProgress(
                    track_number=i,
                    total_tracks=total_tracks,
                    track_progress=progress,
                    status="Warning",
                    error=f"Metadata write failed: {e}",
                ))

        self.progress.emit(RipProgress(
            track_number=total_tracks,
            total_tracks=total_tracks,
            track_progress=1.0,
            status="Complete",
        ))

    def _cleanup_temp_dir(self, temp_dir: Path) -> None:
        """Clean up temporary directory and all its contents."""
        try:
            for f in temp_dir.iterdir():
                f.unlink()
            temp_dir.rmdir()
        except OSError:
            pass

    def _combine_mp3_files(self, mp3_files: list[Path], output_path: Path) -> None:
        """Combine multiple MP3 files into a single file using FFmpeg."""
        import subprocess

        # Create a file list for FFmpeg concat demuxer
        list_file = mp3_files[0].parent / "concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for mp3 in mp3_files:
                # Use forward slashes for FFmpeg compatibility on Windows
                # and escape single quotes in filenames
                path_str = str(mp3).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{path_str}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg concat timed out after 10 minutes")
        finally:
            if list_file.exists():
                list_file.unlink()

    def _emit_progress(
        self,
        track_num: int,
        total: int,
        progress: float,
        path: Path,
        status: str,
    ) -> None:
        self.progress.emit(RipProgress(
            track_number=track_num,
            total_tracks=total,
            track_progress=progress,
            current_file=path,
            status=status,
        ))

    def cancel(self) -> None:
        """Cancel the ripping operation."""
        self._cancelled = True
        self._ripper.cancel()
        self._encoder.cancel()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, container: Container, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._config = Config.load()
        self._tracks: list[Track] = []
        self._rip_worker: RipWorker | None = None
        self._scan_worker: ScanWorker | None = None

        self._setup_ui()
        self._connect_services()
        self._load_settings()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Audiobook CD Ripper")
        self.resize(self._config.window_width, self._config.window_height)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Drive selector in toolbar
        self._drive_selector = DriveSelector()
        toolbar.addWidget(self._drive_selector)
        toolbar.addSeparator()

        # Lookup button
        self._lookup_btn = QPushButton("Lookup")
        self._lookup_btn.setToolTip("Look up disc info from MusicBrainz")
        self._lookup_btn.clicked.connect(self._on_lookup)
        toolbar.addWidget(self._lookup_btn)

        toolbar.addSeparator()

        # Settings button
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._on_settings)
        toolbar.addWidget(settings_btn)

        # Track list
        self._track_list = TrackListWidget()
        layout.addWidget(self._track_list)

        # Selection buttons
        select_layout = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._track_list.select_all)
        select_layout.addWidget(self._select_all_btn)

        self._select_none_btn = QPushButton("Select None")
        self._select_none_btn.clicked.connect(self._track_list.select_none)
        select_layout.addWidget(self._select_none_btn)

        self._edit_btn = QPushButton("Edit Metadata...")
        self._edit_btn.clicked.connect(self._on_edit_metadata)
        select_layout.addWidget(self._edit_btn)

        self._edit_batch_btn = QPushButton("Batch Edit...")
        self._edit_batch_btn.clicked.connect(self._on_batch_edit)
        select_layout.addWidget(self._edit_batch_btn)

        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Output folder
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Folder:"))
        self._output_label = QLabel()
        self._output_label.setStyleSheet("color: #666;")
        output_layout.addWidget(self._output_label)
        output_layout.addStretch()

        browse_btn = QPushButton("Change...")
        browse_btn.clicked.connect(self._on_browse_output)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout)

        # Combine option and Rip button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._combine_checkbox = QCheckBox("Combine into single file")
        self._combine_checkbox.setToolTip("Combine all tracks into a single MP3 file")
        button_layout.addWidget(self._combine_checkbox)

        self._rip_btn = QPushButton("Rip Selected Tracks")
        self._rip_btn.setMinimumWidth(200)
        self._rip_btn.clicked.connect(self._on_rip)
        button_layout.addWidget(self._rip_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        # Connect signals
        self._drive_selector.drive_changed.connect(self._on_drive_changed)
        self._drive_selector.refresh_requested.connect(self._on_refresh)
        self._track_list.selection_changed.connect(self._update_status)

        # Initialize button states
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Enable/disable buttons based on whether tracks are loaded."""
        has_tracks = len(self._tracks) > 0
        self._lookup_btn.setEnabled(has_tracks)
        self._select_all_btn.setEnabled(has_tracks)
        self._select_none_btn.setEnabled(has_tracks)
        self._edit_btn.setEnabled(has_tracks)
        self._edit_batch_btn.setEnabled(has_tracks)
        self._rip_btn.setEnabled(has_tracks)

    def _connect_services(self) -> None:
        """Connect services from container to UI components."""
        if self._container.is_registered(ICDDrive):
            cd_drive = self._container.resolve(ICDDrive)
            self._drive_selector.set_service(cd_drive)
            self._drive_selector.refresh()

    def _load_settings(self) -> None:
        """Load settings into UI."""
        output_dir = self._config.get_output_dir()
        self._output_label.setText(str(output_dir))

        if self._config.last_drive:
            self._drive_selector.set_drive(self._config.last_drive)

    def _on_drive_changed(self, drive: str) -> None:
        """Handle drive selection change."""
        self._config.last_drive = drive
        self._refresh_tracks()

    def _on_refresh(self) -> None:
        """Handle refresh button."""
        self._refresh_tracks()

    def _refresh_tracks(self) -> None:
        """Refresh the track list from the current drive."""
        drive = self._drive_selector.current_drive()
        if not drive:
            self._tracks = []
            self._track_list.set_tracks([])
            self._update_button_states()
            return

        if not self._container.is_registered(ICDDrive):
            self._status_bar.showMessage("CD drive service not available")
            return

        cd_drive = self._container.resolve(ICDDrive)

        # Show scanning dialog
        scanning_dialog = ScanningDialog(self)

        # Create worker
        self._scan_worker = ScanWorker(cd_drive, drive)

        def on_scan_finished(tracks: list[Track]) -> None:
            scanning_dialog.accept()
            self._tracks = tracks
            self._track_list.set_tracks(self._tracks)
            self._update_button_states()

            if tracks:
                self._status_bar.showMessage(f"Found {len(tracks)} tracks")
                # Auto-lookup if enabled
                if self._config.auto_lookup:
                    self._on_lookup()
            else:
                self._status_bar.showMessage("No tracks found on disc")

        def on_scan_error(error: str) -> None:
            scanning_dialog.accept()
            self._status_bar.showMessage(f"Error: {error}")

        self._scan_worker.finished.connect(on_scan_finished)
        self._scan_worker.error.connect(on_scan_error)

        # Start worker and show dialog
        self._scan_worker.start()
        scanning_dialog.exec()

    def _on_lookup(self) -> None:
        """Look up disc metadata from MusicBrainz."""
        drive = self._drive_selector.current_drive()
        if not drive or not self._tracks:
            return

        self._status_bar.showMessage("Looking up disc info...")

        try:
            if not self._container.is_registered(ICDDrive):
                return
            if not self._container.is_registered(IMusicBrainzService):
                return

            cd_drive = self._container.resolve(ICDDrive)
            disc_id = cd_drive.get_disc_id(drive)

            if not disc_id:
                self._status_bar.showMessage("Could not read disc ID")
                return

            mb_service = self._container.resolve(IMusicBrainzService)
            release_info = mb_service.lookup_by_disc_id(disc_id)

            if release_info:
                metadata = mb_service.apply_to_tracks(release_info, self._tracks)
                self._track_list.set_tracks(self._tracks, metadata)
                self._status_bar.showMessage(
                    f"Found: {release_info.get('title', 'Unknown')} by {release_info.get('artist', 'Unknown')}"
                )
            else:
                self._status_bar.showMessage("Disc not found in MusicBrainz")

        except Exception as e:
            self._status_bar.showMessage(f"Lookup failed: {e}")

    def _on_edit_metadata(self) -> None:
        """Edit metadata for selected tracks."""
        selected = self._track_list.get_highlighted_tracks()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a track to edit.")
            return

        # Edit first selected track
        track_num = selected[0]
        metadata = self._track_list.get_metadata(track_num) or AudiobookMetadata(track_number=track_num)

        dialog = MetadataEditorDialog(metadata, parent=self)
        if dialog.exec():
            new_metadata = dialog.get_metadata()
            self._track_list.set_metadata(track_num, new_metadata)

    def _on_batch_edit(self) -> None:
        """Batch edit metadata for all checked tracks."""
        selected = self._track_list.get_selected_tracks()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please check tracks to edit.")
            return

        # Create empty metadata for batch editing
        dialog = MetadataEditorDialog(AudiobookMetadata(), batch_mode=True, parent=self)
        if dialog.exec():
            updates = dialog.get_batch_updates()
            if updates:
                for track_num in selected:
                    metadata = self._track_list.get_metadata(track_num) or AudiobookMetadata(track_number=track_num)
                    for key, value in updates.items():
                        setattr(metadata, key, value)
                    metadata.total_tracks = len(self._tracks)
                    self._track_list.set_metadata(track_num, metadata)

    def _on_browse_output(self) -> None:
        """Browse for output directory."""
        current = self._config.get_output_dir()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(current),
        )
        if directory:
            self._config.output_directory = directory
            self._config.save()
            self._output_label.setText(directory)

    def _on_settings(self) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(self._config, parent=self)
        if dialog.exec():
            self._config = dialog.get_config()
            self._output_label.setText(str(self._config.get_output_dir()))

    def _on_rip(self) -> None:
        """Start ripping selected tracks."""
        selected = self._track_list.get_selected_tracks()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select tracks to rip.")
            return

        drive = self._drive_selector.current_drive()
        if not drive:
            QMessageBox.warning(self, "No Drive", "Please select a CD drive.")
            return

        # Get all required services
        if not self._container.is_registered(IRipper):
            QMessageBox.warning(self, "Error", "Ripper service not available.")
            return
        if not self._container.is_registered(IEncoder):
            QMessageBox.warning(self, "Error", "Encoder service not available.")
            return
        if not self._container.is_registered(IMetadataService):
            QMessageBox.warning(self, "Error", "Metadata service not available.")
            return

        # Ensure output directory exists
        output_dir = self._config.get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get metadata
        metadata = self._track_list.get_all_metadata()

        # Check if combining into single file
        combine = self._combine_checkbox.isChecked()
        combined_filename = "audiobook.mp3"
        disc_number: int | None = None
        total_discs: int | None = None

        if combine and selected:
            # Show dialog to get filename and disc number
            first_meta = metadata.get(selected[0])
            default_title = first_meta.album if first_meta and first_meta.album else ""

            options_dialog = CombineOptionsDialog(
                default_title=default_title,
                default_disc=1,
                parent=self,
            )
            if not options_dialog.exec():
                return  # User cancelled

            combined_filename = options_dialog.get_filename()
            disc_number = options_dialog.get_disc_number()
            total_discs = options_dialog.get_total_discs()
            disc_title = options_dialog.get_title()

            # Update first track's metadata (used for combined file)
            first_track = selected[0]
            if first_track in metadata:
                metadata[first_track].disc_number = disc_number
                metadata[first_track].total_discs = total_discs
                metadata[first_track].title = disc_title

        # Create progress dialog
        progress_dialog = ProgressDialog(len(selected), parent=self)

        # Create worker
        self._rip_worker = RipWorker(
            ripper=self._container.resolve(IRipper),
            encoder=self._container.resolve(IEncoder),
            metadata_service=self._container.resolve(IMetadataService),
            drive=drive,
            tracks=selected,
            output_dir=output_dir,
            metadata=metadata,
            bitrate=self._config.default_bitrate,
            combine=combine,
            combined_filename=combined_filename,
        )

        # Connect signals
        self._rip_worker.progress.connect(progress_dialog.update_progress)
        # Only log on status changes, not every progress tick
        last_status = {"status": None, "track": None}
        def log_status_change(p: RipProgress) -> None:
            key = (p.status, p.track_number)
            if key != (last_status["status"], last_status["track"]):
                last_status["status"] = p.status
                last_status["track"] = p.track_number
                progress_dialog.log(f"{p.status}: Track {p.track_number}")
        self._rip_worker.progress.connect(log_status_change)
        self._rip_worker.finished.connect(lambda success: progress_dialog.set_finished(success))
        self._rip_worker.error.connect(lambda e: progress_dialog.log(f"Error: {e}"))
        progress_dialog.cancel_requested.connect(self._rip_worker.cancel)

        # Start worker and show dialog
        self._rip_worker.start()
        progress_dialog.exec()

        # Clean up
        if self._rip_worker.isRunning():
            self._rip_worker.cancel()
            self._rip_worker.wait()
        self._rip_worker = None

    def _update_status(self, selected: list[int]) -> None:
        """Update status bar with selection info."""
        checked = len(self._track_list.get_selected_tracks())
        self._status_bar.showMessage(f"{checked} tracks selected for ripping")

    def closeEvent(self, event) -> None:
        """Handle window close."""
        # Save window size
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        super().closeEvent(event)
