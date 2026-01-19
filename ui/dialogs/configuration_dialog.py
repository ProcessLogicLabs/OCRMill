"""
Configuration Dialog for OCRMill - TariffMill Style

A unified tabbed dialog combining:
- Invoice Mapping Profiles (column mapping for imported invoices)
- Output Mapping (column mapping for exported CSV - TariffMill style)
- Parts Import (import parts from CSV/Excel - TariffMill style)
- MID Management (manufacturer ID list management)
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget,
    QGroupBox, QFormLayout, QCheckBox, QPushButton, QLabel,
    QLineEdit, QScrollArea, QFrame, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QFileDialog,
    QProgressDialog, QApplication, QSizePolicy, QColorDialog,
    QGridLayout, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag, QColor, QPalette
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.theme_manager import get_theme_manager

# Output mapping profiles path
OUTPUT_PROFILES_FILE = Path(__file__).parent.parent.parent / "Resources" / "output_profiles.json"


class ConfigurationDialog(QDialog):
    """
    Unified Configuration dialog with tabs for:
    - Invoice Mapping Profiles
    - Output Mapping
    - Parts Import
    - MID Management
    """

    mapping_changed = pyqtSignal()
    parts_imported = pyqtSignal()

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("Configuration")
        self.setMinimumSize(1100, 700)
        self.setModal(True)

        # Initialize data
        self.output_profiles = {}
        self.current_output_profile = None
        self.parts_file_path = None
        self.parts_columns = []
        self.parts_mapping = {}

        self._setup_ui()
        self._apply_styling()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog with tabbed interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(0)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tabs = self.tab_widget  # Alias for backward compatibility

        # Tab 1: Output Mapping (TariffMill style)
        self.output_mapping_tab = self._create_output_mapping_tab()
        self.tabs.addTab(self.output_mapping_tab, "Output Mapping")

        # Tab 2: Parts Import (TariffMill style)
        self.parts_import_tab = self._create_parts_import_tab()
        self.tabs.addTab(self.parts_import_tab, "Parts Import")

        # Tab 3: MID Management
        self.mid_tab = self._create_mid_management_tab()
        self.tabs.addTab(self.mid_tab, "MID Management")

        layout.addWidget(self.tabs)

        # Bottom close button
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 10, 20, 0)
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    # ========== INVOICE MAPPING PROFILES TAB ==========

    # ========== OUTPUT MAPPING TAB (TariffMill Style) ==========

    def _create_output_mapping_tab(self) -> QWidget:
        """Create the Output Mapping tab - TariffMill style."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Title
        title = QLabel("Output Column Mapping")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Profile row
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Saved Profiles:"))

        self.output_profile_combo = QComboBox()
        self.output_profile_combo.setMinimumWidth(200)
        self.output_profile_combo.addItem("-- Select Profile --")
        self.output_profile_combo.currentTextChanged.connect(self._on_output_profile_selected)
        profile_layout.addWidget(self.output_profile_combo)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_output_mapping)
        profile_layout.addWidget(reset_btn)

        save_new_btn = QPushButton("Save As New...")
        save_new_btn.clicked.connect(self._save_output_profile_as_new)
        profile_layout.addWidget(save_new_btn)

        update_btn = QPushButton("Update Profile")
        update_btn.clicked.connect(self._update_output_profile)
        profile_layout.addWidget(update_btn)

        delete_btn = QPushButton("Delete Profile")
        delete_btn.clicked.connect(self._delete_output_profile)
        profile_layout.addWidget(delete_btn)

        profile_layout.addStretch()
        layout.addLayout(profile_layout)

        # Three group boxes row
        options_row = QHBoxLayout()
        options_row.setSpacing(15)

        # Export Text Colors
        colors_group = QGroupBox("Export Text Colors")
        colors_layout = QGridLayout(colors_group)
        colors_layout.setSpacing(8)

        self.color_buttons = {}
        color_fields = [
            ("default", "Default:", 0, 0),
            ("steel", "Steel:", 0, 2),
            ("aluminum", "Aluminum:", 0, 4),
            ("copper", "Copper:", 1, 0),
            ("wood", "Wood:", 1, 2),
            ("auto", "Auto:", 1, 4),
            ("non232", "Non-232:", 2, 0),
        ]

        for field, label, row, col in color_fields:
            colors_layout.addWidget(QLabel(label), row, col)
            btn = ColorButton(field)
            btn.setFixedSize(30, 25)
            btn.clicked.connect(lambda checked, f=field: self._pick_color(f))
            self.color_buttons[field] = btn
            colors_layout.addWidget(btn, row, col + 1)

        options_row.addWidget(colors_group)

        # Column Visibility
        visibility_group = QGroupBox("Column Visibility")
        visibility_layout = QGridLayout(visibility_group)
        visibility_layout.setSpacing(8)

        self.visibility_checks = {}
        visibility_fields = [
            ("steel_pct", "Steel%", 0, 0),
            ("aluminum_pct", "Aluminum%", 0, 1),
            ("copper_pct", "Copper%", 1, 0),
            ("wood_pct", "Wood%", 1, 1),
            ("auto_pct", "Auto%", 2, 0),
            ("non_steel_pct", "NonSteel%", 2, 1),
        ]

        for field, label, row, col in visibility_fields:
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.visibility_checks[field] = cb
            visibility_layout.addWidget(cb, row, col)

        options_row.addWidget(visibility_group)

        # Export Options
        export_options_group = QGroupBox("Export Options")
        export_options_layout = QVBoxLayout(export_options_group)

        self.split_by_invoice_check = QCheckBox("Split by Invoice Number")
        self.split_by_invoice_check.setChecked(True)
        export_options_layout.addWidget(self.split_by_invoice_check)

        split_info = QLabel("Creates separate files per invoice.\nRequires Invoice Number mapping.")
        split_info.setStyleSheet("color: #666; font-size: 9pt;")
        export_options_layout.addWidget(split_info)

        export_options_layout.addStretch()
        options_row.addWidget(export_options_group)

        layout.addLayout(options_row)

        # Column Name Mapping (drag to reorder)
        mapping_group = QGroupBox("Column Name Mapping (drag to reorder)")
        mapping_layout = QVBoxLayout(mapping_group)

        # Scroll area for columns
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        self.output_columns_layout = QVBoxLayout(scroll_widget)
        self.output_columns_layout.setSpacing(4)

        # Create column rows
        self.output_column_rows = []
        self._create_output_column_rows()

        scroll.setWidget(scroll_widget)
        mapping_layout.addWidget(scroll)

        layout.addWidget(mapping_group, 1)

        return widget

    def _create_output_column_rows(self):
        """Create output column mapping rows."""
        # Clear existing
        for row in self.output_column_rows:
            row.setParent(None)
            row.deleteLater()
        self.output_column_rows = []

        # Default columns
        columns = [
            ("product_no", "Product No", "Product No"),
            ("value_usd", "ValueUSD", "ValueUSD"),
            ("hts_code", "HTSCode", "HTSCode"),
            ("mid", "MID", "MID"),
            ("qty1", "Qty1", "Qty1"),
            ("qty2", "Qty2", "Qty2"),
            ("dec_type_cd", "DecTypeCd", "DecTypeCd"),
            ("country_of_melt", "CountryofMelt", "CountryofMelt"),
            ("country_of_cast", "CountryOfCast", "CountryOfCast"),
            ("prim_country_of_smelt", "PrimCountryOfSmelt", "PrimCountryOfSmelt"),
            ("declaration_flag", "DeclarationFlag", "DeclarationFlag"),
            ("steel_ratio", "SteelRatio", "SteelRatio"),
            ("aluminum_ratio", "AluminumRatio", "AluminumRatio"),
            ("copper_ratio", "CopperRatio", "CopperRatio"),
            ("wood_ratio", "WoodRatio", "WoodRatio"),
        ]

        for internal, display, default_name in columns:
            row = OutputColumnRow(internal, display, default_name)
            self.output_columns_layout.addWidget(row)
            self.output_column_rows.append(row)

        self.output_columns_layout.addStretch()

    # ========== PARTS IMPORT TAB (TariffMill Style) ==========

    def _create_parts_import_tab(self) -> QWidget:
        """Create the Parts Import tab - TariffMill style."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Title
        title = QLabel("Parts Import from CSV/Excel")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Drag & drop columns to map fields")
        subtitle.setStyleSheet("color: #666;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Button toolbar
        toolbar_layout = QHBoxLayout()

        load_btn = QPushButton("Load CSV/Excel File")
        load_btn.clicked.connect(self._load_parts_file)
        toolbar_layout.addWidget(load_btn)

        reset_btn = QPushButton("Reset Mapping")
        reset_btn.clicked.connect(self._reset_parts_mapping)
        toolbar_layout.addWidget(reset_btn)

        update_sec301_btn = QPushButton("Update Sec301 Exclusion")
        update_sec301_btn.clicked.connect(self._update_sec301)
        toolbar_layout.addWidget(update_sec301_btn)

        import_sec301_btn = QPushButton("Import Sec301 CSV")
        import_sec301_btn.clicked.connect(self._import_sec301_csv)
        toolbar_layout.addWidget(import_sec301_btn)

        toolbar_layout.addStretch()

        import_btn = QPushButton("Import Now")
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._import_parts)
        toolbar_layout.addWidget(import_btn)

        layout.addLayout(toolbar_layout)

        # Main mapping area - 2 columns
        mapping_widget = QWidget()
        mapping_layout = QHBoxLayout(mapping_widget)
        mapping_layout.setSpacing(15)

        # Left: CSV/Excel Columns - Drag
        left_group = QGroupBox("CSV/Excel Columns - Drag")
        left_layout = QVBoxLayout(left_group)
        left_group.setMinimumWidth(200)
        left_group.setMaximumWidth(250)

        self.parts_csv_list = QListWidget()
        self.parts_csv_list.setDragEnabled(True)
        self.parts_csv_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        left_layout.addWidget(self.parts_csv_list)

        mapping_layout.addWidget(left_group)

        # Right: Available Fields - Drop Here
        right_group = QGroupBox("Available Fields - Drop Here")
        right_layout = QVBoxLayout(right_group)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_widget = QWidget()
        self.parts_fields_layout = QFormLayout(right_widget)
        self.parts_fields_layout.setSpacing(8)
        self.parts_fields_layout.setHorizontalSpacing(15)

        # Parts fields - TariffMill style
        self.parts_targets = {}
        parts_fields = [
            ("part_number", "Part Number:", True),
            ("hts_code", "HTS Code:", True),
            ("mid", "MID:", False),
            ("steel_pct", "Steel %:", False),
            ("aluminum_pct", "Aluminum %:", False),
            ("copper_pct", "Copper %:", False),
            ("wood_pct", "Wood %:", False),
            ("auto_pct", "Auto %:", False),
            ("qty_unit", "Qty Unit:", False),
            ("country_of_melt", "Country of Melt:", False),
            ("country_of_cast", "Country of Cast:", False),
            ("country_of_smelt", "Country of Smelt:", False),
            ("sec301_exclusion_tariff", "Sec301 Exclusion Tariff:", False),
            ("client_code", "Client Code:", False),
            ("description", "Description:", False),
            ("country_origin", "Country of Origin:", False),
        ]

        for field_key, label, required in parts_fields:
            target = DropTargetLabel(field_key, f"Drop {label.replace(':', '')} here")
            self.parts_targets[field_key] = target

            if required:
                row_label = QLabel(f"<b>{label}</b> *")
            else:
                row_label = QLabel(label)

            self.parts_fields_layout.addRow(row_label, target)

        right_scroll.setWidget(right_widget)
        right_layout.addWidget(right_scroll)

        mapping_layout.addWidget(right_group, 1)
        layout.addWidget(mapping_widget, 1)

        # Status
        self.parts_status_label = QLabel("Load a CSV or Excel file to begin")
        self.parts_status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.parts_status_label)

        return widget

    # ========== MID MANAGEMENT TAB ==========

    def _create_mid_management_tab(self) -> QWidget:
        """Create the MID Management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Manufacturer ID (MID) Management")
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)

        # Import section
        import_group = QGroupBox("Import MID List")
        import_layout = QHBoxLayout(import_group)

        self.mid_import_label = QLabel("No file selected")
        self.mid_import_label.setStyleSheet("color: #666;")
        import_layout.addWidget(self.mid_import_label, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_mid_file)
        import_layout.addWidget(browse_btn)

        import_btn = QPushButton("Import")
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._import_mid_file)
        import_layout.addWidget(import_btn)

        layout.addWidget(import_group)

        # Info
        info = QLabel(
            "Expected columns: <b>Manufacturer Name</b>, <b>MID</b>, "
            "<b>Customer ID</b>, <b>Related Parties</b> (Y/N)"
        )
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        # Filter row
        filter_group = QGroupBox("Current MID List")
        filter_main_layout = QVBoxLayout(filter_group)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Customer ID:"))
        self.mid_customer_filter = QLineEdit()
        self.mid_customer_filter.setPlaceholderText("Filter...")
        self.mid_customer_filter.setMaximumWidth(150)
        self.mid_customer_filter.returnPressed.connect(self._filter_mid_table)
        filter_layout.addWidget(self.mid_customer_filter)

        filter_layout.addWidget(QLabel("MID:"))
        self.mid_mid_filter = QLineEdit()
        self.mid_mid_filter.setPlaceholderText("Search...")
        self.mid_mid_filter.setMaximumWidth(180)
        self.mid_mid_filter.returnPressed.connect(self._filter_mid_table)
        filter_layout.addWidget(self.mid_mid_filter)

        filter_layout.addWidget(QLabel("Manufacturer:"))
        self.mid_manufacturer_filter = QLineEdit()
        self.mid_manufacturer_filter.setPlaceholderText("Search...")
        self.mid_manufacturer_filter.returnPressed.connect(self._filter_mid_table)
        filter_layout.addWidget(self.mid_manufacturer_filter)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._filter_mid_table)
        filter_layout.addWidget(search_btn)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self._clear_mid_filters)
        filter_layout.addWidget(clear_btn)

        filter_main_layout.addLayout(filter_layout)

        # MID Table
        self.mid_table = QTableWidget()
        self.mid_table.setColumnCount(4)
        self.mid_table.setHorizontalHeaderLabels([
            "Manufacturer Name", "MID", "Customer ID", "Related Parties"
        ])
        self.mid_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mid_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.mid_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.mid_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.mid_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mid_table.setAlternatingRowColors(True)
        filter_main_layout.addWidget(self.mid_table)

        layout.addWidget(filter_group, 1)

        # Action buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add MID")
        add_btn.clicked.connect(self._add_mid_row)
        btn_layout.addWidget(add_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_mid_selected)
        btn_layout.addWidget(delete_btn)

        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self._clear_all_mids)
        btn_layout.addWidget(clear_all_btn)

        btn_layout.addStretch()

        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self._export_mids)
        btn_layout.addWidget(export_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_mid_changes)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        return widget

    # ========== STYLING ==========

    def _apply_styling(self):
        """Apply theme-aware styling."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }

                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #2d2d2d;
                }

                QTabBar::tab {
                    background-color: #252526;
                    color: #cccccc;
                    padding: 10px 20px;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                    margin-right: 2px;
                }

                QTabBar::tab:selected {
                    background-color: #094771;
                    color: white;
                }

                QTabBar::tab:hover:!selected {
                    background-color: #2a2d2e;
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
                    background-color: #0e639c;
                    color: white;
                    border: none;
                }

                QPushButton:hover {
                    background-color: #1177bb;
                }

                QPushButton#primaryButton {
                    background-color: #0e639c;
                }

                QLineEdit, QComboBox, QSpinBox {
                    padding: 6px;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }

                QListWidget, QTableWidget {
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    alternate-background-color: #2d2d2d;
                }

                QListWidget::item:selected, QTableWidget::item:selected {
                    background-color: #094771;
                }

                QHeaderView::section {
                    background-color: #2d2d2d;
                    color: #cccccc;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #3c3c3c;
                    border-bottom: 1px solid #3c3c3c;
                }

                QCheckBox {
                    color: #cccccc;
                }

                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                }

                QTabWidget::pane {
                    border: 1px solid #d0d0d0;
                    background-color: white;
                }

                QTabBar::tab {
                    background-color: #f0f0f0;
                    color: #333333;
                    padding: 10px 20px;
                    border: 1px solid #d0d0d0;
                    border-bottom: none;
                    margin-right: 2px;
                }

                QTabBar::tab:selected {
                    background-color: #5f9ea0;
                    color: white;
                }

                QTabBar::tab:hover:!selected {
                    background-color: #e0e8e8;
                }

                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #d0d0d0;
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
                    background-color: #5f9ea0;
                    color: white;
                    border: none;
                }

                QPushButton:hover {
                    background-color: #4f8e90;
                }

                QLineEdit, QComboBox, QSpinBox {
                    padding: 6px;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    background-color: white;
                }

                QListWidget, QTableWidget {
                    background-color: white;
                    border: 1px solid #d0d0d0;
                    alternate-background-color: #f8f9fa;
                }

                QListWidget::item:selected, QTableWidget::item:selected {
                    background-color: #5f9ea0;
                    color: white;
                }

                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #333;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #d0d0d0;
                    border-bottom: 1px solid #d0d0d0;
                }

                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
            """)

    # ========== DATA LOADING ==========

    def _load_data(self):
        """Load all data for tabs."""
        self._load_mid_data()
        self._load_output_profiles()
        self._set_default_colors()

    def _load_mid_data(self):
        """Load MID data from database."""
        try:
            mids = self.db.get_all_manufacturers()
            self.mid_table.setRowCount(len(mids))

            for row, mid in enumerate(mids):
                self.mid_table.setItem(row, 0, QTableWidgetItem(mid.get('company_name', '')))
                self.mid_table.setItem(row, 1, QTableWidgetItem(mid.get('mid', '')))
                self.mid_table.setItem(row, 2, QTableWidgetItem(mid.get('customer_id', '')))
                self.mid_table.setItem(row, 3, QTableWidgetItem(mid.get('related_parties', '')))
        except Exception as e:
            print(f"Error loading MID data: {e}")

    def _load_output_profiles(self):
        """Load output mapping profiles."""
        try:
            if OUTPUT_PROFILES_FILE.exists():
                self.output_profiles = json.loads(OUTPUT_PROFILES_FILE.read_text())
                for name in self.output_profiles.keys():
                    self.output_profile_combo.addItem(name)
                    self.linked_export_combo.addItem(name)
        except Exception as e:
            print(f"Error loading output profiles: {e}")

    def _set_default_colors(self):
        """Set default colors for export text."""
        default_colors = {
            "default": "#000000",
            "steel": "#4a4a4a",
            "aluminum": "#0066cc",
            "copper": "#cc6600",
            "wood": "#996633",
            "auto": "#009966",
            "non232": "#cc0000",
        }
        for field, color in default_colors.items():
            if field in self.color_buttons:
                self.color_buttons[field].setColor(color)

    # ========== INVOICE MAPPING HANDLERS ==========

    def _load_invoice_file(self):
        """Load an invoice file for mapping."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice File", "",
            "Excel/CSV Files (*.xlsx *.xls *.csv)"
        )
        if file_path:
            try:
                import pandas as pd
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path, nrows=0)
                else:
                    df = pd.read_excel(file_path, nrows=0)

                self.csv_columns_list.clear()
                for col in df.columns:
                    item = QListWidgetItem(str(col))
                    self.csv_columns_list.addItem(item)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    def _reset_invoice_mapping(self):
        """Reset invoice mapping to defaults."""
        for target in self.required_targets.values():
            target.clear()
        for target in self.optional_targets.values():
            target.clear()

    def _save_invoice_mapping(self):
        """Save current invoice mapping as a profile."""
        QMessageBox.information(self, "Save", "Invoice mapping save not yet implemented")

    def _delete_invoice_profile(self):
        """Delete the selected invoice profile."""
        pass

    def _save_profile_link(self):
        """Save the link between invoice and export profiles."""
        pass

    def _clear_profile_link(self):
        """Clear the profile link."""
        self.linked_export_combo.setCurrentIndex(0)

    # ========== OUTPUT MAPPING HANDLERS ==========

    def _on_output_profile_selected(self, profile_name: str):
        """Handle output profile selection."""
        if profile_name == "-- Select Profile --" or profile_name not in self.output_profiles:
            return

        profile = self.output_profiles[profile_name]
        self.current_output_profile = profile_name

        # Load colors
        colors = profile.get("colors", {})
        for field, color in colors.items():
            if field in self.color_buttons:
                self.color_buttons[field].setColor(color)

        # Load visibility
        visibility = profile.get("visibility", {})
        for field, visible in visibility.items():
            if field in self.visibility_checks:
                self.visibility_checks[field].setChecked(visible)

        # Load export options
        self.split_by_invoice_check.setChecked(profile.get("split_by_invoice", True))

    def _reset_output_mapping(self):
        """Reset output mapping to defaults."""
        self._set_default_colors()
        for cb in self.visibility_checks.values():
            cb.setChecked(True)
        self.split_by_invoice_check.setChecked(True)
        self._create_output_column_rows()

    def _save_output_profile_as_new(self):
        """Save current output mapping as a new profile."""
        name, ok = QInputDialog.getText(self, "Save Profile", "Enter profile name:")
        if not ok or not name:
            return

        self._save_current_output_profile(name)
        if name not in [self.output_profile_combo.itemText(i) for i in range(self.output_profile_combo.count())]:
            self.output_profile_combo.addItem(name)
            self.linked_export_combo.addItem(name)

        QMessageBox.information(self, "Saved", f"Profile '{name}' saved successfully")

    def _update_output_profile(self):
        """Update the current output profile."""
        if not self.current_output_profile:
            QMessageBox.warning(self, "No Profile", "Please select a profile first")
            return

        self._save_current_output_profile(self.current_output_profile)
        QMessageBox.information(self, "Updated", f"Profile '{self.current_output_profile}' updated")

    def _delete_output_profile(self):
        """Delete the current output profile."""
        name = self.output_profile_combo.currentText()
        if name == "-- Select Profile --":
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if name in self.output_profiles:
            del self.output_profiles[name]
            self._save_output_profiles_to_file()

            # Remove from combo boxes
            idx = self.output_profile_combo.findText(name)
            if idx >= 0:
                self.output_profile_combo.removeItem(idx)
            idx = self.linked_export_combo.findText(name)
            if idx >= 0:
                self.linked_export_combo.removeItem(idx)

    def _save_current_output_profile(self, name: str):
        """Save current output settings to a profile."""
        profile = {
            "colors": {field: btn.color for field, btn in self.color_buttons.items()},
            "visibility": {field: cb.isChecked() for field, cb in self.visibility_checks.items()},
            "split_by_invoice": self.split_by_invoice_check.isChecked(),
            "columns": [row.get_config() for row in self.output_column_rows],
        }
        self.output_profiles[name] = profile
        self._save_output_profiles_to_file()

    def _save_output_profiles_to_file(self):
        """Save output profiles to file."""
        try:
            OUTPUT_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PROFILES_FILE.write_text(json.dumps(self.output_profiles, indent=2))
        except Exception as e:
            print(f"Error saving output profiles: {e}")

    def _pick_color(self, field: str):
        """Pick a color for export text."""
        current = QColor(self.color_buttons[field].color)
        color = QColorDialog.getColor(current, self, f"Select {field} color")
        if color.isValid():
            self.color_buttons[field].setColor(color.name())

    # ========== PARTS IMPORT HANDLERS ==========

    def _load_parts_file(self):
        """Load a parts file for import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Parts File", "",
            "Excel/CSV Files (*.xlsx *.xls *.csv)"
        )
        if not file_path:
            return

        self.parts_file_path = file_path

        try:
            import pandas as pd
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, nrows=0)
            else:
                df = pd.read_excel(file_path, nrows=0)

            self.parts_columns = list(df.columns)
            self.parts_csv_list.clear()
            for col in self.parts_columns:
                item = QListWidgetItem(str(col))
                self.parts_csv_list.addItem(item)

            self.parts_status_label.setText(f"Loaded: {Path(file_path).name} ({len(self.parts_columns)} columns)")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    def _reset_parts_mapping(self):
        """Reset parts mapping."""
        for target in self.parts_targets.values():
            target.clear()
        self.parts_mapping = {}

    def _update_sec301(self):
        """Update Sec301 exclusion data."""
        QMessageBox.information(self, "Update", "Sec301 exclusion update not yet implemented")

    def _import_sec301_csv(self):
        """Import Sec301 exclusion CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sec301 CSV", "",
            "CSV Files (*.csv)"
        )
        if file_path:
            QMessageBox.information(self, "Import", f"Sec301 import from {file_path} not yet implemented")

    def _import_parts(self):
        """Import parts from the file."""
        if not self.parts_file_path:
            QMessageBox.warning(self, "No File", "Please select a file first")
            return

        # Collect mappings
        mapping = {}
        for field_key, target in self.parts_targets.items():
            if target.mapped_value:
                mapping[field_key] = target.mapped_value

        # Check required fields
        if 'part_number' not in mapping:
            QMessageBox.warning(self, "Missing Required Field", "Please map Part Number field")
            return

        try:
            import pandas as pd
            from datetime import datetime

            # Load file
            if self.parts_file_path.endswith('.csv'):
                df = pd.read_csv(self.parts_file_path, dtype=str, keep_default_na=False)
            else:
                df = pd.read_excel(self.parts_file_path, dtype=str, keep_default_na=False)

            df = df.fillna("")

            # Progress dialog
            progress = QProgressDialog("Importing parts...", "Cancel", 0, len(df), self)
            progress.setWindowTitle("Import Progress")
            progress.setMinimumDuration(0)

            cursor = self.db.conn.cursor()
            inserted = 0
            updated = 0
            skipped = 0

            for idx, row in df.iterrows():
                if progress.wasCanceled():
                    break
                progress.setValue(idx)

                part_number = str(row.get(mapping.get('part_number', ''), '')).strip()
                if not part_number:
                    skipped += 1
                    continue

                # Check if exists
                cursor.execute("SELECT part_number FROM parts WHERE part_number = ?", (part_number,))
                exists = cursor.fetchone() is not None

                # Build values
                values = {
                    'part_number': part_number,
                    'hts_code': str(row.get(mapping.get('hts_code', ''), '')).strip() or None,
                    'description': str(row.get(mapping.get('description', ''), '')).strip() or None,
                    'country_origin': str(row.get(mapping.get('country_origin', ''), '')).strip()[:2].upper() or None,
                    'mid': str(row.get(mapping.get('mid', ''), '')).strip() or None,
                    'client_code': str(row.get(mapping.get('client_code', ''), '')).strip() or None,
                    'qty_unit': str(row.get(mapping.get('qty_unit', ''), '')).strip() or 'NO',
                    'last_updated': datetime.now().isoformat(),
                }

                # Parse percentage fields
                for pct_field in ['steel_pct', 'aluminum_pct', 'copper_pct', 'wood_pct', 'auto_pct']:
                    val = str(row.get(mapping.get(pct_field, ''), '')).strip()
                    if val:
                        try:
                            pct = float(val)
                            if 0 < pct <= 1:
                                pct *= 100
                            values[pct_field] = pct
                        except ValueError:
                            values[pct_field] = 0
                    else:
                        values[pct_field] = 0

                if exists:
                    # Update
                    updates = [f"{k} = ?" for k in values.keys() if k != 'part_number']
                    params = [v for k, v in values.items() if k != 'part_number']
                    params.append(part_number)
                    cursor.execute(f"UPDATE parts SET {', '.join(updates)} WHERE part_number = ?", params)
                    updated += 1
                else:
                    # Insert
                    cols = ', '.join(values.keys())
                    placeholders = ', '.join(['?' for _ in values])
                    cursor.execute(f"INSERT INTO parts ({cols}) VALUES ({placeholders})", list(values.values()))
                    inserted += 1

            self.db.conn.commit()
            progress.close()

            QMessageBox.information(
                self, "Import Complete",
                f"Import completed!\n\n"
                f"Inserted: {inserted}\n"
                f"Updated: {updated}\n"
                f"Skipped: {skipped}"
            )

            self.parts_imported.emit()
            self.parts_status_label.setText(f"Import complete: {inserted} inserted, {updated} updated")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    # ========== MID MANAGEMENT HANDLERS ==========

    def _browse_mid_file(self):
        """Browse for MID file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select MID File", "",
            "Excel/CSV Files (*.xlsx *.xls *.csv)"
        )
        if file_path:
            self.mid_file_path = file_path
            self.mid_import_label.setText(Path(file_path).name)

    def _import_mid_file(self):
        """Import MIDs from file."""
        if not hasattr(self, 'mid_file_path'):
            QMessageBox.warning(self, "No File", "Please select a file first")
            return

        try:
            import pandas as pd

            if self.mid_file_path.endswith('.csv'):
                df = pd.read_csv(self.mid_file_path)
            else:
                df = pd.read_excel(self.mid_file_path)

            # Map columns
            col_map = {}
            for col in df.columns:
                col_lower = col.lower().strip()
                if 'manufacturer' in col_lower or 'name' in col_lower:
                    col_map['company_name'] = col
                elif 'mid' in col_lower and 'customer' not in col_lower:
                    col_map['mid'] = col
                elif 'customer' in col_lower:
                    col_map['customer_id'] = col
                elif 'related' in col_lower:
                    col_map['related_parties'] = col

            # Import rows
            count = 0
            for _, row in df.iterrows():
                company = row.get(col_map.get('company_name', ''), '')
                mid = row.get(col_map.get('mid', ''), '')
                customer = row.get(col_map.get('customer_id', ''), '')
                related = row.get(col_map.get('related_parties', ''), '')

                if company and mid:
                    self.db.add_manufacturer(str(company), str(mid), str(customer), str(related))
                    count += 1

            self._load_mid_data()
            QMessageBox.information(self, "Import Complete", f"Imported {count} MIDs")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    def _filter_mid_table(self):
        """Filter the MID table."""
        customer = self.mid_customer_filter.text().lower()
        mid = self.mid_mid_filter.text().lower()
        manufacturer = self.mid_manufacturer_filter.text().lower()

        for row in range(self.mid_table.rowCount()):
            show = True

            if customer:
                cell = self.mid_table.item(row, 2)
                if cell and customer not in cell.text().lower():
                    show = False

            if mid and show:
                cell = self.mid_table.item(row, 1)
                if cell and mid not in cell.text().lower():
                    show = False

            if manufacturer and show:
                cell = self.mid_table.item(row, 0)
                if cell and manufacturer not in cell.text().lower():
                    show = False

            self.mid_table.setRowHidden(row, not show)

    def _clear_mid_filters(self):
        """Clear MID filters."""
        self.mid_customer_filter.clear()
        self.mid_mid_filter.clear()
        self.mid_manufacturer_filter.clear()
        for row in range(self.mid_table.rowCount()):
            self.mid_table.setRowHidden(row, False)

    def _add_mid_row(self):
        """Add a new MID row."""
        row = self.mid_table.rowCount()
        self.mid_table.insertRow(row)
        for col in range(4):
            self.mid_table.setItem(row, col, QTableWidgetItem(""))

    def _delete_mid_selected(self):
        """Delete selected MID rows."""
        rows = set(item.row() for item in self.mid_table.selectedItems())
        for row in sorted(rows, reverse=True):
            self.mid_table.removeRow(row)

    def _clear_all_mids(self):
        """Clear all MIDs."""
        reply = QMessageBox.question(
            self, "Confirm",
            "Are you sure you want to clear all MIDs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.mid_table.setRowCount(0)

    def _export_mids(self):
        """Export MIDs to Excel."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export MIDs", "mid_list.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        try:
            import pandas as pd

            data = []
            for row in range(self.mid_table.rowCount()):
                data.append({
                    'Manufacturer Name': self.mid_table.item(row, 0).text() if self.mid_table.item(row, 0) else '',
                    'MID': self.mid_table.item(row, 1).text() if self.mid_table.item(row, 1) else '',
                    'Customer ID': self.mid_table.item(row, 2).text() if self.mid_table.item(row, 2) else '',
                    'Related Parties': self.mid_table.item(row, 3).text() if self.mid_table.item(row, 3) else '',
                })

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            QMessageBox.information(self, "Exported", f"MIDs exported to {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _save_mid_changes(self):
        """Save all MID changes to database."""
        try:
            # Clear existing and reimport
            self.db.clear_manufacturers()

            for row in range(self.mid_table.rowCount()):
                company = self.mid_table.item(row, 0).text() if self.mid_table.item(row, 0) else ''
                mid = self.mid_table.item(row, 1).text() if self.mid_table.item(row, 1) else ''
                customer = self.mid_table.item(row, 2).text() if self.mid_table.item(row, 2) else ''
                related = self.mid_table.item(row, 3).text() if self.mid_table.item(row, 3) else ''

                if company and mid:
                    self.db.add_manufacturer(company, mid, customer, related)

            QMessageBox.information(self, "Saved", "MID changes saved successfully")

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")


class DropTargetLabel(QLabel):
    """A label that accepts drops for column mapping."""

    dropped = pyqtSignal(str, str)  # field_key, dropped_value

    def __init__(self, field_key: str, placeholder: str, parent=None):
        super().__init__(placeholder, parent)
        self.field_key = field_key
        self.placeholder = placeholder
        self.mapped_value = None

        self.setAcceptDrops(True)
        self.setMinimumHeight(28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_style()

    def _update_style(self):
        """Update the label style based on state."""
        if self.mapped_value:
            self.setStyleSheet("""
                QLabel {
                    background-color: #5f9ea0;
                    color: white;
                    border: 1px solid #4f8e90;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: #f8f8f8;
                    color: #666;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QLabel {
                    background-color: #e0f0f0;
                    color: #333;
                    border: 2px solid #5f9ea0;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)

    def dragLeaveEvent(self, event):
        self._update_style()

    def dropEvent(self, event):
        text = event.mimeData().text()
        self.setText(text)
        self.mapped_value = text
        self._update_style()
        self.dropped.emit(self.field_key, text)
        event.acceptProposedAction()

    def clear(self):
        """Clear the mapping."""
        self.setText(self.placeholder)
        self.mapped_value = None
        self._update_style()

    def mouseDoubleClickEvent(self, event):
        """Clear on double-click."""
        self.clear()


class ColorButton(QPushButton):
    """A button that displays and selects a color."""

    def __init__(self, field: str, parent=None):
        super().__init__(parent)
        self.field = field
        self.color = "#000000"
        self._update_style()

    def setColor(self, color: str):
        """Set the button color."""
        self.color = color
        self._update_style()

    def _update_style(self):
        """Update button style to show current color."""
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                border: 1px solid #666;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """)


class OutputColumnRow(QWidget):
    """A row for output column configuration with up/down buttons and name edit."""

    def __init__(self, internal_name: str, display_name: str, default_output_name: str, parent=None):
        super().__init__(parent)
        self.internal_name = internal_name
        self.display_name = display_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(8)

        # Up/Down buttons
        up_btn = QPushButton("\u25B2")
        up_btn.setFixedSize(24, 24)
        up_btn.setStyleSheet("font-size: 8pt; padding: 0;")
        up_btn.clicked.connect(self._move_up)
        layout.addWidget(up_btn)

        down_btn = QPushButton("\u25BC")
        down_btn.setFixedSize(24, 24)
        down_btn.setStyleSheet("font-size: 8pt; padding: 0;")
        down_btn.clicked.connect(self._move_down)
        layout.addWidget(down_btn)

        # Label
        label = QLabel(f"{display_name}:")
        label.setMinimumWidth(120)
        layout.addWidget(label)

        # Output name edit
        self.name_edit = QLineEdit(default_output_name)
        self.name_edit.setMinimumWidth(200)
        layout.addWidget(self.name_edit, 1)

    def _move_up(self):
        """Move this row up."""
        parent = self.parent()
        if parent and hasattr(parent, 'layout'):
            layout = parent.layout()
            idx = layout.indexOf(self)
            if idx > 0:
                layout.removeWidget(self)
                layout.insertWidget(idx - 1, self)

    def _move_down(self):
        """Move this row down."""
        parent = self.parent()
        if parent and hasattr(parent, 'layout'):
            layout = parent.layout()
            idx = layout.indexOf(self)
            # -1 for stretch at end
            if idx < layout.count() - 2:
                layout.removeWidget(self)
                layout.insertWidget(idx + 1, self)

    def get_config(self):
        """Get the configuration for this row."""
        return {
            "internal": self.internal_name,
            "display": self.display_name,
            "output_name": self.name_edit.text(),
        }
