"""
Output Column Mapping Dialog for OCRMill.

Allows users to configure:
- Which columns appear in exported CSV files
- Column names (rename columns)
- Column order (drag to reorder)
- Save/load mapping profiles
- Export options (split by invoice, etc.)
"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QGroupBox, QFormLayout, QCheckBox, QPushButton, QLabel,
    QLineEdit, QScrollArea, QFrame, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QColorDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon


# Default column definitions with display names
DEFAULT_COLUMNS = [
    ('invoice_number', 'Invoice Number', True),
    ('project_number', 'Project Number', True),
    ('part_number', 'Part Number', True),
    ('description', 'Description', True),
    ('mid', 'MID', True),
    ('country_origin', 'Country Origin', True),
    ('hts_code', 'HTS Code', True),
    ('quantity', 'Quantity', True),
    ('total_price', 'Total Price', True),
    ('po_number', 'PO Number', False),
    ('packages', 'Packages', False),
    ('net_weight', 'Net Weight', False),
    ('gross_weight', 'Gross Weight', False),
    ('dimensions', 'Dimensions', False),
    ('unit_price', 'Unit Price', False),
    ('bol_gross_weight', 'BOL Gross Weight', False),
]


class ColumnMappingRow(QWidget):
    """A single row in the column mapping list."""

    moved_up = pyqtSignal(object)
    moved_down = pyqtSignal(object)

    def __init__(self, internal_name: str, display_name: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.internal_name = internal_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)

        # Up/Down buttons
        up_btn = QPushButton("▲")
        up_btn.setFixedSize(24, 24)
        up_btn.clicked.connect(lambda: self.moved_up.emit(self))
        layout.addWidget(up_btn)

        down_btn = QPushButton("▼")
        down_btn.setFixedSize(24, 24)
        down_btn.clicked.connect(lambda: self.moved_down.emit(self))
        layout.addWidget(down_btn)

        # Enable checkbox
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(enabled)
        layout.addWidget(self.enabled_check)

        # Internal name label
        internal_label = QLabel(f"{internal_name}:")
        internal_label.setFixedWidth(150)
        internal_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(internal_label)

        # Display name edit
        self.display_edit = QLineEdit(display_name)
        self.display_edit.setMinimumWidth(200)
        layout.addWidget(self.display_edit, 1)

    def get_mapping(self) -> dict:
        """Get the mapping configuration for this column."""
        return {
            'internal_name': self.internal_name,
            'display_name': self.display_edit.text(),
            'enabled': self.enabled_check.isChecked()
        }

    def set_mapping(self, display_name: str, enabled: bool):
        """Set the mapping configuration for this column."""
        self.display_edit.setText(display_name)
        self.enabled_check.setChecked(enabled)


class OutputMappingDialog(QDialog):
    """Dialog for configuring output column mapping."""

    mapping_changed = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("Output Column Mapping")
        self.setMinimumSize(700, 600)
        self.setModal(True)

        self._setup_ui()
        self._load_settings()
        self._apply_styling()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Output Column Mapping")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # Profile selection
        profile_group = QGroupBox()
        profile_group.setStyleSheet("QGroupBox { border: none; }")
        profile_layout = QHBoxLayout(profile_group)

        profile_layout.addWidget(QLabel("Saved Profiles:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.addItem("-- Select Profile --")
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        profile_layout.addWidget(self.profile_combo)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_to_default)
        profile_layout.addWidget(reset_btn)

        save_new_btn = QPushButton("Save As New...")
        save_new_btn.clicked.connect(self._save_as_new_profile)
        profile_layout.addWidget(save_new_btn)

        update_btn = QPushButton("Update Profile")
        update_btn.clicked.connect(self._update_profile)
        profile_layout.addWidget(update_btn)

        delete_btn = QPushButton("Delete Profile")
        delete_btn.clicked.connect(self._delete_profile)
        profile_layout.addWidget(delete_btn)

        profile_layout.addStretch()
        layout.addWidget(profile_group)

        # Options row
        options_layout = QHBoxLayout()

        # Export Options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout(export_group)

        self.split_by_invoice_check = QCheckBox("Split by Invoice Number")
        self.split_by_invoice_check.setToolTip("Creates separate files per invoice.\nRequires Invoice Number mapping.")
        export_layout.addWidget(self.split_by_invoice_check)

        options_layout.addWidget(export_group)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Column mapping section
        mapping_group = QGroupBox("Column Name Mapping (drag to reorder)")
        mapping_layout = QVBoxLayout(mapping_group)

        # Scroll area for column rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.columns_widget = QWidget()
        self.columns_layout = QVBoxLayout(self.columns_widget)
        self.columns_layout.setSpacing(2)

        self.column_rows = []

        scroll.setWidget(self.columns_widget)
        mapping_layout.addWidget(scroll)

        layout.addWidget(mapping_group, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(apply_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _apply_styling(self):
        """Apply styling to the dialog."""
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #008B8B;
            }
            QPushButton {
                background-color: #008B8B;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #006666;
            }
            QPushButton:pressed {
                background-color: #004d4d;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

    def _load_settings(self):
        """Load current mapping settings."""
        # Load saved profiles
        profiles = self.config.get_output_mapping_profiles()
        self.profile_combo.clear()
        self.profile_combo.addItem("-- Select Profile --")
        for profile_name in profiles.keys():
            self.profile_combo.addItem(profile_name)

        # Load current mapping
        mapping = self.config.get_output_column_mapping()
        self._populate_columns(mapping)

        # Load export options
        self.split_by_invoice_check.setChecked(
            self.config.get_export_option('split_by_invoice', False)
        )

    def _populate_columns(self, mapping: dict = None):
        """Populate column rows from mapping or defaults."""
        # Clear existing rows
        for row in self.column_rows:
            row.setParent(None)
            row.deleteLater()
        self.column_rows.clear()

        if mapping and 'columns' in mapping:
            # Use saved mapping
            for col_config in mapping['columns']:
                row = ColumnMappingRow(
                    col_config['internal_name'],
                    col_config['display_name'],
                    col_config.get('enabled', True),
                    self
                )
                row.moved_up.connect(self._move_row_up)
                row.moved_down.connect(self._move_row_down)
                self.column_rows.append(row)
                self.columns_layout.addWidget(row)
        else:
            # Use defaults
            for internal_name, display_name, enabled in DEFAULT_COLUMNS:
                row = ColumnMappingRow(internal_name, display_name, enabled, self)
                row.moved_up.connect(self._move_row_up)
                row.moved_down.connect(self._move_row_down)
                self.column_rows.append(row)
                self.columns_layout.addWidget(row)

        self.columns_layout.addStretch()

    def _move_row_up(self, row):
        """Move a column row up in the list."""
        idx = self.column_rows.index(row)
        if idx > 0:
            self.column_rows[idx], self.column_rows[idx-1] = self.column_rows[idx-1], self.column_rows[idx]
            self._refresh_column_layout()

    def _move_row_down(self, row):
        """Move a column row down in the list."""
        idx = self.column_rows.index(row)
        if idx < len(self.column_rows) - 1:
            self.column_rows[idx], self.column_rows[idx+1] = self.column_rows[idx+1], self.column_rows[idx]
            self._refresh_column_layout()

    def _refresh_column_layout(self):
        """Refresh the column layout after reordering."""
        # Remove all widgets
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Re-add in new order
        for row in self.column_rows:
            self.columns_layout.addWidget(row)
        self.columns_layout.addStretch()

    def _get_current_mapping(self) -> dict:
        """Get the current mapping configuration."""
        columns = []
        for row in self.column_rows:
            columns.append(row.get_mapping())

        return {
            'columns': columns,
            'split_by_invoice': self.split_by_invoice_check.isChecked()
        }

    def _reset_to_default(self):
        """Reset mapping to default values."""
        reply = QMessageBox.question(
            self, "Reset to Default",
            "Reset all column mappings to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._populate_columns(None)
            self.split_by_invoice_check.setChecked(False)

    def _on_profile_selected(self, profile_name: str):
        """Load selected profile."""
        if profile_name == "-- Select Profile --":
            return

        profiles = self.config.get_output_mapping_profiles()
        if profile_name in profiles:
            mapping = profiles[profile_name]
            self._populate_columns(mapping)
            self.split_by_invoice_check.setChecked(
                mapping.get('split_by_invoice', False)
            )

    def _save_as_new_profile(self):
        """Save current mapping as a new profile."""
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, "Save Profile",
            "Enter profile name:"
        )
        if ok and name:
            mapping = self._get_current_mapping()
            self.config.save_output_mapping_profile(name, mapping)

            # Update combo box
            if self.profile_combo.findText(name) == -1:
                self.profile_combo.addItem(name)
            self.profile_combo.setCurrentText(name)

            QMessageBox.information(
                self, "Profile Saved",
                f"Profile '{name}' has been saved."
            )

    def _update_profile(self):
        """Update the currently selected profile."""
        profile_name = self.profile_combo.currentText()
        if profile_name == "-- Select Profile --":
            QMessageBox.warning(
                self, "No Profile Selected",
                "Please select a profile to update."
            )
            return

        mapping = self._get_current_mapping()
        self.config.save_output_mapping_profile(profile_name, mapping)

        QMessageBox.information(
            self, "Profile Updated",
            f"Profile '{profile_name}' has been updated."
        )

    def _delete_profile(self):
        """Delete the currently selected profile."""
        profile_name = self.profile_combo.currentText()
        if profile_name == "-- Select Profile --":
            QMessageBox.warning(
                self, "No Profile Selected",
                "Please select a profile to delete."
            )
            return

        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete profile '{profile_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.delete_output_mapping_profile(profile_name)
            self.profile_combo.removeItem(self.profile_combo.currentIndex())
            self.profile_combo.setCurrentIndex(0)

    def _apply_settings(self):
        """Apply the current settings."""
        mapping = self._get_current_mapping()
        self.config.set_output_column_mapping(mapping)
        self.config.set_export_option('split_by_invoice', self.split_by_invoice_check.isChecked())

        self.mapping_changed.emit()

        QMessageBox.information(
            self, "Settings Applied",
            "Output column mapping has been applied."
        )
