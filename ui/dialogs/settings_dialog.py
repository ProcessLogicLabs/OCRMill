"""
Settings Dialog for OCRMill.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QFormLayout, QCheckBox, QPushButton, QLabel,
    QSpinBox, QLineEdit, QFileDialog, QScrollArea, QFrame,
    QComboBox, QApplication
)
from PyQt6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config_manager import ConfigManager
from core.theme_manager import get_theme_manager, AVAILABLE_THEMES


class SettingsDialog(QDialog):
    """Settings dialog for application preferences."""

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._changes_made = False
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 550)
        self.setModal(True)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()

        # General tab
        general_tab = self._create_general_tab()
        self.tabs.addTab(general_tab, "General")

        # Appearance tab
        appearance_tab = self._create_appearance_tab()
        self.tabs.addTab(appearance_tab, "Appearance")

        # Processing tab
        processing_tab = self._create_processing_tab()
        self.tabs.addTab(processing_tab, "Processing")

        # Columns tab
        columns_tab = self._create_columns_tab()
        self.tabs.addTab(columns_tab, "Columns")

        # CBP Export tab
        cbp_tab = self._create_cbp_tab()
        self.tabs.addTab(cbp_tab, "CBP Export")

        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Folders group
        folders_group = QGroupBox("Folders")
        folders_layout = QFormLayout(folders_group)

        # Input folder
        input_layout = QHBoxLayout()
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setReadOnly(True)
        input_layout.addWidget(self.input_folder_edit)
        input_browse = QPushButton("...")
        input_browse.setMaximumWidth(30)
        input_browse.clicked.connect(self._browse_input)
        input_layout.addWidget(input_browse)
        folders_layout.addRow("Input Folder:", input_layout)

        # Output folder
        output_layout = QHBoxLayout()
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        output_layout.addWidget(self.output_folder_edit)
        output_browse = QPushButton("...")
        output_browse.setMaximumWidth(30)
        output_browse.clicked.connect(self._browse_output)
        output_layout.addWidget(output_browse)
        folders_layout.addRow("Output Folder:", output_layout)

        # Database path
        db_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setReadOnly(True)
        db_layout.addWidget(self.db_path_edit)
        db_browse = QPushButton("...")
        db_browse.setMaximumWidth(30)
        db_browse.clicked.connect(self._browse_database)
        db_layout.addWidget(db_browse)
        folders_layout.addRow("Database:", db_layout)

        layout.addWidget(folders_group)

        # Monitoring group
        monitor_group = QGroupBox("Monitoring")
        monitor_layout = QFormLayout(monitor_group)

        self.poll_spinbox = QSpinBox()
        self.poll_spinbox.setRange(5, 300)
        self.poll_spinbox.setSuffix(" seconds")
        monitor_layout.addRow("Poll Interval:", self.poll_spinbox)

        self.auto_start_check = QCheckBox("Start monitoring on application launch")
        monitor_layout.addRow("", self.auto_start_check)

        layout.addWidget(monitor_group)

        layout.addStretch()

        return widget

    def _create_appearance_tab(self) -> QWidget:
        """Create the appearance/theme settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme selection group
        theme_group = QGroupBox("Application Theme")
        theme_layout = QFormLayout(theme_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(AVAILABLE_THEMES)
        self.theme_combo.currentTextChanged.connect(self._preview_theme)
        theme_layout.addRow("Theme:", self.theme_combo)

        # Theme descriptions
        desc_label = QLabel(
            "<b>Available Themes:</b><br>"
            "<b>Muted Cyan</b> - Default OCRMill theme (light)<br>"
            "<b>Fusion (Light)</b> - Standard light theme<br>"
            "<b>Fusion (Dark)</b> - Dark mode for low-light environments<br>"
            "<b>Ocean</b> - Deep blue theme for dark mode<br>"
            "<b>System Default</b> - Follow system settings"
        )
        desc_label.setStyleSheet("color: gray; font-size: 9pt; padding: 10px;")
        desc_label.setWordWrap(True)
        theme_layout.addRow("", desc_label)

        layout.addWidget(theme_group)

        # Preview note
        preview_note = QLabel(
            "Theme changes are applied immediately for preview.\n"
            "Click Save to keep the selected theme, or Cancel to revert."
        )
        preview_note.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        preview_note.setWordWrap(True)
        layout.addWidget(preview_note)

        layout.addStretch()

        return widget

    def _preview_theme(self, theme_name: str):
        """Preview the selected theme immediately."""
        self.theme_manager.apply_theme(theme_name)

    def _create_processing_tab(self) -> QWidget:
        """Create the processing settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Multi-invoice handling
        invoice_group = QGroupBox("Multi-Invoice Handling")
        invoice_layout = QVBoxLayout(invoice_group)

        self.consolidate_check = QCheckBox("Consolidate multiple invoices into single CSV")
        invoice_layout.addWidget(self.consolidate_check)

        info_label = QLabel(
            "When enabled, PDFs with multiple invoices will be saved to a single CSV file.\n"
            "When disabled, each invoice will be saved to a separate CSV file."
        )
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        invoice_layout.addWidget(info_label)

        layout.addWidget(invoice_group)

        # Templates group
        templates_group = QGroupBox("Invoice Templates")
        templates_layout = QVBoxLayout(templates_group)

        from templates import TEMPLATE_REGISTRY
        self.template_checks = {}

        for name in TEMPLATE_REGISTRY.keys():
            check = QCheckBox(name.replace('_', ' ').title())
            self.template_checks[name] = check
            templates_layout.addWidget(check)

        layout.addWidget(templates_group)

        layout.addStretch()

        return widget

    def _create_columns_tab(self) -> QWidget:
        """Create the columns visibility tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Select columns to display in Parts Master:"))

        # Scrollable area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

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
            self.column_checks[col_name] = check
            scroll_layout.addWidget(check)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Select all / none buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_columns)
        btn_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_no_columns)
        btn_layout.addWidget(select_none_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_cbp_tab(self) -> QWidget:
        """Create the CBP export settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # CBP Export folders
        folders_group = QGroupBox("CBP Export Folders")
        folders_layout = QFormLayout(folders_group)

        # CBP Input folder
        cbp_input_layout = QHBoxLayout()
        self.cbp_input_edit = QLineEdit()
        self.cbp_input_edit.setReadOnly(True)
        cbp_input_layout.addWidget(self.cbp_input_edit)
        cbp_input_browse = QPushButton("...")
        cbp_input_browse.setMaximumWidth(30)
        cbp_input_browse.clicked.connect(self._browse_cbp_input)
        cbp_input_layout.addWidget(cbp_input_browse)
        folders_layout.addRow("Input Folder:", cbp_input_layout)

        # CBP Output folder
        cbp_output_layout = QHBoxLayout()
        self.cbp_output_edit = QLineEdit()
        self.cbp_output_edit.setReadOnly(True)
        cbp_output_layout.addWidget(self.cbp_output_edit)
        cbp_output_browse = QPushButton("...")
        cbp_output_browse.setMaximumWidth(30)
        cbp_output_browse.clicked.connect(self._browse_cbp_output)
        cbp_output_layout.addWidget(cbp_output_browse)
        folders_layout.addRow("Output Folder:", cbp_output_layout)

        layout.addWidget(folders_group)

        # Auto export
        auto_group = QGroupBox("Automation")
        auto_layout = QVBoxLayout(auto_group)

        self.auto_cbp_check = QCheckBox("Auto-run CBP export after invoice processing")
        auto_layout.addWidget(self.auto_cbp_check)

        layout.addWidget(auto_group)

        layout.addStretch()

        return widget

    def _load_settings(self):
        """Load current settings into UI."""
        # General
        self.input_folder_edit.setText(str(self.config.input_folder))
        self.output_folder_edit.setText(str(self.config.output_folder))
        self.db_path_edit.setText(str(self.config.database_path))
        self.poll_spinbox.setValue(self.config.poll_interval)
        self.auto_start_check.setChecked(self.config.auto_start)

        # Appearance - load saved theme
        self._original_theme = self.theme_manager.load_saved_theme()
        index = self.theme_combo.findText(self._original_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        # Processing
        self.consolidate_check.setChecked(self.config.consolidate_multi_invoice)

        for name, check in self.template_checks.items():
            check.setChecked(self.config.get_template_enabled(name))

        # Columns
        for col_name, check in self.column_checks.items():
            check.setChecked(self.config.get_column_visible(col_name))

        # CBP Export
        self.cbp_input_edit.setText(str(self.config.cbp_input_folder))
        self.cbp_output_edit.setText(str(self.config.cbp_output_folder))
        self.auto_cbp_check.setChecked(self.config.auto_cbp_export)

    def _save_settings(self):
        """Save settings and close dialog."""
        # General
        self.config.input_folder = self.input_folder_edit.text()
        self.config.output_folder = self.output_folder_edit.text()
        self.config.database_path = self.db_path_edit.text()
        self.config.poll_interval = self.poll_spinbox.value()
        self.config.auto_start = self.auto_start_check.isChecked()

        # Processing
        self.config.consolidate_multi_invoice = self.consolidate_check.isChecked()

        for name, check in self.template_checks.items():
            self.config.set_template_enabled(name, check.isChecked())

        # Columns
        for col_name, check in self.column_checks.items():
            self.config.set_column_visible(col_name, check.isChecked())

        # CBP Export
        self.config.cbp_input_folder = self.cbp_input_edit.text()
        self.config.cbp_output_folder = self.cbp_output_edit.text()
        self.config.auto_cbp_export = self.auto_cbp_check.isChecked()

        self._changes_made = True
        self.accept()

    # ----- Browse handlers -----

    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if folder:
            self.input_folder_edit.setText(folder)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_edit.setText(folder)

    def _browse_database(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Database", "", "SQLite Database (*.db)"
        )
        if path:
            self.db_path_edit.setText(path)

    def _browse_cbp_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CBP Input Folder")
        if folder:
            self.cbp_input_edit.setText(folder)

    def _browse_cbp_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CBP Output Folder")
        if folder:
            self.cbp_output_edit.setText(folder)

    def _select_all_columns(self):
        for check in self.column_checks.values():
            check.setChecked(True)

    def _select_no_columns(self):
        for check in self.column_checks.values():
            check.setChecked(False)

    def reject(self):
        """Handle dialog cancel - revert theme if changed."""
        if hasattr(self, '_original_theme'):
            current_theme = self.theme_combo.currentText()
            if current_theme != self._original_theme:
                # Revert to original theme
                self.theme_manager.apply_theme(self._original_theme)
        super().reject()
