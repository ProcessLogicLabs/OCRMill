"""
OCRMill - Invoice Processing Suite
Unified GUI application for invoice processing and parts database management.
"""

__version__ = "2.2.0"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import time
import csv
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

try:
    import pdfplumber
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from config_manager import ConfigManager
from templates import get_all_templates, TEMPLATE_REGISTRY
from parts_database import PartsDatabase, create_parts_report


class LogHandler:
    """Custom log handler that writes to a queue for GUI display."""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def write(self, message: str):
        if message.strip():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_queue.put(f"[{timestamp}] {message}")

    def flush(self):
        pass


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

    def process_pdf(self, pdf_path: Path) -> List[Dict]:
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

                    # Skip packing list pages
                    if 'packing list' in page_text.lower() and 'invoice' not in page_text.lower():
                        continue

                    # Check for new invoice on this page
                    import re
                    inv_match = re.search(r'(?:Proforma\s+)?[Ii]nvoice\s+(?:number|n)\.?\s*:?\s*(\d+(?:/\d+)?)', page_text)
                    proj_match = re.search(r'(?:\d+\.\s*)?[Pp]roject\s*(?:n\.?)?\s*:?\s*(US\d+[A-Z]\d+)', page_text, re.IGNORECASE)

                    # If we found a new invoice number, process the buffer first
                    new_invoice = inv_match.group(1) if inv_match else None
                    if new_invoice and current_invoice and new_invoice != current_invoice:
                        # Process accumulated pages for previous invoice
                        if page_buffer:
                            buffer_text = "\n".join(page_buffer)
                            _, _, items = template.extract_all(buffer_text)
                            for item in items:
                                item['invoice_number'] = current_invoice
                                item['project_number'] = current_project
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
                    all_items.extend(items)

                # Count unique invoices and calculate grand total
                unique_invoices = set(item.get('invoice_number', 'UNKNOWN') for item in all_items)
                grand_total = sum(float(item.get('total_price', 0) or 0) for item in all_items)
                self.log(f"  Found {len(unique_invoices)} invoice(s), {len(all_items)} total items, Grand Total: ${grand_total:,.2f}")
                for inv in sorted(unique_invoices):
                    inv_items = [item for item in all_items if item.get('invoice_number') == inv]
                    proj = inv_items[0].get('project_number', 'UNKNOWN') if inv_items else 'UNKNOWN'
                    total_value = sum(float(item.get('total_price', 0) or 0) for item in inv_items)
                    self.log(f"    - Invoice {inv} (Project {proj}): {len(inv_items)} items, ${total_value:,.2f}")

                return all_items

        except Exception as e:
            self.log(f"  Error processing {pdf_path.name}: {e}")
            return []

    def save_to_csv(self, items: List[Dict], output_folder: Path, pdf_name: str = None):
        """Save items to CSV files and add to parts database."""
        if not items:
            return

        # Add items to parts database and enrich with descriptions, HTS codes, and MID
        for item in items:
            part_data = item.copy()
            part_data['source_file'] = pdf_name or 'unknown'
            self.parts_db.add_part_occurrence(part_data)

            # Add description and HTS code back to item for CSV export
            if 'description' not in item or not item['description']:
                item['description'] = part_data.get('description', '')
            if 'hts_code' not in item or not item['hts_code']:
                item['hts_code'] = part_data.get('hts_code', '')

            # Look up MID from manufacturer name extracted from invoice
            if 'mid' not in item or not item['mid']:
                manufacturer_name = item.get('manufacturer_name', '')
                if manufacturer_name:
                    manufacturer = self.parts_db.get_manufacturer_by_name(manufacturer_name)
                    if manufacturer and manufacturer.get('mid'):
                        item['mid'] = manufacturer.get('mid', '')

                if 'mid' not in item or not item['mid']:
                    part_summary = self.parts_db.get_part_summary(item.get('part_number', ''))
                    if part_summary and part_summary.get('mid'):
                        item['mid'] = part_summary.get('mid', '')

            # Remove manufacturer_name from item (we only need MID in output)
            if 'manufacturer_name' in item:
                del item['manufacturer_name']

        # Group by invoice number
        by_invoice = {}
        for item in items:
            inv_num = item.get('invoice_number', 'UNKNOWN')
            if inv_num not in by_invoice:
                by_invoice[inv_num] = []
            by_invoice[inv_num].append(item)

        # Determine columns from items with specific ordering
        columns = ['invoice_number', 'project_number', 'part_number', 'description', 'mid', 'hts_code', 'quantity', 'total_price']

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
            self.log(f"  Saved: {filename} ({len(items)} items from {len(by_invoice)} invoices: {invoice_list})")

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

    def move_to_processed(self, pdf_path: Path, processed_folder: Path):
        """Move processed PDF to the Processed folder."""
        processed_folder.mkdir(exist_ok=True, parents=True)

        dest = processed_folder / pdf_path.name
        counter = 1
        while dest.exists():
            stem = pdf_path.stem
            dest = processed_folder / f"{stem}_{counter}{pdf_path.suffix}"
            counter += 1

        pdf_path.rename(dest)
        self.log(f"  Moved to: Processed/{dest.name}")

    def move_to_failed(self, pdf_path: Path, failed_folder: Path, reason: str = ""):
        """Move failed PDF to the Failed folder."""
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
        failed_count = 0

        for pdf_path in pdf_files:
            try:
                items = self.process_pdf(pdf_path)
                if items:
                    self.save_to_csv(items, output_folder, pdf_name=pdf_path.name)
                    self.move_to_processed(pdf_path, processed_folder)
                    processed_count += 1
                else:
                    self.move_to_failed(pdf_path, failed_folder, "No items extracted")
                    failed_count += 1
            except Exception as e:
                self.log(f"  Error processing {pdf_path.name}: {e}")
                self.move_to_failed(pdf_path, failed_folder, f"Error: {str(e)[:50]}")
                failed_count += 1

        if failed_count > 0:
            self.log(f"Summary: {processed_count} processed successfully, {failed_count} failed")

        return processed_count


class ManufacturerEditDialog:
    """Dialog for adding/editing a manufacturer."""

    def __init__(self, parent, db, mfr_id=None, on_save=None):
        self.db = db
        self.mfr_id = mfr_id
        self.on_save = on_save

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Manufacturer" if mfr_id else "Add Manufacturer")
        self.dialog.geometry("450x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

        if mfr_id:
            self._load_data()

    def _create_widgets(self):
        """Create dialog widgets."""
        form_frame = ttk.Frame(self.dialog, padding="10")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Company Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.company_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.company_var, width=40).grid(row=0, column=1, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Country:").grid(row=1, column=0, sticky="w", pady=5)
        self.country_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.country_var, width=40).grid(row=1, column=1, pady=5, sticky="ew")

        ttk.Label(form_frame, text="MID:").grid(row=2, column=0, sticky="w", pady=5)
        self.mid_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.mid_var, width=40).grid(row=2, column=1, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Notes:").grid(row=3, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(form_frame, width=40, height=4)
        self.notes_text.grid(row=3, column=1, pady=5, sticky="ew")

        form_frame.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self.dialog, padding="10")
        btn_frame.pack(fill="x", side="bottom")

        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right", padx=5)

    def _load_data(self):
        """Load existing manufacturer data."""
        manufacturers = self.db.get_all_manufacturers()
        mfr = next((m for m in manufacturers if m['id'] == self.mfr_id), None)

        if mfr:
            self.company_var.set(mfr.get('company_name', ''))
            self.country_var.set(mfr.get('country', ''))
            self.mid_var.set(mfr.get('mid', ''))
            self.notes_text.insert("1.0", mfr.get('notes', '') or '')

    def _save(self):
        """Save the manufacturer."""
        company_name = self.company_var.get().strip()
        if not company_name:
            messagebox.showerror("Error", "Company name is required.")
            return

        country = self.country_var.get().strip()
        mid = self.mid_var.get().strip()
        notes = self.notes_text.get("1.0", "end-1c").strip()

        try:
            if self.mfr_id:
                self.db.update_manufacturer(self.mfr_id, company_name, country, mid, notes)
            else:
                self.db.add_manufacturer(company_name, country, mid, notes)

            if self.on_save:
                self.on_save()

            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")


class ManufacturersDialog:
    """Dialog for managing manufacturers/MID list."""

    def __init__(self, parent, db):
        self.db = db
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manufacturers / MID List")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_data()

    def _create_widgets(self):
        """Create dialog widgets."""
        btn_frame = ttk.Frame(self.dialog, padding="5")
        btn_frame.pack(fill="x", side="top")

        ttk.Button(btn_frame, text="Add New", command=self._add_new).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._load_data).pack(side="left", padx=2)

        ttk.Label(btn_frame, text="Search:").pack(side="left", padx=(20, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._search())
        search_entry = ttk.Entry(btn_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=2)

        tree_frame = ttk.Frame(self.dialog)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("id", "company_name", "country", "mid", "notes")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        self.tree.heading("id", text="ID")
        self.tree.heading("company_name", text="Company Name")
        self.tree.heading("country", text="Country")
        self.tree.heading("mid", text="MID")
        self.tree.heading("notes", text="Notes")

        self.tree.column("id", width=50)
        self.tree.column("company_name", width=250)
        self.tree.column("country", width=100)
        self.tree.column("mid", width=150)
        self.tree.column("notes", width=200)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.dialog, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

        close_frame = ttk.Frame(self.dialog, padding="5")
        close_frame.pack(fill="x", side="bottom")
        ttk.Button(close_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def _load_data(self):
        """Load manufacturers into treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        manufacturers = self.db.get_all_manufacturers()
        for mfr in manufacturers:
            values = (
                mfr.get('id', ''),
                mfr.get('company_name', ''),
                mfr.get('country', ''),
                mfr.get('mid', ''),
                mfr.get('notes', '')
            )
            self.tree.insert("", "end", values=values)

        self.status_var.set(f"Loaded {len(manufacturers)} manufacturers")

    def _search(self):
        """Search manufacturers."""
        search_term = self.search_var.get()

        for item in self.tree.get_children():
            self.tree.delete(item)

        if search_term:
            manufacturers = self.db.search_manufacturers(search_term)
        else:
            manufacturers = self.db.get_all_manufacturers()

        for mfr in manufacturers:
            values = (
                mfr.get('id', ''),
                mfr.get('company_name', ''),
                mfr.get('country', ''),
                mfr.get('mid', ''),
                mfr.get('notes', '')
            )
            self.tree.insert("", "end", values=values)

        self.status_var.set(f"Found {len(manufacturers)} manufacturers")

    def _add_new(self):
        """Add new manufacturer."""
        ManufacturerEditDialog(self.dialog, self.db, on_save=self._load_data)

    def _edit_selected(self):
        """Edit selected manufacturer."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a manufacturer to edit.")
            return

        item = self.tree.item(selection[0])
        mfr_id = item['values'][0]

        ManufacturerEditDialog(self.dialog, self.db, mfr_id=mfr_id, on_save=self._load_data)

    def _delete_selected(self):
        """Delete selected manufacturer."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a manufacturer to delete.")
            return

        item = self.tree.item(selection[0])
        mfr_id = item['values'][0]
        company_name = item['values'][1]

        if messagebox.askyesno("Confirm Delete", f"Delete manufacturer '{company_name}'?"):
            self.db.delete_manufacturer(mfr_id)
            self._load_data()


class OCRMillApp:
    """Unified OCRMill Application - Invoice Processing Suite."""

    def __init__(self):
        # Initialize root window (with drag-drop support if available)
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title(f"OCRMill - Invoice Processing Suite v{__version__}")
        self.root.geometry("1200x750")

        # Shared resources
        self.config = ConfigManager()
        self.db = PartsDatabase(db_path=self.config.database_path)
        self.log_queue = queue.Queue()

        # Processing state
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.processing_lock = threading.Lock()  # Prevents concurrent processing
        self.files_processed = 0
        self.last_check: Optional[str] = None

        # Create the processor engine
        self.engine = ProcessorEngine(self.config, self.db, log_callback=self._queue_log)

        # Build the UI
        self._create_menu()
        self._create_main_ui()
        self._create_status_bar()

        # Start log consumer
        self._consume_logs()

        # Auto-start if configured
        if self.config.auto_start:
            self.root.after(1000, self.start_processing)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Initial data load
        self._load_parts_data()
        self._update_parts_statistics()
        self._load_hts_list()

    def _create_menu(self):
        """Create the unified menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Parts List...", command=self._load_hts_file)
        file_menu.add_command(label="Export Master CSV...", command=self._export_master)
        file_menu.add_command(label="Export History CSV...", command=self._export_history)
        file_menu.add_separator()
        file_menu.add_command(label="Generate Reports...", command=self._generate_reports)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # Lists menu
        lists_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Lists", menu=lists_menu)
        lists_menu.add_command(label="Manufacturers/MID...", command=self._show_manufacturers_dialog)

        # Processing menu
        proc_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Processing", menu=proc_menu)
        proc_menu.add_command(label="Start Monitoring", command=self.start_processing)
        proc_menu.add_command(label="Stop Monitoring", command=self.stop_processing)
        proc_menu.add_command(label="Process Now", command=self.process_now)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Change Database Location...", command=self._change_database_location)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _create_main_ui(self):
        """Create the main user interface with tabbed notebook."""
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Main notebook for Invoice Processing and Parts Database
        self.main_notebook = ttk.Notebook(self.root)
        self.main_notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # === Invoice Processing Tab ===
        self.invoice_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.invoice_frame, text="Invoice Processing")
        self._create_invoice_processing_tab()

        # === Parts Database Tab ===
        self.parts_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.parts_frame, text="Parts Database")
        self._create_parts_database_tab()

    def _create_invoice_processing_tab(self):
        """Create the invoice processing tab content."""
        self.invoice_frame.grid_columnconfigure(0, weight=1)
        self.invoice_frame.grid_rowconfigure(3, weight=1)  # Adjusted for drop zone

        # === Header Frame ===
        header_frame = ttk.Frame(self.invoice_frame, padding="10")
        header_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(header_frame, text="Invoice Processor", font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        self.status_label = ttk.Label(header_frame, text="Stopped", foreground="red", font=('Helvetica', 11))
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # === Settings Frame ===
        settings_frame = ttk.LabelFrame(self.invoice_frame, text="Settings", padding="10")
        settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        settings_frame.grid_columnconfigure(1, weight=1)

        # Input folder
        ttk.Label(settings_frame, text="Input Folder:").grid(row=0, column=0, sticky="w", pady=2)
        self.input_var = tk.StringVar(value=str(self.config.input_folder))
        input_entry = ttk.Entry(settings_frame, textvariable=self.input_var)
        input_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(settings_frame, text="Browse...", command=self._browse_input).grid(row=0, column=2, pady=2)

        # Output folder
        ttk.Label(settings_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=2)
        self.output_var = tk.StringVar(value=str(self.config.output_folder))
        output_entry = ttk.Entry(settings_frame, textvariable=self.output_var)
        output_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        ttk.Button(settings_frame, text="Browse...", command=self._browse_output).grid(row=1, column=2, pady=2)

        # Poll interval
        ttk.Label(settings_frame, text="Poll Interval (sec):").grid(row=2, column=0, sticky="w", pady=2)
        self.poll_var = tk.StringVar(value=str(self.config.poll_interval))
        poll_spinbox = ttk.Spinbox(settings_frame, from_=5, to=300, textvariable=self.poll_var, width=10)
        poll_spinbox.grid(row=2, column=1, sticky="w", padx=5, pady=2)

        # Auto-start checkbox
        self.autostart_var = tk.BooleanVar(value=self.config.auto_start)
        ttk.Checkbutton(settings_frame, text="Auto-start on launch", variable=self.autostart_var,
                       command=self._save_autostart).grid(row=2, column=2, pady=2)

        # Multi-invoice consolidation option
        ttk.Label(settings_frame, text="Multi-Invoice PDFs:").grid(row=3, column=0, sticky="w", pady=2)
        self.consolidate_var = tk.BooleanVar(value=self.config.consolidate_multi_invoice)
        ttk.Checkbutton(settings_frame, text="Consolidate into one CSV per PDF",
                       variable=self.consolidate_var,
                       command=self._save_consolidate).grid(row=3, column=1, sticky="w", padx=5, pady=2, columnspan=2)

        # Control buttons
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_processing, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_processing, width=12, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Process Now", command=self.process_now, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Save Settings", command=self._save_settings, width=12).pack(side=tk.LEFT, padx=5)

        # === PDF Drop Zone ===
        drop_frame = ttk.LabelFrame(self.invoice_frame, text="Drop PDF Files Here", padding="5")
        drop_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.pdf_drop_label = tk.Label(
            drop_frame,
            text="Drag and drop PDF invoice files here to process\nor click to browse for files",
            bg="#e8f4e8",
            fg="#2e7d32",
            font=("Segoe UI", 10),
            relief="ridge",
            padx=20,
            pady=15,
            cursor="hand2"
        )
        self.pdf_drop_label.pack(fill="x", padx=5, pady=5)

        # Bind click to browse
        self.pdf_drop_label.bind("<Button-1>", lambda e: self._browse_pdf_files())

        # Set up drag-and-drop for PDFs if available
        if HAS_DND:
            self._setup_pdf_drag_drop()
        else:
            self.pdf_drop_label.config(
                text="Click to browse for PDF invoice files\n(Install tkinterdnd2 for drag-and-drop support)",
                bg="#fff3e0",
                fg="#e65100"
            )

        # === Sub-notebook for Activity Log, Templates, Statistics ===
        sub_notebook = ttk.Notebook(self.invoice_frame)
        sub_notebook.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        # --- Log Tab ---
        log_frame = ttk.Frame(sub_notebook, padding="5")
        sub_notebook.add(log_frame, text="Activity Log")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.grid(row=1, column=0, sticky="e", pady=5)
        ttk.Button(log_btn_frame, text="Clear Log", command=self._clear_log).pack(side=tk.RIGHT)

        # --- Templates Tab ---
        template_frame = ttk.Frame(sub_notebook, padding="5")
        sub_notebook.add(template_frame, text="Templates")
        template_frame.grid_columnconfigure(0, weight=1)
        template_frame.grid_rowconfigure(0, weight=1)

        self.template_vars = {}
        template_list_frame = ttk.LabelFrame(template_frame, text="Available Templates", padding="10")
        template_list_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        for i, (name, template) in enumerate(get_all_templates().items()):
            var = tk.BooleanVar(value=self.config.get_template_enabled(name))
            self.template_vars[name] = var

            frame = ttk.Frame(template_list_frame)
            frame.pack(fill=tk.X, pady=2)

            cb = ttk.Checkbutton(frame, text=f"{template.name}", variable=var,
                                command=lambda n=name, v=var: self._toggle_template(n, v))
            cb.pack(side=tk.LEFT)

            ttk.Label(frame, text=f"v{template.version} - {template.description}",
                     foreground="gray").pack(side=tk.LEFT, padx=10)

        info_frame = ttk.LabelFrame(template_frame, text="Template Information", padding="10")
        info_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        info_text = """Templates recognize and extract data from different invoice formats.

To add a new template:
1. Create a new Python file in the 'templates' folder
2. Inherit from BaseTemplate class
3. Implement: can_process(), extract_invoice_number(), extract_project_number(), extract_line_items()
4. Register in templates/__init__.py"""

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        # --- Processing Statistics Tab ---
        proc_stats_frame = ttk.Frame(sub_notebook, padding="5")
        sub_notebook.add(proc_stats_frame, text="Processing Stats")

        self.proc_stats_labels = {}
        stats_info = ttk.LabelFrame(proc_stats_frame, text="Processing Statistics", padding="10")
        stats_info.pack(fill=tk.X, padx=5, pady=5)

        stats = [
            ("Files Processed:", "files_processed", "0"),
            ("Last Check:", "last_check", "Never"),
            ("Status:", "status", "Stopped"),
            ("Input Folder:", "input_count", "0 PDFs waiting"),
            ("Output Folder:", "output_count", "0 CSVs generated"),
        ]

        for i, (label, key, default) in enumerate(stats):
            ttk.Label(stats_info, text=label).grid(row=i, column=0, sticky="w", pady=2)
            self.proc_stats_labels[key] = ttk.Label(stats_info, text=default)
            self.proc_stats_labels[key].grid(row=i, column=1, sticky="w", padx=10, pady=2)

        ttk.Button(proc_stats_frame, text="Refresh Statistics", command=self._update_proc_statistics).pack(pady=10)

        # Initial log message
        self._queue_log("OCRMill Invoice Processing Suite started")
        self._queue_log(f"Input folder: {self.config.input_folder}")
        self._queue_log(f"Output folder: {self.config.output_folder}")

    def _create_parts_database_tab(self):
        """Create the parts database tab content."""
        self.parts_frame.grid_columnconfigure(0, weight=1)
        self.parts_frame.grid_rowconfigure(1, weight=1)

        # === Toolbar ===
        toolbar = ttk.Frame(self.parts_frame, padding="5")
        toolbar.grid(row=0, column=0, sticky="ew")

        ttk.Button(toolbar, text="Refresh", command=self._refresh_parts_data).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export Master CSV", command=self._export_master).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export History CSV", command=self._export_history).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Import Parts List", command=self._load_hts_file).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Generate Reports", command=self._generate_reports).pack(side="left", padx=2)

        # Search bar
        ttk.Label(toolbar, text="   Search:").pack(side="left", padx=(20, 2))
        self.parts_search_var = tk.StringVar()
        self.parts_search_var.trace('w', lambda *args: self._search_parts())
        search_entry = ttk.Entry(toolbar, textvariable=self.parts_search_var, width=30)
        search_entry.pack(side="left", padx=2)

        ttk.Label(toolbar, text="Filter:").pack(side="left", padx=(20, 2))
        self.filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(toolbar, text="All", variable=self.filter_var,
                       value="all", command=self._refresh_parts_data).pack(side="left")
        ttk.Radiobutton(toolbar, text="With HTS", variable=self.filter_var,
                       value="with_hts", command=self._refresh_parts_data).pack(side="left")
        ttk.Radiobutton(toolbar, text="No HTS", variable=self.filter_var,
                       value="no_hts", command=self._refresh_parts_data).pack(side="left")

        # === Parts Sub-notebook ===
        parts_notebook = ttk.Notebook(self.parts_frame)
        parts_notebook.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- Parts Master Tab ---
        parts_master_frame = ttk.Frame(parts_notebook)
        parts_notebook.add(parts_master_frame, text="Parts Master")
        self._create_parts_master_tab(parts_master_frame)

        # --- Part History Tab ---
        history_frame = ttk.Frame(parts_notebook)
        parts_notebook.add(history_frame, text="Part History")
        self._create_part_history_tab(history_frame)

        # --- Database Statistics Tab ---
        db_stats_frame = ttk.Frame(parts_notebook)
        parts_notebook.add(db_stats_frame, text="Statistics")
        self._create_db_statistics_tab(db_stats_frame)

        # --- HTS Codes Tab ---
        hts_frame = ttk.Frame(parts_notebook)
        parts_notebook.add(hts_frame, text="HTS Codes")
        self._create_hts_codes_tab(hts_frame)

    def _create_parts_master_tab(self, parent):
        """Create the parts master list tab."""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("part_number", "description", "hts_code", "mid", "client_code",
                  "steel_pct", "aluminum_pct", "first_seen", "last_seen")

        self.parts_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.parts_tree.yview)
        hsb.config(command=self.parts_tree.xview)

        self.parts_tree.heading("part_number", text="Part Number")
        self.parts_tree.heading("description", text="Description")
        self.parts_tree.heading("hts_code", text="HTS Code")
        self.parts_tree.heading("mid", text="MID")
        self.parts_tree.heading("client_code", text="Client")
        self.parts_tree.heading("steel_pct", text="Steel %")
        self.parts_tree.heading("aluminum_pct", text="Aluminum %")
        self.parts_tree.heading("first_seen", text="First Seen")
        self.parts_tree.heading("last_seen", text="Last Seen")

        self.parts_tree.column("part_number", width=140)
        self.parts_tree.column("description", width=180)
        self.parts_tree.column("hts_code", width=100)
        self.parts_tree.column("mid", width=130)
        self.parts_tree.column("client_code", width=80)
        self.parts_tree.column("steel_pct", width=60)
        self.parts_tree.column("aluminum_pct", width=70)
        self.parts_tree.column("first_seen", width=90)
        self.parts_tree.column("last_seen", width=90)

        self.parts_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.parts_tree.bind("<Double-1>", self._show_part_details)

        # Context menu
        self.parts_menu = tk.Menu(self.parts_tree, tearoff=0)
        self.parts_menu.add_command(label="View Details", command=self._show_part_details)
        self.parts_menu.add_command(label="Set HTS Code", command=self._set_hts_code)
        self.parts_menu.add_command(label="View History", command=self._view_part_history)
        self.parts_tree.bind("<Button-3>", self._show_parts_context_menu)

    def _create_part_history_tab(self, parent):
        """Create the part history tab."""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("part_number", "invoice_number", "project_number", "quantity",
                  "total_price", "hts_code", "processed_date")

        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                        yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.history_tree.yview)
        hsb.config(command=self.history_tree.xview)

        self.history_tree.heading("part_number", text="Part Number")
        self.history_tree.heading("invoice_number", text="Invoice")
        self.history_tree.heading("project_number", text="Project")
        self.history_tree.heading("quantity", text="Quantity")
        self.history_tree.heading("total_price", text="Price")
        self.history_tree.heading("hts_code", text="HTS")
        self.history_tree.heading("processed_date", text="Processed")

        self.history_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def _create_db_statistics_tab(self, parent):
        """Create the database statistics tab."""
        self.db_stats_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, width=80, height=30)
        self.db_stats_text.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Button(parent, text="Refresh Statistics",
                  command=self._update_parts_statistics).pack(pady=5)

    def _create_hts_codes_tab(self, parent):
        """Create the HTS codes management tab."""
        # Drop zone at top
        drop_frame = ttk.LabelFrame(parent, text="Import HTS/Product List", padding="10")
        drop_frame.pack(fill="x", padx=5, pady=5)

        self.drop_label = tk.Label(
            drop_frame,
            text="Drag and drop Excel (.xlsx) or CSV (.csv) file here\nor click to browse",
            bg="#e8e8e8",
            fg="#666666",
            font=("Segoe UI", 10),
            relief="ridge",
            padx=20,
            pady=20,
            cursor="hand2"
        )
        self.drop_label.pack(fill="x", padx=5, pady=5)

        self.drop_label.bind("<Button-1>", lambda e: self._load_hts_file())

        # Set up drag-and-drop if available
        if HAS_DND:
            self._setup_drag_drop()
        else:
            self.drop_label.config(text="Click to browse for Excel (.xlsx) or CSV (.csv) file\n(Install tkinterdnd2 for drag-and-drop support)")

        # HTS treeview
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("hts_code", "description", "suggested")

        self.hts_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                    yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.hts_tree.yview)
        hsb.config(command=self.hts_tree.xview)

        self.hts_tree.heading("hts_code", text="HTS Code")
        self.hts_tree.heading("description", text="Description")
        self.hts_tree.heading("suggested", text="Suggested")

        self.hts_tree.column("hts_code", width=120)
        self.hts_tree.column("description", width=400)
        self.hts_tree.column("suggested", width=300)

        self.hts_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def _setup_drag_drop(self):
        """Set up drag-and-drop handlers for HTS files."""
        try:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self._on_drop)
            self.drop_label.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            self.drop_label.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        except Exception as e:
            print(f"Could not set up drag-drop: {e}")
            self.drop_label.config(text="Click to browse for Excel (.xlsx) or CSV (.csv) file")

    def _setup_pdf_drag_drop(self):
        """Set up drag-and-drop handlers for PDF files."""
        try:
            self.pdf_drop_label.drop_target_register(DND_FILES)
            self.pdf_drop_label.dnd_bind('<<Drop>>', self._on_pdf_drop)
            self.pdf_drop_label.dnd_bind('<<DragEnter>>', self._on_pdf_drag_enter)
            self.pdf_drop_label.dnd_bind('<<DragLeave>>', self._on_pdf_drag_leave)
        except Exception as e:
            print(f"Could not set up PDF drag-drop: {e}")
            self.pdf_drop_label.config(
                text="Click to browse for PDF invoice files",
                bg="#fff3e0",
                fg="#e65100"
            )

    def _on_pdf_drag_enter(self, event):
        """Handle PDF drag enter event."""
        self.pdf_drop_label.config(bg="#c8e6c9", fg="#1b5e20")
        return event.action

    def _on_pdf_drag_leave(self, event):
        """Handle PDF drag leave event."""
        self.pdf_drop_label.config(bg="#e8f4e8", fg="#2e7d32")
        return event.action

    def _on_pdf_drop(self, event):
        """Handle PDF file drop event."""
        self.pdf_drop_label.config(bg="#e8f4e8", fg="#2e7d32")

        files = self._parse_drop_data(event.data)

        if not files:
            messagebox.showerror("Error", "No valid file dropped")
            return

        pdf_files = [f for f in files if Path(f).suffix.lower() == '.pdf']

        if not pdf_files:
            messagebox.showerror("Error", "Please drop PDF files only")
            return

        self._process_dropped_pdfs(pdf_files)

    def _browse_pdf_files(self):
        """Browse for PDF files to process."""
        filepaths = filedialog.askopenfilenames(
            title="Select PDF Invoice Files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=str(self.config.input_folder)
        )

        if filepaths:
            self._process_dropped_pdfs(list(filepaths))

    def _process_dropped_pdfs(self, pdf_files: list):
        """Process dropped or selected PDF files."""
        input_folder = Path(self.input_var.get())
        input_folder.mkdir(exist_ok=True, parents=True)

        copied_count = 0
        for pdf_path in pdf_files:
            pdf_path = Path(pdf_path)
            if pdf_path.exists() and pdf_path.suffix.lower() == '.pdf':
                dest = input_folder / pdf_path.name
                # Handle duplicate filenames
                counter = 1
                while dest.exists():
                    dest = input_folder / f"{pdf_path.stem}_{counter}{pdf_path.suffix}"
                    counter += 1

                shutil.copy2(pdf_path, dest)
                self._queue_log(f"Added to input: {dest.name}")
                copied_count += 1

        if copied_count > 0:
            self._queue_log(f"Added {copied_count} PDF file(s) to input folder")
            self._update_proc_statistics()

            # Ask user if they want to process now
            if messagebox.askyesno("Process Files?",
                                   f"{copied_count} PDF file(s) added to input folder.\n\nProcess them now?"):
                self.process_now()
        else:
            messagebox.showwarning("No Files", "No valid PDF files were found.")

    def _on_drag_enter(self, event):
        """Handle drag enter event."""
        self.drop_label.config(bg="#c8e6c9", fg="#2e7d32")
        return event.action

    def _on_drag_leave(self, event):
        """Handle drag leave event."""
        self.drop_label.config(bg="#e8e8e8", fg="#666666")
        return event.action

    def _on_drop(self, event):
        """Handle file drop event."""
        self.drop_label.config(bg="#e8e8e8", fg="#666666")

        files = self._parse_drop_data(event.data)

        if not files:
            messagebox.showerror("Error", "No valid file dropped")
            return

        for filepath in files:
            filepath = Path(filepath)
            if filepath.suffix.lower() in ['.xlsx', '.csv']:
                self._import_hts_file(filepath)
                return

        messagebox.showerror("Error", "Please drop an Excel (.xlsx) or CSV (.csv) file")

    def _parse_drop_data(self, data):
        """Parse the dropped file data string into file paths."""
        import re
        files = []
        if '{' in data:
            matches = re.findall(r'\{([^}]+)\}', data)
            files.extend(matches)
            remaining = re.sub(r'\{[^}]+\}', '', data).strip()
            if remaining:
                files.extend(remaining.split())
        else:
            files = data.split()

        cleaned = []
        for f in files:
            f = f.strip()
            if f:
                cleaned.append(f)

        return cleaned

    def _create_status_bar(self):
        """Create the unified status bar."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=1, column=0, sticky="ew", padx=2, pady=2)

    # === Invoice Processing Methods ===

    def _queue_log(self, message: str):
        """Queue a log message for display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def _consume_logs(self):
        """Consume log messages from the queue and display them."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self._append_log(message)
        except queue.Empty:
            pass

        self.root.after(100, self._consume_logs)

    def _append_log(self, message: str):
        """Append a message to the log display."""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def _browse_input(self):
        """Browse for input folder."""
        folder = filedialog.askdirectory(initialdir=self.input_var.get())
        if folder:
            self.input_var.set(folder)

    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory(initialdir=self.output_var.get())
        if folder:
            self.output_var.set(folder)

    def _save_settings(self):
        """Save current settings."""
        self.config.input_folder = self.input_var.get()
        self.config.output_folder = self.output_var.get()
        self.config.poll_interval = int(self.poll_var.get())
        self._queue_log("Settings saved")
        messagebox.showinfo("Settings", "Settings saved successfully!")

    def _save_autostart(self):
        """Save auto-start setting."""
        self.config.auto_start = self.autostart_var.get()

    def _save_consolidate(self):
        """Save multi-invoice consolidation setting."""
        self.config.consolidate_multi_invoice = self.consolidate_var.get()
        mode = "one CSV per PDF" if self.consolidate_var.get() else "separate CSVs per invoice"
        self._queue_log(f"Multi-invoice mode: {mode}")

    def _toggle_template(self, name: str, var: tk.BooleanVar):
        """Toggle template enabled state."""
        self.config.set_template_enabled(name, var.get())
        status = "enabled" if var.get() else "disabled"
        self._queue_log(f"Template '{name}' {status}")

    def _clear_log(self):
        """Clear the log display."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')

    def _update_proc_statistics(self):
        """Update the processing statistics display."""
        input_folder = Path(self.input_var.get())
        output_folder = Path(self.output_var.get())

        input_count = len(list(input_folder.glob("*.pdf"))) if input_folder.exists() else 0
        output_count = len(list(output_folder.glob("*.csv"))) if output_folder.exists() else 0

        self.proc_stats_labels["files_processed"].config(text=str(self.files_processed))
        self.proc_stats_labels["last_check"].config(text=self.last_check or "Never")
        self.proc_stats_labels["status"].config(text="Running" if self.running else "Stopped")
        self.proc_stats_labels["input_count"].config(text=f"{input_count} PDFs waiting")
        self.proc_stats_labels["output_count"].config(text=f"{output_count} CSVs generated")

    def start_processing(self):
        """Start the background processing thread."""
        if self.running:
            return

        self._save_settings()

        self.running = True
        self.stop_event.clear()

        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="Running", foreground="green")
        self.status_var.set("Processing active...")

        self._queue_log("Processing started")

        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()

    def stop_processing(self):
        """Stop the background processing thread."""
        if not self.running:
            return

        self._queue_log("Stopping processor...")
        self.stop_event.set()
        self.running = False

        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="Stopped", foreground="red")
        self.status_var.set("Processing stopped")

        self._queue_log("Processing stopped")

    def process_now(self):
        """Process files immediately (one-time)."""
        # Try to acquire lock - if already processing, skip
        if not self.processing_lock.acquire(blocking=False):
            self._queue_log("Processing already in progress, please wait...")
            return

        try:
            self._queue_log("Manual processing triggered")

            input_folder = Path(self.input_var.get())
            output_folder = Path(self.output_var.get())

            count = self.engine.process_folder(input_folder, output_folder)
            self.files_processed += count
            self.last_check = datetime.now().strftime("%H:%M:%S")

            self._update_proc_statistics()
            self._queue_log(f"Manual processing complete: {count} files processed")

            # Refresh parts data after processing
            self._refresh_parts_data()
        finally:
            self.processing_lock.release()

    def _processing_loop(self):
        """Background processing loop."""
        input_folder = Path(self.input_var.get())
        output_folder = Path(self.output_var.get())

        while not self.stop_event.is_set():
            try:
                # Acquire lock before processing
                with self.processing_lock:
                    count = self.engine.process_folder(input_folder, output_folder)
                    self.files_processed += count
                    self.last_check = datetime.now().strftime("%H:%M:%S")

                    self.root.after(0, self._update_proc_statistics)

                    # Refresh parts data if any files were processed
                    if count > 0:
                        self.root.after(0, self._refresh_parts_data)

                poll_interval = int(self.poll_var.get())
                for _ in range(poll_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                self._queue_log(f"Error in processing loop: {e}")
                time.sleep(5)

    # === Parts Database Methods ===

    def _load_parts_data(self):
        """Load initial parts data."""
        self._refresh_parts_data()

    def _refresh_parts_data(self):
        """Refresh the parts list."""
        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        filter_type = self.filter_var.get()

        parts = self.db.get_all_parts()

        if filter_type == "with_hts":
            parts = [p for p in parts if p.get('hts_code')]
        elif filter_type == "no_hts":
            parts = [p for p in parts if not p.get('hts_code')]

        for part in parts:
            values = (
                part.get('part_number', ''),
                part.get('description', ''),
                part.get('hts_code', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('avg_steel_pct', 0):.0f}%" if part.get('avg_steel_pct') else '',
                f"{part.get('avg_aluminum_pct', 0):.0f}%" if part.get('avg_aluminum_pct') else '',
                part.get('first_seen_date', '')[:10] if part.get('first_seen_date') else '',
                part.get('last_seen_date', '')[:10] if part.get('last_seen_date') else ''
            )
            self.parts_tree.insert("", "end", values=values)

        self.status_var.set(f"Loaded {len(parts)} parts")

    def _search_parts(self):
        """Search parts based on search term."""
        search_term = self.parts_search_var.get()

        if not search_term:
            self._refresh_parts_data()
            return

        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        parts = self.db.search_parts(search_term)

        for part in parts:
            values = (
                part.get('part_number', ''),
                part.get('description', ''),
                part.get('hts_code', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('avg_steel_pct', 0):.0f}%" if part.get('avg_steel_pct') else '',
                f"{part.get('avg_aluminum_pct', 0):.0f}%" if part.get('avg_aluminum_pct') else '',
                part.get('first_seen_date', '')[:10] if part.get('first_seen_date') else '',
                part.get('last_seen_date', '')[:10] if part.get('last_seen_date') else ''
            )
            self.parts_tree.insert("", "end", values=values)

        self.status_var.set(f"Found {len(parts)} parts matching '{search_term}'")

    def _update_parts_statistics(self):
        """Update the database statistics display."""
        self.db_stats_text.delete("1.0", tk.END)

        stats = self.db.get_statistics()

        report = f"""
Parts Database Statistics
{'=' * 60}

Database Overview
{'-' * 60}
Total Unique Parts:          {stats['total_parts']:,}
Total Part Occurrences:      {stats['total_occurrences']:,}
Total Invoices Processed:    {stats['total_invoices']:,}
Total Projects:              {stats['total_projects']:,}

Financial Summary
{'-' * 60}
Total Value Processed:       ${stats['total_value']:,.2f}

HTS Code Coverage
{'-' * 60}
Parts with HTS Codes:        {stats['parts_with_hts']:,} ({stats['hts_coverage_pct']:.1f}%)
Parts without HTS Codes:     {stats['total_parts'] - stats['parts_with_hts']:,}

Top 10 Parts by Value
{'-' * 60}
"""
        self.db_stats_text.insert("1.0", report)

        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT part_number, invoice_count, total_quantity, total_value, hts_code
            FROM parts
            ORDER BY total_value DESC
            LIMIT 10
        """)

        for i, row in enumerate(cursor.fetchall(), 1):
            line = f"{i:2d}. {row['part_number']:15s}  ${row['total_value']:>10,.2f}  (Qty: {row['total_quantity']:>6.0f}, Invoices: {row['invoice_count']:>3d})"
            if row['hts_code']:
                line += f"  HTS: {row['hts_code']}"
            self.db_stats_text.insert(tk.END, line + "\n")

    def _load_hts_list(self):
        """Load HTS codes into the HTS tab."""
        for item in self.hts_tree.get_children():
            self.hts_tree.delete(item)

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM hts_codes ORDER BY hts_code")

        for row in cursor.fetchall():
            values = (
                row['hts_code'],
                row['description'],
                row['suggested'] or ''
            )
            self.hts_tree.insert("", "end", values=values)

    def _show_parts_context_menu(self, event):
        """Show context menu for parts."""
        item = self.parts_tree.identify_row(event.y)
        if item:
            self.parts_tree.selection_set(item)
            self.parts_menu.post(event.x_root, event.y_root)

    def _show_part_details(self, event=None):
        """Show detailed information for selected part."""
        selection = self.parts_tree.selection()
        if not selection:
            return

        item = self.parts_tree.item(selection[0])
        part_number = item['values'][0]

        part = self.db.get_part_summary(part_number)
        if not part:
            return

        details_win = tk.Toplevel(self.root)
        details_win.title(f"Part Details - {part_number}")
        details_win.geometry("600x400")

        text = scrolledtext.ScrolledText(details_win, wrap=tk.WORD)
        text.pack(fill="both", expand=True, padx=10, pady=10)

        details = f"""
Part Number: {part_number}
{'=' * 60}

HTS Code:           {part.get('hts_code') or 'Not assigned'}
Description:        {part.get('description') or 'N/A'}

Usage Statistics
{'-' * 60}
Times Used:         {part.get('invoice_count', 0)} invoices
Total Quantity:     {part.get('total_quantity', 0):.2f}
Total Value:        ${part.get('total_value', 0):,.2f}

Material Composition (Average)
{'-' * 60}
Steel:              {part.get('avg_steel_pct', 0):.0f}%
Aluminum:           {part.get('avg_aluminum_pct', 0):.0f}%
Net Weight:         {part.get('avg_net_weight', 0):.2f} kg

Timeline
{'-' * 60}
First Seen:         {part.get('first_seen_date', 'N/A')}
Last Seen:          {part.get('last_seen_date', 'N/A')}
"""
        text.insert("1.0", details)
        text.config(state="disabled")

    def _set_hts_code(self):
        """Set HTS code for selected part."""
        selection = self.parts_tree.selection()
        if not selection:
            return

        item = self.parts_tree.item(selection[0])
        part_number = item['values'][0]
        current_hts = item['values'][2]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Set HTS Code - {part_number}")
        dialog.geometry("400x150")

        ttk.Label(dialog, text=f"Part Number: {part_number}").pack(pady=10)
        ttk.Label(dialog, text="HTS Code:").pack()

        hts_var = tk.StringVar(value=current_hts)
        hts_entry = ttk.Entry(dialog, textvariable=hts_var, width=30)
        hts_entry.pack(pady=5)

        def save_hts():
            new_hts = hts_var.get().strip()
            if new_hts:
                self.db.update_part_hts(part_number, new_hts)
                messagebox.showinfo("Success", f"HTS code updated for {part_number}")
                self._refresh_parts_data()
                dialog.destroy()

        ttk.Button(dialog, text="Save", command=save_hts).pack(pady=10)

    def _view_part_history(self):
        """View history for selected part."""
        selection = self.parts_tree.selection()
        if not selection:
            return

        item = self.parts_tree.item(selection[0])
        part_number = item['values'][0]

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        history = self.db.get_part_history(part_number)

        for record in history:
            values = (
                record.get('part_number', ''),
                record.get('invoice_number', ''),
                record.get('project_number', ''),
                f"{record.get('quantity', 0):.2f}",
                f"${record.get('total_price', 0):,.2f}",
                record.get('hts_code', ''),
                record.get('processed_date', '')[:10] if record.get('processed_date') else ''
            )
            self.history_tree.insert("", "end", values=values)

        # Switch to history tab
        self.main_notebook.select(1)  # Parts Database tab
        self.status_var.set(f"Showing {len(history)} occurrences of {part_number}")

    # === Export/Import Methods ===

    def _export_master(self):
        """Export parts master to CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parts_master_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if filepath:
            if self.db.export_to_csv(Path(filepath), include_history=False):
                messagebox.showinfo("Success", f"Parts master exported to {filepath}")
            else:
                messagebox.showerror("Error", "Failed to export data")

    def _export_history(self):
        """Export parts history to CSV."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parts_history_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if filepath:
            if self.db.export_to_csv(Path(filepath), include_history=True):
                messagebox.showinfo("Success", f"Parts history exported to {filepath}")
            else:
                messagebox.showerror("Error", "Failed to export data")

    def _load_hts_file(self):
        """Load parts/HTS codes from Excel or CSV file."""
        filepath = filedialog.askopenfilename(
            title="Select Parts/HTS Mapping File",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir="reports"
        )

        if filepath:
            self._import_hts_file(Path(filepath))

    def _import_hts_file(self, filepath: Path):
        """Import parts/HTS codes from dropped file."""
        self.status_var.set(f"Importing {filepath.name}...")
        self.root.update()

        try:
            imported, updated, errors = self.db.import_parts_list(filepath)

            if errors and imported == 0 and updated == 0:
                messagebox.showerror("Import Error", "\n".join(errors[:10]))
                self.status_var.set("Import failed")
            else:
                msg = f"Imported: {imported} new parts\nUpdated: {updated} existing parts"
                if errors:
                    msg += f"\n\nWarnings ({len(errors)}):\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        msg += f"\n... and {len(errors) - 5} more"

                messagebox.showinfo("Import Complete", msg)
                self._refresh_parts_data()
                self._load_hts_list()
                self._update_parts_statistics()
                self.status_var.set(f"Imported {imported} new, updated {updated} parts from {filepath.name}")

        except Exception as e:
            messagebox.showerror("Error", f"Error importing file: {e}")
            self.status_var.set("Import error")

    def _generate_reports(self):
        """Generate comprehensive parts reports."""
        folder = filedialog.askdirectory(title="Select Output Folder", initialdir="reports")

        if folder:
            create_parts_report(self.db, Path(folder))
            messagebox.showinfo("Success", f"Reports generated in {folder}")

    # === Dialog Methods ===

    def _show_manufacturers_dialog(self):
        """Show the manufacturers/MID management dialog."""
        ManufacturersDialog(self.root, self.db)

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About OCRMill",
            f"OCRMill - Invoice Processing Suite\n\n"
            f"Version {__version__}\n\n"
            "Unified application for:\n"
            "- Invoice PDF processing and data extraction\n"
            "- Parts database management\n"
            "- HTS code tracking\n"
            "- Manufacturer/MID management"
        )

    def _change_database_location(self):
        """Show dialog to change the database file location."""
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Database Location")
        dialog.geometry("550x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # Current path display
        ttk.Label(dialog, text="Current Database Path:", font=('Helvetica', 10, 'bold')).pack(anchor="w", padx=10, pady=(10, 0))

        current_path_var = tk.StringVar(value=str(self.config.database_path))
        current_label = ttk.Label(dialog, textvariable=current_path_var, foreground="gray")
        current_label.pack(anchor="w", padx=20, pady=(0, 10))

        # New path entry
        ttk.Label(dialog, text="New Database Path:").pack(anchor="w", padx=10, pady=(10, 0))

        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill="x", padx=10, pady=5)

        new_path_var = tk.StringVar(value=str(self.config.database_path))
        path_entry = ttk.Entry(path_frame, textvariable=new_path_var, width=50)
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def browse_file():
            filepath = filedialog.asksaveasfilename(
                title="Select Database Location",
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
                initialfile=Path(new_path_var.get()).name,
                initialdir=Path(new_path_var.get()).parent
            )
            if filepath:
                new_path_var.set(filepath)

        ttk.Button(path_frame, text="Browse...", command=browse_file).pack(side="left")

        # Info label
        info_label = ttk.Label(dialog, text="Note: Changing the database will reload all data.\nExisting data in the new location will be preserved.", foreground="blue")
        info_label.pack(anchor="w", padx=10, pady=10)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)

        def apply_change():
            new_path = new_path_var.get().strip()
            if not new_path:
                messagebox.showerror("Error", "Please specify a database path.")
                return

            # Check if processing is running
            if self.running:
                messagebox.showwarning("Warning", "Please stop processing before changing the database location.")
                return

            try:
                # Update config
                self.config.database_path = new_path

                # Close current database connection
                if self.db.conn:
                    self.db.conn.close()

                # Reinitialize database with new path
                self.db = PartsDatabase(db_path=Path(new_path))

                # Update the engine's reference to the database
                self.engine.parts_db = self.db

                # Reload all data in the UI
                self._refresh_parts_data()
                self._update_parts_statistics()
                self._load_hts_list()

                self._queue_log(f"Database changed to: {new_path}")
                messagebox.showinfo("Success", f"Database location changed to:\n{new_path}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to change database: {e}")

        ttk.Button(btn_frame, text="Apply", command=apply_change).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="right", padx=5)

    # === Window Management ===

    def _on_close(self):
        """Handle window close event."""
        if self.running:
            if messagebox.askyesno("Confirm Exit", "Processing is running. Stop and exit?"):
                self.stop_processing()
            else:
                return

        # Save window position/size
        self.config.set("window.width", self.root.winfo_width())
        self.config.set("window.height", self.root.winfo_height())

        self.root.destroy()

    def run(self):
        """Start the GUI application."""
        self.root.mainloop()


# Keep the old class for backwards compatibility
class InvoiceProcessorGUI(OCRMillApp):
    """Backwards compatible alias for OCRMillApp."""
    pass


def main():
    """Main entry point."""
    app = OCRMillApp()
    app.run()


if __name__ == "__main__":
    main()
