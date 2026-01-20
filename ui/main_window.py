"""
Main window for OCRMill application.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QFileDialog,
    QApplication, QLabel, QFrame, QDialog, QProgressBar,
    QPushButton, QPlainTextEdit, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QSpinBox, QGroupBox, QStyle, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QCloseEvent, QFont, QPixmap, QKeySequence, QShortcut, QColor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase
from updater import UpdateChecker

from ui.tabs.invoice_tab import InvoiceProcessingTab
from ui.tabs.parts_tab import PartsDatabaseTab
from ui.tabs.templates_tab import TemplatesTab
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.mid_management_dialog import MIDManagementDialog
from ui.dialogs.hts_reference_dialog import HTSReferenceDialog
from ui.dialogs.login_dialog import LoginDialog
from ui.dialogs.license_dialog import LicenseDialog, LicenseExpiredDialog
from ui.dialogs.billing_dialog import BillingDialog
from ui.dialogs.statistics_dialog import StatisticsDialog
from ui.dialogs.output_mapping_dialog import OutputMappingDialog
from ui.dialogs.configuration_dialog import ConfigurationDialog
from ui.dialogs.admin_dialog import AdminDialog
from core.workers import ProcessingWorker, UpdateCheckWorker, UpdateDownloadWorker
from licensing.license_manager import LicenseManager
from licensing.auth_manager import AuthenticationManager


# Application version
VERSION = "0.99.05"


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

    def __init__(self, config=None, db=None):
        super().__init__()

        # Initialize core components (use passed instances or create new)
        self.config = config if config else ConfigManager()
        self.db = db if db else PartsDatabase(db_path=self.config.database_path)

        # Licensing and auth managers
        self.license_manager = LicenseManager(self.db)
        self.auth_manager = AuthenticationManager(self.db)
        self.current_user = None

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
        self.setMinimumSize(900, 600)

        # Set window icon if available
        icon_path = Path(__file__).parent.parent / "Resources" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Set window title with license status
        self._update_window_title()

    def _create_menu_bar(self):
        """Create the menu bar with all menus (TariffMill style)."""
        menubar = self.menuBar()

        # Session menu
        session_menu = menubar.addMenu("&Session")

        self.start_action = QAction("&Start Monitoring", self)
        self.start_action.setShortcut("F5")
        self.start_action.triggered.connect(self._start_processing)
        session_menu.addAction(self.start_action)

        self.stop_action = QAction("S&top Monitoring", self)
        self.stop_action.setShortcut("F6")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._stop_processing)
        session_menu.addAction(self.stop_action)

        session_menu.addSeparator()

        process_now = QAction("Process &Now", self)
        process_now.setShortcut("F9")
        process_now.triggered.connect(self._process_now)
        session_menu.addAction(process_now)

        cbp_export_action = QAction("Run &CBP Export", self)
        cbp_export_action.triggered.connect(self._run_cbp_export)
        session_menu.addAction(cbp_export_action)

        session_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        session_menu.addAction(exit_action)

        # Settings menu
        settings_menu = menubar.addMenu("S&ettings")

        preferences_action = QAction("&Preferences...", self)
        preferences_action.triggered.connect(self._show_settings_dialog)
        settings_menu.addAction(preferences_action)

        # Master Data menu
        master_data_menu = menubar.addMenu("&Master Data")

        # Configuration dialog (TariffMill-style with tabs)
        config_action = QAction("&Configuration...", self)
        config_action.triggered.connect(self._show_configuration_dialog)
        master_data_menu.addAction(config_action)

        # References menu
        references_menu = menubar.addMenu("&References")

        hts_action = QAction("&HTS Reference...", self)
        hts_action.triggered.connect(self._show_hts_reference_dialog)
        references_menu.addAction(hts_action)

        # Help menu (includes licensing items)
        help_menu = menubar.addMenu("&Help")

        update_action = QAction("Check for &Updates...", self)
        update_action.triggered.connect(self._check_for_updates)
        help_menu.addAction(update_action)

        help_menu.addSeparator()

        # Activity Log
        activity_log_action = QAction("&Activity Log...", self)
        activity_log_action.triggered.connect(self._show_activity_log_dialog)
        help_menu.addAction(activity_log_action)

        help_menu.addSeparator()

        # Licensing section (moved from separate Licensing menu)
        license_info_action = QAction("License &Information...", self)
        license_info_action.triggered.connect(self._show_license_dialog)
        help_menu.addAction(license_info_action)

        self.login_action = QAction("&Login...", self)
        self.login_action.triggered.connect(self._show_login_dialog)
        help_menu.addAction(self.login_action)

        self.logout_action = QAction("Log&out", self)
        self.logout_action.triggered.connect(self._logout)
        self.logout_action.setEnabled(False)
        help_menu.addAction(self.logout_action)

        help_menu.addSeparator()

        billing_action = QAction("&Billing Records...", self)
        billing_action.triggered.connect(self._show_billing_dialog)
        help_menu.addAction(billing_action)

        statistics_action = QAction("&Statistics...", self)
        statistics_action.triggered.connect(self._show_statistics_dialog)
        help_menu.addAction(statistics_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Hidden admin shortcut (Ctrl+Shift+A) - matches TariffMill
        self._admin_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self._admin_shortcut.activated.connect(self._show_admin_dialog)

    def _create_central_widget(self):
        """Create the central widget with tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 5)
        layout.setSpacing(10)

        # Branding header (TariffMill style)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 8, 10, 12)

        # Logo icon - use icon_hires.svg (matching app icon)
        icon_path = Path(__file__).parent.parent / "Resources" / "icon_hires.svg"
        if icon_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(icon_path))
            logo_label.setPixmap(pixmap.scaledToHeight(44, Qt.TransformationMode.SmoothTransformation))
            header_layout.addWidget(logo_label)

        # App title - styled like TariffMill with dual-color text
        # Colors match icon_hires.svg: teal (#56E0D5/#28B5AA) and purple (#A78BFA/#7C3AED)
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(8, 0, 0, 0)
        title_layout.setSpacing(0)

        # "OCR" in muted purple/accent color (matching icon purpleGrad)
        ocr_label = QLabel("OCR")
        ocr_label.setStyleSheet("font-size: 34px; font-weight: bold; color: #6b5b95; font-family: 'Segoe UI', sans-serif;")
        title_layout.addWidget(ocr_label)

        # "Mill" in teal/primary color (matching icon tealGrad)
        mill_label = QLabel("Mill")
        mill_label.setStyleSheet("font-size: 34px; font-weight: bold; color: #28B5AA; font-family: 'Segoe UI', sans-serif;")
        title_layout.addWidget(mill_label)

        title_layout.addStretch()
        header_layout.addWidget(title_widget)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Main tab widget
        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs)

        # Invoice Processing tab (main processing interface)
        self.invoice_tab = InvoiceProcessingTab(self.config, self.db, self)
        self.main_tabs.addTab(self.invoice_tab, "Invoice Processing")

        # Templates tab (template management and AI assistant)
        self.templates_tab = TemplatesTab(self.config, self.db, self)
        self.templates_tab.templates_changed.connect(self._refresh_templates)
        self.main_tabs.addTab(self.templates_tab, "Templates")

        # Parts View tab (database view and management)
        self.parts_tab = PartsDatabaseTab(self.config, self.db, self)
        self.main_tabs.addTab(self.parts_tab, "Parts View")

    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Spacer
        self.status_bar.addWidget(QLabel(), 1)

        # User info
        self.user_status = QLabel("Not logged in")
        self.user_status.setStyleSheet("color: #666;")
        self.status_bar.addPermanentWidget(self.user_status)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #ccc;")
        self.status_bar.addPermanentWidget(sep)

        # Processing status
        self.processing_status = QLabel("Monitoring: Stopped")
        self.status_bar.addPermanentWidget(self.processing_status)

        # Database info
        self.db_status = QLabel()
        self._update_db_status()
        self.status_bar.addPermanentWidget(self.db_status)

        # Separator before version
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #ccc;")
        self.status_bar.addPermanentWidget(sep2)

        # Version label (right corner)
        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #999;")
        self.status_bar.addPermanentWidget(version_label)

    def _connect_signals(self):
        """Connect internal signals."""
        self.parts_data_changed.connect(self._update_db_status)
        self.parts_data_changed.connect(self.parts_tab.refresh_data)

        self.processing_started.connect(self._on_processing_started)
        self.processing_stopped.connect(self._on_processing_stopped)

        # Connect invoice tab signals
        # Note: Don't connect log_message to _log - InvoiceProcessingTab._log() already
        # appends to log_viewer directly. Connecting would cause duplicate log entries.
        self.invoice_tab.files_processed.connect(self._on_files_processed)
        self.invoice_tab.file_failed.connect(self._on_file_failed)

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
        self.processing_worker.file_failed.connect(self._on_file_failed)
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
    def _on_file_failed(self, filename: str):
        """Handle file processing failure - open Activity Log dialog."""
        self.status_label.setText(f"Failed: {filename}")
        # Open Activity Log dialog to show what went wrong
        self._show_activity_log_dialog()

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
    def _show_parts_import(self):
        """Show the Parts Import tab in the Configuration dialog."""
        dialog = ConfigurationDialog(self.config, self.db, self)
        dialog.mapping_changed.connect(self._on_mapping_changed)
        dialog.parts_imported.connect(self._on_parts_imported)
        # Switch to Parts Import tab (index 2)
        dialog.tab_widget.setCurrentIndex(2)
        dialog.exec()

    @pyqtSlot()
    def _show_mid_management_dialog(self):
        """Show the MID Management tab in the Configuration dialog."""
        dialog = ConfigurationDialog(self.config, self.db, self)
        dialog.mapping_changed.connect(self._on_mapping_changed)
        dialog.parts_imported.connect(self._on_parts_imported)
        # Switch to MID Management tab (index 3)
        dialog.tab_widget.setCurrentIndex(3)
        dialog.exec()

    @pyqtSlot()
    def _show_hts_reference_dialog(self):
        """Show the HTS reference dialog."""
        dialog = HTSReferenceDialog(self.db, self)
        if dialog.exec():
            self.parts_data_changed.emit()

    @pyqtSlot()
    def _show_ai_template_generator(self):
        """Show the AI template generator dialog."""
        from ai_template_generator import AITemplateGeneratorDialog
        dialog = AITemplateGeneratorDialog(self, db=self.db)
        dialog.template_created.connect(self._on_template_created)
        dialog.exec()

    @pyqtSlot(str, str)
    def _on_template_created(self, template_name: str, file_path: str):
        """Handle when a new template is created."""
        self._refresh_templates()
        self.status_label.setText(f"Template '{template_name}' created successfully")

    @pyqtSlot()
    def _refresh_templates(self):
        """Refresh the template registry."""
        from templates import refresh_templates
        refresh_templates()
        self.status_label.setText("Templates refreshed")

    @pyqtSlot()
    def _show_template_manager(self):
        """Show the template manager dialog (lists available templates)."""
        from templates import get_all_templates
        templates = get_all_templates()

        # Simple dialog showing available templates
        dialog = QDialog(self)
        dialog.setWindowTitle("Template Manager")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Available Templates:"))

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)

        template_info = []
        for name, template in templates.items():
            enabled = "Enabled" if template.enabled else "Disabled"
            template_info.append(f"{name}:")
            template_info.append(f"  Name: {template.name}")
            template_info.append(f"  Description: {template.description}")
            template_info.append(f"  Client: {template.client}")
            template_info.append(f"  Version: {template.version}")
            template_info.append(f"  Status: {enabled}")
            template_info.append("")

        if not template_info:
            template_info = ["No templates found."]

        text_edit.setPlainText("\n".join(template_info))
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()

    @pyqtSlot()
    def _show_license_dialog(self):
        """Show the license information dialog."""
        dialog = LicenseDialog(self.db, self)
        dialog.exec()
        self._update_window_title()

    @pyqtSlot()
    def _show_login_dialog(self):
        """Show the login dialog."""
        dialog = LoginDialog(self.db, self, allow_skip=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            user_info = dialog.get_authenticated_user()
            if user_info:
                self.current_user = user_info
                self._update_user_status()

    @pyqtSlot()
    def _logout(self):
        """Log out the current user."""
        self.auth_manager.logout()
        self.current_user = None
        self._update_user_status()
        self.status_label.setText("Logged out")

    @pyqtSlot()
    def _show_billing_dialog(self):
        """Show the billing records dialog."""
        is_admin = self.auth_manager.is_admin() if self.current_user else False
        dialog = BillingDialog(self.db, self, is_admin=is_admin)
        dialog.exec()

    @pyqtSlot()
    def _show_statistics_dialog(self):
        """Show the statistics dialog."""
        dialog = StatisticsDialog(self.db, self)
        dialog.exec()

    def _update_user_status(self):
        """Update the user status display in status bar and menus."""
        if self.current_user and self.current_user.get('is_authenticated'):
            name = self.current_user.get('name') or self.current_user.get('email', 'User')
            role = self.current_user.get('role', '')
            if role == 'admin':
                self.user_status.setText(f"{name} (Admin)")
                self.user_status.setStyleSheet("color: #5f9ea0; font-weight: bold;")
            else:
                self.user_status.setText(name)
                self.user_status.setStyleSheet("color: #333;")
            self.login_action.setEnabled(False)
            self.logout_action.setEnabled(True)
        else:
            self.user_status.setText("Not logged in")
            self.user_status.setStyleSheet("color: #666;")
            self.login_action.setEnabled(True)
            self.logout_action.setEnabled(False)

    def _update_window_title(self):
        """Update window title."""
        self.setWindowTitle(f"OCRMill v{VERSION}")

    @pyqtSlot()
    def _show_settings_dialog(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Reload config and update UI
            self.invoice_tab.reload_config()
            self.parts_tab.reload_columns()

    def _show_output_mapping_dialog(self):
        """Show the output column mapping dialog."""
        dialog = OutputMappingDialog(self.config, self)
        dialog.exec()

    def _show_configuration_dialog(self):
        """Show the unified configuration dialog (TariffMill-style with tabs)."""
        dialog = ConfigurationDialog(self.config, self.db, self)
        dialog.mapping_changed.connect(self._on_mapping_changed)
        dialog.parts_imported.connect(self._on_parts_imported)
        dialog.exec()

    def _on_mapping_changed(self):
        """Handle output mapping changes from configuration dialog."""
        self.status_label.setText("Output column mapping updated")

    def _on_parts_imported(self):
        """Handle parts import from configuration dialog."""
        self.parts_data_changed.emit()
        self.status_label.setText("Parts imported successfully")

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
        self._manual_update_check = True

        worker = UpdateCheckWorker(VERSION)
        worker.update_available.connect(self._on_update_available)
        worker.no_update.connect(self._on_no_update)
        worker.error.connect(self._on_update_error)
        worker.start()

        # Store reference to prevent garbage collection
        self._update_worker = worker

    def _check_for_updates_silent(self):
        """Check for updates silently on startup."""
        # Only check if enabled in config
        if not getattr(self.config, 'check_updates_on_startup', True):
            return

        self._manual_update_check = False
        worker = UpdateCheckWorker(VERSION)
        worker.update_available.connect(self._on_update_available)
        # Don't connect no_update or error for silent check
        worker.start()
        self._update_worker = worker

    @pyqtSlot(dict)
    def _on_update_available(self, info: dict):
        """Handle update available - show TariffMill-style dialog."""
        self.status_label.setText("Update available!")

        # Store update info for later use
        self._update_info = info

        # Create update available dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Update Available")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Version info
        current_ver = info.get('current_version', VERSION)
        latest_ver = info.get('latest_version', 'Unknown')
        version_label = QLabel(
            f"<h3>A new version of OCRMill is available!</h3>"
            f"<p>Current version: <b>v{current_ver}</b></p>"
            f"<p>Latest version: <b>v{latest_ver}</b></p>"
        )
        layout.addWidget(version_label)

        # Release notes
        notes_label = QLabel("Release Notes:")
        layout.addWidget(notes_label)

        notes_text = QPlainTextEdit()
        notes_text.setPlainText(info.get('release_notes', 'No release notes available.'))
        notes_text.setReadOnly(True)
        layout.addWidget(notes_text)

        # Buttons
        button_layout = QHBoxLayout()

        # Download & Install button (Windows only, if direct download available)
        if sys.platform == 'win32' and info.get('has_direct_download'):
            download_btn = QPushButton("Download && Install")
            download_btn.clicked.connect(lambda: self._start_update_download(dialog))
            button_layout.addWidget(download_btn)

        # View on GitHub button
        github_btn = QPushButton("View on GitHub")
        github_btn.clicked.connect(lambda: self._open_github_release(info))
        button_layout.addWidget(github_btn)

        button_layout.addStretch()

        # Remind Me Later button
        later_btn = QPushButton("Remind Me Later")
        later_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(later_btn)

        layout.addLayout(button_layout)

        dialog.exec()
        self.status_label.setText("Ready")

    def _start_update_download(self, parent_dialog: QDialog):
        """Start downloading the update with progress dialog."""
        parent_dialog.accept()  # Close the update available dialog

        # Create the UpdateChecker with current info
        from updater import UpdateChecker
        checker = UpdateChecker(VERSION)
        checker.check_for_updates()  # Re-check to populate download info

        if not checker.download_url or checker.download_url == checker.latest_release_url:
            QMessageBox.warning(
                self,
                "Download Unavailable",
                "Direct download is not available for this release.\n"
                "Please download manually from GitHub."
            )
            checker.open_releases_page()
            return

        # Create download progress dialog
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("Downloading Update")
        progress_dialog.setFixedSize(400, 120)
        progress_dialog.setModal(True)

        layout = QVBoxLayout(progress_dialog)

        status_label = QLabel("Downloading update...")
        layout.addWidget(status_label)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        layout.addWidget(progress_bar)

        cancel_btn = QPushButton("Cancel")
        layout.addWidget(cancel_btn)

        # Create download worker
        download_worker = UpdateDownloadWorker(checker)

        def on_progress(downloaded, total):
            if total > 0:
                pct = int(downloaded / total * 100)
                progress_bar.setValue(pct)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                status_label.setText(f"Downloaded {mb_downloaded:.1f} MB of {mb_total:.1f} MB")

        def on_finished(success, result):
            progress_dialog.accept()
            if success:
                self._prompt_install_update(Path(result), checker)
            else:
                QMessageBox.warning(
                    self,
                    "Download Failed",
                    f"Failed to download update:\n{result}"
                )

        def on_cancelled():
            progress_dialog.reject()

        download_worker.progress.connect(on_progress)
        download_worker.finished.connect(on_finished)
        download_worker.cancelled.connect(on_cancelled)
        cancel_btn.clicked.connect(download_worker.cancel)

        # Store reference and start
        self._download_worker = download_worker
        download_worker.start()

        progress_dialog.exec()

    def _prompt_install_update(self, installer_path: Path, checker):
        """Prompt user to install the downloaded update."""
        reply = QMessageBox.question(
            self,
            "Install Update",
            "Update downloaded successfully!\n\n"
            "Do you want to install the update now?\n"
            "The application will close and the installer will start.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if checker.install_update(installer_path):
                # Give installer time to start, then quit
                QTimer.singleShot(500, QApplication.quit)
            else:
                QMessageBox.warning(
                    self,
                    "Installation Failed",
                    f"Failed to start installer:\n{checker.last_error}"
                )

    def _open_github_release(self, info: dict):
        """Open the GitHub release page."""
        import webbrowser
        url = info.get('release_url') or 'https://github.com/ProcessLogicLabs/OCRMill/releases'
        webbrowser.open(url)

    @pyqtSlot()
    def _on_no_update(self):
        """Handle no update available."""
        self.status_label.setText("Ready")
        # Only show message for manual checks
        if getattr(self, '_manual_update_check', False):
            QMessageBox.information(
                self,
                "No Updates",
                f"You are running the latest version (v{VERSION})."
            )

    @pyqtSlot(str)
    def _on_update_error(self, error: str):
        """Handle update check error."""
        self.status_label.setText("Ready")
        # Only show message for manual checks
        if getattr(self, '_manual_update_check', False):
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
            "<p>&copy; 2024-2025 Process Logic Labs, LLC</p>"
            "<p><a href='https://github.com/ProcessLogicLabs/OCRMill'>"
            "GitHub Repository</a></p>"
        )

    @pyqtSlot()
    def _show_activity_log_dialog(self):
        """Show the activity log in a dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Activity Log")
        dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(dialog)

        # Get the current log text from invoice tab
        log_text = self.invoice_tab.get_log_text()

        # Create log viewer
        log_edit = QPlainTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setPlainText(log_text)
        log_edit.setFont(QFont("Consolas", 9))

        # Scroll to bottom
        cursor = log_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        log_edit.setTextCursor(cursor)

        layout.addWidget(log_edit)

        # Buttons
        button_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(lambda: (self.invoice_tab.clear_log(), log_edit.clear()))
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

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

    # ----- Admin Functions (Ctrl+Shift+A) -----

    def _is_billing_admin(self) -> bool:
        """Check if the current user has admin role (can access billing/admin settings)."""
        try:
            # Primary check: Use authentication manager
            if hasattr(self, 'auth_manager') and self.auth_manager:
                return self.auth_manager.is_admin()

            # Fallback: check if user is logged in with admin role
            if self.current_user and self.current_user.get('role') == 'admin':
                return True
        except Exception as e:
            print(f"Error checking billing admin status: {e}")
        return False

    def _show_admin_dialog(self):
        """Show the hidden Administration dialog (Ctrl+Shift+A).

        This dialog contains sensitive billing, user management, and audit functions
        that should only be accessible to administrators.
        """
        # Verify admin access
        if not self._is_billing_admin():
            QMessageBox.warning(
                self, "Access Denied",
                "You do not have administrator privileges.\n\n"
                "Please contact your system administrator."
            )
            return

        # Use the dedicated AdminDialog with full user management capabilities
        dialog = AdminDialog(self, self.config, self.db)
        dialog.exec()

    # ----- Event Handlers -----

    def showEvent(self, event):
        """Handle window show event - trigger initial layout refresh."""
        super().showEvent(event)
        # Delayed refresh to ensure all widgets are properly rendered
        QTimer.singleShot(100, self._on_first_show)

    def _on_first_show(self):
        """Perform initialization after window is shown."""
        # Update status bar
        self._update_db_status()
        # Force invoice tab to refresh its layout
        if hasattr(self, 'invoice_tab'):
            self.invoice_tab.updateGeometry()
            self.invoice_tab.repaint()

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
