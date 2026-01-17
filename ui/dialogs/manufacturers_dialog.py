"""
Manufacturers/MID Management Dialog for OCRMill.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog,
    QAbstractItemView, QFormLayout, QTextEdit
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase


class ManufacturersTableModel(QAbstractTableModel):
    """Table model for manufacturers data."""

    COLUMNS = [
        ("id", "ID", 40),
        ("company_name", "Company Name", 200),
        ("country", "Country", 80),
        ("mid", "MID", 150),
        ("notes", "Notes", 200),
    ]

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self._data = []

    def refresh(self, search_term: str = ""):
        """Refresh data from database."""
        self.beginResetModel()
        if search_term:
            self._data = self.db.search_manufacturers(search_term)
        else:
            self._data = self.db.get_all_manufacturers()
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
            mfr = self._data[index.row()]
            value = mfr.get(col_name, '')
            return str(value) if value else ''

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section][1]
        return None

    def get_manufacturer_at_row(self, row: int):
        """Get manufacturer data at specified row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class ManufacturerEditDialog(QDialog):
    """Dialog for adding/editing a manufacturer."""

    def __init__(self, db: PartsDatabase, manufacturer: dict = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.manufacturer = manufacturer
        self.saved = False

        title = "Edit Manufacturer" if manufacturer else "Add Manufacturer"
        self.setWindowTitle(title)
        self.setMinimumSize(450, 280)
        self.setModal(True)

        self._setup_ui()

        if manufacturer:
            self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        self.company_edit = QLineEdit()
        form.addRow("Company Name:", self.company_edit)

        self.country_edit = QLineEdit()
        self.country_edit.setMaxLength(2)
        self.country_edit.setPlaceholderText("e.g., CZ, US, BR")
        form.addRow("Country Code:", self.country_edit)

        self.mid_edit = QLineEdit()
        self.mid_edit.setPlaceholderText("Manufacturer Identification Code")
        form.addRow("MID:", self.mid_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_data(self):
        """Load existing manufacturer data."""
        self.company_edit.setText(self.manufacturer.get('company_name', ''))
        self.country_edit.setText(self.manufacturer.get('country', ''))
        self.mid_edit.setText(self.manufacturer.get('mid', ''))
        self.notes_edit.setPlainText(self.manufacturer.get('notes', '') or '')

    def _save(self):
        """Save the manufacturer."""
        company_name = self.company_edit.text().strip()
        if not company_name:
            QMessageBox.warning(self, "Validation Error", "Company name is required.")
            return

        country = self.country_edit.text().strip().upper()
        mid = self.mid_edit.text().strip()
        notes = self.notes_edit.toPlainText().strip()

        try:
            if self.manufacturer:
                # Update existing
                self.db.update_manufacturer(
                    self.manufacturer['id'],
                    company_name,
                    country,
                    mid,
                    notes
                )
            else:
                # Add new
                self.db.add_manufacturer(company_name, country, mid, notes)

            self.saved = True
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save manufacturer:\n{e}")


class ManufacturersDialog(QDialog):
    """Dialog for managing manufacturers/MID list."""

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db

        self.setWindowTitle("Manufacturers / MID Management")
        self.setMinimumSize(800, 500)
        self.setModal(True)

        self._setup_ui()
        self._refresh_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_manufacturer)
        toolbar.addWidget(add_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_manufacturer)
        toolbar.addWidget(edit_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_manufacturer)
        toolbar.addWidget(delete_btn)

        toolbar.addWidget(QLabel(" | "))

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_manufacturers)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_manufacturers)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Company name or MID...")
        self.search_edit.returnPressed.connect(self._search)
        toolbar.addWidget(self.search_edit)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        toolbar.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_search)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # Table
        self.model = ManufacturersTableModel(self.db)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._edit_manufacturer)

        # Set column widths
        for i, (_, _, width) in enumerate(ManufacturersTableModel.COLUMNS):
            self.table.setColumnWidth(i, width)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)

        layout.addWidget(self.table)

        # Count label
        self.count_label = QLabel("0 manufacturers")
        layout.addWidget(self.count_label)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _refresh_data(self, search_term: str = ""):
        """Refresh manufacturer data."""
        self.model.refresh(search_term)
        self.count_label.setText(f"{self.model.rowCount()} manufacturers")

    def _search(self):
        """Search manufacturers."""
        self._refresh_data(self.search_edit.text().strip())

    def _clear_search(self):
        """Clear search and refresh."""
        self.search_edit.clear()
        self._refresh_data()

    def _add_manufacturer(self):
        """Add a new manufacturer."""
        dialog = ManufacturerEditDialog(self.db, parent=self)
        if dialog.exec() and dialog.saved:
            self._refresh_data()

    def _edit_manufacturer(self):
        """Edit the selected manufacturer."""
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select a manufacturer to edit.")
            return

        mfr = self.model.get_manufacturer_at_row(index.row())
        if mfr:
            dialog = ManufacturerEditDialog(self.db, manufacturer=mfr, parent=self)
            if dialog.exec() and dialog.saved:
                self._refresh_data()

    def _delete_manufacturer(self):
        """Delete the selected manufacturer."""
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.warning(self, "No Selection", "Please select a manufacturer to delete.")
            return

        mfr = self.model.get_manufacturer_at_row(index.row())
        if not mfr:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete manufacturer '{mfr.get('company_name', '')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_manufacturer(mfr['id'])
                self._refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete:\n{e}")

    def _import_manufacturers(self):
        """Import manufacturers from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Manufacturers",
            "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        if file_path:
            try:
                count = self.db.import_manufacturers_from_excel(file_path)
                QMessageBox.information(self, "Import Complete", f"Imported {count} manufacturers.")
                self._refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import:\n{e}")

    def _export_manufacturers(self):
        """Export manufacturers to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Manufacturers",
            "manufacturers.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            try:
                import csv
                manufacturers = self.db.get_all_manufacturers()

                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=['company_name', 'country', 'mid', 'notes']
                    )
                    writer.writeheader()
                    for mfr in manufacturers:
                        writer.writerow({
                            'company_name': mfr.get('company_name', ''),
                            'country': mfr.get('country', ''),
                            'mid': mfr.get('mid', ''),
                            'notes': mfr.get('notes', ''),
                        })

                QMessageBox.information(self, "Export Complete", f"Exported to:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")
