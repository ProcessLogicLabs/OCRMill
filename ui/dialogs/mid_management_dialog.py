"""
MID Management Dialog for OCRMill - TariffMill Format Compatible.

Provides management of Manufacturer IDs (MIDs) with:
- Import from Excel/CSV
- Filter/Search by Customer ID, MID, Manufacturer
- Add/Edit/Delete MID entries
- Export to Excel
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QMessageBox, QFileDialog,
    QAbstractItemView
)
from PyQt6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase


class MIDManagementDialog(QDialog):
    """
    MID Management dialog matching TariffMill's format.

    Features:
    - Import MID List section with file selection and import
    - Filter row with Customer ID, MID, and Manufacturer search fields
    - Data table with columns: Manufacturer Name, MID, Customer ID, Related Parties
    - Action buttons: Add MID, Delete Selected, Clear All, Export to Excel, Save Changes
    """

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.import_file_path = None

        self.setWindowTitle("MID Management")
        self.setMinimumSize(900, 600)
        self.setModal(True)

        self._setup_ui()
        self._apply_styling()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI matching TariffMill format."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title = QLabel("<h2>Manufacturer ID (MID) Management</h2>")
        layout.addWidget(title)

        # Import section
        import_group = QGroupBox("Import MID List")
        import_layout = QHBoxLayout(import_group)

        self.import_path_label = QLabel("No file selected")
        self.import_path_label.setStyleSheet("color: gray;")
        import_layout.addWidget(self.import_path_label, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_import_file)
        import_layout.addWidget(browse_btn)

        import_btn = QPushButton("Import")
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._import_file)
        import_layout.addWidget(import_btn)

        layout.addWidget(import_group)

        # Info label
        info_label = QLabel(
            "Expected Excel columns: <b>Manufacturer Name</b>, <b>MID</b>, "
            "<b>Customer ID</b>, <b>Related Parties</b> (Y/N)"
        )
        info_label.setStyleSheet("color: #666; margin: 5px;")
        layout.addWidget(info_label)

        # MID Table section
        table_group = QGroupBox("Current MID List")
        table_layout = QVBoxLayout(table_group)

        # Filter/Search row
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Customer ID:"))
        self.customer_filter = QLineEdit()
        self.customer_filter.setPlaceholderText("Filter...")
        self.customer_filter.setMaximumWidth(150)
        self.customer_filter.returnPressed.connect(self._filter_table)
        filter_layout.addWidget(self.customer_filter)

        filter_layout.addWidget(QLabel("MID:"))
        self.mid_filter = QLineEdit()
        self.mid_filter.setPlaceholderText("Search...")
        self.mid_filter.setMaximumWidth(180)
        self.mid_filter.returnPressed.connect(self._filter_table)
        filter_layout.addWidget(self.mid_filter)

        filter_layout.addWidget(QLabel("Manufacturer:"))
        self.manufacturer_filter = QLineEdit()
        self.manufacturer_filter.setPlaceholderText("Search...")
        self.manufacturer_filter.returnPressed.connect(self._filter_table)
        filter_layout.addWidget(self.manufacturer_filter)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("primaryButton")
        search_btn.clicked.connect(self._filter_table)
        filter_layout.addWidget(search_btn)

        clear_filter_btn = QPushButton("Clear Filters")
        clear_filter_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_filter_btn)

        table_layout.addLayout(filter_layout)

        # MID Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Manufacturer Name", "MID", "Customer ID", "Related Parties"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)

        # Table action buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add MID")
        add_btn.clicked.connect(self._add_row)
        btn_layout.addWidget(add_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(delete_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self._export_to_excel)
        btn_layout.addWidget(export_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_changes)
        btn_layout.addWidget(save_btn)

        table_layout.addLayout(btn_layout)
        layout.addWidget(table_group)

        # Bottom close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _apply_styling(self):
        """Apply TariffMill-style styling."""
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
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
                background-color: #e0e0e0;
                border: 1px solid #ccc;
            }

            QPushButton:hover {
                background-color: #d0d0d0;
            }

            QPushButton#primaryButton {
                background-color: #5f9ea0;
                color: white;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background-color: #4f8e90;
            }

            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }

            QLineEdit:focus {
                border-color: #5f9ea0;
            }

            QTableWidget {
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }

            QTableWidget::item:selected {
                background-color: #5f9ea0;
                color: white;
            }

            QHeaderView::section {
                background-color: #e8f4f5;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #ccc;
                font-weight: bold;
            }
        """)

    def _load_data(self):
        """Load MID data from database into table."""
        try:
            mids = self.db.get_all_mids()
            self.table.setRowCount(0)

            for entry in mids:
                self._add_table_row(
                    entry.get('manufacturer_name', ''),
                    entry.get('mid', ''),
                    entry.get('customer_id', ''),
                    entry.get('related_parties', 'N')
                )
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load MID data:\n{e}")

    def _add_table_row(self, manufacturer_name: str = "", mid: str = "",
                       customer_id: str = "", related_parties: str = "N"):
        """Add a row to the table with the given data."""
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        self.table.setItem(row_idx, 0, QTableWidgetItem(manufacturer_name))
        self.table.setItem(row_idx, 1, QTableWidgetItem(mid))
        self.table.setItem(row_idx, 2, QTableWidgetItem(customer_id))

        # Related parties as combo box
        combo = QComboBox()
        combo.addItems(['N', 'Y'])
        combo.setCurrentText(related_parties if related_parties in ('Y', 'N') else 'N')
        self.table.setCellWidget(row_idx, 3, combo)

    def _browse_import_file(self):
        """Browse for MID import file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select MID List File", "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.import_file_path = file_path
            self.import_path_label.setText(Path(file_path).name)
            self.import_path_label.setStyleSheet("color: black;")

    def _import_file(self):
        """Import MID list from selected file."""
        if not self.import_file_path:
            QMessageBox.warning(self, "No File", "Please select a file to import first.")
            return

        try:
            # Ask about import mode if there's existing data
            existing_count = self.table.rowCount()
            append_mode = True

            if existing_count > 0:
                reply = QMessageBox.question(
                    self, "Import Mode",
                    f"There are {existing_count} existing MID records.\n\n"
                    "Do you want to ADD to the existing list?\n\n"
                    "Click 'Yes' to append new records\n"
                    "Click 'No' to replace all records",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No |
                    QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                append_mode = (reply == QMessageBox.StandardButton.Yes)

            # Import from file
            imported, skipped = self.db.import_mids_from_file(
                self.import_file_path, append_mode=append_mode
            )

            # Reload table
            self._load_data()

            msg = f"Imported {imported} MID records."
            if skipped > 0:
                msg += f"\nSkipped {skipped} duplicate MIDs."
            msg += "\n\nData has been saved to database."
            QMessageBox.information(self, "Import Complete", msg)

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import file:\n{str(e)}")

    def _add_row(self):
        """Add a new empty row to the table."""
        self._add_table_row()
        row_idx = self.table.rowCount() - 1
        self.table.setCurrentCell(row_idx, 0)
        self.table.editItem(self.table.item(row_idx, 0))

    def _delete_selected(self):
        """Delete selected MID rows."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select rows to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(selected_rows)} selected MID(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for row in sorted(selected_rows, reverse=True):
                self.table.removeRow(row)

    def _clear_all(self):
        """Clear all MIDs from the table."""
        if self.table.rowCount() == 0:
            return

        reply = QMessageBox.question(
            self, "Confirm Clear",
            "Clear all MIDs from the table?\n\n"
            "This will not delete from database until you click 'Save Changes'.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)

    def _save_changes(self):
        """Save table data to database."""
        try:
            mids = []
            for row in range(self.table.rowCount()):
                manufacturer_item = self.table.item(row, 0)
                mid_item = self.table.item(row, 1)
                customer_item = self.table.item(row, 2)
                combo = self.table.cellWidget(row, 3)

                mid = mid_item.text().strip() if mid_item else ""
                if not mid:
                    continue

                mids.append({
                    'manufacturer_name': manufacturer_item.text().strip() if manufacturer_item else "",
                    'mid': mid,
                    'customer_id': customer_item.text().strip() if customer_item else "",
                    'related_parties': combo.currentText() if combo else 'N'
                })

            saved = self.db.save_mids_batch(mids)
            QMessageBox.information(self, "Saved", f"Saved {saved} MID records to database.")

        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{str(e)}")

    def _export_to_excel(self):
        """Export MIDs to Excel file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export MID List",
            "MID_List.xlsx",
            "Excel Files (*.xlsx)"
        )
        if file_path:
            try:
                count = self.db.export_mids_to_excel(file_path)
                QMessageBox.information(
                    self, "Export Complete",
                    f"Exported {count} MID records to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def _filter_table(self):
        """Filter table based on search fields."""
        customer_filter = self.customer_filter.text().strip().upper()
        mid_filter = self.mid_filter.text().strip().upper()
        manufacturer_filter = self.manufacturer_filter.text().strip().upper()

        for row in range(self.table.rowCount()):
            manufacturer_item = self.table.item(row, 0)
            mid_item = self.table.item(row, 1)
            customer_item = self.table.item(row, 2)

            manufacturer = manufacturer_item.text().upper() if manufacturer_item else ''
            mid = mid_item.text().upper() if mid_item else ''
            customer_id = customer_item.text().upper() if customer_item else ''

            # Determine if row should be visible (all filters must match)
            show_row = True
            if customer_filter and customer_filter not in customer_id:
                show_row = False
            if mid_filter and mid_filter not in mid:
                show_row = False
            if manufacturer_filter and manufacturer_filter not in manufacturer:
                show_row = False

            self.table.setRowHidden(row, not show_row)

    def _clear_filters(self):
        """Clear all filter fields and show all rows."""
        self.customer_filter.clear()
        self.mid_filter.clear()
        self.manufacturer_filter.clear()

        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, False)
