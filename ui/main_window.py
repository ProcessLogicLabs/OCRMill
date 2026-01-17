"""
Main window for OCRMill application.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QFileDialog,
    QApplication, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QCloseEvent

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase
from updater import UpdateChecker

from ui.tabs.invoice_tab import InvoiceProcessingTab
from ui.tabs.parts_tab import PartsDatabaseTab
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.manufacturers_dialog import ManufacturersDialog
from ui.dialogs.hts_reference_dialog import HTSReferenceDialog
from core.workers import ProcessingWorker, UpdateCheckWorker


# Application version
VERSION = "2.5.0"


class OCRMillMainWindow(QMainWindow):
    """
    Main application window for OCRMill.

    Signals:
        parts_data_changed: Emitted when parts database is modified
        processing_started: Emitted when processing starts
        processing_stopped: Emitted when processing stops
    """

    parts_data_changed = pyqtSignal()
    processing_started = pyqtSignal()
    processing_stopped = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Initialize core components
        self.config = ConfigManager()
        self.db = PartsDatabase(db_path=self.config.database_path)

        # Processing state
        self.processing_worker = None
        self.is_processing = False

        # Set up UI
        self._setup_window()
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        self._connect_signals()

        # Restore window state
        self._restore_window_state()

        # Check for updates on startup (delayed)
        QTimer.singleShot(2000, self._check_for_updates_silent)

        # Auto-start if configured
        if self.config.auto_start:
            QTimer.singleShot(500, self._start_processing)

    def _setup_window(self):
        """Configure window properties."""
        self.setWindowTitle(f"OCRMill v{VERSION}")
        self.setMinimumSize(900, 600)

        # Set window icon if available
        icon_path = Path(__file__).parent.parent / "Resources" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _create_menu_bar(self):
        """Create the menu bar with all menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        import_action = QAction("&Import Parts List...", self)
        import_action.triggered.connect(self._import_parts_list)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        export_master = QAction("Export &Master CSV...", self)
        export_master.triggered.connect(self._export_master)
        file_menu.addAction(export_master)

        export_history = QAction("Export &History CSV...", self)
        export_history.triggered.connect(self._export_history)
        file_menu.addAction(export_history)

        file_menu.addSeparator()

        reports_action = QAction("&Generate Reports...", self)
        reports_action.triggered.connect(self._generate_reports)
        file_menu.addAction(reports_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Lists menu
        lists_menu = menubar.addMenu("&Lists")

        manufacturers_action = QAction("&Manufacturers/MID...", self)
        manufacturers_action.triggered.connect(self._show_manufacturers_dialog)
        lists_menu.addAction(manufacturers_action)

        hts_action = QAction("&HTS Reference...", self)
        hts_action.triggered.connect(self._show_hts_reference_dialog)
        lists_menu.addAction(hts_action)

        # Processing menu
        processing_menu = menubar.addMenu("&Processing")

        self.start_action = QAction("&Start Monitoring", self)
        self.start_action.setShortcut("F5")
        self.start_action.triggered.connect(self._start_processing)
        processing_menu.addAction(self.start_action)

        self.stop_action = QAction("S&top Monitoring", self)
        self.stop_action.setShortcut("F6")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._stop_processing)
        processing_menu.addAction(self.stop_action)

        processing_menu.addSeparator()

        process_now = QAction("Process &Now", self)
        process_now.setShortcut("F9")
        process_now.triggered.connect(self._process_now)
        processing_menu.addAction(process_now)

        processing_menu.addSeparator()

        cbp_export_action = QAction("Run &CBP Export", self)
        cbp_export_action.triggered.connect(self._run_cbp_export)
        processing_menu.addAction(cbp_export_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")

        preferences_action = QAction("&Preferences...", self)
        preferences_action.triggered.connect(self._show_settings_dialog)
        settings_menu.addAction(preferences_action)

        settings_menu.addSeparator()

        db_location_action = QAction("Change &Database Location...", self)
        db_location_action.triggered.connect(self._change_database_location)
        settings_menu.addAction(db_location_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        update_action = QAction("Check for &Updates...", self)
        update_action.triggered.connect(self._check_for_updates)
        help_menu.addAction(update_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_central_widget(self):
        """Create the central widget with tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Main tab widget
        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs)

        # Invoice Processing tab
        self.invoice_tab = InvoiceProcessingTab(self.config, self.db, self)
        self.main_tabs.addTab(self.invoice_tab, "Invoice Processing")

        # Parts Database tab
        self.parts_tab = PartsDatabaseTab(self.config, self.db, self)
        self.main_tabs.addTab(self.parts_tab, "Parts Database")

    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Spacer
        self.status_bar.addWidget(QLabel(), 1)

        # Processing status
        self.processing_status = QLabel("Monitoring: Stopped")
        self.status_bar.addPermanentWidget(self.processing_status)

        # Database info
        self.db_status = QLabel()
        self._update_db_status()
        self.status_bar.addPermanentWidget(self.db_status)

    def _connect_signals(self):
        """Connect internal signals."""
        self.parts_data_changed.connect(self._update_db_status)
        self.parts_data_changed.connect(self.parts_tab.refresh_data)

        self.processing_started.connect(self._on_processing_started)
        self.processing_stopped.connect(self._on_processing_stopped)

        # Connect invoice tab signals
        self.invoice_tab.log_message.connect(self._log)
        self.invoice_tab.files_processed.connect(self._on_files_processed)

    def _restore_window_state(self):
        """Restore window size and position from config."""
        width = self.config.get("window.width", 1200)
        height = self.config.get("window.height", 730)
        x = self.config.get("window.x")
        y = self.config.get("window.y")

        self.resize(width, height)

        if x is not None and y is not None:
            # Validate position is on screen
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                if 0 <= x < screen_geo.width() - 100 and 0 <= y < screen_geo.height() - 100:
                    self.move(x, y)

    def _save_window_state(self):
        """Save window size and position to config."""
        self.config.set("window.width", self.width())
        self.config.set("window.height", self.height())
        self.config.set("window.x", self.x())
        self.config.set("window.y", self.y())

    # ----- Processing Control -----

    @pyqtSlot()
    def _start_processing(self):
        """Start the background processing worker."""
        if self.is_processing:
            return

        # Create and start worker
        self.processing_worker = ProcessingWorker(
            engine=self.invoice_tab.engine,
            input_folder=Path(self.config.input_folder),
            output_folder=Path(self.config.output_folder),
            poll_interval=self.config.poll_interval
        )

        # Connect worker signals
        self.processing_worker.log_message.connect(self.invoice_tab.append_log)
        self.processing_worker.files_processed.connect(self._on_files_processed)
        self.processing_worker.status_changed.connect(self._on_status_changed)
        self.processing_worker.finished.connect(self._on_worker_finished)

        self.processing_worker.start()
        self.is_processing = True
        self.processing_started.emit()

    @pyqtSlot()
    def _stop_processing(self):
        """Stop the background processing worker."""
        if not self.is_processing or not self.processing_worker:
            return

        self.processing_worker.request_stop()
        self.processing_worker.wait(5000)  # Wait up to 5 seconds
        self.is_processing = False
        self.processing_stopped.emit()

    @pyqtSlot()
    def _process_now(self):
        """Process files immediately (one-shot)."""
        self.invoice_tab.process_now()

    @pyqtSlot()
    def _run_cbp_export(self):
        """Run the CBP export process."""
        self.invoice_tab.run_cbp_export()

    @pyqtSlot()
    def _on_processing_started(self):
        """Handle processing started."""
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.processing_status.setText("Monitoring: Running")
        self.processing_status.setStyleSheet("color: green; font-weight: bold;")
        self.invoice_tab.set_processing_state(True)

    @pyqtSlot()
    def _on_processing_stopped(self):
        """Handle processing stopped."""
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.processing_status.setText("Monitoring: Stopped")
        self.processing_status.setStyleSheet("")
        self.invoice_tab.set_processing_state(False)

    @pyqtSlot(int)
    def _on_files_processed(self, count: int):
        """Handle files processed notification."""
        if count > 0:
            self.parts_data_changed.emit()
            self.status_label.setText(f"Processed {count} file(s)")

            # Auto CBP export if enabled
            if self.config.auto_cbp_export:
                self._run_cbp_export()

    @pyqtSlot(str)
    def _on_status_changed(self, status: str):
        """Handle status change from worker."""
        self.processing_status.setText(f"Monitoring: {status}")

    @pyqtSlot()
    def _on_worker_finished(self):
        """Handle worker thread finished."""
        self.is_processing = False
        self.processing_stopped.emit()

    # ----- Menu Actions -----

    @pyqtSlot()
    def _import_parts_list(self):
        """Import parts from Excel/CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Parts List",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            try:
                count = self.db.import_parts_list(file_path)
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {count} parts."
                )
                self.parts_data_changed.emit()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"Failed to import parts:\n{e}"
                )

    @pyqtSlot()
    def _export_master(self):
        """Export parts master to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Parts Master",
            "parts_master.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            try:
                self.db.export_to_csv(file_path, include_history=False)
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Parts master exported to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export:\n{e}"
                )

    @pyqtSlot()
    def _export_history(self):
        """Export parts history to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Parts History",
            "parts_history.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            try:
                self.db.export_to_csv(file_path, include_history=True)
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Parts history exported to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export:\n{e}"
                )

    @pyqtSlot()
    def _generate_reports(self):
        """Generate all reports."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Reports Folder",
            str(Path(self.config.output_folder) / "reports")
        )
        if folder:
            try:
                self.db.create_parts_report(folder)
                QMessageBox.information(
                    self,
                    "Reports Generated",
                    f"Reports saved to:\n{folder}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Report Error",
                    f"Failed to generate reports:\n{e}"
                )

    @pyqtSlot()
    def _show_manufacturers_dialog(self):
        """Show the manufacturers management dialog."""
        dialog = ManufacturersDialog(self.db, self)
        dialog.exec()

    @pyqtSlot()
    def _show_hts_reference_dialog(self):
        """Show the HTS reference dialog."""
        dialog = HTSReferenceDialog(self.db, self)
        if dialog.exec():
            self.parts_data_changed.emit()

    @pyqtSlot()
    def _show_settings_dialog(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Reload config and update UI
            self.invoice_tab.reload_config()
            self.parts_tab.reload_columns()

    @pyqtSlot()
    def _change_database_location(self):
        """Change the database file location."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Database Location",
            str(self.config.database_path),
            "SQLite Database (*.db)"
        )
        if file_path:
            try:
                # Close current database
                self.db.close()

                # Update config
                self.config.database_path = file_path

                # Open new database
                self.db = PartsDatabase(db_path=Path(file_path))

                # Update tabs
                self.invoice_tab.db = self.db
                self.parts_tab.db = self.db

                self.parts_data_changed.emit()
                self._update_db_status()

                QMessageBox.information(
                    self,
                    "Database Changed",
                    f"Database location changed to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Database Error",
                    f"Failed to change database:\n{e}"
                )

    @pyqtSlot()
    def _check_for_updates(self):
        """Check for application updates (user-initiated)."""
        self.status_label.setText("Checking for updates...")

        worker = UpdateCheckWorker(VERSION)
        worker.update_available.connect(self._on_update_available)
        worker.no_update.connect(self._on_no_update)
        worker.error.connect(self._on_update_error)
        worker.start()

        # Store reference to prevent garbage collection
        self._update_worker = worker

    def _check_for_updates_silent(self):
        """Check for updates silently on startup."""
        worker = UpdateCheckWorker(VERSION)
        worker.update_available.connect(self._on_update_available)
        worker.start()
        self._update_worker = worker

    @pyqtSlot(dict)
    def _on_update_available(self, info: dict):
        """Handle update available."""
        self.status_label.setText("Update available!")

        reply = QMessageBox.question(
            self,
            "Update Available",
            f"A new version is available: {info.get('version', 'Unknown')}\n\n"
            f"Release notes:\n{info.get('notes', 'No notes available')[:500]}\n\n"
            "Would you like to download it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            import webbrowser
            webbrowser.open(info.get('url', 'https://github.com/ProcessLogicLabs/OCRInvoiceMill/releases'))

    @pyqtSlot()
    def _on_no_update(self):
        """Handle no update available."""
        self.status_label.setText("Ready")
        QMessageBox.information(
            self,
            "No Updates",
            f"You are running the latest version (v{VERSION})."
        )

    @pyqtSlot(str)
    def _on_update_error(self, error: str):
        """Handle update check error."""
        self.status_label.setText("Ready")
        QMessageBox.warning(
            self,
            "Update Check Failed",
            f"Could not check for updates:\n{error}"
        )

    @pyqtSlot()
    def _show_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "About OCRMill",
            f"<h2>OCRMill v{VERSION}</h2>"
            "<p>Invoice Processing & Parts Database Management</p>"
            "<p>&copy; 2024 Process Logic Labs, LLC</p>"
            "<p><a href='https://github.com/ProcessLogicLabs/OCRInvoiceMill'>"
            "GitHub Repository</a></p>"
        )

    # ----- Helper Methods -----

    def _update_db_status(self):
        """Update the database status in the status bar."""
        try:
            stats = self.db.get_statistics()
            part_count = stats.get('total_parts', 0)
            self.db_status.setText(f"Parts: {part_count}")
        except Exception:
            self.db_status.setText("Parts: --")

    def _log(self, message: str):
        """Log a message to the activity log."""
        self.invoice_tab.append_log(message)

    # ----- Event Handlers -----

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event."""
        # Check if processing is running
        if self.is_processing:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Processing is running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # Stop processing
            self._stop_processing()

        # Save window state
        self._save_window_state()

        # Close database
        try:
            self.db.close()
        except Exception:
            pass

        event.accept()
