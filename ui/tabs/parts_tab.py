"""
Parts Database Tab for OCRMill.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableView, QHeaderView,
    QRadioButton, QButtonGroup, QMenu, QMessageBox,
    QFileDialog, QPlainTextEdit, QGroupBox, QFormLayout,
    QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QAction

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase


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

        # Part History tab
        history_widget = self._create_history_tab()
        self.sub_tabs.addTab(history_widget, "Part History")

        # Statistics tab
        stats_widget = self._create_stats_tab()
        self.sub_tabs.addTab(stats_widget, "Statistics")

        # HTS Codes tab
        hts_widget = self._create_hts_tab()
        self.sub_tabs.addTab(hts_widget, "HTS Codes")

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

    def _create_history_tab(self) -> QWidget:
        """Create the part history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Part selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("Part Number:"))
        self.history_part_edit = QLineEdit()
        self.history_part_edit.setPlaceholderText("Enter part number...")
        select_layout.addWidget(self.history_part_edit)

        view_btn = QPushButton("View History")
        view_btn.clicked.connect(self._view_part_history)
        select_layout.addWidget(view_btn)
        select_layout.addStretch()
        layout.addLayout(select_layout)

        # History display
        self.history_text = QPlainTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(self.history_text)

        return widget

    def _create_stats_tab(self) -> QWidget:
        """Create the statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Stats display
        stats_group = QGroupBox("Database Statistics")
        stats_layout = QFormLayout(stats_group)

        self.stats_labels = {}
        stats_items = [
            ("total_parts", "Total Parts:"),
            ("parts_with_hts", "Parts with HTS:"),
            ("parts_without_hts", "Parts without HTS:"),
            ("total_occurrences", "Total Occurrences:"),
            ("unique_projects", "Unique Projects:"),
            ("unique_invoices", "Unique Invoices:"),
        ]

        for key, label in stats_items:
            value_label = QLabel("--")
            self.stats_labels[key] = value_label
            stats_layout.addRow(label, value_label)

        layout.addWidget(stats_group)

        # Refresh button
        refresh_btn = QPushButton("Refresh Statistics")
        refresh_btn.clicked.connect(self._refresh_stats)
        layout.addWidget(refresh_btn)

        layout.addStretch()

        return widget

    def _create_hts_tab(self) -> QWidget:
        """Create the HTS codes management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Info
        info = QLabel("Manage HTS codes for parts. Import HTS mappings or manually set codes.")
        layout.addWidget(info)

        # Actions
        actions_layout = QHBoxLayout()

        import_hts_btn = QPushButton("Import HTS Mappings")
        import_hts_btn.clicked.connect(self._import_hts)
        actions_layout.addWidget(import_hts_btn)

        set_hts_btn = QPushButton("Set HTS for Selected Part")
        set_hts_btn.clicked.connect(self._set_hts_for_selected)
        actions_layout.addWidget(set_hts_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # HTS codes list
        layout.addWidget(QLabel("Recent HTS Codes:"))
        self.hts_list = QPlainTextEdit()
        self.hts_list.setReadOnly(True)
        layout.addWidget(self.hts_list)

        return widget

    def _connect_signals(self):
        """Connect internal signals."""
        self.filter_group.buttonClicked.connect(self._on_filter_changed)

    # ----- Data operations -----

    @pyqtSlot()
    def refresh_data(self):
        """Refresh parts data from database."""
        self._apply_filter()
        self._update_counts()
        self._refresh_stats()

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
        """Show part history in the history tab."""
        part_number = part.get('part_number', '')
        self.history_part_edit.setText(part_number)
        self._view_part_history()
        self.sub_tabs.setCurrentIndex(1)  # Switch to History tab

    def _view_part_history(self):
        """View history for the entered part number."""
        part_number = self.history_part_edit.text().strip()
        if not part_number:
            return

        history = self.db.get_part_history(part_number)

        if not history:
            self.history_text.setPlainText(f"No history found for part: {part_number}")
            return

        lines = [f"History for Part: {part_number}\n"]
        lines.append("=" * 50)

        for record in history:
            lines.append(f"\nDate: {record.get('processing_date', 'N/A')}")
            lines.append(f"Invoice: {record.get('invoice_number', 'N/A')}")
            lines.append(f"Project: {record.get('project_number', 'N/A')}")
            lines.append(f"Quantity: {record.get('quantity', 'N/A')}")
            lines.append(f"Total Price: ${record.get('total_price', 0):,.2f}")
            lines.append("-" * 30)

        self.history_text.setPlainText("\n".join(lines))

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

    # ----- Statistics -----

    def _refresh_stats(self):
        """Refresh database statistics."""
        try:
            stats = self.db.get_statistics()

            self.stats_labels['total_parts'].setText(str(stats.get('total_parts', 0)))
            self.stats_labels['parts_with_hts'].setText(str(stats.get('parts_with_hts', 0)))
            self.stats_labels['parts_without_hts'].setText(str(stats.get('parts_without_hts', 0)))
            self.stats_labels['total_occurrences'].setText(str(stats.get('total_occurrences', 0)))
            self.stats_labels['unique_projects'].setText(str(stats.get('unique_projects', 0)))
            self.stats_labels['unique_invoices'].setText(str(stats.get('unique_invoices', 0)))
        except Exception:
            pass
