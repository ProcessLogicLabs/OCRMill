"""
Settings Dialog for OCRMill - TariffMill Style with Sidebar Navigation.
"""

import os
import sys
import shutil
import logging
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

        # Get database from parent window
        self.db = getattr(parent, 'db', None)

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
        """Create the sidebar with TariffMill-style category navigation."""
        sidebar = QWidget()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(160)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)

        # Category list - TariffMill style with no scrollbar appearance
        self.category_list = QListWidget()
        self.category_list.setObjectName("settingsCategoryList")
        self.category_list.setSpacing(8)
        self.category_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
            self.category_list.addItem(item)

        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self._on_category_changed)

        layout.addWidget(self.category_list)

        return sidebar

    def _apply_styling(self):
        """Apply theme-aware TariffMill-style styling."""
        current_theme = self.theme_manager.current_theme
        is_dark = self.theme_manager.is_dark_theme()

        # Ocean theme has special styling
        if current_theme == "Ocean":
            self.setStyleSheet("""
                QDialog {
                    background-color: #1a3050;
                }

                #settingsSidebar {
                    background-color: #152a42;
                    border-right: 1px solid #3a6a9a;
                }

                #settingsCategoryList {
                    background-color: transparent;
                    border: none;
                    outline: none;
                }

                #settingsCategoryList::item {
                    padding: 10px 16px;
                    border-radius: 4px;
                    margin: 0px 8px;
                    color: #c0e0f0;
                }

                #settingsCategoryList::item:selected {
                    background-color: #3a6a9a;
                    color: white;
                }

                #settingsCategoryList::item:hover:!selected {
                    background-color: rgba(58, 106, 154, 0.3);
                }

                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3a6a9a;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: #1e3a55;
                    color: #c0e0f0;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #00a8cc;
                }

                QLabel {
                    color: #c0e0f0;
                }

                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    background-color: #3a7ca5;
                    color: white;
                    border: none;
                }

                QPushButton:hover {
                    background-color: #4a8cb5;
                }

                QPushButton:pressed {
                    background-color: #2a5a80;
                }

                QLineEdit {
                    padding: 6px;
                    border: 1px solid #3a6a9a;
                    border-radius: 3px;
                    background-color: #152a42;
                    color: #e0f0ff;
                }

                QLineEdit:focus {
                    border-color: #00a8cc;
                }

                QLineEdit:read-only {
                    background-color: #1a3050;
                }

                QComboBox {
                    padding: 5px 8px;
                    border: 1px solid #3a6a9a;
                    border-radius: 3px;
                    background-color: #152a42;
                    color: #e0f0ff;
                }

                QComboBox:focus {
                    border-color: #00a8cc;
                }

                QComboBox QAbstractItemView {
                    background-color: #1a3550;
                    color: #e0f0ff;
                    selection-background-color: #00a8cc;
                }

                QSpinBox {
                    padding: 5px;
                    border: 1px solid #3a6a9a;
                    border-radius: 3px;
                    background-color: #152a42;
                    color: #e0f0ff;
                }

                QCheckBox {
                    color: #c0e0f0;
                }

                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }

                QCheckBox::indicator:unchecked {
                    border: 1px solid #3a6a9a;
                    background-color: #1a3050;
                }

                QCheckBox::indicator:checked {
                    background-color: #00a8cc;
                    border: 1px solid #00a8cc;
                }

                QScrollArea {
                    border: none;
                    background-color: transparent;
                }

                .infoLabel {
                    color: #8ac4e0;
                    font-size: 9pt;
                }

                .warningLabel {
                    color: #ff6b6b;
                    font-size: 9pt;
                }
            """)
        elif is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }

                #settingsSidebar {
                    background-color: #252526;
                    border-right: 1px solid #3c3c3c;
                }

                #settingsCategoryList {
                    background-color: transparent;
                    border: none;
                    outline: none;
                }

                #settingsCategoryList::item {
                    padding: 10px 16px;
                    border-radius: 4px;
                    margin: 0px 8px;
                    color: #cccccc;
                }

                #settingsCategoryList::item:selected {
                    background-color: #2980b9;
                    color: white;
                }

                #settingsCategoryList::item:hover:!selected {
                    background-color: rgba(52, 152, 219, 0.2);
                }

                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: #252526;
                    color: #cccccc;
                }

                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #4ec9b0;
                }

                QLabel {
                    color: #cccccc;
                }

                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    background-color: #0e639c;
                    color: white;
                    border: none;
                }

                QPushButton:hover {
                    background-color: #1177bb;
                }

                QPushButton:pressed {
                    background-color: #094771;
                }

                QPushButton#primaryButton {
                    background-color: #0e639c;
                    color: white;
                    border: none;
                }

                QPushButton#primaryButton:hover {
                    background-color: #1177bb;
                }

                QPushButton#successButton {
                    background-color: #388a34;
                    color: white;
                    border: none;
                }

                QPushButton#successButton:hover {
                    background-color: #4caf50;
                }

                QLineEdit {
                    padding: 6px;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }

                QLineEdit:focus {
                    border-color: #0078d4;
                }

                QLineEdit:read-only {
                    background-color: #2d2d2d;
                }

                QComboBox {
                    padding: 5px 8px;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }

                QComboBox:focus {
                    border-color: #0078d4;
                }

                QComboBox QAbstractItemView {
                    background-color: #3c3c3c;
                    color: #cccccc;
                    selection-background-color: #094771;
                }

                QSpinBox {
                    padding: 5px;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }

                QCheckBox {
                    color: #cccccc;
                }

                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }

                QCheckBox::indicator:unchecked {
                    border: 1px solid #3c3c3c;
                    background-color: #2d2d2d;
                }

                QCheckBox::indicator:checked {
                    background-color: #0078d4;
                    border: 1px solid #0078d4;
                }

                QScrollArea {
                    border: none;
                    background-color: transparent;
                }

                .infoLabel {
                    color: #aaaaaa;
                    font-size: 9pt;
                }

                .warningLabel {
                    color: #f14c4c;
                    font-size: 9pt;
                }
            """)
        else:
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
                    outline: none;
                }

                #settingsCategoryList::item {
                    padding: 10px 16px;
                    border-radius: 4px;
                    margin: 0px 8px;
                    color: #333;
                }

                #settingsCategoryList::item:selected {
                    background-color: #2980b9;
                    color: white;
                }

                #settingsCategoryList::item:hover:!selected {
                    background-color: rgba(52, 152, 219, 0.2);
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
                    background-color: #5f9ea0;
                    color: white;
                    border: none;
                }

                QPushButton:hover {
                    background-color: #4f8e90;
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
                    background-color: white;
                }

                QLineEdit:focus {
                    border-color: #5f9ea0;
                }

                QComboBox {
                    padding: 5px 8px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    background-color: white;
                    color: #333;
                }

                QComboBox:focus {
                    border-color: #5f9ea0;
                }

                QComboBox QAbstractItemView {
                    background-color: white;
                    color: #333;
                    selection-background-color: #5f9ea0;
                    selection-color: white;
                    border: 1px solid #ccc;
                }

                QSpinBox {
                    padding: 5px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                }

                QCheckBox {
                    color: #333;
                    spacing: 8px;
                }

                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                }

                QCheckBox::indicator:unchecked {
                    border: 1px solid #ccc;
                    background-color: white;
                }

                QCheckBox::indicator:checked {
                    background-color: #5f9ea0;
                    border: 1px solid #5f9ea0;
                }

                QCheckBox::indicator:unchecked:hover {
                    border-color: #5f9ea0;
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
        """Create the AI Provider settings page - TariffMill style."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("AI Provider Settings")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Info label
        info_label = QLabel(
            "Configure AI providers for the Template Generator. API keys are stored securely in the\n"
            "local database."
        )
        info_label.setStyleSheet("color: #666; font-size: 9pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Create scroll area for provider sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)

        # Store provider widgets for reference
        self.ai_provider_widgets = {}

        # Define providers with their models
        providers = [
            {
                "name": "Anthropic (Claude)",
                "key": "anthropic",
                "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                "placeholder": "sk-ant-api03-..."
            },
            {
                "name": "OpenAI (GPT-4)",
                "key": "openai",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4"],
                "placeholder": "sk-..."
            },
            {
                "name": "Google Gemini",
                "key": "gemini",
                "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"],
                "placeholder": "AI..."
            },
            {
                "name": "Groq (Llama, Mixtral)",
                "key": "groq",
                "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
                "placeholder": "gsk_..."
            },
            {
                "name": "Ollama (Local)",
                "key": "ollama",
                "models": ["llama3.2", "codellama", "mistral", "qwen2.5-coder"],
                "placeholder": None,  # No API key needed
                "local": True
            }
        ]

        for provider in providers:
            group = QGroupBox(provider["name"])
            group_layout = QFormLayout(group)
            group_layout.setSpacing(8)

            widgets = {}

            if provider.get("local"):
                # Ollama - no API key, just status check
                info_label = QLabel(
                    "Ollama runs locally - no API key required.\n"
                    "Install from ollama.ai, then run: ollama serve"
                )
                info_label.setStyleSheet("color: #666; font-size: 9pt;")
                group_layout.addRow("", info_label)

                # Model selection
                model_combo = QComboBox()
                model_combo.addItems(provider["models"])
                model_combo.setEditable(True)  # Allow custom model names
                widgets["model"] = model_combo
                group_layout.addRow("Default Model:", model_combo)

                # Status row
                status_layout = QHBoxLayout()
                status_indicator = QLabel("")
                status_indicator.setStyleSheet("font-size: 9pt;")
                widgets["status"] = status_indicator
                status_layout.addWidget(status_indicator)
                status_layout.addStretch()

                test_btn = QPushButton("Test Connection")
                test_btn.clicked.connect(lambda checked, k=provider["key"]: self._validate_api_key(k))
                status_layout.addWidget(test_btn)
                group_layout.addRow("Status:", status_layout)
            else:
                # Cloud provider - needs API key
                key_edit = QLineEdit()
                key_edit.setEchoMode(QLineEdit.EchoMode.Password)
                key_edit.setPlaceholderText(provider["placeholder"])
                widgets["key"] = key_edit
                group_layout.addRow("API Key:", key_edit)

                # Model selection
                model_combo = QComboBox()
                model_combo.addItems(provider["models"])
                widgets["model"] = model_combo
                group_layout.addRow("Default Model:", model_combo)

                # Status row with test button
                status_layout = QHBoxLayout()
                status_indicator = QLabel("")
                status_indicator.setStyleSheet("font-size: 9pt;")
                widgets["status"] = status_indicator
                status_layout.addWidget(status_indicator)
                status_layout.addStretch()

                test_btn = QPushButton("Test Connection")
                test_btn.clicked.connect(lambda checked, k=provider["key"]: self._validate_api_key(k))
                status_layout.addWidget(test_btn)
                group_layout.addRow("Status:", status_layout)

            self.ai_provider_widgets[provider["key"]] = widgets
            scroll_layout.addWidget(group)

        # Default Settings group
        default_group = QGroupBox("Default Settings")
        default_layout = QFormLayout(default_group)

        self.default_provider_combo = QComboBox()
        self.default_provider_combo.addItems(["Anthropic", "OpenAI", "Google Gemini", "Groq", "Ollama"])
        default_layout.addRow("Default Provider:", self.default_provider_combo)

        scroll_layout.addWidget(default_group)

        # Save button
        save_btn = QPushButton("Save AI Settings")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_ai_settings)
        scroll_layout.addWidget(save_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Load saved settings
        self._load_ai_settings()

        return page

    def _load_ai_settings(self):
        """Load saved AI settings from database."""
        if not self.db:
            # No database available, set default status
            for provider_key in self.ai_provider_widgets:
                widgets = self.ai_provider_widgets[provider_key]
                if "status" in widgets:
                    widgets["status"].setText("○ Database not available")
                    widgets["status"].setStyleSheet("color: #888; font-size: 9pt;")
            return

        try:
            # Load API keys
            key_map = {
                "anthropic": "anthropic_api_key",
                "openai": "openai_api_key",
                "gemini": "gemini_api_key",
                "groq": "groq_api_key"
            }

            for provider_key, config_key in key_map.items():
                if provider_key in self.ai_provider_widgets:
                    widgets = self.ai_provider_widgets[provider_key]
                    if "key" in widgets:
                        api_key = self.db.get_app_config(config_key) or ''
                        widgets["key"].setText(api_key)

                        # Update status indicator
                        if api_key:
                            widgets["status"].setText("● Key configured - test to verify")
                            widgets["status"].setStyleSheet("color: #f0b429; font-size: 9pt;")
                        else:
                            widgets["status"].setText("○ No API key configured")
                            widgets["status"].setStyleSheet("color: #888; font-size: 9pt;")

            # Load default models
            model_map = {
                "anthropic": "anthropic_default_model",
                "openai": "openai_default_model",
                "gemini": "gemini_default_model",
                "groq": "groq_default_model",
                "ollama": "ollama_default_model"
            }

            for provider_key, config_key in model_map.items():
                if provider_key in self.ai_provider_widgets:
                    widgets = self.ai_provider_widgets[provider_key]
                    if "model" in widgets:
                        saved_model = self.db.get_app_config(config_key)
                        if saved_model:
                            idx = widgets["model"].findText(saved_model)
                            if idx >= 0:
                                widgets["model"].setCurrentIndex(idx)
                            elif widgets["model"].isEditable():
                                widgets["model"].setCurrentText(saved_model)

            # Load default provider
            default_provider = self.db.get_app_config('default_ai_provider') or 'Anthropic'
            idx = self.default_provider_combo.findText(default_provider)
            if idx >= 0:
                self.default_provider_combo.setCurrentIndex(idx)

            # Check Ollama status
            if "ollama" in self.ai_provider_widgets:
                widgets = self.ai_provider_widgets["ollama"]
                widgets["status"].setText("○ Click Test Connection to check")
                widgets["status"].setStyleSheet("color: #888; font-size: 9pt;")

        except Exception as e:
            logging.warning(f"Failed to load AI settings: {e}")

    def _save_ai_settings(self):
        """Save AI settings to database."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Database not available. Cannot save settings.")
            return

        try:
            # Save API keys
            key_map = {
                "anthropic": "anthropic_api_key",
                "openai": "openai_api_key",
                "gemini": "gemini_api_key",
                "groq": "groq_api_key"
            }

            for provider_key, config_key in key_map.items():
                if provider_key in self.ai_provider_widgets:
                    widgets = self.ai_provider_widgets[provider_key]
                    if "key" in widgets:
                        self.db.set_app_config(config_key, widgets["key"].text().strip())

            # Save default models
            model_map = {
                "anthropic": "anthropic_default_model",
                "openai": "openai_default_model",
                "gemini": "gemini_default_model",
                "groq": "groq_default_model",
                "ollama": "ollama_default_model"
            }

            for provider_key, config_key in model_map.items():
                if provider_key in self.ai_provider_widgets:
                    widgets = self.ai_provider_widgets[provider_key]
                    if "model" in widgets:
                        self.db.set_app_config(config_key, widgets["model"].currentText())

            # Save default provider
            self.db.set_app_config('default_ai_provider', self.default_provider_combo.currentText())

            QMessageBox.information(self, "Saved", "AI settings saved successfully.")

        except Exception as e:
            logging.warning(f"Failed to save AI settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings:\n{e}")

    def _validate_api_key(self, provider_key: str):
        """Validate an API key by making a test request."""
        import json
        import urllib.request
        import urllib.error

        if provider_key not in self.ai_provider_widgets:
            return

        widgets = self.ai_provider_widgets[provider_key]
        status_label = widgets.get("status")
        if not status_label:
            return

        status_label.setText("● Validating...")
        status_label.setStyleSheet("color: #888; font-size: 9pt;")
        QApplication.processEvents()

        try:
            if provider_key == "ollama":
                # Check if Ollama is running
                req = urllib.request.Request("http://localhost:11434/api/tags")
                with urllib.request.urlopen(req, timeout=5) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    models = result.get('models', [])
                    if models:
                        status_label.setText(f"● Connected ({len(models)} models available)")
                    else:
                        status_label.setText("● Connected (no models installed)")
                    status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")
                return

            # Get API key
            api_key = widgets.get("key", QLineEdit()).text().strip()
            if not api_key:
                status_label.setText("○ No API key configured")
                status_label.setStyleSheet("color: #f14c4c; font-size: 9pt;")
                return

            # Get selected model
            model = widgets.get("model", QComboBox()).currentText()

            # Test API calls for each provider
            if provider_key == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                }
                data = {
                    "model": model or "claude-3-5-haiku-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}]
                }

            elif provider_key == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                data = {
                    "model": model or "gpt-4o-mini",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}]
                }

            elif provider_key == "gemini":
                test_model = model or "gemini-1.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{test_model}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                }

            elif provider_key == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                data = {
                    "model": model or "llama-3.1-8b-instant",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}]
                }
            else:
                return

            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                status_label.setText("● API key valid")
                status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                status_label.setText("● Invalid API key")
            elif e.code == 403:
                status_label.setText("● Access denied")
            elif e.code == 429:
                status_label.setText("● Valid (rate limited)")
                status_label.setStyleSheet("color: #f0b429; font-size: 9pt;")
                return
            else:
                status_label.setText(f"● Error {e.code}")
            status_label.setStyleSheet("color: #f14c4c; font-size: 9pt;")

        except urllib.error.URLError as e:
            if provider_key == "ollama":
                status_label.setText("● Ollama not running")
            else:
                status_label.setText("● Network error")
            status_label.setStyleSheet("color: #f14c4c; font-size: 9pt;")

        except Exception as e:
            status_label.setText("● Connection error")
            status_label.setStyleSheet("color: #f14c4c; font-size: 9pt;")
            logging.warning(f"API validation error for {provider_key}: {e}")

    def _load_api_keys(self):
        """Load saved API keys from database."""
        try:
            anthropic_key = self.db.get_app_config('anthropic_api_key') or ''
            openai_key = self.db.get_app_config('openai_api_key') or ''
            gemini_key = self.db.get_app_config('gemini_api_key') or ''
            groq_key = self.db.get_app_config('groq_api_key') or ''

            self.anthropic_key_edit.setText(anthropic_key)
            self.openai_key_edit.setText(openai_key)
            self.gemini_key_edit.setText(gemini_key)
            self.groq_key_edit.setText(groq_key)

            # Update status indicators for configured keys
            if anthropic_key:
                self.anthropic_status_label.setText("✓ Configured")
                self.anthropic_status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")
            if openai_key:
                self.openai_status_label.setText("✓ Configured")
                self.openai_status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")
            if gemini_key:
                self.gemini_status_label.setText("✓ Configured")
                self.gemini_status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")
            if groq_key:
                self.groq_status_label.setText("✓ Configured")
                self.groq_status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")

        except Exception as e:
            logging.warning(f"Failed to load API keys: {e}")

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

        # Windows Domain Authentication group
        domain_group = QGroupBox("Windows Domain Authentication")
        domain_layout = QVBoxLayout(domain_group)

        domain_info = QLabel(
            "Configure which Windows domains are allowed for automatic login.\n"
            "Users on these domains can authenticate automatically using their Windows credentials."
        )
        domain_info.setWordWrap(True)
        domain_info.setStyleSheet("color: #666; font-size: 9pt;")
        domain_layout.addWidget(domain_info)

        # Allowed domains input
        domains_form = QFormLayout()
        self.allowed_domains_edit = QLineEdit()
        self.allowed_domains_edit.setPlaceholderText("e.g., MYCOMPANY, CORP, DOMAIN1")
        self.allowed_domains_edit.textChanged.connect(self._mark_changed)
        domains_form.addRow("Allowed Domains:", self.allowed_domains_edit)

        domains_help = QLabel("Enter domain names separated by commas. Case-insensitive.")
        domains_help.setStyleSheet("color: #999; font-size: 9pt;")
        domains_form.addRow("", domains_help)

        domain_layout.addLayout(domains_form)
        layout.addWidget(domain_group)

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
        self.allowed_domains_edit.setText(', '.join(self.config.allowed_domains))
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
        # Parse allowed domains from comma-separated string
        domains_text = self.allowed_domains_edit.text().strip()
        if domains_text:
            domains = [d.strip().upper() for d in domains_text.split(',') if d.strip()]
        else:
            domains = []
        self.config.allowed_domains = domains
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
        # Re-apply dialog styling to match new theme
        self._apply_styling()
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
