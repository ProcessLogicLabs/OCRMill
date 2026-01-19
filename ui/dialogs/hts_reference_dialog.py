"""
HTS Reference Dialog for OCRMill.
Dark-themed dialog for looking up HTS codes.
"""

import sys
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog,
    QAbstractItemView, QGroupBox, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase
from core.theme_manager import get_theme_manager

# Path to the HTS database (copied from TariffMill)
HTS_DB_PATH = Path(__file__).parent.parent.parent / "Resources" / "hts.db"


class HTSTableModel(QAbstractTableModel):
    """Table model for HTS codes data."""

    COLUMNS = [
        ("full_code", "HTS Code", 120),
        ("description", "Description", 400),
        ("general_rate", "General Rate", 100),
        ("unit_of_quantity", "Unit", 80),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._hts_conn = None
        self._connect_hts_db()

    def _connect_hts_db(self):
        """Connect to the HTS database."""
        try:
            if HTS_DB_PATH.exists():
                self._hts_conn = sqlite3.connect(str(HTS_DB_PATH))
        except Exception:
            self._hts_conn = None

    def refresh(self, search_term: str = ""):
        """Refresh data from HTS database."""
        self.beginResetModel()
        try:
            if self._hts_conn is None:
                self._connect_hts_db()

            if self._hts_conn is None:
                self._data = []
                self.endResetModel()
                return

            cursor = self._hts_conn.cursor()
            if search_term:
                # Search by code or description
                cursor.execute("""
                    SELECT full_code, description, general_rate, unit_of_quantity
                    FROM hts_codes
                    WHERE full_code LIKE ? OR description LIKE ?
                    ORDER BY full_code
                    LIMIT 500
                """, (f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute("""
                    SELECT full_code, description, general_rate, unit_of_quantity
                    FROM hts_codes
                    ORDER BY full_code
                    LIMIT 500
                """)

            self._data = [
                {
                    'full_code': row[0] or '',
                    'description': row[1] or '',
                    'general_rate': row[2] or '',
                    'unit_of_quantity': row[3] or ''
                }
                for row in cursor.fetchall()
            ]
        except Exception:
            self._data = []
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            col_name = self.COLUMNS[index.column()][0]
            hts = self._data[index.row()]
            value = hts.get(col_name, '')
            return str(value) if value else ''

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][1]
        return None

    def get_hts_at_row(self, row: int):
        """Get HTS data at specified row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def get_total_count(self):
        """Get total count of HTS codes in database."""
        try:
            if self._hts_conn is None:
                return 0
            cursor = self._hts_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM hts_codes")
            return cursor.fetchone()[0]
        except Exception:
            return 0


class HTSReferenceDialog(QDialog):
    """
    HTS Reference lookup dialog with theme support.
    """

    def __init__(self, db: PartsDatabase = None, parent=None):
        super().__init__(parent)
        self.db = db  # Keep for compatibility, but HTS uses its own database
        self.selected_hts = None
        self.theme_manager = get_theme_manager()

        self.setObjectName("HTSReferenceDialog")
        self.setWindowTitle("HTS Reference")
        self.setMinimumSize(1000, 700)
        self.setModal(True)

        self._setup_ui()
        self._apply_styling()
        self._refresh_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("HTS Code Reference")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # Info box
        info_group = QGroupBox("Quick Lookup")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("Search by HTS code or description:"), 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter HTS code or keywords...")
        self.search_edit.returnPressed.connect(self._search)
        info_layout.addWidget(self.search_edit, 0, 1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        info_layout.addWidget(search_btn, 0, 2)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_search)
        info_layout.addWidget(clear_btn, 0, 3)

        layout.addWidget(info_group)

        # Table
        self.model = HTSTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._select_hts)

        # Set column widths
        for i, (_, _, width) in enumerate(HTSTableModel.COLUMNS):
            self.table.setColumnWidth(i, width)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        layout.addWidget(self.table, 1)

        # Count and info
        info_row = QHBoxLayout()
        self.count_label = QLabel("0 codes")
        self.count_label.setObjectName("infoLabel")
        info_row.addWidget(self.count_label)

        info_row.addStretch()

        info_text = QLabel("Double-click to select a code, or use buttons below")
        info_text.setObjectName("infoLabel")
        info_row.addWidget(info_text)

        layout.addLayout(info_row)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        import_btn = QPushButton("Import HTS File")
        import_btn.clicked.connect(self._import_hts)
        btn_layout.addWidget(import_btn)

        btn_layout.addStretch()

        select_btn = QPushButton("Select Code")
        select_btn.clicked.connect(self._select_hts)
        btn_layout.addWidget(select_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _refresh_data(self, search_term: str = ""):
        """Refresh HTS data."""
        self.model.refresh(search_term)
        count = self.model.rowCount()
        total = self.model.get_total_count()
        if count >= 500:
            self.count_label.setText(f"Showing first 500 of {total:,} codes (search to filter)")
        else:
            self.count_label.setText(f"{count:,} codes (of {total:,} total)")

    def _search(self):
        """Search HTS codes."""
        self._refresh_data(self.search_edit.text().strip())

    def _clear_search(self):
        """Clear search and refresh."""
        self.search_edit.clear()
        self._refresh_data()

    def _select_hts(self):
        """Select the current HTS code."""
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select an HTS code.")
            return

        hts = self.model.get_hts_at_row(index.row())
        if hts:
            self.selected_hts = hts.get('full_code', '')
            self.accept()

    def _import_hts(self):
        """Import HTS codes from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import HTS Codes",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if file_path:
            try:
                count = self.db.load_hts_mapping(file_path)
                QMessageBox.information(self, "Import Complete", f"Imported {count} HTS codes.")
                self._refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    def get_selected_code(self):
        """Get the selected HTS code."""
        return self.selected_hts

    def _apply_styling(self):
        """Apply theme-aware styling."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }
                QLabel {
                    color: #cccccc;
                }
                QLabel#titleLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #6b5b95;
                }
                QLabel#infoLabel {
                    color: #999999;
                    font-size: 9pt;
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
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    background-color: #3c3c3c;
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
                QPushButton#closeButton {
                    background-color: #3c3c3c;
                    color: #cccccc;
                    border: 1px solid #555;
                }
                QPushButton#closeButton:hover {
                    background-color: #4c4c4c;
                }
                QTableView {
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    gridline-color: #3c3c3c;
                    alternate-background-color: #2d2d2d;
                    selection-background-color: #094771;
                    selection-color: white;
                }
                QTableView::item:hover {
                    background-color: #2a2d2e;
                }
                QHeaderView::section {
                    background-color: #2d2d2d;
                    color: #4ec9b0;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #3c3c3c;
                    border-bottom: 1px solid #3c3c3c;
                    font-weight: bold;
                }
                QScrollBar:vertical {
                    background: #2d2d2d;
                    width: 14px;
                }
                QScrollBar::handle:vertical {
                    background: #555;
                    border-radius: 7px;
                    margin: 2px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #666;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                }
                QLabel {
                    color: #333;
                }
                QLabel#titleLabel {
                    font-size: 18px;
                    font-weight: bold;
                    color: #6b5b95;
                }
                QLabel#infoLabel {
                    color: #666;
                    font-size: 9pt;
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
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    background-color: white;
                }
                QLineEdit:focus {
                    border: 1px solid #5f9ea0;
                }
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #5f9ea0;
                    color: white;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4f8e90;
                }
                QPushButton#closeButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #d0d0d0;
                }
                QPushButton#closeButton:hover {
                    background-color: #e0e0e0;
                }
                QTableView {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    color: #333;
                    border: 1px solid #d0d0d0;
                    gridline-color: #e0e0e0;
                    selection-background-color: #5f9ea0;
                    selection-color: white;
                }
                QTableView::item:hover {
                    background-color: #e8f4f4;
                }
                QHeaderView::section {
                    background-color: #e8f4f4;
                    color: #5f9ea0;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #d0d0d0;
                    border-bottom: 1px solid #d0d0d0;
                    font-weight: bold;
                }
                QScrollBar:vertical {
                    background: #f8f9fa;
                    width: 14px;
                }
                QScrollBar::handle:vertical {
                    background: #d0d0d0;
                    border-radius: 7px;
                    margin: 2px;
                    min-height: 30px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #7ab8ba;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                }
            """)
