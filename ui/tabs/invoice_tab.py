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
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QApplication, QComboBox
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
    """QListWidget that accepts file drops - respects application theme."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # DropOnly mode for accepting external file drops
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setObjectName("dropListWidget")
        self._is_dragging = False
        self._drop_in_progress = False  # Prevent re-entrant drop handling
        # Cache the base stylesheet to avoid dynamic updates during drag
        self._init_style()

    def _init_style(self):
        """Initialize the base style for the widget."""
        try:
            app = QApplication.instance()
            if app:
                palette = app.palette()
                self._highlight_color = palette.color(palette.ColorRole.Highlight).name()
                self._base_color = palette.color(palette.ColorRole.Base).name()
                self._midlight_color = palette.color(palette.ColorRole.Midlight).name()
            else:
                # Fallback colors
                self._highlight_color = "#0078d4"
                self._base_color = "#ffffff"
                self._midlight_color = "#f0f0f0"
            self._apply_normal_style()
        except Exception:
            pass  # Fail silently if styling fails

    def _apply_normal_style(self):
        """Apply the normal (non-dragging) style."""
        try:
            self.setStyleSheet(f"""
                QListWidget#dropListWidget {{
                    border: 2px dashed {self._highlight_color};
                    border-radius: 4px;
                    background-color: {self._base_color};
                }}
                QListWidget#dropListWidget:hover {{
                    border: 2px dashed {self._highlight_color};
                }}
            """)
        except Exception:
            pass

    def _apply_dragging_style(self):
        """Apply the dragging style."""
        try:
            self.setStyleSheet(f"""
                QListWidget#dropListWidget {{
                    border: 2px solid {self._highlight_color};
                    border-radius: 4px;
                    background-color: {self._midlight_color};
                }}
            """)
        except Exception:
            pass

    def dragEnterEvent(self, event):
        try:
            if event.mimeData().hasUrls():
                # Check if any URLs are PDF files
                for url in event.mimeData().urls():
                    if url.toLocalFile().lower().endswith('.pdf'):
                        event.acceptProposedAction()
                        self._is_dragging = True
                        # Defer style update to avoid crash during drag event
                        QTimer.singleShot(0, self._apply_dragging_style)
                        return
            event.ignore()
        except Exception:
            event.ignore()

    def dragMoveEvent(self, event):
        """Required for drag and drop to work in PyQt6."""
        try:
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    if url.toLocalFile().lower().endswith('.pdf'):
                        event.acceptProposedAction()
                        return
            event.ignore()
        except Exception:
            event.ignore()

    def dragLeaveEvent(self, event):
        try:
            self._is_dragging = False
            # Defer style update to avoid crash during drag event
            QTimer.singleShot(0, self._apply_normal_style)
            event.accept()
        except Exception:
            pass

    def dropEvent(self, event):
        # Prevent re-entrant drop handling (fixes duplicate processing issue)
        if self._drop_in_progress:
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
            return
        self._drop_in_progress = True

        try:
            files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith('.pdf'):
                    files.append(file_path)

            self._is_dragging = False
            # Defer style update to avoid crash during drop event
            QTimer.singleShot(0, self._apply_normal_style)

            if files:
                self.files_dropped.emit(files)
                # Set drop action and accept - do NOT call super().dropEvent()
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
        except Exception:
            event.ignore()
        finally:
            self._drop_in_progress = False


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
                    # Try multiple invoice number formats
                    inv_match = re.search(r'(?:Proforma\s+)?[Ii]nvoice\s+(?:number|n)\.?\s*:?\s*(\d+(?:/\d+)?)', page_text)
                    if not inv_match:
                        # Try Vitech format: INVOICE # HFVT25-A001
                        inv_match = re.search(r'[Ii]nvoice\s*#\s*([A-Z0-9-]+)', page_text)
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
                if page_buffer:
                    buffer_text = "\n".join(page_buffer)
                    inv_num, proj_num, items = template.extract_all(buffer_text)
                    # Use template-extracted values as fallback if regex didn't find them
                    final_invoice = current_invoice or inv_num or "UNKNOWN"
                    final_project = current_project or proj_num or "UNKNOWN"
                    for item in items:
                        item['invoice_number'] = final_invoice
                        item['project_number'] = final_project
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
            # Look up MID and country_origin from manufacturer name (using mid_table)
            if ('mid' not in item or not item['mid']) or ('country_origin' not in item or not item['country_origin']):
                manufacturer_name = item.get('manufacturer_name', '')
                if manufacturer_name:
                    mid_entry = self.parts_db.get_mid_by_manufacturer_name(manufacturer_name)
                    if mid_entry:
                        if 'mid' not in item or not item['mid']:
                            if mid_entry.get('mid'):
                                item['mid'] = mid_entry.get('mid', '')
                        # Extract country from MID code (first 2 characters)
                        if 'country_origin' not in item or not item['country_origin']:
                            mid_code = mid_entry.get('mid', '')
                            if len(mid_code) >= 2:
                                item['country_origin'] = mid_code[:2].upper()

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

        # Get column mapping configuration
        mapping = self.config.get_output_column_mapping()
        if mapping and 'columns' in mapping:
            # Use configured columns (in order, only enabled ones)
            columns = []
            column_renames = {}
            for col_config in mapping['columns']:
                if col_config.get('enabled', True):
                    internal = col_config['internal_name']
                    display = col_config['display_name']
                    columns.append(internal)
                    if internal != display:
                        column_renames[internal] = display
        else:
            # Default columns
            columns = ['invoice_number', 'project_number', 'part_number', 'description', 'mid', 'country_origin', 'hts_code', 'quantity', 'total_price']
            column_renames = {}
            # Add any extra columns from items
            for item in items:
                for key in item.keys():
                    if key not in columns:
                        columns.append(key)

        # Check export options
        split_by_invoice = self.config.get_export_option('split_by_invoice', False)
        consolidate = self.config.consolidate_multi_invoice

        # Helper function to write CSV with renamed columns
        def write_csv_with_mapping(filepath, items_to_write, columns, renames):
            # Rename columns in header
            header = [renames.get(col, col) for col in columns]
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for item in items_to_write:
                    row = [item.get(col, '') for col in columns]
                    writer.writerow(row)

        if split_by_invoice:
            # Split by invoice - one file per invoice
            for inv_num, inv_items in by_invoice.items():
                proj_num = inv_items[0].get('project_number', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_inv_num = inv_num.replace('/', '-')
                filename = f"{safe_inv_num}_{proj_num}_{timestamp}.csv"
                filepath = output_folder / filename

                write_csv_with_mapping(filepath, inv_items, columns, column_renames)
                self.log(f"  Saved: {filename} ({len(inv_items)} items)")

        elif consolidate and len(by_invoice) > 1:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if pdf_name:
                base_name = Path(pdf_name).stem
            else:
                base_name = f"consolidated_{list(by_invoice.keys())[0]}"
            filename = f"{base_name}_{timestamp}.csv"
            filepath = output_folder / filename

            write_csv_with_mapping(filepath, items, columns, column_renames)

            invoice_list = ", ".join(sorted(by_invoice.keys()))
            self.log(f"  Saved: {filename} ({len(items)} items from {len(by_invoice)} invoices)")
        else:
            for inv_num, inv_items in by_invoice.items():
                proj_num = inv_items[0].get('project_number', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_inv_num = inv_num.replace('/', '-')
                filename = f"{safe_inv_num}_{proj_num}_{timestamp}.csv"
                filepath = output_folder / filename

                write_csv_with_mapping(filepath, inv_items, columns, column_renames)
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
    file_failed = pyqtSignal(str)  # Emitted when a file fails processing (filename)

    def __init__(self, config: ConfigManager, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.engine = ProcessorEngine(config, db, log_callback=self._log)
        self._is_processing = False
        self._last_results = []  # Store last processed results for preview
        self._first_show = True  # Track first show for initialization
        self._last_drop_time = 0  # Debounce for file drops

        self._setup_ui()
        self._connect_signals()
        self._load_config()

    def showEvent(self, event):
        """Handle first show to properly initialize layouts on Windows."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Delay the layout initialization to ensure proper rendering
            QTimer.singleShot(50, self._on_first_show)

    def _on_first_show(self):
        """Initialize layout after first show."""
        # Force tables to update for proper Windows rendering
        if hasattr(self, 'results_table'):
            self._delayed_column_init()
        if hasattr(self, 'preview_tabs'):
            self.preview_tabs.updateGeometry()
        self.updateGeometry()
        self.repaint()

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
        # Create scroll area to handle overflow
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumWidth(240)
        scroll_area.setMaximumWidth(320)
        # Set object name for specific styling
        scroll_area.setObjectName("sidebarScrollArea")
        scroll_area.setStyleSheet("""
            QScrollArea#sidebarScrollArea { background: transparent; border: none; }
            QScrollArea#sidebarScrollArea > QWidget > QWidget { background: transparent; }
        """)

        # Content widget inside scroll area
        sidebar = QWidget()
        sidebar.setObjectName("sidebarContent")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(6)

        # Input Files (PDFs) group - DropListWidget handles drops
        input_group = QGroupBox("Input Files (PDFs) - Drop files here")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(4)

        # Input files list with drop support
        self.input_files_list = DropListWidget()
        self.input_files_list.setAlternatingRowColors(True)
        self.input_files_list.setMinimumHeight(100)
        # Use UniqueConnection to prevent duplicate signal connections
        self.input_files_list.files_dropped.connect(
            self._on_files_dropped, Qt.ConnectionType.UniqueConnection
        )
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
        self.output_files_list.itemClicked.connect(self._load_output_file)
        self.output_files_list.itemDoubleClicked.connect(self._open_output_file)
        output_layout.addWidget(self.output_files_list)

        # Refresh button
        output_refresh_btn = QPushButton("Refresh")
        output_refresh_btn.clicked.connect(self._refresh_output_files)
        output_layout.addWidget(output_refresh_btn)

        layout.addWidget(output_group)

        # Actions group
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(4)
        actions_layout.setContentsMargins(8, 12, 8, 8)

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

        # Auto-process dropped files checkbox
        self.auto_process_drops_check = QCheckBox("Auto-process dropped files")
        self.auto_process_drops_check.setChecked(self.config.get('auto_process_drops', True))
        self.auto_process_drops_check.setToolTip(
            "When enabled, dropped files are processed immediately.\n"
            "When disabled, dropped files are copied to the input folder only."
        )
        self.auto_process_drops_check.stateChanged.connect(self._save_auto_process_drops)
        actions_layout.addWidget(self.auto_process_drops_check)

        # Separator line
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet("background-color: #ccc;")
        actions_layout.addWidget(line1)

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

        # Separator line
        line4 = QFrame()
        line4.setFrameShape(QFrame.Shape.HLine)
        line4.setStyleSheet("background-color: #ccc;")
        actions_layout.addWidget(line4)

        # Output Mapping Profile selector
        mapping_label = QLabel("Output Mapping Profile:")
        actions_layout.addWidget(mapping_label)

        self.mapping_profile_combo = QComboBox()
        self.mapping_profile_combo.setToolTip(
            "Select which output mapping profile to use when exporting CSVs.\n"
            "Profiles control which columns are exported and their order."
        )
        self.mapping_profile_combo.currentTextChanged.connect(self._on_mapping_profile_changed)
        actions_layout.addWidget(self.mapping_profile_combo)

        # Refresh profiles list
        self._refresh_mapping_profiles()

        layout.addWidget(actions_group)

        layout.addStretch()

        # Set the sidebar as the scroll area's widget
        scroll_area.setWidget(sidebar)
        return scroll_area

    def _create_right_panel(self) -> QWidget:
        """Create the right panel with tabbed preview (Processing Results / Exported Files)."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(8)

        # Tabbed preview panel
        self.preview_tabs = QTabWidget()

        # Tab 1: Processing Results (shows extracted data before/after processing)
        processing_results_widget = self._create_processing_results_tab()
        self.preview_tabs.addTab(processing_results_widget, "Processing Results")

        # Tab 2: Exported Files (shows CSV content when clicking Output Files)
        exported_files_widget = self._create_exported_files_tab()
        self.preview_tabs.addTab(exported_files_widget, "Exported Files")

        layout.addWidget(self.preview_tabs)

        # Schedule a repaint after the widget is fully initialized (fixes Windows Qt6 rendering)
        QTimer.singleShot(50, self._force_panel_repaint)

        # Create hidden log viewer for background logging (accessible via Help menu)
        self._setup_background_log()

        return panel

    def _force_panel_repaint(self):
        """Force the right panel and tables to repaint properly on Windows."""
        try:
            if hasattr(self, 'preview_tabs'):
                self.preview_tabs.updateGeometry()
                self.preview_tabs.repaint()
            if hasattr(self, 'results_table'):
                self.results_table.updateGeometry()
                self.results_table.repaint()
                if self.results_table.viewport():
                    self.results_table.viewport().repaint()
            if hasattr(self, 'exported_file_table'):
                self.exported_file_table.updateGeometry()
                self.exported_file_table.repaint()
                if self.exported_file_table.viewport():
                    self.exported_file_table.viewport().repaint()
            self.updateGeometry()
            self.repaint()
        except Exception:
            pass  # Fail silently if repaint fails

    def _create_processing_results_tab(self) -> QWidget:
        """Create the Processing Results tab content (shows extracted data after processing)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header label
        header = QLabel("Extracted data from processed PDFs:")
        header.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(header)

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

        return widget

    def _create_exported_files_tab(self) -> QWidget:
        """Create the Exported Files tab content (shows CSV content when clicking Output Files)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header label
        header = QLabel("Click a CSV file in Output Files to preview its contents:")
        header.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(header)

        # Table to preview exported CSV content
        self.exported_file_table = QTableWidget()
        self.exported_file_table.setAlternatingRowColors(True)
        self.exported_file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.exported_file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.exported_file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.exported_file_table.horizontalHeader().setStretchLastSection(True)

        # Initialize with placeholder
        self.exported_file_table.setColumnCount(1)
        self.exported_file_table.setHorizontalHeaderLabels(["Select a CSV file from Output Files to preview"])
        self.exported_file_table.setRowCount(0)

        layout.addWidget(self.exported_file_table)

        # Status bar for exported file
        status_layout = QHBoxLayout()
        self.exported_file_status = QLabel("No file selected")
        self.exported_file_status.setStyleSheet("color: #666;")
        status_layout.addWidget(self.exported_file_status)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        return widget

    def _setup_background_log(self):
        """Set up background logging (log viewer accessible via Help menu)."""
        # Create a hidden log viewer widget for storing log messages
        self.log_viewer = LogViewerWidget()
        self.log_viewer.setVisible(False)  # Hidden - accessed via Help > Activity Log

    def _init_results_columns(self):
        """Initialize results table with default columns."""
        # Default columns - will be updated dynamically based on extracted data
        default_columns = [
            "Part Number", "Description", "Quantity", "Unit Price", "Total",
            "Invoice #", "Project #"
        ]
        self.results_table.setColumnCount(len(default_columns))
        self.results_table.setHorizontalHeaderLabels(default_columns)

        # Set all columns to ResizeToContents initially for proper header display
        header = self.results_table.horizontalHeader()
        header.setMinimumSectionSize(60)  # Ensure minimum readable width

        # Set specific column widths
        column_widths = [110, 180, 70, 85, 85, 75, 90]  # Part#, Desc, Qty, UnitP, Total, Inv#, Proj#

        for i, width in enumerate(column_widths):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            self.results_table.setColumnWidth(i, width)

        # Make Description column stretch to fill available space
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Ensure horizontal scrollbar is available if needed
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Schedule delayed initialization for Windows rendering fix
        QTimer.singleShot(100, self._delayed_column_init)

    def _force_header_repaint(self):
        """Force the table header to repaint properly."""
        try:
            if not hasattr(self, 'results_table'):
                return
            header = self.results_table.horizontalHeader()
            if header:
                header.updateGeometry()
                header.repaint()
            viewport = self.results_table.viewport()
            if viewport:
                viewport.update()
        except Exception:
            pass  # Fail silently if repaint fails

    def _delayed_column_init(self):
        """Delayed column initialization for Windows rendering fix."""
        try:
            if not hasattr(self, 'results_table'):
                return

            # Re-apply column widths after widget is fully initialized
            column_widths = [110, 180, 70, 85, 85, 75, 90]
            for i, width in enumerate(column_widths):
                if i < self.results_table.columnCount():
                    self.results_table.setColumnWidth(i, width)

            # Force header and table update
            header = self.results_table.horizontalHeader()
            if header:
                header.updateGeometry()

                # Ensure Description column stretches
                if self.results_table.columnCount() > 1:
                    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            self.results_table.updateGeometry()
            self.results_table.repaint()

            viewport = self.results_table.viewport()
            if viewport:
                viewport.update()
        except Exception:
            pass  # Fail silently if initialization fails

    def _update_results_table(self, items: list):
        """Update the results table with extracted items (dynamic columns)."""
        import traceback

        try:
            if not items:
                self._log("No items to display in results table")
                return

            self._log(f"Updating results table with {len(items)} items...")
            self._last_results = items

            # Switch to Processing Results tab to show the user the results
            if hasattr(self, 'preview_tabs'):
                self.preview_tabs.setCurrentIndex(0)  # Processing Results is tab 0

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

            self._log(f"Results table updated: {self.results_table.rowCount()} rows, {self.results_table.columnCount()} columns")
        except Exception as e:
            error_msg = traceback.format_exc()
            self._log(f"ERROR updating results table: {e}")
            self._write_crash_log("Error in _update_results_table", error_msg)

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

        # Apply saved mapping profile on startup
        saved_profile = self.config.get_export_option('selected_mapping_profile', 'Default')
        if saved_profile and saved_profile != 'Default':
            profiles = self.config.get_output_mapping_profiles()
            if saved_profile in profiles:
                self.config.set_output_column_mapping(profiles[saved_profile])

        # Refresh file lists
        self._refresh_input_files()
        self._refresh_output_files()

    def reload_config(self):
        """Reload configuration after settings change."""
        self._load_config()
        self._refresh_mapping_profiles()
        self.engine = ProcessorEngine(self.config, self.db, log_callback=self._log)

    # ----- Settings handlers -----

    def _save_auto_start(self, state: int):
        """Save auto-start setting."""
        self.config.auto_start = (state == Qt.CheckState.Checked.value)

    def _save_auto_process_drops(self, state: int):
        """Save auto-process dropped files setting."""
        self.config.set('auto_process_drops', state == Qt.CheckState.Checked.value)

    def _save_multi_invoice_mode(self, checked: bool):
        """Save multi-invoice PDF mode (split vs combine)."""
        # Split = NOT consolidate, Combine = consolidate
        self.config.consolidate_multi_invoice = self.combine_radio.isChecked()

    def _save_template_enabled(self, name: str, state: int):
        """Save template enabled state."""
        self.config.set_template_enabled(name, state == Qt.CheckState.Checked.value)

    def _refresh_mapping_profiles(self):
        """Refresh the output mapping profile dropdown."""
        # Block signals to prevent triggering change handler during refresh
        self.mapping_profile_combo.blockSignals(True)

        current_selection = self.mapping_profile_combo.currentText()
        self.mapping_profile_combo.clear()

        # Add "Default" option
        self.mapping_profile_combo.addItem("Default")

        # Add saved profiles
        profiles = self.config.get_output_mapping_profiles()
        for profile_name in sorted(profiles.keys()):
            self.mapping_profile_combo.addItem(profile_name)

        # Restore previous selection or load saved selection
        saved_profile = self.config.get_export_option('selected_mapping_profile', 'Default')

        if current_selection:
            # Try to restore current selection
            idx = self.mapping_profile_combo.findText(current_selection)
            if idx >= 0:
                self.mapping_profile_combo.setCurrentIndex(idx)
            else:
                # Current selection no longer exists, fall back to saved
                idx = self.mapping_profile_combo.findText(saved_profile)
                self.mapping_profile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            # Initial load - use saved profile
            idx = self.mapping_profile_combo.findText(saved_profile)
            self.mapping_profile_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self.mapping_profile_combo.blockSignals(False)

    def _on_mapping_profile_changed(self, profile_name: str):
        """Handle output mapping profile selection change."""
        if not profile_name:
            return

        # Save the selection
        self.config.set_export_option('selected_mapping_profile', profile_name)

        if profile_name == "Default":
            # Clear active mapping to use default columns
            self.config.set_output_column_mapping({})
            self._log(f"Output mapping: Using default columns")
        else:
            # Load and apply the selected profile
            profiles = self.config.get_output_mapping_profiles()
            if profile_name in profiles:
                profile_mapping = profiles[profile_name]
                self.config.set_output_column_mapping(profile_mapping)
                self._log(f"Output mapping: {profile_name}")
            else:
                self._log(f"Warning: Profile '{profile_name}' not found")

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
                    self.file_failed.emit(pdf_path.name)
            except Exception as e:
                self._log(f"Error processing {pdf_path.name}: {e}")
                self.engine.move_to_failed(pdf_path, reason=str(e)[:50])
                self.file_failed.emit(pdf_path.name)

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
        """Handle files dropped on drop zone - behavior controlled by toggle."""
        import time
        import traceback
        import shutil

        try:
            # Debounce: ignore drops within 500ms of each other (prevents double-processing)
            current_time = time.time()
            if current_time - self._last_drop_time < 0.5:
                return  # Ignore duplicate drop event
            self._last_drop_time = current_time

            self._log(f"Files dropped: {len(files)} PDF(s)")

            if not files:
                return

            # Check if auto-process is enabled
            auto_process = self.config.get('auto_process_drops', True)

            if auto_process:
                # Process files directly - this updates the results table
                self._process_pdf_files(files)
            else:
                # Just copy files to input folder (don't process)
                input_folder = Path(self.config.input_folder)
                input_folder.mkdir(exist_ok=True, parents=True)

                copied_count = 0
                for file_path in files:
                    src = Path(file_path)
                    if src.exists() and src.suffix.lower() == '.pdf':
                        dest = input_folder / src.name
                        # Avoid overwriting - add number suffix if exists
                        if dest.exists():
                            base = dest.stem
                            suffix = dest.suffix
                            counter = 1
                            while dest.exists():
                                dest = input_folder / f"{base}_{counter}{suffix}"
                                counter += 1
                        shutil.copy2(src, dest)
                        copied_count += 1
                        self._log(f"Copied to input folder: {dest.name}")

                if copied_count > 0:
                    self._log(f"Copied {copied_count} file(s) to input folder")
                    self._refresh_input_files()
        except Exception as e:
            # Log the full exception to crash log and activity log
            error_msg = traceback.format_exc()
            self._log(f"ERROR in _on_files_dropped: {e}")
            self._write_crash_log("Error in _on_files_dropped", error_msg)

    def _browse_files(self):
        """Browse for PDF files to process directly."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if files:
            self._process_pdf_files(files)

    def _process_pdf_files(self, file_paths: list):
        """Process PDF files directly and show results in preview table."""
        import traceback
        import time

        try:
            output_folder = Path(self.config.output_folder)
            output_folder.mkdir(exist_ok=True, parents=True)

            all_items = []
            processed_count = 0

            for file_path in file_paths:
                pdf_path = Path(file_path)
                # Note: engine.process_pdf already logs "Processing: {filename}"
                start_time = time.time()
                template_used = None

                try:
                    items = self.engine.process_pdf(pdf_path)
                    processing_time_ms = int((time.time() - start_time) * 1000)

                    # Get template name if available
                    if hasattr(self.engine, 'last_template_used'):
                        template_used = self.engine.last_template_used

                    if items:
                        all_items.extend(items)
                        self.engine.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                        processed_count += 1
                        self._log(f"  Extracted {len(items)} items")

                        # Record success in processing history
                        self.parts_db.record_processing_history(
                            file_name=pdf_path.name,
                            template_used=template_used,
                            items_extracted=len(items),
                            status='SUCCESS',
                            processing_time_ms=processing_time_ms
                        )
                    else:
                        self._log(f"  No items extracted from {pdf_path.name}")
                        self.file_failed.emit(pdf_path.name)

                        # Record partial/no-extract in processing history
                        self.parts_db.record_processing_history(
                            file_name=pdf_path.name,
                            template_used=template_used,
                            items_extracted=0,
                            status='PARTIAL',
                            processing_time_ms=processing_time_ms,
                            error_message='No items extracted'
                        )
                except Exception as e:
                    processing_time_ms = int((time.time() - start_time) * 1000)
                    self._log(f"  Error: {e}")
                    # Log to crash file for diagnostics
                    error_msg = traceback.format_exc()
                    self._write_crash_log(f"Error processing {pdf_path.name}", error_msg)
                    self.file_failed.emit(pdf_path.name)

                    # Record failure in processing history
                    self.parts_db.record_processing_history(
                        file_name=pdf_path.name,
                        template_used=template_used,
                        items_extracted=0,
                        status='FAILED',
                        processing_time_ms=processing_time_ms,
                        error_message=str(e)[:500]  # Limit error message length
                    )

            if processed_count > 0:
                self.files_processed.emit(processed_count)
                self._log(f"Processed {processed_count} file(s), {len(all_items)} total items")

                # Update results preview table
                if all_items:
                    self._update_results_table(all_items)

            self._refresh_output_files()
        except Exception as e:
            error_msg = traceback.format_exc()
            self._log(f"ERROR in _process_pdf_files: {e}")
            self._write_crash_log("Error in _process_pdf_files", error_msg)

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

    def _load_output_file(self, item: QListWidgetItem):
        """Load selected CSV file and display in Exported File Preview table."""
        if not item:
            return

        output_folder = Path(self.config.output_folder)
        csv_path = output_folder / item.text()

        if not csv_path.exists():
            self._log(f"File not found: {csv_path.name}")
            return

        try:
            import csv
            items = []
            headers = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                for row in reader:
                    items.append(dict(row))

            if items and headers:
                self._update_exported_file_table(items, headers, csv_path.name)
                self._log(f"Loaded {len(items)} items from {csv_path.name}")
            else:
                self._log(f"No data found in {csv_path.name}")
                self.exported_file_table.setRowCount(0)
                self.exported_file_table.setColumnCount(1)
                self.exported_file_table.setHorizontalHeaderLabels(["No data in file"])
                self.exported_file_status.setText("No items to display")
        except Exception as e:
            self._log(f"Error loading CSV: {e}")

    def _open_output_file(self, item: QListWidgetItem):
        """Double-click handler: Load CSV and switch to Exported Files tab."""
        if not item:
            return

        # Load the file content
        self._load_output_file(item)

        # Switch to Exported Files tab (tab index 1)
        if hasattr(self, 'preview_tabs'):
            self.preview_tabs.setCurrentIndex(1)

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
                    self.file_failed.emit(pdf_path.name)
            except Exception as e:
                self._log(f"Error: {e}")
                self.engine.move_to_failed(pdf_path, reason=str(e)[:50])
                self.file_failed.emit(pdf_path.name)

            self._refresh_input_files()
            self._refresh_output_files()

    # ----- Exported File Preview -----

    def _update_exported_file_table(self, items: list, headers: list, filename: str):
        """Update the exported file preview table with CSV data."""
        try:
            # Set up columns
            self.exported_file_table.setColumnCount(len(headers))

            # Create display-friendly headers
            display_headers = [h.replace('_', ' ').title() for h in headers]
            self.exported_file_table.setHorizontalHeaderLabels(display_headers)

            # Populate rows
            self.exported_file_table.setRowCount(len(items))
            for row_idx, item in enumerate(items):
                for col_idx, header in enumerate(headers):
                    value = item.get(header, '')
                    if value is None:
                        value = ''
                    cell = QTableWidgetItem(str(value))
                    self.exported_file_table.setItem(row_idx, col_idx, cell)

            # Update status
            self.exported_file_status.setText(f"{filename}: {len(items)} rows")

            # Resize columns to content
            self.exported_file_table.resizeColumnsToContents()
        except Exception as e:
            self._log(f"Error updating exported file table: {e}")

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

    def get_log_text(self) -> str:
        """Get all log text for display in dialog."""
        return self.log_viewer.get_text()

    def clear_log(self):
        """Clear the activity log."""
        self.log_viewer.clear()

    def _write_crash_log(self, context: str, error_msg: str):
        """Write an error to the crash log file for diagnostics."""
        try:
            crash_log = Path(__file__).parent.parent.parent / "crash_log.txt"
            with open(crash_log, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"{context} - {datetime.now()}\n")
                f.write(f"{'='*60}\n")
                f.write(error_msg)
                f.write("\n")
        except Exception:
            pass  # Fail silently if we can't write to log
