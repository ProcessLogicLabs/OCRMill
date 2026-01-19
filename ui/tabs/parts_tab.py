"""
Parts Database Tab for OCRMill.
"""

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableView, QHeaderView,
    QRadioButton, QButtonGroup, QMenu, QMessageBox,
    QFileDialog, QPlainTextEdit, QGroupBox, QFormLayout,
    QAbstractItemView, QFrame, QScrollArea, QSizePolicy,
    QProgressDialog, QDialog, QComboBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QAbstractTableModel, QModelIndex, QMimeData
from PyQt6.QtGui import QAction, QDrag, QCursor, QPixmap

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase

# Path for persisting column mappings
MAPPING_FILE = Path(__file__).parent.parent.parent / "Resources" / "column_mapping.json"


class DraggableLabel(QLabel):
    """
    A draggable label for CSV/Excel column names.
    Used in the left panel of the parts import UI.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            background: #6b6b6b;
            border: 2px solid #aaa;
            border-radius: 8px;
            padding: 12px;
            font-weight: bold;
            color: #ffffff;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.text())
            drag.setMimeData(mime)
            # Create a transparent pixmap for drag
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            drag.setPixmap(pixmap)
            drag.exec(Qt.DropAction.CopyAction)


class DropTarget(QLabel):
    """
    A drop target for mapping CSV columns to database fields.
    Used in the right panel of the parts import UI.
    """

    dropped = pyqtSignal(str, str)  # field_key, column_name

    def __init__(self, field_key: str, field_name: str, drop_label: str = None, parent=None):
        label_text = drop_label if drop_label else field_name
        super().__init__(f"Drop {label_text} here", parent)
        self.field_key = field_key
        self.field_name = field_name
        self._default_text = f"Drop {label_text} here"

        self.setStyleSheet("""
            padding: 4px 8px;
            background: #f8f8f8;
            border: 1px solid #bbb;
            border-radius: 4px;
            color: #222;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setWordWrap(False)
        self.column_name = None
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()

    def dragLeaveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        col = event.mimeData().text()
        self.column_name = col
        self.setText("\u2713")  # Checkmark
        self.setStyleSheet("""
            padding: 4px 8px;
            background: #d4edda;
            border: 1px solid #28a745;
            border-radius: 4px;
            color: #28a745;
            font-size: 16px;
            font-weight: bold;
        """)
        self.setProperty("occupied", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self.dropped.emit(self.field_key, col)
        event.accept()

    def reset(self):
        """Reset the drop target to its default state."""
        self.column_name = None
        self.setText(self._default_text)
        self.setStyleSheet("""
            padding: 4px 8px;
            background: #f8f8f8;
            border: 1px solid #bbb;
            border-radius: 4px;
            color: #222;
        """)
        self.setProperty("occupied", False)
        self.style().unpolish(self)
        self.style().polish(self)


class NewFieldDialog(QDialog):
    """Dialog for creating a new database field."""

    def __init__(self, csv_column_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Database Field")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(f"Create a new database field for CSV column: <b>{csv_column_name}</b>")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Form
        form_layout = QFormLayout()

        # Field name (database column name)
        self.field_name_edit = QLineEdit()
        # Convert CSV column name to valid database column name
        suggested_name = csv_column_name.lower().replace(' ', '_').replace('-', '_')
        suggested_name = ''.join(c for c in suggested_name if c.isalnum() or c == '_')
        self.field_name_edit.setText(suggested_name)
        self.field_name_edit.setPlaceholderText("e.g., custom_field_1")
        form_layout.addRow("Database Field Name:", self.field_name_edit)

        # Display name (for UI)
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setText(csv_column_name)
        self.display_name_edit.setPlaceholderText("e.g., Custom Field 1")
        form_layout.addRow("Display Name:", self.display_name_edit)

        # Field type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["TEXT", "REAL", "INTEGER"])
        form_layout.addRow("Field Type:", self.type_combo)

        layout.addLayout(form_layout)

        # Warning
        warning = QLabel(
            "<i>Note: This will permanently add a new column to the parts database. "
            "Field names should contain only letters, numbers, and underscores.</i>"
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(warning)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_field_info(self):
        """Return the field information."""
        return {
            'field_name': self.field_name_edit.text().strip(),
            'display_name': self.display_name_edit.text().strip(),
            'field_type': self.type_combo.currentText(),
        }

    def accept(self):
        """Validate before accepting."""
        field_name = self.field_name_edit.text().strip()

        if not field_name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a field name.")
            return

        # Check for valid identifier
        if not field_name[0].isalpha() and field_name[0] != '_':
            QMessageBox.warning(self, "Invalid Name", "Field name must start with a letter or underscore.")
            return

        if not all(c.isalnum() or c == '_' for c in field_name):
            QMessageBox.warning(self, "Invalid Name", "Field name can only contain letters, numbers, and underscores.")
            return

        # Reserved words check
        reserved = ['part_number', 'description', 'hts_code', 'country_origin', 'mid', 'client_code',
                    'steel_pct', 'aluminum_pct', 'copper_pct', 'wood_pct', 'auto_pct', 'non_steel_pct',
                    'qty_unit', 'sec301_exclusion_tariff', 'last_updated', 'notes', 'id', 'rowid']
        if field_name.lower() in reserved:
            QMessageBox.warning(self, "Reserved Name", f"'{field_name}' is already used. Please choose a different name.")
            return

        super().accept()


class AddFieldDropTarget(QLabel):
    """
    Special drop target for adding new database fields.
    When a column is dropped here, it prompts to create a new field.
    """

    new_field_requested = pyqtSignal(str)  # csv_column_name

    def __init__(self, parent=None):
        super().__init__("+ Drop here to add new field", parent)

        self.setStyleSheet("""
            padding: 8px 12px;
            background: #fff3e0;
            border: 2px dashed #ff9800;
            border-radius: 6px;
            color: #e65100;
            font-weight: bold;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self.setStyleSheet("""
                padding: 8px 12px;
                background: #ffe0b2;
                border: 2px solid #ff9800;
                border-radius: 6px;
                color: #e65100;
                font-weight: bold;
            """)
            event.accept()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            padding: 8px 12px;
            background: #fff3e0;
            border: 2px dashed #ff9800;
            border-radius: 6px;
            color: #e65100;
            font-weight: bold;
        """)
        event.accept()

    def dropEvent(self, event):
        col = event.mimeData().text()
        self.setStyleSheet("""
            padding: 8px 12px;
            background: #fff3e0;
            border: 2px dashed #ff9800;
            border-radius: 6px;
            color: #e65100;
            font-weight: bold;
        """)
        self.new_field_requested.emit(col)
        event.accept()


class PartsTableModel(QAbstractTableModel):
    """Table model for parts data."""

    COLUMNS = [
        ("part_number", "Part Number", 140),
        ("description", "Description", 220),
        ("hts_code", "HTS Code", 100),
        ("country_origin", "Country", 70),
        ("mid", "MID", 150),
        ("client_code", "Client Code", 90),
        ("steel_pct", "Steel %", 60),
        ("aluminum_pct", "Alum %", 60),
        ("copper_pct", "Copper %", 60),
        ("wood_pct", "Wood %", 60),
        ("auto_pct", "Auto %", 60),
        ("non_steel_pct", "Non-Steel %", 70),
        ("qty_unit", "Unit", 50),
        ("sec301_exclusion_tariff", "301 Excl", 60),
        ("fsc_certified", "FSC", 40),
        ("fsc_certificate_code", "FSC Code", 100),
        ("last_updated", "Last Updated", 130),
    ]

    def __init__(self, db: PartsDatabase, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self._data = []
        self._visible_columns = self._get_visible_columns()

    def _get_visible_columns(self):
        """Get list of visible column indices based on config."""
        visible = []
        for i, (col_name, _, _) in enumerate(self.COLUMNS):
            if self.config.get_column_visible(col_name):
                visible.append(i)
        return visible

    def refresh_columns(self):
        """Refresh visible columns from config."""
        self.beginResetModel()
        self._visible_columns = self._get_visible_columns()
        self.endResetModel()

    def refresh(self, filter_type: str = "all", search_term: str = ""):
        """Refresh data from database."""
        self.beginResetModel()

        if search_term:
            self._data = self.db.search_parts(search_term)
        else:
            self._data = self.db.get_all_parts()

        # Apply filter
        if filter_type == "with_hts":
            self._data = [p for p in self._data if p.get('hts_code')]
        elif filter_type == "no_hts":
            self._data = [p for p in self._data if not p.get('hts_code')]

        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._visible_columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            col_idx = self._visible_columns[index.column()]
            col_name = self.COLUMNS[col_idx][0]
            part = self._data[index.row()]
            value = part.get(col_name, '')

            # Format percentage columns
            if col_name.endswith('_pct') and value:
                try:
                    return f"{float(value):.0f}"
                except (ValueError, TypeError):
                    return str(value)

            # Format boolean columns
            if col_name in ('fsc_certified',):
                return "Yes" if value else "No"

            return str(value) if value else ''

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            col_idx = self._visible_columns[section]
            return self.COLUMNS[col_idx][1]
        return None

    def get_part_at_row(self, row: int):
        """Get part data at specified row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def get_column_width(self, column: int):
        """Get preferred column width."""
        if 0 <= column < len(self._visible_columns):
            col_idx = self._visible_columns[column]
            return self.COLUMNS[col_idx][2]
        return 100


class PartsDatabaseTab(QWidget):
    """
    Parts Database tab for browsing and managing parts.

    Signals:
        part_selected: Emitted when a part is selected (part_number)
        data_changed: Emitted when data is modified
    """

    part_selected = pyqtSignal(str)
    data_changed = pyqtSignal()

    def __init__(self, config: ConfigManager, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db

        self._current_filter = "all"
        self._current_search = ""

        self._setup_ui()
        self._connect_signals()
        self.refresh_data()

    def _setup_ui(self):
        """Set up the tab UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)

        # Main content with sub-tabs
        self.sub_tabs = QTabWidget()

        # Parts Master tab
        parts_master = self._create_parts_master_tab()
        self.sub_tabs.addTab(parts_master, "Parts Master")

        # Parts Import tab (drag & drop)
        import_widget = self._create_hts_tab()
        self.sub_tabs.addTab(import_widget, "Parts Import")

        layout.addWidget(self.sub_tabs, 1)

    def _create_toolbar(self) -> QHBoxLayout:
        """Create the toolbar."""
        toolbar = QHBoxLayout()

        # Action buttons
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_parts)
        toolbar.addWidget(export_btn)

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_parts)
        toolbar.addWidget(import_btn)

        toolbar.addWidget(QLabel(" | "))

        # Filter radio buttons
        self.filter_group = QButtonGroup(self)

        self.all_radio = QRadioButton("All")
        self.all_radio.setChecked(True)
        self.filter_group.addButton(self.all_radio)
        toolbar.addWidget(self.all_radio)

        self.with_hts_radio = QRadioButton("With HTS")
        self.filter_group.addButton(self.with_hts_radio)
        toolbar.addWidget(self.with_hts_radio)

        self.no_hts_radio = QRadioButton("No HTS")
        self.filter_group.addButton(self.no_hts_radio)
        toolbar.addWidget(self.no_hts_radio)

        toolbar.addStretch()

        # Search
        toolbar.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Part number or description...")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.returnPressed.connect(self._on_search)
        toolbar.addWidget(self.search_edit)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        toolbar.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_search)
        toolbar.addWidget(clear_btn)

        return toolbar

    def _create_parts_master_tab(self) -> QWidget:
        """Create the parts master table tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 0)

        # Table
        self.parts_model = PartsTableModel(self.db, self.config)
        self.parts_table = QTableView()
        self.parts_table.setModel(self.parts_model)
        self.parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.parts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.parts_table.setAlternatingRowColors(True)
        self.parts_table.setSortingEnabled(True)
        self.parts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.parts_table.customContextMenuRequested.connect(self._show_context_menu)
        self.parts_table.doubleClicked.connect(self._on_double_click)

        # Set column widths
        header = self.parts_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(self.parts_model.columnCount()):
            width = self.parts_model.get_column_width(i)
            self.parts_table.setColumnWidth(i, width)

        layout.addWidget(self.parts_table)

        # Status bar
        self.parts_count_label = QLabel("0 parts")
        layout.addWidget(self.parts_count_label)

        return widget

    def _create_hts_tab(self) -> QWidget:
        """Create the Parts Import tab with drag-and-drop column mapping."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title and description
        title = QLabel("<h2>Parts Import from CSV/Excel</h2><p>Drag & drop columns to map fields</p>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Button toolbar
        button_widget = QWidget()
        btn_layout = QHBoxLayout(button_widget)
        btn_layout.setContentsMargins(0, 0, 0, 10)

        btn_load = QPushButton("Load CSV/Excel File")
        btn_load.clicked.connect(self._load_csv_for_import)
        btn_layout.addWidget(btn_load)

        btn_reset = QPushButton("Reset Mapping")
        btn_reset.clicked.connect(self._reset_import_mapping)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_import = QPushButton("Import Now")
        btn_import.clicked.connect(self._start_parts_import)
        btn_layout.addWidget(btn_import)

        layout.addWidget(button_widget)

        # Main drag/drop area
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(15)

        # LEFT: CSV/Excel Columns - Drag
        left_group = QGroupBox("CSV/Excel Columns - Drag")
        left_outer_layout = QVBoxLayout(left_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumWidth(180)

        scroll_widget = QWidget()
        self.import_left_layout = QVBoxLayout(scroll_widget)
        self.import_left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(scroll_widget)
        left_outer_layout.addWidget(scroll_area)

        # RIGHT: Available Fields - Drop Here
        right_group = QGroupBox("Available Fields - Drop Here")
        right_outer_layout = QVBoxLayout(right_group)

        right_scroll_area = QScrollArea()
        right_scroll_area.setWidgetResizable(True)

        right_scroll_widget = QWidget()
        right_layout = QFormLayout(right_scroll_widget)
        right_layout.setSpacing(8)

        # Define all available fields for mapping
        # Fields marked with * are required
        self.import_targets = {}
        fields = [
            ("part_number", "Part Number", "Part Number *", True),
            ("hts_code", "HTS Code", "HTS Code *", True),
            ("mid", "MID", "MID", False),
            ("steel_ratio", "Steel %", "Steel%", False),
            ("aluminum_ratio", "Aluminum %", "Aluminum%", False),
            ("copper_ratio", "Copper %", "Copper%", False),
            ("wood_ratio", "Wood %", "Wood%", False),
            ("auto_ratio", "Auto %", "Auto%", False),
            ("qty_unit", "Qty Unit", "Qty Unit", False),
            ("country_of_melt", "Country of Melt", "Country of Melt", False),
            ("country_of_cast", "Country of Cast", "Country of Cast", False),
            ("country_of_smelt", "Country of Smelt", "Country of Smelt", False),
            ("sec301_exclusion_tariff", "Sec301 Exclusion Tariff", "Sec301 Exclusion Tariff", False),
            ("client_code", "Client Code", "Client Code", False),
            ("description", "Description", "Description", False),
            ("country_origin", "Country of Origin", "Country of Origin", False),
        ]

        for field_key, field_name, drop_label, is_required in fields:
            target = DropTarget(field_key, field_name, drop_label)
            target.dropped.connect(self._on_import_drop)

            if is_required:
                label = QLabel(f"{field_name}: <span style='color:red;'>*</span>")
            else:
                label = QLabel(f"{field_name}:")

            right_layout.addRow(label, target)
            self.import_targets[field_key] = target

        # Store reference to the form layout for adding dynamic fields
        self.import_fields_layout = right_layout

        # Add separator and "Add New Field" drop target
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #ddd; margin: 10px 0;")
        right_layout.addRow(separator)

        # Custom fields section label
        custom_label = QLabel("<b>Custom Fields:</b>")
        custom_label.setStyleSheet("color: #666; margin-top: 5px;")
        right_layout.addRow(custom_label)

        # Track dynamically added fields
        self.custom_fields = {}  # field_name -> (display_name, field_type, DropTarget)

        # Load any previously added custom fields from database
        self._load_custom_fields_from_db(right_layout)

        # Add new field drop target
        self.add_field_target = AddFieldDropTarget()
        self.add_field_target.new_field_requested.connect(self._on_add_new_field)
        right_layout.addRow(self.add_field_target)

        right_scroll_area.setWidget(right_scroll_widget)
        right_outer_layout.addWidget(right_scroll_area)

        main_layout.addWidget(left_group, 1)
        main_layout.addWidget(right_group, 2)

        layout.addWidget(main_widget, 1)

        # Status label at bottom
        self.import_status_label = QLabel("Load a CSV or Excel file to begin")
        self.import_status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.import_status_label)

        # Initialize variables for import
        self.import_csv_path = None
        self.drag_labels = []
        self.current_mapping = {}

        return widget

    def _load_custom_fields_from_db(self, layout: QFormLayout):
        """Load any custom fields that were previously added to the database."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("PRAGMA table_info(parts)")
            columns = cursor.fetchall()

            # Standard fields that we already have targets for
            standard_fields = {
                'part_number', 'description', 'hts_code', 'country_origin', 'mid', 'client_code',
                'steel_pct', 'aluminum_pct', 'copper_pct', 'wood_pct', 'auto_pct', 'non_steel_pct',
                'qty_unit', 'sec301_exclusion_tariff', 'last_updated', 'notes',
                'fsc_certified', 'fsc_certificate_code'
            }

            # Also check our import_targets keys (in case of mapping differences)
            standard_fields.update(self.import_targets.keys())

            for col in columns:
                col_name = col[1]  # Column name is at index 1
                col_type = col[2]  # Column type is at index 2

                if col_name.lower() not in standard_fields and col_name.lower() not in self.custom_fields:
                    # This is a custom field - add a drop target for it
                    display_name = col_name.replace('_', ' ').title()
                    target = DropTarget(col_name, display_name, display_name)
                    target.dropped.connect(self._on_import_drop)

                    label = QLabel(f"{display_name}:")
                    layout.addRow(label, target)

                    self.import_targets[col_name] = target
                    self.custom_fields[col_name] = (display_name, col_type, target)

        except Exception:
            pass  # Ignore errors loading custom fields

    def _on_add_new_field(self, csv_column_name: str):
        """Handle request to add a new database field."""
        dialog = NewFieldDialog(csv_column_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        field_info = dialog.get_field_info()
        field_name = field_info['field_name']
        display_name = field_info['display_name']
        field_type = field_info['field_type']

        # Check if field already exists
        if field_name in self.import_targets:
            QMessageBox.warning(self, "Field Exists", f"Field '{field_name}' already exists.")
            return

        try:
            # Add column to database
            cursor = self.db.conn.cursor()
            cursor.execute(f"ALTER TABLE parts ADD COLUMN {field_name} {field_type}")
            self.db.conn.commit()

            # Create and add the drop target
            target = DropTarget(field_name, display_name, display_name)
            target.dropped.connect(self._on_import_drop)

            label = QLabel(f"{display_name}:")

            # Insert before the "Add New Field" target
            row_count = self.import_fields_layout.rowCount()
            self.import_fields_layout.insertRow(row_count - 1, label, target)

            self.import_targets[field_name] = target
            self.custom_fields[field_name] = (display_name, field_type, target)

            # Auto-map the CSV column to the new field
            target.column_name = csv_column_name
            target.setText("\u2713")  # Checkmark
            target.setStyleSheet("""
                padding: 4px 8px;
                background: #d4edda;
                border: 1px solid #28a745;
                border-radius: 4px;
                color: #28a745;
                font-size: 16px;
                font-weight: bold;
            """)

            self.current_mapping[field_name] = csv_column_name
            self._save_mapping()

            self.import_status_label.setText(f"Added new field: {display_name} ({field_type})")

            QMessageBox.information(
                self, "Field Added",
                f"New field '{display_name}' has been added to the database and mapped to '{csv_column_name}'."
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add field:\n{e}")

    def _save_mapping(self):
        """Save the current mapping to file."""
        try:
            MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
            MAPPING_FILE.write_text(json.dumps(self.current_mapping, indent=2))
        except Exception:
            pass

    def _connect_signals(self):
        """Connect internal signals."""
        self.filter_group.buttonClicked.connect(self._on_filter_changed)

    # ----- Data operations -----

    @pyqtSlot()
    def refresh_data(self):
        """Refresh parts data from database."""
        self._apply_filter()
        self._update_counts()

    def reload_columns(self):
        """Reload column visibility from config."""
        self.parts_model.refresh_columns()

        # Reset column widths
        for i in range(self.parts_model.columnCount()):
            width = self.parts_model.get_column_width(i)
            self.parts_table.setColumnWidth(i, width)

    def _apply_filter(self):
        """Apply current filter and search."""
        self.parts_model.refresh(self._current_filter, self._current_search)

    def _update_counts(self):
        """Update the parts count label."""
        count = self.parts_model.rowCount()
        self.parts_count_label.setText(f"{count} parts")

    def _on_filter_changed(self):
        """Handle filter radio button change."""
        if self.all_radio.isChecked():
            self._current_filter = "all"
        elif self.with_hts_radio.isChecked():
            self._current_filter = "with_hts"
        else:
            self._current_filter = "no_hts"

        self._apply_filter()
        self._update_counts()

    def _on_search(self):
        """Handle search."""
        self._current_search = self.search_edit.text().strip()
        self._apply_filter()
        self._update_counts()

    def _clear_search(self):
        """Clear search and reset."""
        self.search_edit.clear()
        self._current_search = ""
        self._apply_filter()
        self._update_counts()

    # ----- Context menu -----

    def _show_context_menu(self, pos):
        """Show context menu for parts table."""
        index = self.parts_table.indexAt(pos)
        if not index.isValid():
            return

        part = self.parts_model.get_part_at_row(index.row())
        if not part:
            return

        menu = QMenu(self)

        view_action = QAction("View Details", self)
        view_action.triggered.connect(lambda: self._view_part_details(part))
        menu.addAction(view_action)

        edit_action = QAction("Edit Part", self)
        edit_action.triggered.connect(lambda: self._edit_part(part))
        menu.addAction(edit_action)

        menu.addSeparator()

        history_action = QAction("View History", self)
        history_action.triggered.connect(lambda: self._show_part_history(part))
        menu.addAction(history_action)

        menu.addSeparator()

        set_hts_action = QAction("Set HTS Code...", self)
        set_hts_action.triggered.connect(lambda: self._set_hts_for_part(part))
        menu.addAction(set_hts_action)

        menu.exec(self.parts_table.viewport().mapToGlobal(pos))

    def _on_double_click(self, index):
        """Handle double-click on table row."""
        part = self.parts_model.get_part_at_row(index.row())
        if part:
            self._view_part_details(part)

    # ----- Part operations -----

    def _view_part_details(self, part: dict):
        """View part details in a dialog."""
        from ui.dialogs.part_dialogs import PartViewDialog
        dialog = PartViewDialog(part, self)
        dialog.exec()

    def _edit_part(self, part: dict):
        """Edit a part."""
        from ui.dialogs.part_dialogs import PartEditDialog
        dialog = PartEditDialog(part, self.db, self)
        if dialog.exec():
            self.refresh_data()
            self.data_changed.emit()

    def _show_part_history(self, part: dict):
        """Show part history - opens the Statistics dialog at Part History tab."""
        from ui.dialogs.statistics_dialog import StatisticsDialog
        dialog = StatisticsDialog(self.db, self)
        # Switch to Part History tab (index 3)
        dialog.tabs.setCurrentIndex(3)
        # Pre-fill the part number
        dialog.history_part_edit.setText(part.get('part_number', ''))
        dialog._view_part_history()
        dialog.exec()

    def _set_hts_for_selected(self):
        """Set HTS code for selected part."""
        index = self.parts_table.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select a part first.")
            return

        part = self.parts_model.get_part_at_row(index.row())
        if part:
            self._set_hts_for_part(part)

    def _set_hts_for_part(self, part: dict):
        """Set HTS code for a specific part."""
        from PyQt6.QtWidgets import QInputDialog

        current_hts = part.get('hts_code', '')
        new_hts, ok = QInputDialog.getText(
            self, "Set HTS Code",
            f"Enter HTS code for {part.get('part_number', '')}:",
            text=current_hts
        )

        if ok and new_hts:
            try:
                self.db.update_part_hts(part.get('part_number'), new_hts)
                self.refresh_data()
                self.data_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update HTS code:\n{e}")

    # ----- Import/Export -----

    def _export_parts(self):
        """Export parts to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Parts", "parts_export.csv", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                self.db.export_to_csv(file_path)
                QMessageBox.information(self, "Export Complete", f"Parts exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _import_parts(self):
        """Import parts from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Parts",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if file_path:
            try:
                count = self.db.import_parts_list(file_path)
                QMessageBox.information(self, "Import Complete", f"Imported {count} parts.")
                self.refresh_data()
                self.data_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    def _import_hts(self):
        """Import HTS mappings."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import HTS Mappings",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if file_path:
            try:
                count = self.db.load_hts_mapping(file_path)
                QMessageBox.information(self, "Import Complete", f"Imported {count} HTS mappings.")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    # ----- Parts Import (Drag & Drop) -----

    def _load_csv_for_import(self):
        """Open file dialog and load CSV/Excel file for import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load CSV/Excel File",
            "",
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if file_path:
            self._load_csv_from_path(file_path)

    def _load_csv_from_path(self, path: str):
        """Load CSV/Excel file from a given path and extract column headers."""
        if not path:
            return

        self.import_csv_path = path

        try:
            import pandas as pd

            # Read only the header row to get column names
            if path.lower().endswith('.xlsx') or path.lower().endswith('.xls'):
                df = pd.read_excel(path, nrows=0, dtype=str)
            else:
                df = pd.read_csv(path, nrows=0, dtype=str)

            cols = list(df.columns)

            # Clear previous mappings when loading a new file
            for target in self.import_targets.values():
                target.reset()

            # Clear existing labels from the left panel
            for label in self.drag_labels:
                label.setParent(None)
                label.deleteLater()
            self.drag_labels = []

            # Add new labels for each column
            for col in cols:
                lbl = DraggableLabel(str(col))
                self.import_left_layout.addWidget(lbl)
                self.drag_labels.append(lbl)

            # Add stretch at the end to push labels to the top
            self.import_left_layout.addStretch()

            # Try to restore saved mappings if they match columns in the new file
            if MAPPING_FILE.exists():
                try:
                    saved_mapping = json.loads(MAPPING_FILE.read_text())
                    for field_key, column_name in saved_mapping.items():
                        if column_name in cols and field_key in self.import_targets:
                            target = self.import_targets[field_key]
                            target.column_name = column_name
                            target.setText("\u2713")  # Checkmark
                            target.setStyleSheet("""
                                padding: 4px 8px;
                                background: #d4edda;
                                border: 1px solid #28a745;
                                border-radius: 4px;
                                color: #28a745;
                                font-size: 16px;
                                font-weight: bold;
                            """)
                            target.setProperty("occupied", True)
                            target.style().unpolish(target)
                            target.style().polish(target)
                except Exception:
                    pass  # Ignore errors loading saved mappings

            self.import_status_label.setText(f"Loaded: {Path(path).name} ({len(cols)} columns)")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot read file:\n{e}")

    def _on_import_drop(self, field_key: str, column_name: str):
        """Handle a column being dropped onto a field target."""
        # Remove mapping from other fields if the same column was mapped elsewhere
        for key, target in self.import_targets.items():
            if target.column_name == column_name and key != field_key:
                target.reset()

        # Update current mapping
        self.current_mapping[field_key] = column_name

        # Persist mapping to file
        try:
            MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
            MAPPING_FILE.write_text(json.dumps(self.current_mapping, indent=2))
        except Exception:
            pass  # Ignore errors saving mapping

        self.import_status_label.setText(f"Mapped: {column_name} \u2192 {field_key}")

    def _reset_import_mapping(self):
        """Clear all field mappings and column list."""
        result = QMessageBox.question(
            self, "Reset",
            "Clear all field mappings and column list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        # Clear drop targets (right side)
        for target in self.import_targets.values():
            target.reset()

        # Clear drag labels (left side - CSV/Excel columns)
        for label in self.drag_labels:
            label.setParent(None)
            label.deleteLater()
        self.drag_labels = []

        # Clear the file path
        self.import_csv_path = None
        self.current_mapping = {}

        # Delete mapping file if it exists
        if MAPPING_FILE.exists():
            try:
                MAPPING_FILE.unlink()
            except Exception:
                pass

        self.import_status_label.setText("Mapping cleared. Load a CSV or Excel file to begin.")

    def _start_parts_import(self):
        """Process the mapped CSV/Excel data and import to database."""
        if not self.import_csv_path:
            QMessageBox.warning(self, "No File", "Load a CSV or Excel file first.")
            return

        # Collect current mappings
        mapping = {k: t.column_name for k, t in self.import_targets.items() if t.column_name}

        # Check required fields
        required_fields = ['part_number', 'hts_code']
        missing = [f for f in required_fields if f not in mapping]
        if missing:
            QMessageBox.warning(
                self, "Missing Required Fields",
                f"Please map the required fields: {', '.join(missing)}"
            )
            return

        try:
            import pandas as pd

            # Show progress dialog
            progress = QProgressDialog("Loading file...", "Cancel", 0, 100, self)
            progress.setWindowTitle("Parts Import Progress")
            progress.setMinimumDuration(0)
            progress.show()

            # Load the full file
            progress.setLabelText("Reading file...")
            if self.import_csv_path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(self.import_csv_path, dtype=str, keep_default_na=False)
            else:
                df = pd.read_csv(self.import_csv_path, dtype=str, keep_default_na=False)

            df = df.fillna("").rename(columns=str.strip)

            # Reverse mapping: CSV column -> field key
            col_map = {v: k for k, v in mapping.items()}
            df = df.rename(columns=col_map)

            total_rows = len(df)
            if total_rows == 0:
                progress.close()
                QMessageBox.warning(self, "Empty File", "The file contains no data rows.")
                return

            progress.setMaximum(total_rows)
            progress.setLabelText(f"Processing {total_rows} rows...")

            # Helper function to parse percentage values
            def parse_percentage(value_str):
                try:
                    if value_str:
                        pct = float(value_str)
                        # Convert ratio (0-1) to percentage if needed
                        if 0 < pct <= 1.0:
                            pct *= 100.0
                        return max(0.0, pct)
                    return None
                except (ValueError, TypeError):
                    return None

            updated = 0
            inserted = 0
            skipped = 0

            # Get database cursor directly
            from datetime import datetime
            cursor = self.db.conn.cursor()

            for idx, row in df.iterrows():
                if progress.wasCanceled():
                    break

                progress.setValue(idx + 1)

                part_number = str(row.get('part_number', '')).strip()
                if not part_number:
                    skipped += 1
                    continue

                hts_code = str(row.get('hts_code', '')).strip() or None
                description = str(row.get('description', '')).strip() or None
                country_origin = str(row.get('country_origin', '')).strip().upper()[:2] or None
                mid = str(row.get('mid', '')).strip() or None
                client_code = str(row.get('client_code', '')).strip() or None
                qty_unit = str(row.get('qty_unit', '')).strip() or 'NO'

                # Parse percentage fields
                steel_pct = parse_percentage(str(row.get('steel_ratio', '')).strip())
                aluminum_pct = parse_percentage(str(row.get('aluminum_ratio', '')).strip())
                copper_pct = parse_percentage(str(row.get('copper_ratio', '')).strip())
                wood_pct = parse_percentage(str(row.get('wood_ratio', '')).strip())
                auto_pct = parse_percentage(str(row.get('auto_ratio', '')).strip())

                sec301 = str(row.get('sec301_exclusion_tariff', '')).strip() or None

                try:
                    # Check if part exists
                    cursor.execute("SELECT part_number FROM parts WHERE part_number = ?", (part_number,))
                    exists = cursor.fetchone() is not None

                    if exists:
                        # Update existing part - only update non-null values
                        updates = []
                        params = []

                        if hts_code:
                            updates.append("hts_code = ?")
                            params.append(hts_code)
                        if description:
                            updates.append("description = ?")
                            params.append(description)
                        if country_origin:
                            updates.append("country_origin = ?")
                            params.append(country_origin)
                        if mid:
                            updates.append("mid = ?")
                            params.append(mid)
                        if client_code:
                            updates.append("client_code = ?")
                            params.append(client_code)
                        if qty_unit and qty_unit != 'NO':
                            updates.append("qty_unit = ?")
                            params.append(qty_unit)
                        if steel_pct is not None:
                            updates.append("steel_pct = ?")
                            params.append(steel_pct)
                        if aluminum_pct is not None:
                            updates.append("aluminum_pct = ?")
                            params.append(aluminum_pct)
                        if copper_pct is not None:
                            updates.append("copper_pct = ?")
                            params.append(copper_pct)
                        if wood_pct is not None:
                            updates.append("wood_pct = ?")
                            params.append(wood_pct)
                        if auto_pct is not None:
                            updates.append("auto_pct = ?")
                            params.append(auto_pct)
                        if sec301:
                            updates.append("sec301_exclusion_tariff = ?")
                            params.append(sec301)

                        # Handle custom fields
                        for field_name in self.custom_fields.keys():
                            if field_name in mapping:
                                value = str(row.get(field_name, '')).strip()
                                if value:
                                    updates.append(f"{field_name} = ?")
                                    params.append(value)

                        updates.append("last_updated = ?")
                        params.append(datetime.now().isoformat())

                        if updates:
                            params.append(part_number)
                            cursor.execute(f"UPDATE parts SET {', '.join(updates)} WHERE part_number = ?", params)
                            updated += 1
                    else:
                        # Insert new part - build dynamic column list for custom fields
                        base_columns = [
                            'part_number', 'description', 'hts_code', 'country_origin', 'mid', 'client_code',
                            'steel_pct', 'aluminum_pct', 'copper_pct', 'wood_pct', 'auto_pct',
                            'qty_unit', 'sec301_exclusion_tariff', 'last_updated'
                        ]
                        base_values = [
                            part_number, description, hts_code, country_origin, mid, client_code,
                            steel_pct or 0, aluminum_pct or 0, copper_pct or 0, wood_pct or 0, auto_pct or 0,
                            qty_unit, sec301, datetime.now().isoformat()
                        ]

                        # Add custom fields
                        for field_name in self.custom_fields.keys():
                            if field_name in mapping:
                                value = str(row.get(field_name, '')).strip() or None
                                base_columns.append(field_name)
                                base_values.append(value)

                        placeholders = ', '.join(['?' for _ in base_columns])
                        columns_str = ', '.join(base_columns)

                        cursor.execute(f"""
                            INSERT INTO parts ({columns_str}) VALUES ({placeholders})
                        """, base_values)
                        inserted += 1
                except Exception:
                    skipped += 1

            # Commit all changes
            self.db.conn.commit()
            progress.close()

            # Show summary
            QMessageBox.information(
                self, "Import Complete",
                f"Import completed!\n\n"
                f"Total rows: {total_rows}\n"
                f"New parts inserted: {inserted}\n"
                f"Existing parts updated: {updated}\n"
                f"Skipped (no part number or errors): {skipped}"
            )

            self.refresh_data()
            self.data_changed.emit()

            self.import_status_label.setText(f"Import complete: {inserted} inserted, {updated} updated")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

