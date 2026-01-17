"""
Part View and Edit Dialogs for OCRMill.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QMessageBox,
    QTextEdit, QGroupBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QScrollArea, QWidget, QFrame
)
from PyQt6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase


class PartViewDialog(QDialog):
    """Dialog for viewing part details."""

    def __init__(self, part: dict, parent=None):
        super().__init__(parent)
        self.part = part

        self.setWindowTitle(f"Part Details - {part.get('part_number', 'Unknown')}")
        self.setMinimumSize(500, 600)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        fields = [
            ("part_number", "Part Number"),
            ("description", "Description"),
            ("hts_code", "HTS Code"),
            ("country_origin", "Country of Origin"),
            ("mid", "Manufacturer ID"),
            ("client_code", "Client Code"),
            ("qty_unit", "Quantity Unit"),
        ]

        for field_name, label in fields:
            value = self.part.get(field_name, '')
            value_label = QLabel(str(value) if value else "--")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            basic_layout.addRow(f"{label}:", value_label)

        content_layout.addWidget(basic_group)

        # Material composition group
        material_group = QGroupBox("Material Composition")
        material_layout = QFormLayout(material_group)

        material_fields = [
            ("steel_pct", "Steel %"),
            ("aluminum_pct", "Aluminum %"),
            ("copper_pct", "Copper %"),
            ("wood_pct", "Wood %"),
            ("auto_pct", "Auto %"),
            ("non_steel_pct", "Non-Steel %"),
        ]

        for field_name, label in material_fields:
            value = self.part.get(field_name)
            if value is not None:
                display = f"{float(value):.1f}%"
            else:
                display = "--"
            material_layout.addRow(f"{label}:", QLabel(display))

        content_layout.addWidget(material_group)

        # Trade info group
        trade_group = QGroupBox("Trade Information")
        trade_layout = QFormLayout(trade_group)

        trade_fields = [
            ("sec301_exclusion_tariff", "Section 301 Exclusion"),
            ("fsc_certified", "FSC Certified"),
            ("fsc_certificate_code", "FSC Certificate Code"),
        ]

        for field_name, label in trade_fields:
            value = self.part.get(field_name)
            if field_name in ('fsc_certified',):
                display = "Yes" if value else "No"
            else:
                display = str(value) if value else "--"
            trade_layout.addRow(f"{label}:", QLabel(display))

        content_layout.addWidget(trade_group)

        # Metadata group
        meta_group = QGroupBox("Metadata")
        meta_layout = QFormLayout(meta_group)

        meta_fields = [
            ("last_updated", "Last Updated"),
            ("notes", "Notes"),
        ]

        for field_name, label in meta_fields:
            value = self.part.get(field_name, '')
            value_label = QLabel(str(value) if value else "--")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            meta_layout.addRow(f"{label}:", value_label)

        content_layout.addWidget(meta_group)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class PartEditDialog(QDialog):
    """Dialog for editing part details."""

    def __init__(self, part: dict, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.part = part.copy()
        self.db = db
        self.saved = False

        self.setWindowTitle(f"Edit Part - {part.get('part_number', 'Unknown')}")
        self.setMinimumSize(550, 650)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Part number (read-only)
        part_num_layout = QHBoxLayout()
        part_num_layout.addWidget(QLabel("Part Number:"))
        self.part_number_label = QLabel(self.part.get('part_number', ''))
        self.part_number_label.setStyleSheet("font-weight: bold;")
        part_num_layout.addWidget(self.part_number_label)
        part_num_layout.addStretch()
        content_layout.addLayout(part_num_layout)

        # Basic info group
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        self.description_edit = QLineEdit()
        basic_layout.addRow("Description:", self.description_edit)

        self.hts_edit = QLineEdit()
        self.hts_edit.setPlaceholderText("e.g., 9401.71.0011")
        basic_layout.addRow("HTS Code:", self.hts_edit)

        self.country_edit = QLineEdit()
        self.country_edit.setMaxLength(2)
        self.country_edit.setPlaceholderText("e.g., CZ, US")
        basic_layout.addRow("Country of Origin:", self.country_edit)

        self.mid_edit = QLineEdit()
        basic_layout.addRow("Manufacturer ID:", self.mid_edit)

        self.client_edit = QLineEdit()
        basic_layout.addRow("Client Code:", self.client_edit)

        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText("e.g., EA, PCS, KG")
        basic_layout.addRow("Quantity Unit:", self.unit_edit)

        content_layout.addWidget(basic_group)

        # Material composition group
        material_group = QGroupBox("Material Composition (%)")
        material_layout = QFormLayout(material_group)

        self.steel_spin = QDoubleSpinBox()
        self.steel_spin.setRange(0, 100)
        self.steel_spin.setDecimals(1)
        material_layout.addRow("Steel:", self.steel_spin)

        self.aluminum_spin = QDoubleSpinBox()
        self.aluminum_spin.setRange(0, 100)
        self.aluminum_spin.setDecimals(1)
        material_layout.addRow("Aluminum:", self.aluminum_spin)

        self.copper_spin = QDoubleSpinBox()
        self.copper_spin.setRange(0, 100)
        self.copper_spin.setDecimals(1)
        material_layout.addRow("Copper:", self.copper_spin)

        self.wood_spin = QDoubleSpinBox()
        self.wood_spin.setRange(0, 100)
        self.wood_spin.setDecimals(1)
        material_layout.addRow("Wood:", self.wood_spin)

        self.auto_spin = QDoubleSpinBox()
        self.auto_spin.setRange(0, 100)
        self.auto_spin.setDecimals(1)
        material_layout.addRow("Auto:", self.auto_spin)

        self.non_steel_spin = QDoubleSpinBox()
        self.non_steel_spin.setRange(0, 100)
        self.non_steel_spin.setDecimals(1)
        material_layout.addRow("Non-Steel:", self.non_steel_spin)

        content_layout.addWidget(material_group)

        # Trade info group
        trade_group = QGroupBox("Trade Information")
        trade_layout = QFormLayout(trade_group)

        self.sec301_edit = QLineEdit()
        trade_layout.addRow("Section 301 Exclusion:", self.sec301_edit)

        self.fsc_check = QCheckBox("FSC Certified")
        trade_layout.addRow("", self.fsc_check)

        self.fsc_code_edit = QLineEdit()
        trade_layout.addRow("FSC Certificate Code:", self.fsc_code_edit)

        content_layout.addWidget(trade_group)

        # Notes group
        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        notes_layout.addWidget(self.notes_edit)
        content_layout.addWidget(notes_group)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

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
        """Load part data into form."""
        self.description_edit.setText(self.part.get('description', ''))
        self.hts_edit.setText(self.part.get('hts_code', ''))
        self.country_edit.setText(self.part.get('country_origin', ''))
        self.mid_edit.setText(self.part.get('mid', ''))
        self.client_edit.setText(self.part.get('client_code', ''))
        self.unit_edit.setText(self.part.get('qty_unit', ''))

        # Material percentages
        self.steel_spin.setValue(float(self.part.get('steel_pct') or 0))
        self.aluminum_spin.setValue(float(self.part.get('aluminum_pct') or 0))
        self.copper_spin.setValue(float(self.part.get('copper_pct') or 0))
        self.wood_spin.setValue(float(self.part.get('wood_pct') or 0))
        self.auto_spin.setValue(float(self.part.get('auto_pct') or 0))
        self.non_steel_spin.setValue(float(self.part.get('non_steel_pct') or 0))

        # Trade info
        self.sec301_edit.setText(self.part.get('sec301_exclusion_tariff', '') or '')
        self.fsc_check.setChecked(bool(self.part.get('fsc_certified')))
        self.fsc_code_edit.setText(self.part.get('fsc_certificate_code', '') or '')

        # Notes
        self.notes_edit.setPlainText(self.part.get('notes', '') or '')

    def _save(self):
        """Save the part data."""
        part_number = self.part.get('part_number')
        if not part_number:
            QMessageBox.warning(self, "Error", "Part number is required.")
            return

        try:
            # Build update data
            update_data = {
                'description': self.description_edit.text().strip(),
                'hts_code': self.hts_edit.text().strip(),
                'country_origin': self.country_edit.text().strip().upper(),
                'mid': self.mid_edit.text().strip(),
                'client_code': self.client_edit.text().strip(),
                'qty_unit': self.unit_edit.text().strip(),
                'steel_pct': self.steel_spin.value() if self.steel_spin.value() > 0 else None,
                'aluminum_pct': self.aluminum_spin.value() if self.aluminum_spin.value() > 0 else None,
                'copper_pct': self.copper_spin.value() if self.copper_spin.value() > 0 else None,
                'wood_pct': self.wood_spin.value() if self.wood_spin.value() > 0 else None,
                'auto_pct': self.auto_spin.value() if self.auto_spin.value() > 0 else None,
                'non_steel_pct': self.non_steel_spin.value() if self.non_steel_spin.value() > 0 else None,
                'sec301_exclusion_tariff': self.sec301_edit.text().strip() or None,
                'fsc_certified': self.fsc_check.isChecked(),
                'fsc_certificate_code': self.fsc_code_edit.text().strip() or None,
                'notes': self.notes_edit.toPlainText().strip() or None,
            }

            self.db.update_part(part_number, update_data)
            self.saved = True
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save part:\n{e}")
