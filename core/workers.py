"""
Worker threads for OCRMill background operations.
Uses QThread with signals for thread-safe UI updates.
"""

from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal, QObject


class SignalLogHandler(QObject):
    """Thread-safe log handler using Qt signals."""
    message_logged = pyqtSignal(str)

    def write(self, message: str):
        """Write a log message (emits signal)."""
        if message and message.strip():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.message_logged.emit(f"[{timestamp}] {message}")

    def flush(self):
        """Flush (no-op for signal-based logging)."""
        pass


class ProcessingWorker(QThread):
    """Background worker for monitoring and processing PDF files."""

    # Signals for communicating with main thread
    log_message = pyqtSignal(str)
    files_processed = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, engine, input_folder: Path, output_folder: Path, poll_interval: int):
        super().__init__()
        self.engine = engine
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.poll_interval = poll_interval
        self._stop_requested = False

    def run(self):
        """Main processing loop."""
        self.status_changed.emit("Running")
        self._log(f"Started monitoring {self.input_folder}")

        while not self._stop_requested:
            try:
                # Process any PDFs in the input folder
                count = self.engine.process_folder(self.input_folder, self.output_folder)
                if count > 0:
                    self.files_processed.emit(count)
                    self._log(f"Processed {count} file(s)")

            except Exception as e:
                self._log(f"Error during processing: {e}")
                self.error_occurred.emit(str(e))

            # Sleep in 1-second intervals for responsive stopping
            for _ in range(self.poll_interval):
                if self._stop_requested:
                    break
                self.msleep(1000)

        self._log("Monitoring stopped")
        self.status_changed.emit("Stopped")

    def request_stop(self):
        """Request the worker to stop gracefully."""
        self._stop_requested = True
        self._log("Stop requested...")

    def _log(self, message: str):
        """Emit a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")


class SingleFileWorker(QThread):
    """Worker for processing a single PDF file."""

    log_message = pyqtSignal(str)
    finished_processing = pyqtSignal(bool, str)  # success, message

    def __init__(self, engine, file_path: Path, output_folder: Path):
        super().__init__()
        self.engine = engine
        self.file_path = file_path
        self.output_folder = output_folder

    def run(self):
        """Process the single file."""
        try:
            self._log(f"Processing {self.file_path.name}...")
            result = self.engine.process_pdf(self.file_path)

            if result and result.get('items'):
                self.engine.save_to_csv(
                    result['items'],
                    self.output_folder,
                    self.file_path.name
                )
                self.engine.move_to_processed(self.file_path)
                self._log(f"Successfully processed {self.file_path.name}")
                self.finished_processing.emit(True, f"Processed {self.file_path.name}")
            else:
                self.engine.move_to_failed(self.file_path, "No items extracted")
                self._log(f"No data extracted from {self.file_path.name}")
                self.finished_processing.emit(False, "No data could be extracted")

        except Exception as e:
            self._log(f"Error: {e}")
            self.finished_processing.emit(False, str(e))

    def _log(self, message: str):
        """Emit a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")


class CBPExportWorker(QThread):
    """Worker for CBP export processing."""

    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, input_folder: Path, output_folder: Path):
        super().__init__()
        self.input_folder = input_folder
        self.output_folder = output_folder

    def run(self):
        """Run the CBP export process."""
        try:
            from cbp_exporter import CBPExporter

            self._log("Starting CBP export...")

            exporter = CBPExporter(self.input_folder, self.output_folder)
            files = list(self.input_folder.glob("*.csv"))
            total = len(files)

            if total == 0:
                self._log("No CSV files found for export")
                self.finished.emit(False, "No CSV files to process")
                return

            for i, file in enumerate(files, 1):
                self.progress.emit(i, total)
                exporter.process_file(file)
                self._log(f"Exported {file.name}")

            self._log(f"CBP export complete: {total} files processed")
            self.finished.emit(True, f"Exported {total} files")

        except ImportError:
            self._log("CBP exporter module not found")
            self.finished.emit(False, "CBP exporter module not available")
        except Exception as e:
            self._log(f"CBP export error: {e}")
            self.finished.emit(False, str(e))

    def _log(self, message: str):
        """Emit a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")


class UpdateCheckWorker(QThread):
    """Worker for checking application updates."""

    update_available = pyqtSignal(dict)  # update info dict
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        """Check for updates."""
        try:
            from updater import UpdateChecker

            checker = UpdateChecker(self.current_version)
            has_update = checker.check_for_updates()

            if has_update:
                self.update_available.emit(checker.get_update_info())
            else:
                if checker.last_error:
                    self.error.emit(checker.last_error)
                else:
                    self.no_update.emit()

        except Exception as e:
            self.error.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Worker for downloading updates."""

    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(bool, str)  # success, path_or_error
    cancelled = pyqtSignal()

    def __init__(self, checker):
        super().__init__()
        self.checker = checker
        self._cancelled = False

    def run(self):
        """Download the update."""
        try:
            def progress_callback(downloaded, total):
                self.progress.emit(downloaded, total)

            def cancel_check():
                return self._cancelled

            path = self.checker.download_update(
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

            if self._cancelled:
                self.cancelled.emit()
            elif path:
                self.finished.emit(True, str(path))
            else:
                self.finished.emit(False, self.checker.last_error or "Download failed")

        except Exception as e:
            self.finished.emit(False, str(e))

    def cancel(self):
        """Cancel the download."""
        self._cancelled = True


class ImportWorker(QThread):
    """Worker for importing data files (Excel, CSV)."""

    log_message = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str, int)  # success, message, count

    def __init__(self, file_path: Path, db, import_type: str = "parts"):
        super().__init__()
        self.file_path = file_path
        self.db = db
        self.import_type = import_type

    def run(self):
        """Run the import process."""
        try:
            self._log(f"Importing from {self.file_path.name}...")

            if self.import_type == "parts":
                count = self.db.import_parts_list(str(self.file_path))
                self._log(f"Imported {count} parts")
                self.finished.emit(True, f"Imported {count} parts", count)

            elif self.import_type == "manufacturers":
                count = self.db.import_manufacturers_from_excel(str(self.file_path))
                self._log(f"Imported {count} manufacturers")
                self.finished.emit(True, f"Imported {count} manufacturers", count)

            elif self.import_type == "hts":
                count = self.db.load_hts_mapping(str(self.file_path))
                self._log(f"Imported {count} HTS codes")
                self.finished.emit(True, f"Imported {count} HTS codes", count)

            else:
                self.finished.emit(False, f"Unknown import type: {self.import_type}", 0)

        except Exception as e:
            self._log(f"Import error: {e}")
            self.finished.emit(False, str(e), 0)

    def _log(self, message: str):
        """Emit a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")


class ExportWorker(QThread):
    """Worker for exporting data to CSV."""

    log_message = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, file_path or error message

    def __init__(self, db, output_path: Path, export_type: str = "master"):
        super().__init__()
        self.db = db
        self.output_path = output_path
        self.export_type = export_type

    def run(self):
        """Run the export process."""
        try:
            self._log(f"Exporting {self.export_type} to {self.output_path.name}...")

            if self.export_type == "master":
                self.db.export_to_csv(str(self.output_path), include_history=False)
            elif self.export_type == "history":
                self.db.export_to_csv(str(self.output_path), include_history=True)
            else:
                self.finished.emit(False, f"Unknown export type: {self.export_type}")
                return

            self._log(f"Export complete: {self.output_path}")
            self.finished.emit(True, str(self.output_path))

        except Exception as e:
            self._log(f"Export error: {e}")
            self.finished.emit(False, str(e))

    def _log(self, message: str):
        """Emit a log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")
