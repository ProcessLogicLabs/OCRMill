"""
Invoice Processing Tab for OCRMill.
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
    QFrame, QGridLayout, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QColor

import pdfplumber

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_manager import ConfigManager
from parts_database import PartsDatabase
from templates import get_all_templates, TEMPLATE_REGISTRY
from templates.bill_of_lading import BillOfLadingTemplate
from ui.widgets.drop_zone import PDFDropZone
from ui.widgets.log_viewer import LogViewerWidget, CompactLogViewer


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
    Invoice Processing tab containing controls, drop zone, and activity log.

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

        self._setup_ui()
        self._connect_signals()
        self._load_config()

    def _setup_ui(self):
        """Set up the tab UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header with status
        header = self._create_header()
        layout.addWidget(header)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Controls and drop zone
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right side: Sub-tabs
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)

    def _create_header(self) -> QFrame:
        """Create the header frame with status indicator."""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)

        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
        layout.addWidget(self.status_indicator)

        self.status_text = QLabel("Monitoring: Stopped")
        layout.addWidget(self.status_text)

        layout.addStretch()

        # Quick action buttons
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.clicked.connect(self._request_start)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._request_stop)
        layout.addWidget(self.stop_btn)

        self.process_now_btn = QPushButton("Process Now")
        self.process_now_btn.clicked.connect(self.process_now)
        layout.addWidget(self.process_now_btn)

        return frame

    def _create_left_panel(self) -> QWidget:
        """Create the left panel with settings and drop zone."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 5, 0)

        # Settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout(settings_group)

        # Input folder
        settings_layout.addWidget(QLabel("Input Folder:"), 0, 0)
        self.input_folder_edit = QLineEdit()
        self.input_folder_edit.setReadOnly(True)
        settings_layout.addWidget(self.input_folder_edit, 0, 1)
        input_browse_btn = QPushButton("...")
        input_browse_btn.setMaximumWidth(30)
        input_browse_btn.clicked.connect(self._browse_input_folder)
        settings_layout.addWidget(input_browse_btn, 0, 2)

        # Output folder
        settings_layout.addWidget(QLabel("Output Folder:"), 1, 0)
        self.output_folder_edit = QLineEdit()
        self.output_folder_edit.setReadOnly(True)
        settings_layout.addWidget(self.output_folder_edit, 1, 1)
        output_browse_btn = QPushButton("...")
        output_browse_btn.setMaximumWidth(30)
        output_browse_btn.clicked.connect(self._browse_output_folder)
        settings_layout.addWidget(output_browse_btn, 1, 2)

        # Poll interval
        settings_layout.addWidget(QLabel("Poll Interval (sec):"), 2, 0)
        self.poll_spinbox = QSpinBox()
        self.poll_spinbox.setRange(5, 300)
        self.poll_spinbox.valueChanged.connect(self._save_poll_interval)
        settings_layout.addWidget(self.poll_spinbox, 2, 1, 1, 2)

        # Checkboxes
        self.consolidate_check = QCheckBox("Consolidate Multi-Invoice PDFs")
        self.consolidate_check.stateChanged.connect(self._save_consolidate)
        settings_layout.addWidget(self.consolidate_check, 3, 0, 1, 3)

        self.auto_cbp_check = QCheckBox("Auto-run CBP Export")
        self.auto_cbp_check.stateChanged.connect(self._save_auto_cbp)
        settings_layout.addWidget(self.auto_cbp_check, 4, 0, 1, 3)

        layout.addWidget(settings_group)

        # Drop zone
        self.drop_zone = PDFDropZone()
        self.drop_zone.files_dropped.connect(self._on_files_dropped)
        self.drop_zone.clicked.connect(self._browse_files)
        self.drop_zone.setMinimumHeight(150)
        layout.addWidget(self.drop_zone)

        layout.addStretch()

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right panel with sub-tabs."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 0, 0, 0)

        self.sub_tabs = QTabWidget()

        # Activity Log tab
        self.log_viewer = LogViewerWidget()
        self.sub_tabs.addTab(self.log_viewer, "Activity Log")

        # Templates tab
        templates_widget = self._create_templates_tab()
        self.sub_tabs.addTab(templates_widget, "Templates")

        # Processing Stats tab
        stats_widget = self._create_stats_tab()
        self.sub_tabs.addTab(stats_widget, "Processing Stats")

        # Input Files tab
        input_files_widget = self._create_input_files_tab()
        self.sub_tabs.addTab(input_files_widget, "Input Files")

        # Output Files tab
        output_files_widget = self._create_output_files_tab()
        self.sub_tabs.addTab(output_files_widget, "Output Files")

        layout.addWidget(self.sub_tabs)

        return panel

    def _create_templates_tab(self) -> QWidget:
        """Create the templates configuration tab."""
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

    def _create_stats_tab(self) -> QWidget:
        """Create the processing statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.stats_labels = {}

        stats = [
            ("Files Processed Today:", "processed_today"),
            ("Total Items Extracted:", "items_today"),
            ("Errors Today:", "errors_today"),
            ("Last Processing:", "last_processing"),
        ]

        for label_text, key in stats:
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            value_label = QLabel("--")
            self.stats_labels[key] = value_label
            row.addWidget(value_label)
            row.addStretch()
            layout.addLayout(row)

        layout.addStretch()

        refresh_btn = QPushButton("Refresh Stats")
        refresh_btn.clicked.connect(self._refresh_stats)
        layout.addWidget(refresh_btn)

        return widget

    def _create_input_files_tab(self) -> QWidget:
        """Create the input files list tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_input_files)
        toolbar.addWidget(refresh_btn)

        process_selected_btn = QPushButton("Process Selected")
        process_selected_btn.clicked.connect(self._process_selected_file)
        toolbar.addWidget(process_selected_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected_input)
        toolbar.addWidget(delete_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.input_files_list = QListWidget()
        self.input_files_list.setAlternatingRowColors(True)
        layout.addWidget(self.input_files_list)

        return widget

    def _create_output_files_tab(self) -> QWidget:
        """Create the output files list tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_output_files)
        toolbar.addWidget(refresh_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self._open_output_folder)
        toolbar.addWidget(open_folder_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.output_files_list = QListWidget()
        self.output_files_list.setAlternatingRowColors(True)
        layout.addWidget(self.output_files_list)

        return widget

    def _connect_signals(self):
        """Connect internal signals."""
        pass

    def _load_config(self):
        """Load configuration values into UI."""
        self.input_folder_edit.setText(str(self.config.input_folder))
        self.output_folder_edit.setText(str(self.config.output_folder))
        self.poll_spinbox.setValue(self.config.poll_interval)
        self.consolidate_check.setChecked(self.config.consolidate_multi_invoice)
        self.auto_cbp_check.setChecked(self.config.auto_cbp_export)

        # Refresh file lists
        self._refresh_input_files()
        self._refresh_output_files()

    def reload_config(self):
        """Reload configuration after settings change."""
        self._load_config()
        self.engine = ProcessorEngine(self.config, self.db, log_callback=self._log)

    # ----- Settings handlers -----

    def _browse_input_folder(self):
        """Browse for input folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Input Folder", str(self.config.input_folder)
        )
        if folder:
            self.config.input_folder = folder
            self.input_folder_edit.setText(folder)
            self._refresh_input_files()

    def _browse_output_folder(self):
        """Browse for output folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", str(self.config.output_folder)
        )
        if folder:
            self.config.output_folder = folder
            self.output_folder_edit.setText(folder)
            self._refresh_output_files()

    def _save_poll_interval(self, value: int):
        """Save poll interval setting."""
        self.config.poll_interval = value

    def _save_consolidate(self, state: int):
        """Save consolidate setting."""
        self.config.consolidate_multi_invoice = (state == Qt.CheckState.Checked.value)

    def _save_auto_cbp(self, state: int):
        """Save auto CBP export setting."""
        self.config.auto_cbp_export = (state == Qt.CheckState.Checked.value)

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
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)

        if is_running:
            self.status_indicator.setStyleSheet("color: green; font-size: 16px;")
            self.status_text.setText("Monitoring: Running")
        else:
            self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
            self.status_text.setText("Monitoring: Stopped")

    @pyqtSlot()
    def process_now(self):
        """Process files immediately."""
        input_folder = Path(self.config.input_folder)
        output_folder = Path(self.config.output_folder)

        self._log("Processing files now...")
        count = self.engine.process_folder(input_folder, output_folder)
        if count > 0:
            self.files_processed.emit(count)
            self._log(f"Processed {count} file(s)")
        else:
            self._log("No files to process")

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
        """Browse for PDF files to add."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if files:
            self._on_files_dropped(files)

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
        """Process the selected input file."""
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
                else:
                    self.engine.move_to_failed(pdf_path, reason="No items extracted")
            except Exception as e:
                self._log(f"Error: {e}")
                self.engine.move_to_failed(pdf_path, reason=str(e)[:50])

            self._refresh_input_files()
            self._refresh_output_files()

    def _delete_selected_input(self):
        """Delete the selected input file."""
        current = self.input_files_list.currentItem()
        if not current:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {current.text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            input_folder = Path(self.config.input_folder)
            pdf_path = input_folder / current.text()
            if pdf_path.exists():
                pdf_path.unlink()
                self._refresh_input_files()

    def _open_output_folder(self):
        """Open the output folder in file explorer."""
        import subprocess
        import platform

        folder = Path(self.config.output_folder)
        if folder.exists():
            if platform.system() == 'Windows':
                subprocess.run(['explorer', str(folder)])
            elif platform.system() == 'Darwin':
                subprocess.run(['open', str(folder)])
            else:
                subprocess.run(['xdg-open', str(folder)])

    def _refresh_stats(self):
        """Refresh processing statistics."""
        # TODO: Implement actual stats tracking
        self.stats_labels['processed_today'].setText("--")
        self.stats_labels['items_today'].setText("--")
        self.stats_labels['errors_today'].setText("--")
        self.stats_labels['last_processing'].setText("--")

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
