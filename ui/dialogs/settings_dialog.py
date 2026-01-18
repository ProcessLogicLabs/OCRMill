"""
Settings Dialog for OCRMill - TariffMill Style with Sidebar Navigation.
"""

import os
import sys
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QGroupBox, QFormLayout, QCheckBox, QPushButton, QLabel,
    QSpinBox, QLineEdit, QFileDialog, QScrollArea, QFrame,
    QComboBox, QApplication, QListWidget, QListWidgetItem,
    QStackedWidget, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config_manager import ConfigManager
from core.theme_manager import get_theme_manager, AVAILABLE_THEMES


class SettingsDialog(QDialog):
    """
    Settings dialog with TariffMill-style sidebar navigation.

    Layout:
    - Left sidebar: Category list (General, PDF Processing, AI Provider, Templates, etc.)
    - Right panel: Settings for selected category
    """

    templates_synced = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._changes_made = False
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("Settings")
        self.setMinimumSize(750, 550)
        self.setModal(True)

        self._setup_ui()
        self._load_settings()
        self._apply_styling()

    def _setup_ui(self):
        """Set up the dialog UI with sidebar navigation."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left sidebar with category list
        sidebar = self._create_sidebar()
        layout.addWidget(sidebar)

        # Right panel with stacked pages
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(10)

        # Stacked widget for different settings pages
        self.stacked_widget = QStackedWidget()

        # Create pages
        self.pages = {
            'General': self._create_general_page(),
            'PDF Processing': self._create_processing_page(),
            'AI Provider': self._create_ai_provider_page(),
            'Templates': self._create_templates_page(),
            'Database': self._create_database_page(),
            'Updates': self._create_updates_page(),
            'Authentication': self._create_auth_page(),
        }

        for name, page in self.pages.items():
            self.stacked_widget.addWidget(page)

        right_layout.addWidget(self.stacked_widget, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(close_btn)

        right_layout.addLayout(btn_layout)

        layout.addWidget(right_panel, 1)

    def _create_sidebar(self) -> QWidget:
        """Create the sidebar with category list."""
        sidebar = QWidget()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(180)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Category list
        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")

        categories = [
            'General',
            'PDF Processing',
            'AI Provider',
            'Templates',
            'Database',
            'Updates',
            'Authentication',
        ]

        for cat in categories:
            item = QListWidgetItem(cat)
            item.setSizeHint(item.sizeHint().expandedTo(
                self.category_list.sizeHint()
            ))
            self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self._on_category_changed)

        layout.addWidget(self.category_list)

        return sidebar

    def _apply_styling(self):
        """Apply TariffMill-style styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }

            #settingsSidebar {
                background-color: #e8f4f5;
                border-right: 1px solid #ccc;
            }

            #settingsCategoryList {
                background-color: transparent;
                border: none;
                font-size: 11pt;
                outline: none;
            }

            #settingsCategoryList::item {
                padding: 12px 16px;
                border-left: 3px solid transparent;
            }

            #settingsCategoryList::item:selected {
                background-color: #5f9ea0;
                color: white;
                border-left: 3px solid #2e7d7f;
            }

            #settingsCategoryList::item:hover:!selected {
                background-color: #d0e8ea;
            }

            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: white;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #5f9ea0;
            }

            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }

            QPushButton#primaryButton {
                background-color: #5f9ea0;
                color: white;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background-color: #4f8e90;
            }

            QPushButton#successButton {
                background-color: #28a745;
                color: white;
                border: none;
            }

            QPushButton#successButton:hover {
                background-color: #218838;
            }

            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }

            QLineEdit:focus {
                border-color: #5f9ea0;
            }

            .pageTitle {
                font-size: 16pt;
                font-weight: bold;
                color: #333;
                margin-bottom: 10px;
            }

            .infoLabel {
                color: #666;
                font-size: 9pt;
            }

            .warningLabel {
                color: #dc3545;
                font-size: 9pt;
            }
        """)

    def _on_category_changed(self, index: int):
        """Handle category selection change."""
        self.stacked_widget.setCurrentIndex(index)

    # ========== PAGE CREATION METHODS ==========

    def _create_general_page(self) -> QWidget:
        """Create the General settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # Page title
        title = QLabel("General Settings")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Folders group
        folders_group = QGroupBox("Folders")
        folders_layout = QFormLayout(folders_group)
        folders_layout.setSpacing(10)

        # Input folder
        input_layout = QHBoxLayout()
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setReadOnly(True)
        input_layout.addWidget(self.input_folder_edit)
        input_browse = QPushButton("Browse...")
        input_browse.clicked.connect(self._browse_input)
        input_layout.addWidget(input_browse)
        folders_layout.addRow("Input Folder:", input_layout)

        # Output folder
        output_layout = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        output_layout.addWidget(self.output_folder_edit)
        output_browse = QPushButton("Browse...")
        output_browse.clicked.connect(self._browse_output)
        output_layout.addWidget(output_browse)
        folders_layout.addRow("Output Folder:", output_layout)

        layout.addWidget(folders_group)

        # Monitoring group
        monitor_group = QGroupBox("Folder Monitoring")
        monitor_layout = QFormLayout(monitor_group)
        monitor_layout.setSpacing(10)

        self.poll_spinbox = QSpinBox()
        self.poll_spinbox.setRange(5, 300)
        self.poll_spinbox.setSuffix(" seconds")
        self.poll_spinbox.valueChanged.connect(self._mark_changed)
        monitor_layout.addRow("Poll Interval:", self.poll_spinbox)

        self.auto_start_check = QCheckBox("Start monitoring on application launch")
        self.auto_start_check.stateChanged.connect(self._mark_changed)
        monitor_layout.addRow("", self.auto_start_check)

        layout.addWidget(monitor_group)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(AVAILABLE_THEMES)
        self.theme_combo.currentTextChanged.connect(self._preview_theme)
        appearance_layout.addRow("Theme:", self.theme_combo)

        layout.addWidget(appearance_group)

        layout.addStretch()
        return page

    def _create_processing_page(self) -> QWidget:
        """Create the PDF Processing settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("PDF Processing")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Multi-invoice handling
        invoice_group = QGroupBox("Multi-Invoice Handling")
        invoice_layout = QVBoxLayout(invoice_group)

        self.consolidate_check = QCheckBox("Consolidate multiple invoices into single CSV")
        self.consolidate_check.stateChanged.connect(self._mark_changed)
        invoice_layout.addWidget(self.consolidate_check)

        info_label = QLabel(
            "When enabled, PDFs with multiple invoices will be saved to a single CSV file.\n"
            "When disabled, each invoice will be saved to a separate CSV file."
        )
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        invoice_layout.addWidget(info_label)

        layout.addWidget(invoice_group)

        # CBP Export group
        cbp_group = QGroupBox("CBP Export Folders")
        cbp_layout = QFormLayout(cbp_group)

        # CBP Input folder
        cbp_input_layout = QHBoxLayout()
        self.cbp_input_edit = QLineEdit()
        self.cbp_input_edit.setReadOnly(True)
        cbp_input_layout.addWidget(self.cbp_input_edit)
        cbp_input_browse = QPushButton("Browse...")
        cbp_input_browse.clicked.connect(self._browse_cbp_input)
        cbp_input_layout.addWidget(cbp_input_browse)
        cbp_layout.addRow("CBP Input:", cbp_input_layout)

        # CBP Output folder
        cbp_output_layout = QHBoxLayout()
        self.cbp_output_edit = QLineEdit()
        self.cbp_output_edit.setReadOnly(True)
        cbp_output_layout.addWidget(self.cbp_output_edit)
        cbp_output_browse = QPushButton("Browse...")
        cbp_output_browse.clicked.connect(self._browse_cbp_output)
        cbp_output_layout.addWidget(cbp_output_browse)
        cbp_layout.addRow("CBP Output:", cbp_output_layout)

        self.auto_cbp_check = QCheckBox("Auto-run CBP export after invoice processing")
        self.auto_cbp_check.stateChanged.connect(self._mark_changed)
        cbp_layout.addRow("", self.auto_cbp_check)

        layout.addWidget(cbp_group)

        layout.addStretch()
        return page

    def _create_ai_provider_page(self) -> QWidget:
        """Create the AI Provider settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("AI Provider")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # AI Provider group
        ai_group = QGroupBox("AI Template Generation")
        ai_layout = QFormLayout(ai_group)

        info_label = QLabel(
            "Configure the AI provider used for template generation.\n"
            "Currently supports OpenAI and Anthropic Claude."
        )
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        ai_layout.addRow("", info_label)

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["OpenAI", "Anthropic Claude", "Local (Ollama)"])
        ai_layout.addRow("Provider:", self.ai_provider_combo)

        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_edit.setPlaceholderText("Enter API key...")
        ai_layout.addRow("API Key:", self.ai_api_key_edit)

        layout.addWidget(ai_group)

        layout.addStretch()
        return page

    def _create_templates_page(self) -> QWidget:
        """Create the Templates settings page - TariffMill style."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("Template Settings")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Shared Templates (Network) group
        shared_group = QGroupBox("Shared Templates (Network)")
        shared_layout = QVBoxLayout(shared_group)

        shared_info = QLabel(
            "Configure a shared network folder to share invoice templates across users.\n"
            "Templates from the shared folder will appear with a network indicator."
        )
        shared_info.setStyleSheet("color: #333; font-size: 9pt;")
        shared_info.setWordWrap(True)
        shared_layout.addWidget(shared_info)

        # Shared folder path
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Shared Folder:")
        folder_layout.addWidget(folder_label)

        self.shared_folder_edit = QLineEdit()
        self.shared_folder_edit.setPlaceholderText("Y:\\Dev\\Tariffmill\\Templates")
        folder_layout.addWidget(self.shared_folder_edit, 1)

        shared_browse = QPushButton("Browse...")
        shared_browse.clicked.connect(self._browse_shared_templates)
        folder_layout.addWidget(shared_browse)

        shared_layout.addLayout(folder_layout)

        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_refresh_btn = QPushButton("Save && Refresh Templates")
        save_refresh_btn.setObjectName("primaryButton")
        save_refresh_btn.clicked.connect(self._save_and_refresh_templates)
        btn_layout.addWidget(save_refresh_btn)

        sync_btn = QPushButton("Sync Templates")
        sync_btn.setObjectName("successButton")
        sync_btn.clicked.connect(self._sync_templates)
        btn_layout.addWidget(sync_btn)

        shared_layout.addLayout(btn_layout)

        # Warning note
        note_label = QLabel(
            "Note: Shared templates are read-only. Right-click a shared template and select 'Copy to Local' to create an\n"
            "editable copy."
        )
        note_label.setStyleSheet("color: #dc3545; font-size: 9pt;")
        shared_layout.addWidget(note_label)

        layout.addWidget(shared_group)

        # Local Templates group
        local_group = QGroupBox("Local Templates")
        local_layout = QFormLayout(local_group)

        # Local templates location
        local_path = self.config.local_templates_folder
        self.local_location_label = QLabel(str(local_path))
        self.local_location_label.setStyleSheet("color: #666;")
        local_layout.addRow("Location:", self.local_location_label)

        # Count local templates
        self.local_count_label = QLabel("Templates: 0")
        self.local_count_label.setStyleSheet("color: #5f9ea0; font-weight: bold;")
        local_layout.addRow("", self.local_count_label)

        layout.addWidget(local_group)

        # Template enable/disable group
        templates_group = QGroupBox("Invoice Templates (Enable/Disable)")
        templates_layout = QVBoxLayout(templates_group)

        # Scroll area for template checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(150)

        self.templates_scroll_widget = QWidget()
        self.templates_scroll_layout = QVBoxLayout(self.templates_scroll_widget)
        self.templates_scroll_layout.setSpacing(4)

        from templates import TEMPLATE_REGISTRY
        self.template_checks = {}

        for name in TEMPLATE_REGISTRY.keys():
            check = QCheckBox(name.replace('_', ' ').title())
            check.stateChanged.connect(self._mark_changed)
            self.template_checks[name] = check
            self.templates_scroll_layout.addWidget(check)

        self.templates_scroll_layout.addStretch()
        scroll.setWidget(self.templates_scroll_widget)
        templates_layout.addWidget(scroll)

        layout.addWidget(templates_group)

        layout.addStretch()

        # Update template count
        self._update_template_counts()

        return page

    def _create_database_page(self) -> QWidget:
        """Create the Database settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("Database")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Database group
        db_group = QGroupBox("Parts Database")
        db_layout = QFormLayout(db_group)

        # Database path
        db_path_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        db_path_layout.addWidget(self.db_path_edit)
        db_browse = QPushButton("Browse...")
        db_browse.clicked.connect(self._browse_database)
        db_path_layout.addWidget(db_browse)
        db_layout.addRow("Database File:", db_path_layout)

        layout.addWidget(db_group)

        # Columns visibility group
        columns_group = QGroupBox("Parts Master Columns")
        columns_layout = QVBoxLayout(columns_group)

        columns_layout.addWidget(QLabel("Select columns to display in Parts Master:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(200)

        scroll_widget = QWidget()
        scroll_inner = QVBoxLayout(scroll_widget)

        self.column_checks = {}
        columns = [
            ("part_number", "Part Number"),
            ("description", "Description"),
            ("hts_code", "HTS Code"),
            ("country_origin", "Country of Origin"),
            ("mid", "Manufacturer ID (MID)"),
            ("client_code", "Client Code"),
            ("steel_pct", "Steel %"),
            ("aluminum_pct", "Aluminum %"),
            ("copper_pct", "Copper %"),
            ("wood_pct", "Wood %"),
            ("auto_pct", "Auto %"),
            ("non_steel_pct", "Non-Steel %"),
            ("qty_unit", "Quantity Unit"),
            ("sec301_exclusion_tariff", "Section 301 Exclusion"),
            ("fsc_certified", "FSC Certified"),
            ("fsc_certificate_code", "FSC Certificate Code"),
            ("last_updated", "Last Updated"),
        ]

        for col_name, col_label in columns:
            check = QCheckBox(col_label)
            check.stateChanged.connect(self._mark_changed)
            self.column_checks[col_name] = check
            scroll_inner.addWidget(check)

        scroll_inner.addStretch()
        scroll.setWidget(scroll_widget)
        columns_layout.addWidget(scroll)

        # Select all / none buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_columns)
        btn_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_no_columns)
        btn_layout.addWidget(select_none_btn)

        btn_layout.addStretch()
        columns_layout.addLayout(btn_layout)

        layout.addWidget(columns_group)

        layout.addStretch()
        return page

    def _create_updates_page(self) -> QWidget:
        """Create the Updates settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("Updates")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Updates group
        updates_group = QGroupBox("Application Updates")
        updates_layout = QVBoxLayout(updates_group)

        self.check_updates_check = QCheckBox("Check for updates on application startup")
        self.check_updates_check.stateChanged.connect(self._mark_changed)
        updates_layout.addWidget(self.check_updates_check)

        check_now_btn = QPushButton("Check for Updates Now")
        check_now_btn.clicked.connect(self._check_updates_now)
        updates_layout.addWidget(check_now_btn)

        layout.addWidget(updates_group)

        layout.addStretch()
        return page

    def _create_auth_page(self) -> QWidget:
        """Create the Authentication settings page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("Authentication")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Login group
        login_group = QGroupBox("Login Settings")
        login_layout = QVBoxLayout(login_group)

        self.require_login_check = QCheckBox("Require login at startup")
        self.require_login_check.stateChanged.connect(self._mark_changed)
        login_layout.addWidget(self.require_login_check)

        self.allow_skip_check = QCheckBox("Allow users to skip login")
        self.allow_skip_check.stateChanged.connect(self._mark_changed)
        login_layout.addWidget(self.allow_skip_check)

        self.auto_windows_check = QCheckBox("Auto-login with Windows credentials")
        self.auto_windows_check.stateChanged.connect(self._mark_changed)
        login_layout.addWidget(self.auto_windows_check)

        layout.addWidget(login_group)

        # Billing group
        billing_group = QGroupBox("Billing & Statistics")
        billing_layout = QVBoxLayout(billing_group)

        self.billing_enabled_check = QCheckBox("Enable billing tracking")
        self.billing_enabled_check.stateChanged.connect(self._mark_changed)
        billing_layout.addWidget(self.billing_enabled_check)

        self.billing_sync_check = QCheckBox("Enable remote billing sync")
        self.billing_sync_check.stateChanged.connect(self._mark_changed)
        billing_layout.addWidget(self.billing_sync_check)

        layout.addWidget(billing_group)

        layout.addStretch()
        return page

    # ========== SETTINGS LOAD/SAVE ==========

    def _load_settings(self):
        """Load current settings into UI."""
        # General
        self.input_folder_edit.setText(str(self.config.input_folder))
        self.output_folder_edit.setText(str(self.config.output_folder))
        self.poll_spinbox.setValue(self.config.poll_interval)
        self.auto_start_check.setChecked(self.config.auto_start)

        # Appearance - load saved theme
        self._original_theme = self.theme_manager.load_saved_theme()
        index = self.theme_combo.findText(self._original_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        # Processing
        self.consolidate_check.setChecked(self.config.consolidate_multi_invoice)
        self.cbp_input_edit.setText(str(self.config.cbp_input_folder))
        self.cbp_output_edit.setText(str(self.config.cbp_output_folder))
        self.auto_cbp_check.setChecked(self.config.auto_cbp_export)

        # Templates
        self.shared_folder_edit.setText(self.config.shared_templates_folder)
        for name, check in self.template_checks.items():
            check.setChecked(self.config.get_template_enabled(name))

        # Database
        self.db_path_edit.setText(str(self.config.database_path))
        for col_name, check in self.column_checks.items():
            check.setChecked(self.config.get_column_visible(col_name))

        # Updates
        self.check_updates_check.setChecked(self.config.check_updates_on_startup)

        # Auth
        self.require_login_check.setChecked(self.config.require_login)
        self.allow_skip_check.setChecked(self.config.allow_skip_login)
        self.auto_windows_check.setChecked(self.config.auto_windows_login)
        self.billing_enabled_check.setChecked(self.config.billing_enabled)
        self.billing_sync_check.setChecked(self.config.billing_sync_enabled)

        self._changes_made = False

    def _save_settings(self):
        """Save all settings."""
        # General
        self.config.input_folder = self.input_folder_edit.text()
        self.config.output_folder = self.output_folder_edit.text()
        self.config.poll_interval = self.poll_spinbox.value()
        self.config.auto_start = self.auto_start_check.isChecked()

        # Theme
        selected_theme = self.theme_combo.currentText()
        self.theme_manager.save_theme(selected_theme)

        # Processing
        self.config.consolidate_multi_invoice = self.consolidate_check.isChecked()
        self.config.cbp_input_folder = self.cbp_input_edit.text()
        self.config.cbp_output_folder = self.cbp_output_edit.text()
        self.config.auto_cbp_export = self.auto_cbp_check.isChecked()

        # Templates
        self.config.shared_templates_folder = self.shared_folder_edit.text()
        for name, check in self.template_checks.items():
            self.config.set_template_enabled(name, check.isChecked())

        # Database
        self.config.database_path = self.db_path_edit.text()
        for col_name, check in self.column_checks.items():
            self.config.set_column_visible(col_name, check.isChecked())

        # Updates
        self.config.check_updates_on_startup = self.check_updates_check.isChecked()

        # Auth
        self.config.require_login = self.require_login_check.isChecked()
        self.config.allow_skip_login = self.allow_skip_check.isChecked()
        self.config.auto_windows_login = self.auto_windows_check.isChecked()
        self.config.billing_enabled = self.billing_enabled_check.isChecked()
        self.config.billing_sync_enabled = self.billing_sync_check.isChecked()

        self._changes_made = True

    def _mark_changed(self):
        """Mark that changes have been made."""
        self._changes_made = True

    # ========== TEMPLATE FUNCTIONS ==========

    def _update_template_counts(self):
        """Update the template count labels."""
        from templates import TEMPLATE_REGISTRY, get_shared_templates_folder

        # Local templates count
        local_path = Path(__file__).parent.parent.parent / "templates"
        local_count = len([f for f in local_path.glob("*.py")
                          if f.name not in {'__init__.py', 'base_template.py', 'sample_template.py'}])
        self.local_count_label.setText(f"Templates: {local_count}")

    def _browse_shared_templates(self):
        """Browse for shared templates folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Shared Templates Folder"
        )
        if folder:
            self.shared_folder_edit.setText(folder)
            self._mark_changed()

    def _save_and_refresh_templates(self):
        """Save shared folder setting and refresh templates."""
        # Save the shared folder path
        self.config.shared_templates_folder = self.shared_folder_edit.text()

        # Update the templates module
        from templates import set_shared_templates_folder, refresh_templates
        set_shared_templates_folder(self.shared_folder_edit.text())
        refresh_templates()

        # Update template checkboxes
        from templates import TEMPLATE_REGISTRY

        # Remove checkboxes for templates that no longer exist
        for name, check in list(self.template_checks.items()):
            if name not in TEMPLATE_REGISTRY:
                check.setParent(None)
                check.deleteLater()
                del self.template_checks[name]

        # Remove the stretch at the end temporarily (it's the last item in the layout)
        stretch_item = self.templates_scroll_layout.takeAt(self.templates_scroll_layout.count() - 1)

        # Add checkboxes for new templates
        for name in TEMPLATE_REGISTRY.keys():
            if name not in self.template_checks:
                check = QCheckBox(name.replace('_', ' ').title())
                check.setChecked(self.config.get_template_enabled(name))
                check.stateChanged.connect(self._mark_changed)
                self.template_checks[name] = check
                self.templates_scroll_layout.addWidget(check)

        # Re-add the stretch at the end
        self.templates_scroll_layout.addStretch()

        self._update_template_counts()

        QMessageBox.information(
            self, "Templates Refreshed",
            f"Templates have been refreshed.\nFound {len(TEMPLATE_REGISTRY)} templates."
        )

        self.templates_synced.emit()

    def _sync_templates(self):
        """Bidirectional sync between local and shared templates."""
        shared_folder = self.shared_folder_edit.text()
        if not shared_folder:
            QMessageBox.warning(
                self, "No Shared Folder",
                "Please configure a shared templates folder first."
            )
            return

        from templates import sync_templates_to_shared, set_shared_templates_folder, refresh_templates

        # Make sure the shared folder is set
        set_shared_templates_folder(shared_folder)

        # Perform bidirectional sync
        results = sync_templates_to_shared()

        to_shared = results.get('to_shared', [])
        to_local = results.get('to_local', [])
        skipped = results.get('skipped', [])
        errors = results.get('errors', [])

        message = "Bidirectional Sync Complete!\n\n"
        message += f"Copied to shared: {len(to_shared)} templates\n"
        message += f"Copied to local: {len(to_local)} templates\n"
        message += f"Already in sync: {len(skipped)} templates\n"

        if to_shared:
            message += f"\nTo Shared: {', '.join(to_shared[:5])}"
            if len(to_shared) > 5:
                message += f" (+{len(to_shared)-5} more)"
            message += "\n"

        if to_local:
            message += f"\nTo Local: {', '.join(to_local[:5])}"
            if len(to_local) > 5:
                message += f" (+{len(to_local)-5} more)"
            message += "\n"

        if errors:
            message += f"\nErrors: {len(errors)}\n"
            for template, error in errors[:5]:  # Show first 5 errors
                message += f"  - {template}: {error}\n"

        QMessageBox.information(self, "Sync Results", message)

        # Refresh templates to pick up any new ones
        refresh_templates()
        self._save_and_refresh_templates()
        self.templates_synced.emit()

    # ========== BROWSE HANDLERS ==========

    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_folder_edit.setText(folder)
            self._mark_changed()

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_edit.setText(folder)
            self._mark_changed()

    def _browse_database(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Database", "", "SQLite Database (*.db)"
        )
        if path:
            self.db_path_edit.setText(path)
            self._mark_changed()

    def _browse_cbp_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CBP Input Folder")
        if folder:
            self.cbp_input_edit.setText(folder)
            self._mark_changed()

    def _browse_cbp_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CBP Output Folder")
        if folder:
            self.cbp_output_edit.setText(folder)
            self._mark_changed()

    def _select_all_columns(self):
        for check in self.column_checks.values():
            check.setChecked(True)

    def _select_no_columns(self):
        for check in self.column_checks.values():
            check.setChecked(False)

    def _preview_theme(self, theme_name: str):
        """Preview the selected theme immediately."""
        self.theme_manager.apply_theme(theme_name)
        self._mark_changed()

    def _check_updates_now(self):
        """Trigger update check from parent window."""
        parent = self.parent()
        if parent and hasattr(parent, '_check_for_updates'):
            parent._check_for_updates()

    # ========== DIALOG HANDLERS ==========

    def _on_close(self):
        """Handle close button - save if changes made."""
        if self._changes_made:
            self._save_settings()
        self.accept()

    def reject(self):
        """Handle dialog cancel - revert theme if changed."""
        if hasattr(self, '_original_theme'):
            current_theme = self.theme_combo.currentText()
            if current_theme != self._original_theme:
                # Revert to original theme
                self.theme_manager.apply_theme(self._original_theme)
        super().reject()
