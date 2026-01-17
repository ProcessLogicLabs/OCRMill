"""
Invoice Processing Tab for OCRMill.
TariffMill-style layout with left sidebar controls and results preview.
"""

import sys
import re
import csv
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QSpinBox, QCheckBox, QTabWidget,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QFrame, QGridLayout, QSplitter, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QColor

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase
from templates import get_all_templates, TEMPLATE_REGISTRY
from templates.bill_of_lading import BillOfLadingTemplate
from ui.widgets.log_viewer import LogViewerWidget, CompactLogViewer


class DropListWidget(QListWidget):
    """QListWidget that accepts file drops."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setStyleSheet("""
            QListWidget {
                border: 2px dashed #5f9ea0;
                border-radius: 4px;
                background-color: #f8ffff;
            }
            QListWidget:hover {
                border-color: #4a8a8c;
                background-color: #e8f8f8;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Check if any URLs are PDF files
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        QListWidget {
                            border: 2px solid #5f9ea0;
                            border-radius: 4px;
                            background-color: #d4edda;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QListWidget {
                border: 2px dashed #5f9ea0;
                border-radius: 4px;
                background-color: #f8ffff;
            }
            QListWidget:hover {
                border-color: #4a8a8c;
                background-color: #e8f8f8;
            }
        """)
        event.accept()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                files.append(file_path)

        self.setStyleSheet("""
            QListWidget {
                border: 2px dashed #5f9ea0;
                border-radius: 4px;
                background-color: #f8ffff;
            }
            QListWidget:hover {
                border-color: #4a8a8c;
                background-color: #e8f8f8;
            }
        """)

        if files:
            self.files_dropped.emit(files)
            event.acceptProposedAction()


class ProcessorEngine:
    """Core processing engine using templates."""

    def __init__(self, config: ConfigManager, db: PartsDatabase, log_callback=None):
        self.config = config
        self.log_callback = log_callback or print
        self.templates = {}
        self.parts_db = db
        self._load_templates()

    def _load_templates(self):
        """Load all available templates."""
        self.templates = get_all_templates()

    def log(self, message: str):
        """Log a message."""
        self.log_callback(message)

    def get_best_template(self, text: str):
        """Find the best template for the given text."""
        best_template = None
        best_score = 0.0

        self.log(f"  Evaluating {len(self.templates)} templates...")

        for name, template in self.templates.items():
            if not self.config.get_template_enabled(name):
                self.log(f"    - {name}: Disabled in config")
                continue
            if not template.enabled:
                self.log(f"    - {name}: Disabled in template")
                continue

            score = template.get_confidence_score(text)
            self.log(f"    - {name}: Confidence score {score:.2f}")

            if score > best_score:
                best_score = score
                best_template = template

        if best_template:
            self.log(f"  Selected template: {best_template.name} (score: {best_score:.2f})")
        else:
            self.log(f"  No matching template found")

        return best_template

    def process_pdf(self, pdf_path: Path):
        """Process a single PDF file, handling multiple invoices per PDF."""
        self.log(f"Processing: {pdf_path.name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # First pass: extract all text to detect template
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"

                if not full_text.strip():
                    self.log(f"  No text extracted from {pdf_path.name}")
                    return []

                # Scan for Bill of Lading and extract gross weight
                bol_weight = None
                bol_template = BillOfLadingTemplate()

                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text and bol_template.can_process(page_text):
                        self.log(f"  Found Bill of Lading on a page")
                        bol_weight = bol_template.extract_gross_weight(page_text)
                        if bol_weight:
                            self.log(f"  Extracted BOL gross weight: {bol_weight} kg")
                            break

                # Find the best template
                template = self.get_best_template(full_text)
                if not template:
                    self.log(f"  No matching template for {pdf_path.name}")
                    return []

                self.log(f"  Using template: {template.name}")

                # Check if packing list only
                if template.is_packing_list(full_text):
                    self.log(f"  Skipping packing list: {pdf_path.name}")
                    return []

                # Second pass: process page-by-page to handle multiple invoices
                all_items = []
                current_invoice = None
                current_project = None
                page_buffer = []

                for page in pdf.pages:
                    page_text = page.extract_text()
                    if not page_text:
                        continue

                    # Skip packing list and BOL pages
                    if 'packing list' in page_text.lower() and 'invoice' not in page_text.lower():
                        continue
                    if 'bill of lading' in page_text.lower():
                        continue

                    # Check for new invoice on this page
                    inv_match = re.search(r'(?:Proforma\s+)?[Ii]nvoice\s+(?:number|n)\.?\s*:?\s*(\d+(?:/\d+)?)', page_text)
                    proj_match = re.search(r'(?:\d+\.\s*)?[Pp]roject\s*(?:n\.?)?\s*:?\s*(US\d+[A-Z]\d+)', page_text, re.IGNORECASE)

                    new_invoice = inv_match.group(1) if inv_match else None
                    if new_invoice and current_invoice and new_invoice != current_invoice:
                        # Process accumulated pages for previous invoice
                        if page_buffer:
                            buffer_text = "\n".join(page_buffer)
                            _, _, items = template.extract_all(buffer_text)
                            for item in items:
                                item['invoice_number'] = current_invoice
                                item['project_number'] = current_project
                                if bol_weight:
                                    item['bol_gross_weight'] = bol_weight
                                if bol_weight and ('net_weight' not in item or not item.get('net_weight')):
                                    item['net_weight'] = bol_weight
                            all_items.extend(items)
                            page_buffer = []

                    # Update current invoice/project if found
                    if inv_match:
                        current_invoice = inv_match.group(1)
                    if proj_match:
                        current_project = proj_match.group(1).upper()

                    # Add page to buffer
                    page_buffer.append(page_text)

                # Process remaining pages in buffer
                if page_buffer and current_invoice:
                    buffer_text = "\n".join(page_buffer)
                    _, _, items = template.extract_all(buffer_text)
                    for item in items:
                        item['invoice_number'] = current_invoice
                        item['project_number'] = current_project
                        if bol_weight:
                            item['bol_gross_weight'] = bol_weight
                        if bol_weight and ('net_weight' not in item or not item.get('net_weight')):
                            item['net_weight'] = bol_weight
                    all_items.extend(items)

                # Count unique invoices
                unique_invoices = set(item.get('invoice_number', 'UNKNOWN') for item in all_items)
                grand_total = sum(float(item.get('total_price', 0) or 0) for item in all_items)
                self.log(f"  Found {len(unique_invoices)} invoice(s), {len(all_items)} total items, Grand Total: ${grand_total:,.2f}")

                return all_items

        except Exception as e:
            self.log(f"  Error processing {pdf_path.name}: {e}")
            return []

    def save_to_csv(self, items, output_folder: Path, pdf_name: str = None):
        """Save items to CSV files and add to parts database."""
        if not items:
            return

        # Add items to parts database
        for item in items:
            # Look up MID and country_origin from manufacturer name
            if ('mid' not in item or not item['mid']) or ('country_origin' not in item or not item['country_origin']):
                manufacturer_name = item.get('manufacturer_name', '')
                if manufacturer_name:
                    manufacturer = self.parts_db.get_manufacturer_by_name(manufacturer_name)
                    if manufacturer:
                        if 'mid' not in item or not item['mid']:
                            if manufacturer.get('mid'):
                                item['mid'] = manufacturer.get('mid', '')
                        if 'country_origin' not in item or not item['country_origin']:
                            if manufacturer.get('country'):
                                item['country_origin'] = manufacturer.get('country', '')

            # Extract country from MID if available
            if ('country_origin' not in item or not item['country_origin']) and item.get('mid'):
                mid = item.get('mid', '')
                if len(mid) >= 2:
                    item['country_origin'] = mid[:2].upper()

            part_data = item.copy()
            part_data['source_file'] = pdf_name or 'unknown'
            self.parts_db.add_part_occurrence(part_data)

            # Enrich item with database info
            if 'description' not in item or not item['description']:
                item['description'] = part_data.get('description', '')
            if 'hts_code' not in item or not item['hts_code']:
                item['hts_code'] = part_data.get('hts_code', '')

            # Remove manufacturer_name from output
            if 'manufacturer_name' in item:
                del item['manufacturer_name']

        # Group by invoice number
        by_invoice = {}
        for item in items:
            inv_num = item.get('invoice_number', 'UNKNOWN')
            if inv_num not in by_invoice:
                by_invoice[inv_num] = []
            by_invoice[inv_num].append(item)

        # Determine columns
        columns = ['invoice_number', 'project_number', 'part_number', 'description', 'mid', 'country_origin', 'hts_code', 'quantity', 'total_price']
        for item in items:
            for key in item.keys():
                if key not in columns:
                    columns.append(key)

        # Check consolidation mode
        consolidate = self.config.consolidate_multi_invoice

        if consolidate and len(by_invoice) > 1:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if pdf_name:
                base_name = Path(pdf_name).stem
            else:
                base_name = f"consolidated_{list(by_invoice.keys())[0]}"
            filename = f"{base_name}_{timestamp}.csv"
            filepath = output_folder / filename

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(items)

            invoice_list = ", ".join(sorted(by_invoice.keys()))
            self.log(f"  Saved: {filename} ({len(items)} items from {len(by_invoice)} invoices)")
        else:
            for inv_num, inv_items in by_invoice.items():
                proj_num = inv_items[0].get('project_number', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_inv_num = inv_num.replace('/', '-')
                filename = f"{safe_inv_num}_{proj_num}_{timestamp}.csv"
                filepath = output_folder / filename

                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(inv_items)

                self.log(f"  Saved: {filename} ({len(inv_items)} items)")

    def move_to_processed(self, pdf_path: Path, processed_folder: Path = None):
        """Move processed PDF to the Processed folder."""
        if processed_folder is None:
            processed_folder = pdf_path.parent / "Processed"
        processed_folder.mkdir(exist_ok=True, parents=True)

        dest = processed_folder / pdf_path.name
        counter = 1
        while dest.exists():
            stem = pdf_path.stem
            dest = processed_folder / f"{stem}_{counter}{pdf_path.suffix}"
            counter += 1

        pdf_path.rename(dest)
        self.log(f"  Moved to: Processed/{dest.name}")

    def move_to_failed(self, pdf_path: Path, failed_folder: Path = None, reason: str = ""):
        """Move failed PDF to the Failed folder."""
        if failed_folder is None:
            failed_folder = pdf_path.parent / "Failed"
        failed_folder.mkdir(exist_ok=True, parents=True)

        dest = failed_folder / pdf_path.name
        counter = 1
        while dest.exists():
            stem = pdf_path.stem
            dest = failed_folder / f"{stem}_{counter}{pdf_path.suffix}"
            counter += 1

        pdf_path.rename(dest)
        reason_msg = f" ({reason})" if reason else ""
        self.log(f"  Moved to: Failed/{dest.name}{reason_msg}")

    def process_folder(self, input_folder: Path, output_folder: Path):
        """Process all PDFs in the input folder."""
        input_folder.mkdir(exist_ok=True, parents=True)
        output_folder.mkdir(exist_ok=True, parents=True)
        processed_folder = input_folder / "Processed"
        failed_folder = input_folder / "Failed"

        pdf_files = list(input_folder.glob("*.pdf"))
        if not pdf_files:
            return 0

        self.log(f"Found {len(pdf_files)} PDF(s) to process")
        processed_count = 0

        for pdf_path in pdf_files:
            try:
                items = self.process_pdf(pdf_path)
                if items:
                    self.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                    self.move_to_processed(pdf_path, processed_folder)
                    processed_count += 1
                else:
                    self.move_to_failed(pdf_path, failed_folder, "No items extracted")
            except Exception as e:
                self.log(f"  Error processing {pdf_path.name}: {e}")
                self.move_to_failed(pdf_path, failed_folder, f"Error: {str(e)[:50]}")

        return processed_count


class InvoiceProcessingTab(QWidget):
    """
    Invoice Processing tab with TariffMill-style layout.

    Layout:
    - Left sidebar: Controls (Input Files, Output Files, Actions)
    - Right area: Drop zone and Activity Log sub-tabs
    - Bottom: Dynamic Results Preview table

    Signals:
        log_message: Emitted when a new log message is added
        files_processed: Emitted when files are processed (count)
    """

    log_message = pyqtSignal(str)
    files_processed = pyqtSignal(int)

    def __init__(self, config: ConfigManager, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.engine = ProcessorEngine(config, db, log_callback=self._log)
        self._is_processing = False
        self._last_results = []  # Store last processed results for preview

        self._setup_ui()
        self._connect_signals()
        self._load_config()

    def _setup_ui(self):
        """Set up the tab UI with TariffMill-style layout."""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Left sidebar: Controls
        left_sidebar = self._create_left_sidebar()
        main_layout.addWidget(left_sidebar)

        # Right panel: Sub-tabs with drop zone, activity log, and results preview
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 1)

    def _create_left_sidebar(self) -> QWidget:
        """Create the left sidebar with Controls (TariffMill style)."""
        sidebar = QWidget()
        sidebar.setMaximumWidth(320)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(8)

        # Input Files (PDFs) group - also serves as drop zone
        input_group = QGroupBox("Input Files (PDFs) - Drop files here")
        input_group.setAcceptDrops(True)
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(4)

        # Input files list with drop support
        self.input_files_list = DropListWidget()
        self.input_files_list.setAlternatingRowColors(True)
        self.input_files_list.setMinimumHeight(100)
        self.input_files_list.files_dropped.connect(self._on_files_dropped)
        self.input_files_list.doubleClicked.connect(self._process_selected_file)
        input_layout.addWidget(self.input_files_list)

        # Refresh button
        input_refresh_btn = QPushButton("Refresh")
        input_refresh_btn.clicked.connect(self._refresh_input_files)
        input_layout.addWidget(input_refresh_btn)

        layout.addWidget(input_group)

        # Output Files (CSVs) group
        output_group = QGroupBox("Output Files (CSVs)")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(4)

        # Output files list
        self.output_files_list = QListWidget()
        self.output_files_list.setAlternatingRowColors(True)
        self.output_files_list.setMaximumHeight(120)
        output_layout.addWidget(self.output_files_list)

        # Refresh button
        output_refresh_btn = QPushButton("Refresh")
        output_refresh_btn.clicked.connect(self._refresh_output_files)
        output_layout.addWidget(output_refresh_btn)

        layout.addWidget(output_group)

        # Actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(6)

        # Start/Stop Monitoring button
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.setStyleSheet("font-weight: bold;")
        self.start_btn.clicked.connect(self._request_start)
        actions_layout.addWidget(self.start_btn)

        # Auto-start checkbox
        self.auto_start_check = QCheckBox("Auto-start on launch")
        self.auto_start_check.setChecked(self.config.auto_start)
        self.auto_start_check.stateChanged.connect(self._save_auto_start)
        actions_layout.addWidget(self.auto_start_check)

        # Separator line
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #ccc;")
        actions_layout.addWidget(line1)

        # Process PDF File button
        self.process_file_btn = QPushButton("Process PDF File...")
        self.process_file_btn.clicked.connect(self._browse_files)
        actions_layout.addWidget(self.process_file_btn)

        # Process Folder Now button
        self.process_now_btn = QPushButton("Process Folder Now")
        self.process_now_btn.clicked.connect(self.process_now)
        actions_layout.addWidget(self.process_now_btn)

        # Separator line
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #ccc;")
        actions_layout.addWidget(line2)

        # Send to TariffMill button (placeholder for future integration)
        self.send_tariffmill_btn = QPushButton("Send to TariffMill")
        self.send_tariffmill_btn.setEnabled(False)  # Disabled for now
        self.send_tariffmill_btn.setToolTip("Integration with TariffMill coming soon")
        actions_layout.addWidget(self.send_tariffmill_btn)

        # Separator line
        line3 = QFrame()
        line3.setFrameShape(QFrame.Shape.HLine)
        line3.setStyleSheet("background-color: #ccc;")
        actions_layout.addWidget(line3)

        # Multi-invoice PDFs options
        multi_label = QLabel("Multi-invoice PDFs:")
        actions_layout.addWidget(multi_label)

        self.multi_invoice_group = QButtonGroup(self)
        self.split_radio = QRadioButton("Split")
        self.combine_radio = QRadioButton("Combine")
        self.multi_invoice_group.addButton(self.split_radio)
        self.multi_invoice_group.addButton(self.combine_radio)

        if self.config.consolidate_multi_invoice:
            self.combine_radio.setChecked(True)
        else:
            self.split_radio.setChecked(True)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.split_radio)
        radio_layout.addWidget(self.combine_radio)
        radio_layout.addStretch()
        actions_layout.addLayout(radio_layout)

        self.split_radio.toggled.connect(self._save_multi_invoice_mode)

        layout.addWidget(actions_group)

        layout.addStretch()

        return sidebar

    def _create_right_panel(self) -> QWidget:
        """Create the right panel with results preview and activity log."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(8)

        # Vertical splitter: top = results preview (large), bottom = activity log (small)
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: Results Preview table (large area)
        results_preview = self._create_results_preview()
        self.right_splitter.addWidget(results_preview)

        # Bottom section: Sub-tabs with Activity Log and AI Templates (small area)
        self.sub_tabs = QTabWidget()

        # Invoice Processing sub-tab (activity log)
        invoice_processing_widget = self._create_invoice_processing_subtab()
        self.sub_tabs.addTab(invoice_processing_widget, "Activity Log")

        # AI Templates sub-tab
        templates_widget = self._create_templates_tab()
        self.sub_tabs.addTab(templates_widget, "AI Templates")

        self.right_splitter.addWidget(self.sub_tabs)

        # Set sizes: large results preview (3), small log area (1)
        self.right_splitter.setSizes([450, 150])

        layout.addWidget(self.right_splitter)

        # Schedule a repaint after the widget is fully initialized (fixes Windows Qt6 rendering)
        QTimer.singleShot(50, self._force_panel_repaint)

        return panel

    def _force_panel_repaint(self):
        """Force the right panel and splitter to repaint properly on Windows."""
        if hasattr(self, 'right_splitter'):
            # Re-apply splitter sizes to trigger layout recalculation
            self.right_splitter.setSizes([450, 150])
            self.right_splitter.updateGeometry()
            self.right_splitter.repaint()
        if hasattr(self, 'results_table'):
            self.results_table.updateGeometry()
            self.results_table.repaint()
            if self.results_table.viewport():
                self.results_table.viewport().repaint()
        if hasattr(self, 'sub_tabs'):
            self.sub_tabs.updateGeometry()
            self.sub_tabs.repaint()
        self.updateGeometry()
        self.repaint()

    def _create_invoice_processing_subtab(self) -> QWidget:
        """Create the Activity Log sub-tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        # Activity Log viewer (no group box - tab name is already "Activity Log")
        self.log_viewer = LogViewerWidget()
        layout.addWidget(self.log_viewer)

        return widget

    def _create_templates_tab(self) -> QWidget:
        """Create the AI Templates configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Enable/disable invoice templates:"))

        self.template_checks = {}
        for name in TEMPLATE_REGISTRY.keys():
            check = QCheckBox(name.replace('_', ' ').title())
            check.setChecked(self.config.get_template_enabled(name))
            check.stateChanged.connect(lambda state, n=name: self._save_template_enabled(n, state))
            self.template_checks[name] = check
            layout.addWidget(check)

        layout.addStretch()

        return widget

    def _create_results_preview(self) -> QWidget:
        """Create the dynamic Results Preview table at the bottom."""
        group = QGroupBox("Results Preview")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 5, 5, 5)

        # Results table - dynamic columns based on extracted data
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(True)

        # Initialize with default columns
        self._init_results_columns()

        layout.addWidget(self.results_table)

        # Status bar for results
        status_layout = QHBoxLayout()
        self.results_status = QLabel("No results yet")
        self.results_status.setStyleSheet("color: #666;")
        status_layout.addWidget(self.results_status)

        status_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_results)
        status_layout.addWidget(clear_btn)

        export_btn = QPushButton("Export Results...")
        export_btn.clicked.connect(self._export_results)
        status_layout.addWidget(export_btn)

        layout.addLayout(status_layout)

        return group

    def _init_results_columns(self):
        """Initialize results table with default columns."""
        # Default columns - will be updated dynamically based on extracted data
        default_columns = [
            "Part Number", "Description", "Quantity", "Unit Price", "Total",
            "Invoice #", "Project #"
        ]
        self.results_table.setColumnCount(len(default_columns))
        self.results_table.setHorizontalHeaderLabels(default_columns)

        # Set column widths - set all to Interactive first, then set specific widths
        header = self.results_table.horizontalHeader()
        for i in range(len(default_columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        # Set initial column widths
        self.results_table.setColumnWidth(0, 120)  # Part Number
        self.results_table.setColumnWidth(1, 200)  # Description
        self.results_table.setColumnWidth(2, 80)   # Quantity
        self.results_table.setColumnWidth(3, 90)   # Unit Price
        self.results_table.setColumnWidth(4, 90)   # Total
        self.results_table.setColumnWidth(5, 80)   # Invoice #
        self.results_table.setColumnWidth(6, 100)  # Project #

        # Set Description to stretch after initial widths are set
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Force header repaint to fix rendering issues on Windows
        QTimer.singleShot(0, self._force_header_repaint)

    def _force_header_repaint(self):
        """Force the table header to repaint properly."""
        header = self.results_table.horizontalHeader()
        header.updateGeometry()
        header.repaint()
        self.results_table.viewport().update()

    def _update_results_table(self, items: list):
        """Update the results table with extracted items (dynamic columns)."""
        if not items:
            return

        self._last_results = items

        # Determine all unique keys across all items
        all_keys = set()
        for item in items:
            all_keys.update(item.keys())

        # Define preferred column order (common fields first)
        preferred_order = [
            'part_number', 'description', 'quantity', 'unit_price', 'total_price',
            'invoice_number', 'project_number', 'hts_code', 'country_origin', 'mid',
            'manufacturer_name', 'net_weight', 'gross_weight'
        ]

        # Build column list: preferred first, then remaining alphabetically
        columns = []
        for key in preferred_order:
            if key in all_keys:
                columns.append(key)
                all_keys.discard(key)
        columns.extend(sorted(all_keys))

        # Set up table columns
        display_names = {
            'part_number': 'Part Number',
            'description': 'Description',
            'quantity': 'Quantity',
            'unit_price': 'Unit Price',
            'total_price': 'Total',
            'invoice_number': 'Invoice #',
            'project_number': 'Project #',
            'hts_code': 'HTS Code',
            'country_origin': 'Country',
            'mid': 'MID',
            'manufacturer_name': 'Manufacturer',
            'net_weight': 'Net Weight',
            'gross_weight': 'Gross Weight',
            'bol_gross_weight': 'BOL Weight'
        }

        self.results_table.setColumnCount(len(columns))
        headers = [display_names.get(col, col.replace('_', ' ').title()) for col in columns]
        self.results_table.setHorizontalHeaderLabels(headers)

        # Populate rows
        self.results_table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            for col_idx, key in enumerate(columns):
                value = item.get(key, '')
                if value is None:
                    value = ''
                elif isinstance(value, float):
                    if 'price' in key.lower() or 'total' in key.lower():
                        value = f"${value:,.2f}"
                    else:
                        value = f"{value:,.2f}"
                else:
                    value = str(value)

                cell = QTableWidgetItem(value)
                self.results_table.setItem(row_idx, col_idx, cell)

        # Update status
        total_value = sum(float(item.get('total_price', 0) or 0) for item in items)
        self.results_status.setText(f"{len(items)} items extracted | Total: ${total_value:,.2f}")

        # Resize columns to content
        self.results_table.resizeColumnsToContents()

        # Store column mapping for export
        self._result_columns = columns

        # Force header repaint to fix rendering issues on Windows
        QTimer.singleShot(0, self._force_header_repaint)

    def _clear_results(self):
        """Clear the results preview table."""
        self.results_table.setRowCount(0)
        self._last_results = []
        self.results_status.setText("No results yet")

    def _export_results(self):
        """Export current results to CSV."""
        if not self._last_results:
            QMessageBox.information(self, "No Results", "No results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "results.csv", "CSV Files (*.csv)"
        )
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    if hasattr(self, '_result_columns'):
                        writer = csv.DictWriter(f, fieldnames=self._result_columns, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(self._last_results)
                    else:
                        writer = csv.DictWriter(f, fieldnames=self._last_results[0].keys())
                        writer.writeheader()
                        writer.writerows(self._last_results)

                QMessageBox.information(self, "Export Complete", f"Results exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _connect_signals(self):
        """Connect internal signals."""
        pass

    def _load_config(self):
        """Load configuration values into UI."""
        # Update multi-invoice mode radio buttons
        if self.config.consolidate_multi_invoice:
            self.combine_radio.setChecked(True)
        else:
            self.split_radio.setChecked(True)

        # Update auto-start checkbox
        self.auto_start_check.setChecked(self.config.auto_start)

        # Refresh file lists
        self._refresh_input_files()
        self._refresh_output_files()

    def reload_config(self):
        """Reload configuration after settings change."""
        self._load_config()
        self.engine = ProcessorEngine(self.config, self.db, log_callback=self._log)

    # ----- Settings handlers -----

    def _save_auto_start(self, state: int):
        """Save auto-start setting."""
        self.config.auto_start = (state == Qt.CheckState.Checked.value)

    def _save_multi_invoice_mode(self, checked: bool):
        """Save multi-invoice PDF mode (split vs combine)."""
        # Split = NOT consolidate, Combine = consolidate
        self.config.consolidate_multi_invoice = self.combine_radio.isChecked()

    def _save_template_enabled(self, name: str, state: int):
        """Save template enabled state."""
        self.config.set_template_enabled(name, state == Qt.CheckState.Checked.value)

    # ----- Processing control -----

    def _request_start(self):
        """Request parent to start processing."""
        # Find main window and call start
        main_window = self.window()
        if hasattr(main_window, '_start_processing'):
            main_window._start_processing()

    def _request_stop(self):
        """Request parent to stop processing."""
        main_window = self.window()
        if hasattr(main_window, '_stop_processing'):
            main_window._stop_processing()

    def set_processing_state(self, is_running: bool):
        """Update UI based on processing state."""
        self._is_processing = is_running

        if is_running:
            self.start_btn.setText("Stop Monitoring")
            self.start_btn.setStyleSheet("font-weight: bold; background-color: #f8d7da; color: #721c24;")
            self.start_btn.clicked.disconnect()
            self.start_btn.clicked.connect(self._request_stop)
        else:
            self.start_btn.setText("Start Monitoring")
            self.start_btn.setStyleSheet("font-weight: bold;")
            self.start_btn.clicked.disconnect()
            self.start_btn.clicked.connect(self._request_start)

    @pyqtSlot()
    def process_now(self):
        """Process files immediately and show results in preview table."""
        input_folder = Path(self.config.input_folder)
        output_folder = Path(self.config.output_folder)

        self._log("Processing files now...")

        # Collect all items for results preview
        all_items = []
        pdf_files = list(input_folder.glob("*.pdf"))

        if not pdf_files:
            self._log("No files to process")
            self._refresh_input_files()
            self._refresh_output_files()
            return

        for pdf_path in pdf_files:
            try:
                items = self.engine.process_pdf(pdf_path)
                if items:
                    all_items.extend(items)
                    self.engine.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                    self.engine.move_to_processed(pdf_path)
                else:
                    self.engine.move_to_failed(pdf_path, reason="No items extracted")
            except Exception as e:
                self._log(f"Error processing {pdf_path.name}: {e}")
                self.engine.move_to_failed(pdf_path, reason=str(e)[:50])

        count = len([p for p in pdf_files if not p.exists()])  # Files that were moved
        if count > 0:
            self.files_processed.emit(count)
            self._log(f"Processed {count} file(s)")

            # Update results preview table
            if all_items:
                self._update_results_table(all_items)

        self._refresh_input_files()
        self._refresh_output_files()

    @pyqtSlot()
    def run_cbp_export(self):
        """Run CBP export process."""
        try:
            from cbp_exporter import CBPExporter

            input_folder = Path(self.config.cbp_input_folder)
            output_folder = Path(self.config.cbp_output_folder)

            self._log("Running CBP export...")
            exporter = CBPExporter(input_folder, output_folder)
            count = exporter.process_all()
            self._log(f"CBP export complete: {count} files processed")
        except ImportError:
            self._log("CBP exporter module not available")
        except Exception as e:
            self._log(f"CBP export error: {e}")

    # ----- File handling -----

    def _on_files_dropped(self, files: list):
        """Handle files dropped on drop zone."""
        input_folder = Path(self.config.input_folder)
        input_folder.mkdir(exist_ok=True, parents=True)

        copied = 0
        for file_path in files:
            src = Path(file_path)
            dst = input_folder / src.name
            if not dst.exists():
                import shutil
                shutil.copy2(src, dst)
                copied += 1
                self._log(f"Added: {src.name}")

        if copied > 0:
            self._refresh_input_files()
            QMessageBox.information(
                self, "Files Added",
                f"Added {copied} file(s) to input folder."
            )

    def _browse_files(self):
        """Browse for PDF files to process directly."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if files:
            self._process_pdf_files(files)

    def _process_pdf_files(self, file_paths: list):
        """Process PDF files directly and show results in preview table."""
        output_folder = Path(self.config.output_folder)
        output_folder.mkdir(exist_ok=True, parents=True)

        all_items = []
        processed_count = 0

        for file_path in file_paths:
            pdf_path = Path(file_path)
            self._log(f"Processing: {pdf_path.name}")

            try:
                items = self.engine.process_pdf(pdf_path)
                if items:
                    all_items.extend(items)
                    self.engine.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                    processed_count += 1
                    self._log(f"  Extracted {len(items)} items")
                else:
                    self._log(f"  No items extracted from {pdf_path.name}")
            except Exception as e:
                self._log(f"  Error: {e}")

        if processed_count > 0:
            self.files_processed.emit(processed_count)
            self._log(f"Processed {processed_count} file(s), {len(all_items)} total items")

            # Update results preview table
            if all_items:
                self._update_results_table(all_items)

        self._refresh_output_files()

    def _refresh_input_files(self):
        """Refresh the input files list."""
        self.input_files_list.clear()
        input_folder = Path(self.config.input_folder)
        if input_folder.exists():
            for pdf in sorted(input_folder.glob("*.pdf")):
                item = QListWidgetItem(pdf.name)
                self.input_files_list.addItem(item)

    def _refresh_output_files(self):
        """Refresh the output files list."""
        self.output_files_list.clear()
        output_folder = Path(self.config.output_folder)
        if output_folder.exists():
            for csv_file in sorted(output_folder.glob("*.csv"), reverse=True)[:50]:
                item = QListWidgetItem(csv_file.name)
                self.output_files_list.addItem(item)

    def _process_selected_file(self):
        """Process the selected input file and show results in preview table."""
        current = self.input_files_list.currentItem()
        if not current:
            return

        input_folder = Path(self.config.input_folder)
        output_folder = Path(self.config.output_folder)
        pdf_path = input_folder / current.text()

        if pdf_path.exists():
            self._log(f"Processing selected file: {pdf_path.name}")
            try:
                items = self.engine.process_pdf(pdf_path)
                if items:
                    self.engine.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                    self.engine.move_to_processed(pdf_path)
                    self.files_processed.emit(1)
                    # Update results preview table
                    self._update_results_table(items)
                else:
                    self.engine.move_to_failed(pdf_path, reason="No items extracted")
            except Exception as e:
                self._log(f"Error: {e}")
                self.engine.move_to_failed(pdf_path, reason=str(e)[:50])

            self._refresh_input_files()
            self._refresh_output_files()

    # ----- Logging -----

    def _log(self, message: str):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.log_viewer.append_message(formatted)
        self.log_message.emit(formatted)

    @pyqtSlot(str)
    def append_log(self, message: str):
        """Append a pre-formatted message to the log."""
        self.log_viewer.append_message(message)
