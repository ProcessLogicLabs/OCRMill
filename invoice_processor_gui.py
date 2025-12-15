"""
OCRMill - Invoice Processing Suite
Unified GUI application for invoice processing and parts database management.
"""

__version__ = "2.3.0"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import time
import csv
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

# Add DerivativeMill submodule to path for invoice_processor import
DERIVATIVEMILL_PATH = Path(__file__).parent / "DerivativeMill" / "DerivativeMill"
if DERIVATIVEMILL_PATH.exists():
    sys.path.insert(0, str(DERIVATIVEMILL_PATH))

# Try to import the invoice processor from DerivativeMill
try:
    from invoice_processor import InvoiceProcessor
    HAS_INVOICE_PROCESSOR = True
except ImportError:
    HAS_INVOICE_PROCESSOR = False
    InvoiceProcessor = None

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
from templates.bill_of_lading import BillOfLadingTemplate
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
                            break  # Found weight, no need to check more pages

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
                                # Add BOL gross weight for proration (total shipment weight)
                                if bol_weight:
                                    item['bol_gross_weight'] = bol_weight
                                # Add BOL weight as net_weight if item doesn't have one
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
                        # Add BOL gross weight for proration (total shipment weight)
                        if bol_weight:
                            item['bol_gross_weight'] = bol_weight
                        # Add BOL weight as net_weight if item doesn't have one
                        if bol_weight and ('net_weight' not in item or not item.get('net_weight')):
                            item['net_weight'] = bol_weight
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

        # Add items to parts database and enrich with descriptions, HTS codes, MID, and country of origin
        for item in items:
            # Look up MID and country_origin from manufacturer name BEFORE adding to database
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

            # If country_origin still not set but we have MID, extract from first 2 letters of MID
            if ('country_origin' not in item or not item['country_origin']) and item.get('mid'):
                mid = item.get('mid', '')
                if len(mid) >= 2:
                    item['country_origin'] = mid[:2].upper()

            part_data = item.copy()
            part_data['source_file'] = pdf_name or 'unknown'
            self.parts_db.add_part_occurrence(part_data)

            # Add description and HTS code back to item for CSV export
            if 'description' not in item or not item['description']:
                item['description'] = part_data.get('description', '')
            if 'hts_code' not in item or not item['hts_code']:
                item['hts_code'] = part_data.get('hts_code', '')

            # Get MID and country_origin from parts database if not already set
            if ('mid' not in item or not item['mid']) or ('country_origin' not in item or not item['country_origin']):
                part_summary = self.parts_db.get_part_summary(item.get('part_number', ''))
                if part_summary:
                    if 'mid' not in item or not item['mid']:
                        if part_summary.get('mid'):
                            item['mid'] = part_summary.get('mid', '')
                    if 'country_origin' not in item or not item['country_origin']:
                        if part_summary.get('country_origin'):
                            item['country_origin'] = part_summary.get('country_origin', '')

            # Final fallback: If country_origin still not set but we have MID, extract from first 2 letters of MID
            if ('country_origin' not in item or not item['country_origin']) and item.get('mid'):
                mid = item.get('mid', '')
                if len(mid) >= 2:
                    item['country_origin'] = mid[:2].upper()

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
        ttk.Button(btn_frame, text="Import Excel...", command=self._import_excel).pack(side="left", padx=2)
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

    def _import_excel(self):
        """Import manufacturers from Excel file."""
        from pathlib import Path

        filepath = filedialog.askopenfilename(
            title="Select Manufacturer/MID Excel File",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ],
            initialdir=str(Path.cwd() / "reports")
        )

        if not filepath:
            return

        try:
            imported, updated = self.db.import_manufacturers_from_excel(filepath)
            self._load_data()
            messagebox.showinfo(
                "Import Complete",
                f"Successfully imported {imported} new manufacturers\n"
                f"Updated {updated} existing manufacturers"
            )
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import file:\n{str(e)}")


class SettingsDialog:
    """Dialog for application settings including column visibility."""

    def __init__(self, parent, config, on_save=None):
        self.config = config
        self.on_save = on_save
        self.column_vars = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        """Create dialog widgets."""
        # Create notebook for different settings categories
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === Parts Master Columns Tab ===
        columns_frame = ttk.Frame(notebook)
        notebook.add(columns_frame, text="Parts Master Columns")

        # Instructions
        instructions = ttk.Label(
            columns_frame,
            text="Select which columns to display in the Parts Master tab:",
            font=("TkDefaultFont", 9, "bold")
        )
        instructions.pack(pady=10, padx=10, anchor="w")

        # Scrollable frame for checkboxes
        canvas = tk.Canvas(columns_frame)
        scrollbar = ttk.Scrollbar(columns_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Column display names
        column_labels = {
            "part_number": "Part Number",
            "description": "Description",
            "hts_code": "HTS Code",
            "country_origin": "Country of Origin",
            "mid": "MID",
            "client_code": "Client Code",
            "steel_pct": "Steel %",
            "aluminum_pct": "Aluminum %",
            "copper_pct": "Copper %",
            "wood_pct": "Wood %",
            "auto_pct": "Auto %",
            "non_steel_pct": "Non-Steel %",
            "qty_unit": "Quantity Unit",
            "sec301_exclusion_tariff": "Section 301 Exclusion",
            "last_updated": "Last Updated"
        }

        # Create checkboxes for each column
        for col_name, display_name in column_labels.items():
            var = tk.BooleanVar(value=True)
            self.column_vars[col_name] = var
            cb = ttk.Checkbutton(
                scrollable_frame,
                text=display_name,
                variable=var
            )
            cb.pack(anchor="w", padx=20, pady=3)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10, padx=(0, 10))

        # Buttons at bottom for column tab
        col_btn_frame = ttk.Frame(columns_frame)
        col_btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(col_btn_frame, text="Select All", command=self._select_all_columns).pack(side="left", padx=5)
        ttk.Button(col_btn_frame, text="Deselect All", command=self._deselect_all_columns).pack(side="left", padx=5)

        # === Main dialog buttons ===
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Apply", command=self._apply_settings).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="OK", command=self._ok_clicked).pack(side="right", padx=5)

    def _load_settings(self):
        """Load current settings from config."""
        column_settings = self.config.get_all_column_settings()
        for col_name, var in self.column_vars.items():
            var.set(column_settings.get(col_name, True))

    def _select_all_columns(self):
        """Select all column checkboxes."""
        for var in self.column_vars.values():
            var.set(True)

    def _deselect_all_columns(self):
        """Deselect all column checkboxes."""
        for var in self.column_vars.values():
            var.set(False)

    def _apply_settings(self):
        """Apply settings without closing dialog."""
        # Save column visibility settings
        for col_name, var in self.column_vars.items():
            self.config.set_column_visible(col_name, var.get())

        if self.on_save:
            self.on_save()

        messagebox.showinfo("Settings", "Settings applied successfully!")

    def _ok_clicked(self):
        """Apply settings and close dialog."""
        self._apply_settings()
        self.dialog.destroy()


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

        # Configure ttk styles for tabs with shading
        self._configure_styles()

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

    def _configure_styles(self):
        """Configure ttk styles for tabs."""
        style = ttk.Style()

        # Configure notebook tab styling - make tabs more distinct
        style.configure('TNotebook.Tab',
                        padding=[14, 6],
                        background='#d0d0d0',
                        font=('Segoe UI', 9))

        # Style for selected/active tab - white background stands out
        style.map('TNotebook.Tab',
                  background=[('selected', '#ffffff'), ('active', '#e8e8e8')],
                  foreground=[('selected', '#000000'), ('active', '#333333')],
                  expand=[('selected', [1, 1, 1, 0])])

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
        settings_menu.add_command(label="Preferences...", command=self._show_settings_dialog)
        settings_menu.add_separator()
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

        # === CBP Export Tab ===
        self.cbp_frame = ttk.Frame(self.main_notebook)
        self.main_notebook.add(self.cbp_frame, text="CBP Export")
        self._create_cbp_export_tab()

        # Bind tab change event for auto-refresh
        self.main_notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        """Handle notebook tab selection changes."""
        selected_tab = event.widget.select()
        tab_text = event.widget.tab(selected_tab, "text")

        # Auto-refresh CBP Export tab when selected
        if tab_text == "CBP Export":
            self._refresh_cbp_list()

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

        # Auto CBP Export option
        ttk.Label(settings_frame, text="Auto CBP Export:").grid(row=4, column=0, sticky="w", pady=2)
        self.auto_cbp_var = tk.BooleanVar(value=self.config.auto_cbp_export)
        ttk.Checkbutton(settings_frame, text="Auto-generate CBP export after processing",
                       variable=self.auto_cbp_var,
                       command=self._save_auto_cbp).grid(row=4, column=1, sticky="w", padx=5, pady=2, columnspan=2)

        # Control buttons
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=10)

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

        # --- Output Files Tab ---
        output_files_frame = ttk.Frame(sub_notebook, padding="5")
        sub_notebook.add(output_files_frame, text="Output Files")
        output_files_frame.grid_columnconfigure(0, weight=1)
        output_files_frame.grid_rowconfigure(1, weight=1)

        # Output folder display
        folder_frame = ttk.Frame(output_files_frame)
        folder_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        folder_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(folder_frame, text="Output Folder:", font=('', 9, 'bold')).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.output_files_path_var = tk.StringVar(value=str(self.config.output_folder))
        output_path_label = ttk.Label(folder_frame, textvariable=self.output_files_path_var, foreground="blue", cursor="hand2")
        output_path_label.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        output_path_label.bind("<Button-1>", lambda _: self._open_output_folder())

        ttk.Button(folder_frame, text="Browse Folder", command=self._open_output_folder).grid(row=0, column=2, padx=5, pady=2)
        ttk.Button(folder_frame, text="Refresh List", command=self._refresh_output_files).grid(row=0, column=3, padx=5, pady=2)

        # File list
        list_frame = ttk.LabelFrame(output_files_frame, text="CSV Files", padding="5")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        # Listbox with scrollbar
        file_scroll = ttk.Scrollbar(list_frame, orient="vertical")
        self.output_files_listbox = tk.Listbox(list_frame, yscrollcommand=file_scroll.set, font=('Consolas', 9))
        file_scroll.config(command=self.output_files_listbox.yview)

        self.output_files_listbox.grid(row=0, column=0, sticky="nsew")
        file_scroll.grid(row=0, column=1, sticky="ns")

        # Double-click to open file
        self.output_files_listbox.bind("<Double-Button-1>", lambda _: self._open_selected_output_file())

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Button(btn_frame, text="Open File", command=self._open_selected_output_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open in Excel", command=self._open_selected_output_file_excel).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Folder", command=self._open_output_folder).pack(side=tk.LEFT, padx=5)

        # Initial file list load
        self._refresh_output_files()

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

        # Store all possible columns
        self.all_parts_columns = ("part_number", "description", "hts_code", "country_origin", "mid", "client_code",
                                  "steel_pct", "aluminum_pct", "copper_pct", "wood_pct", "auto_pct", "non_steel_pct",
                                  "qty_unit", "sec301_exclusion_tariff", "fsc_certified", "fsc_certificate_code", "last_updated")

        # Column metadata (heading text and width)
        self.parts_column_config = {
            "part_number": {"text": "Part Number", "width": 140},
            "description": {"text": "Description", "width": 220},
            "hts_code": {"text": "HTS Code", "width": 100},
            "country_origin": {"text": "Country Origin", "width": 100},
            "mid": {"text": "MID", "width": 150},
            "client_code": {"text": "Client Code", "width": 100},
            "steel_pct": {"text": "Steel %", "width": 70},
            "aluminum_pct": {"text": "Aluminum %", "width": 80},
            "copper_pct": {"text": "Copper %", "width": 75},
            "wood_pct": {"text": "Wood %", "width": 70},
            "auto_pct": {"text": "Auto %", "width": 70},
            "non_steel_pct": {"text": "Non-Steel %", "width": 90},
            "qty_unit": {"text": "Qty Unit", "width": 70},
            "sec301_exclusion_tariff": {"text": "Sec301 Exclusion", "width": 120},
            "fsc_certified": {"text": "FSC Certified", "width": 100},
            "fsc_certificate_code": {"text": "FSC Certificate", "width": 140},
            "last_updated": {"text": "Last Updated", "width": 90}
        }

        self.parts_tree = ttk.Treeview(tree_frame, columns=self.all_parts_columns, show="headings",
                                       yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.parts_tree.yview)
        hsb.config(command=self.parts_tree.xview)

        # Configure all columns
        for col_name, col_info in self.parts_column_config.items():
            self.parts_tree.heading(col_name, text=col_info["text"])
            self.parts_tree.column(col_name, width=col_info["width"])

        # Apply initial column visibility
        self._apply_column_visibility()

        self.parts_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.parts_tree.bind("<Double-1>", self._edit_part)

        # Context menu
        self.parts_menu = tk.Menu(self.parts_tree, tearoff=0)
        self.parts_menu.add_command(label="Edit Part", command=self._edit_part)
        self.parts_menu.add_command(label="View Details (Read-Only)", command=self._show_part_details)
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

    def _create_cbp_export_tab(self):
        """Create the CBP Export tab for Section 232 processing."""
        self.cbp_frame.grid_columnconfigure(0, weight=1)
        self.cbp_frame.grid_rowconfigure(2, weight=1)

        # === Header Frame ===
        header_frame = ttk.Frame(self.cbp_frame, padding="10")
        header_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(header_frame, text="CBP Export - Section 232 Processing",
                  font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        # Status indicator
        self.cbp_status_label = ttk.Label(header_frame, text="", font=('Helvetica', 10))
        self.cbp_status_label.pack(side=tk.RIGHT, padx=10)

        if not HAS_INVOICE_PROCESSOR:
            self.cbp_status_label.config(text="Invoice Processor not available", foreground="red")

        # === Settings Frame ===
        settings_frame = ttk.LabelFrame(self.cbp_frame, text="Export Settings", padding="10")
        settings_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        settings_frame.grid_columnconfigure(1, weight=1)

        # Input folder (processed CSVs) - load from config
        ttk.Label(settings_frame, text="Input Folder:").grid(row=0, column=0, sticky="w", pady=2)
        cbp_input_path = Path(self.config.cbp_input_folder).resolve()
        self.cbp_input_var = tk.StringVar(value=str(cbp_input_path))
        ttk.Entry(settings_frame, textvariable=self.cbp_input_var, width=50).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(settings_frame, text="Browse...", command=self._browse_cbp_input).grid(row=0, column=2)

        # Output folder for CBP Excel files - load from config
        ttk.Label(settings_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=2)
        cbp_output_path = Path(self.config.cbp_output_folder).resolve()
        self.cbp_output_var = tk.StringVar(value=str(cbp_output_path))
        ttk.Entry(settings_frame, textvariable=self.cbp_output_var, width=50).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(settings_frame, text="Browse...", command=self._browse_cbp_output).grid(row=1, column=2)

        # Total shipment weight display (auto-populated from selected CSV)
        weight_label = ttk.Label(settings_frame, text="Total Shipment Weight (kg):")
        weight_label.grid(row=2, column=0, sticky="w", pady=2)
        self.cbp_weight_var = tk.StringVar(value="0")
        weight_entry = ttk.Entry(settings_frame, textvariable=self.cbp_weight_var, width=15, state='readonly')
        weight_entry.grid(row=2, column=1, sticky="w", padx=5)

        # Add tooltip explaining weight usage
        try:
            from tktooltip import ToolTip
            ToolTip(weight_label, msg="Auto-populated from bol_gross_weight column in selected CSV file.\nUsed to prorate weight across invoice items.", delay=0.5)
        except ImportError:
            pass  # Tooltip library not available

        # Buttons frame
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)

        self.cbp_process_btn = ttk.Button(btn_frame, text="Process Selected CSV",
                                          command=self._process_cbp_single, width=20)
        self.cbp_process_btn.pack(side=tk.LEFT, padx=5)

        self.cbp_process_all_btn = ttk.Button(btn_frame, text="Process All CSVs",
                                               command=self._process_cbp_all, width=20)
        self.cbp_process_all_btn.pack(side=tk.LEFT, padx=5)

        if not HAS_INVOICE_PROCESSOR:
            self.cbp_process_btn.config(state='disabled')
            self.cbp_process_all_btn.config(state='disabled')

        # === File List Frame ===
        list_frame = ttk.LabelFrame(self.cbp_frame, text="Available CSV Files", padding="5")
        list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        # Treeview for CSV files
        columns = ("filename", "date", "invoices", "items", "status")
        self.cbp_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)

        self.cbp_tree.heading("filename", text="Filename")
        self.cbp_tree.heading("date", text="Date")
        self.cbp_tree.heading("invoices", text="Invoices")
        self.cbp_tree.heading("items", text="Items")
        self.cbp_tree.heading("status", text="Status")

        self.cbp_tree.column("filename", width=300)
        self.cbp_tree.column("date", width=140)
        self.cbp_tree.column("invoices", width=80)
        self.cbp_tree.column("items", width=80)
        self.cbp_tree.column("status", width=100)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.cbp_tree.yview)
        self.cbp_tree.configure(yscrollcommand=vsb.set)

        self.cbp_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Bind selection event to update weight display
        self.cbp_tree.bind("<<TreeviewSelect>>", self._on_cbp_file_select)

        # Refresh button
        ttk.Button(list_frame, text="Refresh List", command=self._refresh_cbp_list).grid(row=1, column=0, pady=5)

        # === Log Frame ===
        log_frame = ttk.LabelFrame(self.cbp_frame, text="Processing Log", padding="5")
        log_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        log_frame.grid_columnconfigure(0, weight=1)

        self.cbp_log_text = scrolledtext.ScrolledText(log_frame, state='disabled', font=('Consolas', 9), height=6)
        self.cbp_log_text.pack(fill="x", expand=False)

        # Initial refresh
        self.root.after(500, self._refresh_cbp_list)

    def _browse_cbp_input(self):
        """Browse for CBP input folder."""
        folder = filedialog.askdirectory(initialdir=self.cbp_input_var.get())
        if folder:
            # Normalize path to Windows format with backslashes
            normalized_path = str(Path(folder).resolve())
            self.cbp_input_var.set(normalized_path)
            # Save to config
            self.config.cbp_input_folder = normalized_path
            self._refresh_cbp_list()

    def _browse_cbp_output(self):
        """Browse for CBP output folder."""
        folder = filedialog.askdirectory(initialdir=self.cbp_output_var.get())
        if folder:
            # Normalize path to Windows format with backslashes
            normalized_path = str(Path(folder).resolve())
            self.cbp_output_var.set(normalized_path)
            # Save to config
            self.config.cbp_output_folder = normalized_path

    def _refresh_cbp_list(self):
        """Refresh the list of available CSV files."""
        # Clear existing items
        for item in self.cbp_tree.get_children():
            self.cbp_tree.delete(item)

        input_folder = Path(self.cbp_input_var.get())
        if not input_folder.exists():
            return

        # Find all CSV files
        csv_files = sorted(input_folder.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)

        for csv_file in csv_files:
            try:
                # Read CSV to get info
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

                item_count = len(rows)
                invoice_set = set()
                for row in rows:
                    if 'invoice_number' in row:
                        invoice_set.add(row['invoice_number'])

                invoice_count = len(invoice_set) if invoice_set else 1

                # Check if already processed - look for any invoice files from this CSV
                output_folder = Path(self.cbp_output_var.get())
                status = "Pending"

                if invoice_set:
                    # Check if any invoice files exist (format: {invoice_number}_{date}.xlsx)
                    for invoice_num in invoice_set:
                        safe_invoice = str(invoice_num).replace('/', '_').replace('\\', '_')
                        # Look for any file starting with this invoice number
                        matching_files = list(output_folder.glob(f"{safe_invoice}_*.xlsx"))
                        if matching_files:
                            status = "Exported"
                            break
                else:
                    # Fallback for old format or single file
                    if list(output_folder.glob(f"{csv_file.stem}_*.xlsx")):
                        status = "Exported"

                # Get modification date with time
                mod_time = datetime.fromtimestamp(csv_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                self.cbp_tree.insert("", "end", values=(
                    csv_file.name,
                    mod_time,
                    invoice_count,
                    item_count,
                    status
                ))
            except Exception as e:
                self.cbp_tree.insert("", "end", values=(csv_file.name, "", "", "", f"Error: {e}"))

    def _on_cbp_file_select(self, event=None):
        """Handle CSV file selection - update weight display from bol_gross_weight column."""
        selection = self.cbp_tree.selection()
        if not selection:
            self.cbp_weight_var.set("0")
            return

        try:
            # Get selected filename
            item = self.cbp_tree.item(selection[0])
            filename = item['values'][0]
            input_path = Path(self.cbp_input_var.get()) / filename

            # Read CSV and extract bol_gross_weight
            import csv
            with open(input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Look for bol_gross_weight column
            if rows and 'bol_gross_weight' in rows[0]:
                # Get first non-empty bol_gross_weight value
                for row in rows:
                    bol_weight = row.get('bol_gross_weight', '').strip()
                    if bol_weight:
                        try:
                            # Validate it's a number and display it
                            weight_float = float(bol_weight)
                            self.cbp_weight_var.set(f"{weight_float:.3f}")
                            return
                        except ValueError:
                            continue

            # If no bol_gross_weight found, set to 0
            self.cbp_weight_var.set("0")

        except Exception as e:
            self.cbp_weight_var.set("0")
            self._cbp_log(f"Error reading weight from CSV: {e}")

    def _cbp_log(self, message: str):
        """Log a message to the CBP log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.cbp_log_text.configure(state='normal')
        self.cbp_log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.cbp_log_text.see(tk.END)
        self.cbp_log_text.configure(state='disabled')

    def _process_cbp_single(self):
        """Process selected CSV file through invoice processor."""
        if not HAS_INVOICE_PROCESSOR:
            messagebox.showerror("Error", "Invoice Processor module not available.\nCheck DerivativeMill submodule.")
            return

        selection = self.cbp_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a CSV file to process.")
            return

        item = self.cbp_tree.item(selection[0])
        filename = item['values'][0]
        input_path = Path(self.cbp_input_var.get()) / filename

        self._process_cbp_file(input_path)

    def _process_cbp_all(self):
        """Process all pending CSV files."""
        if not HAS_INVOICE_PROCESSOR:
            messagebox.showerror("Error", "Invoice Processor module not available.\nCheck DerivativeMill submodule.")
            return

        input_folder = Path(self.cbp_input_var.get())
        output_folder = Path(self.cbp_output_var.get())

        csv_files = list(input_folder.glob("*.csv"))
        pending_files = []

        for csv_file in csv_files:
            output_file = output_folder / f"{csv_file.stem}_CBP.xlsx"
            if not output_file.exists():
                pending_files.append(csv_file)

        if not pending_files:
            messagebox.showinfo("All Done", "All CSV files have already been exported.")
            return

        if not messagebox.askyesno("Process All",
                                   f"Process {len(pending_files)} pending CSV file(s)?"):
            return

        for csv_file in pending_files:
            self._process_cbp_file(csv_file)

        self._refresh_cbp_list()

    def _process_cbp_file(self, csv_path: Path):
        """Process a single CSV file through the invoice processor."""
        import pandas as pd

        try:
            self._cbp_log(f"Processing: {csv_path.name}")

            # Read the CSV
            df = pd.read_csv(csv_path)
            self._cbp_log(f"  Loaded {len(df)} rows")

            # Get net weight from input or from CSV if available
            try:
                net_weight = float(self.cbp_weight_var.get())
            except ValueError:
                net_weight = 0.0

            # If net weight is 0, try to get from CSV columns
            if net_weight == 0:
                # First try bol_gross_weight (total BOL shipment weight)
                if 'bol_gross_weight' in df.columns:
                    # Use first non-null bol_gross_weight value (all items should have same BOL weight)
                    bol_weights = df['bol_gross_weight'].dropna()
                    if len(bol_weights) > 0:
                        net_weight = float(bol_weights.iloc[0])
                        self._cbp_log(f"  Using BOL gross weight from CSV: {net_weight:.2f} kg")
                # Otherwise try summing net_weight column
                elif 'net_weight' in df.columns:
                    net_weight = df['net_weight'].sum()
                    self._cbp_log(f"  Using net weight from CSV: {net_weight:.2f} kg")

            # Map OCRMill columns to invoice_processor expected columns
            column_mapping = {
                'part_number': 'part_number',
                'total_price': 'value_usd',
                'hts_code': 'hts_code',
                'quantity': 'quantity',
                'steel_percentage': 'steel_ratio',
                'aluminum_percentage': 'aluminum_ratio',
                'invoice_number': 'invoice_number',
                'project_number': 'project_number',
                'mid': 'mid'
            }

            # Rename columns if they exist
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns and old_col != new_col:
                    df = df.rename(columns={old_col: new_col})

            # Enrich data with parts database information (material percentages, HTS codes, etc.)
            self._cbp_log(f"  Enriching data from parts database...")
            enriched_rows = []
            parts_found = 0
            parts_missing = 0

            for _, row in df.iterrows():
                part_number = row.get('part_number', '')
                if part_number:
                    # Look up part in database
                    part_info = self.db.get_part_summary(part_number)
                    if part_info:
                        parts_found += 1
                        # Add material percentages from database
                        row['steel_ratio'] = part_info.get('steel_pct', 0)
                        row['aluminum_ratio'] = part_info.get('aluminum_pct', 0)
                        row['copper_ratio'] = part_info.get('copper_pct', 0)
                        row['wood_ratio'] = part_info.get('wood_pct', 0)
                        row['auto_ratio'] = part_info.get('auto_pct', 0)
                        row['non_steel_ratio'] = part_info.get('non_steel_pct', 0)
                        # Add HTS code if not already present
                        if pd.isna(row.get('hts_code')) or not row.get('hts_code'):
                            row['hts_code'] = part_info.get('hts_code', '')
                        # Add MID if not already present
                        if pd.isna(row.get('mid')) or not row.get('mid'):
                            row['mid'] = part_info.get('mid', '')
                        # Add country origin
                        row['country_origin'] = part_info.get('country_origin', '')
                        # Add qty_unit
                        row['qty_unit'] = part_info.get('qty_unit', 'NO')
                        # Add Section 301 exclusion
                        row['Sec301_Exclusion_Tariff'] = part_info.get('sec301_exclusion_tariff', '')
                    else:
                        parts_missing += 1
                        # Set defaults for missing parts
                        row['steel_ratio'] = row.get('steel_ratio', 100)  # Default to 100% steel
                        row['aluminum_ratio'] = row.get('aluminum_ratio', 0)
                        row['copper_ratio'] = row.get('copper_ratio', 0)
                        row['wood_ratio'] = row.get('wood_ratio', 0)
                        row['auto_ratio'] = row.get('auto_ratio', 0)
                        row['non_steel_ratio'] = row.get('non_steel_ratio', 0)
                        row['qty_unit'] = row.get('qty_unit', 'NO')

                enriched_rows.append(row)

            df = pd.DataFrame(enriched_rows)
            self._cbp_log(f"  Parts in database: {parts_found}/{len(df)}")
            if parts_missing > 0:
                self._cbp_log(f"  WARNING: {parts_missing} parts not found in database (using defaults)")

            # Get MID from first row if available
            mid = df['mid'].iloc[0] if 'mid' in df.columns and len(df) > 0 else ""

            # Initialize processor - try database first, fall back to empty
            db_path = DERIVATIVEMILL_PATH / "Resources" / "derivativemill.db"
            if db_path.exists():
                processor = InvoiceProcessor.from_database(str(db_path))
                self._cbp_log(f"  Using tariff database: {db_path.name}")
            else:
                processor = InvoiceProcessor.from_dict({})
                self._cbp_log(f"  No tariff database found, using empty lookup")

            # Process the invoice data
            result = processor.process(df, net_weight=net_weight, mid=mid)

            self._cbp_log(f"  Original rows: {result.original_row_count}")
            self._cbp_log(f"  Expanded rows: {result.expanded_row_count}")
            self._cbp_log(f"  Total value: ${result.total_value:,.2f}")

            # Use user-selected output folder for split invoice files
            output_folder = Path(self.cbp_output_var.get())
            output_folder.mkdir(parents=True, exist_ok=True)

            # Rename _232_flag to 232_Status for output
            if '_232_flag' in result.data.columns:
                result.data['232_Status'] = result.data['_232_flag']

            # Convert material ratio percentages to display format (e.g., "100%" instead of "100.0")
            for col in ['SteelRatio', 'AluminumRatio', 'CopperRatio', 'WoodRatio', 'AutoRatio', 'NonSteelRatio']:
                if col in result.data.columns:
                    result.data[col] = result.data[col].apply(lambda x: f"{x}%" if pd.notna(x) else "")

            # Define CBP export column order (matches required output format)
            cbp_columns = [
                'Product No', 'ValueUSD', 'HTSCode', 'MID', 'Qty1', 'Qty2',
                'DecTypeCd', 'CountryofMelt', 'CountryOfCast', 'PrimCountryOfSmelt',
                'PrimSmeltFlag', 'SteelRatio', 'AluminumRatio', 'NonSteelRatio', '232_Status'
            ]

            # Filter to only columns that exist in the data
            export_columns = [col for col in cbp_columns if col in result.data.columns]

            # Log what columns are being exported
            self._cbp_log(f"  Exporting {len(export_columns)} columns: {', '.join(export_columns)}")

            # Split by invoice_number and export separate files
            if 'invoice_number' in result.data.columns:
                date_suffix = datetime.now().strftime("%Y%m%d")
                invoice_numbers = result.data['invoice_number'].dropna().unique()
                files_created = []

                for invoice_num in invoice_numbers:
                    invoice_df = result.data[result.data['invoice_number'] == invoice_num]
                    safe_invoice = str(invoice_num).replace('/', '_').replace('\\', '_')
                    output_path = output_folder / f"{safe_invoice}_{date_suffix}.xlsx"

                    processor.export(invoice_df, str(output_path), columns=export_columns)
                    files_created.append(output_path.name)

                self._cbp_log(f"  Split into {len(files_created)} invoice file(s):")
                for filename in sorted(files_created):
                    self._cbp_log(f"    - {filename}")
            else:
                # Fallback to single file export if no invoice_number column
                date_suffix = datetime.now().strftime("%Y%m%d")
                output_path = output_folder / f"{csv_path.stem}_{date_suffix}.xlsx"
                processor.export(result.data, str(output_path), columns=export_columns)
                self._cbp_log(f"  Exported to: {output_path.name}")

            self._cbp_log(f"  Success!")

            # Move CSV to Processed subfolder
            input_folder = Path(self.cbp_input_var.get())
            processed_folder = input_folder / "Processed"
            processed_folder.mkdir(parents=True, exist_ok=True)

            # Generate unique filename if destination already exists
            dest_path = processed_folder / csv_path.name
            if dest_path.exists():
                base_name = csv_path.stem
                suffix = csv_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = processed_folder / f"{base_name}_{counter}{suffix}"
                    counter += 1

            csv_path.rename(dest_path)
            self._cbp_log(f"  Moved CSV to: Processed/{dest_path.name}")

            self._refresh_cbp_list()

        except Exception as e:
            self._cbp_log(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

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
            # Normalize path to Windows format with backslashes
            normalized_path = str(Path(folder).resolve())
            self.input_var.set(normalized_path)

    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory(initialdir=self.output_var.get())
        if folder:
            # Normalize path to Windows format with backslashes
            normalized_path = str(Path(folder).resolve())
            self.output_var.set(normalized_path)

    def _refresh_output_files(self):
        """Refresh the output files list."""
        self.output_files_listbox.delete(0, tk.END)

        output_folder = Path(self.config.output_folder)
        if not output_folder.exists():
            return

        # Get all CSV files from output folder and subfolders
        csv_files = []
        for pattern in ['*.csv', '**/*.csv']:
            csv_files.extend(output_folder.glob(pattern))

        # Sort by modification time (newest first)
        csv_files = sorted(csv_files, key=lambda p: p.stat().st_mtime, reverse=True)

        # Add to listbox with relative paths
        for file_path in csv_files:
            try:
                rel_path = file_path.relative_to(output_folder)
                self.output_files_listbox.insert(tk.END, str(rel_path))
            except ValueError:
                # If relative path fails, use absolute
                self.output_files_listbox.insert(tk.END, str(file_path))

    def _open_output_folder(self):
        """Open the output folder in file explorer."""
        output_folder = Path(self.config.output_folder)
        if output_folder.exists():
            try:
                os.startfile(str(output_folder))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder: {e}")
        else:
            messagebox.showwarning("Warning", f"Output folder does not exist:\n{output_folder}")

    def _open_selected_output_file(self):
        """Open the selected output file with default application."""
        selection = self.output_files_listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file to open.")
            return

        rel_path = self.output_files_listbox.get(selection[0])
        file_path = Path(self.config.output_folder) / rel_path

        if file_path.exists():
            try:
                os.startfile(str(file_path))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file: {e}")
        else:
            messagebox.showerror("Error", f"File not found:\n{file_path}")

    def _open_selected_output_file_excel(self):
        """Open the selected output file in Excel."""
        selection = self.output_files_listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file to open.")
            return

        rel_path = self.output_files_listbox.get(selection[0])
        file_path = Path(self.config.output_folder) / rel_path

        if file_path.exists():
            try:
                # Try to open with Excel specifically
                excel_path = "excel.exe"
                subprocess.run([excel_path, str(file_path)], check=False)
            except Exception:
                # Fallback to default application
                try:
                    os.startfile(str(file_path))
                except Exception as e2:
                    messagebox.showerror("Error", f"Could not open file: {e2}")
        else:
            messagebox.showerror("Error", f"File not found:\n{file_path}")

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

    def _save_auto_cbp(self):
        """Save auto CBP export setting."""
        self.config.auto_cbp_export = self.auto_cbp_var.get()
        status = "enabled" if self.auto_cbp_var.get() else "disabled"
        self._queue_log(f"Auto CBP Export: {status}")

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

            # Auto-run CBP export if enabled and files were processed
            if count > 0 and self.auto_cbp_var.get():
                self._auto_cbp_export()
        finally:
            self.processing_lock.release()

    def _auto_cbp_export(self):
        """Automatically process CBP export for pending CSV files."""
        if not HAS_INVOICE_PROCESSOR:
            self._queue_log("Auto CBP Export: Invoice Processor module not available")
            return

        try:
            input_folder = Path(self.config.cbp_input_folder)
            output_folder = Path(self.config.cbp_output_folder)

            # Ensure output folder exists
            output_folder.mkdir(parents=True, exist_ok=True)

            # Find CSV files that don't have corresponding CBP export
            csv_files = list(input_folder.glob("*.csv"))
            pending_files = []

            for csv_file in csv_files:
                # Check both naming conventions for output files
                output_file1 = output_folder / f"{csv_file.stem}_CBP.xlsx"
                output_file2 = output_folder / f"{csv_file.stem}.xlsx"
                if not output_file1.exists() and not output_file2.exists():
                    pending_files.append(csv_file)

            if not pending_files:
                self._queue_log("Auto CBP Export: No pending files to process")
                return

            self._queue_log(f"Auto CBP Export: Processing {len(pending_files)} file(s)...")

            for csv_file in pending_files:
                try:
                    self._process_cbp_file(csv_file)
                except Exception as e:
                    self._queue_log(f"Auto CBP Export error for {csv_file.name}: {e}")

            self._queue_log(f"Auto CBP Export: Complete")

            # Refresh CBP list if on that tab
            self.root.after(0, self._refresh_cbp_list)

        except Exception as e:
            self._queue_log(f"Auto CBP Export error: {e}")

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

                        # Auto-run CBP export if enabled
                        if self.auto_cbp_var.get():
                            self.root.after(0, self._auto_cbp_export)

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
                part.get('country_origin', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('steel_pct', 0):.0f}" if part.get('steel_pct') else '0',
                f"{part.get('aluminum_pct', 0):.0f}" if part.get('aluminum_pct') else '0',
                f"{part.get('copper_pct', 0):.0f}" if part.get('copper_pct') else '0',
                f"{part.get('wood_pct', 0):.0f}" if part.get('wood_pct') else '0',
                f"{part.get('auto_pct', 0):.0f}" if part.get('auto_pct') else '0',
                f"{part.get('non_steel_pct', 0):.0f}" if part.get('non_steel_pct') else '0',
                part.get('qty_unit', ''),
                part.get('sec301_exclusion_tariff', ''),
                part.get('fsc_certified', ''),
                part.get('fsc_certificate_code', ''),
                part.get('last_updated', '')[:10] if part.get('last_updated') else ''
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
                part.get('country_origin', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('steel_pct', 0):.0f}" if part.get('steel_pct') else '0',
                f"{part.get('aluminum_pct', 0):.0f}" if part.get('aluminum_pct') else '0',
                f"{part.get('copper_pct', 0):.0f}" if part.get('copper_pct') else '0',
                f"{part.get('wood_pct', 0):.0f}" if part.get('wood_pct') else '0',
                f"{part.get('auto_pct', 0):.0f}" if part.get('auto_pct') else '0',
                f"{part.get('non_steel_pct', 0):.0f}" if part.get('non_steel_pct') else '0',
                part.get('qty_unit', ''),
                part.get('sec301_exclusion_tariff', ''),
                part.get('fsc_certified', ''),
                part.get('fsc_certificate_code', ''),
                part.get('last_updated', '')[:10] if part.get('last_updated') else ''
            )
            self.parts_tree.insert("", "end", values=values)

        self.status_var.set(f"Found {len(parts)} parts matching '{search_term}'")

    def _apply_column_visibility(self):
        """Apply column visibility settings from config."""
        if not hasattr(self, 'parts_tree'):
            return

        # Get displaycolumns as a list (convert from tuple if needed)
        visible_cols = []

        for col_name in self.all_parts_columns:
            if self.config.get_column_visible(col_name):
                visible_cols.append(col_name)

        # Set the displaycolumns to only show visible columns
        self.parts_tree['displaycolumns'] = visible_cols

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
            SELECT
                po.part_number,
                COUNT(DISTINCT po.invoice_number) as invoice_count,
                SUM(po.quantity) as total_quantity,
                SUM(po.total_price) as total_value,
                p.hts_code
            FROM part_occurrences po
            LEFT JOIN parts p ON po.part_number = p.part_number
            GROUP BY po.part_number
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
MID:                {part.get('mid') or 'N/A'}
Client Code:        {part.get('client_code') or 'N/A'}

Material Composition
{'-' * 60}
Steel:              {part.get('steel_pct', 0):.0f}%
Aluminum:           {part.get('aluminum_pct', 0):.0f}%
Copper:             {part.get('copper_pct', 0):.0f}%
Wood:               {part.get('wood_pct', 0):.0f}%
Auto:               {part.get('auto_pct', 0):.0f}%

Timeline
{'-' * 60}
Last Updated:       {part.get('last_updated', 'N/A')}
"""
        text.insert("1.0", details)
        text.config(state="disabled")

    def _edit_part(self, event=None):
        """Edit selected part information."""
        selection = self.parts_tree.selection()
        if not selection:
            return

        item = self.parts_tree.item(selection[0])
        part_number = item['values'][0]

        # Get current part data
        part = self.db.get_part_summary(part_number)
        if not part:
            messagebox.showerror("Error", f"Part {part_number} not found")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Part - {part_number}")
        dialog.geometry("500x600")

        # Create scrollable frame
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Part Number (read-only)
        ttk.Label(scrollable_frame, text="Part Number:", font=("", 10, "bold")).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        ttk.Label(scrollable_frame, text=part_number).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Description
        ttk.Label(scrollable_frame, text="Description:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        desc_var = tk.StringVar(value=part.get('description', ''))
        desc_entry = ttk.Entry(scrollable_frame, textvariable=desc_var, width=40)
        desc_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # HTS Code
        ttk.Label(scrollable_frame, text="HTS Code:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        hts_var = tk.StringVar(value=part.get('hts_code', ''))
        hts_entry = ttk.Entry(scrollable_frame, textvariable=hts_var, width=40)
        hts_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        # Country Origin
        ttk.Label(scrollable_frame, text="Country Origin:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        country_var = tk.StringVar(value=part.get('country_origin', ''))
        country_entry = ttk.Entry(scrollable_frame, textvariable=country_var, width=40)
        country_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # MID
        ttk.Label(scrollable_frame, text="MID:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        mid_var = tk.StringVar(value=part.get('mid', ''))
        mid_entry = ttk.Entry(scrollable_frame, textvariable=mid_var, width=40)
        mid_entry.grid(row=4, column=1, sticky="w", padx=5, pady=5)

        # Client Code
        ttk.Label(scrollable_frame, text="Client Code:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        client_var = tk.StringVar(value=part.get('client_code', ''))
        client_entry = ttk.Entry(scrollable_frame, textvariable=client_var, width=40)
        client_entry.grid(row=5, column=1, sticky="w", padx=5, pady=5)

        # Steel %
        ttk.Label(scrollable_frame, text="Steel %:").grid(row=6, column=0, sticky="e", padx=5, pady=5)
        steel_var = tk.StringVar(value=str(part.get('steel_pct', 0)))
        steel_entry = ttk.Entry(scrollable_frame, textvariable=steel_var, width=40)
        steel_entry.grid(row=6, column=1, sticky="w", padx=5, pady=5)

        # Aluminum %
        ttk.Label(scrollable_frame, text="Aluminum %:").grid(row=7, column=0, sticky="e", padx=5, pady=5)
        aluminum_var = tk.StringVar(value=str(part.get('aluminum_pct', 0)))
        aluminum_entry = ttk.Entry(scrollable_frame, textvariable=aluminum_var, width=40)
        aluminum_entry.grid(row=7, column=1, sticky="w", padx=5, pady=5)

        # Copper %
        ttk.Label(scrollable_frame, text="Copper %:").grid(row=8, column=0, sticky="e", padx=5, pady=5)
        copper_var = tk.StringVar(value=str(part.get('copper_pct', 0)))
        copper_entry = ttk.Entry(scrollable_frame, textvariable=copper_var, width=40)
        copper_entry.grid(row=8, column=1, sticky="w", padx=5, pady=5)

        # Wood %
        ttk.Label(scrollable_frame, text="Wood %:").grid(row=9, column=0, sticky="e", padx=5, pady=5)
        wood_var = tk.StringVar(value=str(part.get('wood_pct', 0)))
        wood_entry = ttk.Entry(scrollable_frame, textvariable=wood_var, width=40)
        wood_entry.grid(row=9, column=1, sticky="w", padx=5, pady=5)

        # Auto %
        ttk.Label(scrollable_frame, text="Auto %:").grid(row=10, column=0, sticky="e", padx=5, pady=5)
        auto_var = tk.StringVar(value=str(part.get('auto_pct', 0)))
        auto_entry = ttk.Entry(scrollable_frame, textvariable=auto_var, width=40)
        auto_entry.grid(row=10, column=1, sticky="w", padx=5, pady=5)

        # Non-Steel %
        ttk.Label(scrollable_frame, text="Non-Steel %:").grid(row=11, column=0, sticky="e", padx=5, pady=5)
        non_steel_var = tk.StringVar(value=str(part.get('non_steel_pct', 0)))
        non_steel_entry = ttk.Entry(scrollable_frame, textvariable=non_steel_var, width=40)
        non_steel_entry.grid(row=11, column=1, sticky="w", padx=5, pady=5)

        # Qty Unit
        ttk.Label(scrollable_frame, text="Qty Unit:").grid(row=12, column=0, sticky="e", padx=5, pady=5)
        qty_unit_var = tk.StringVar(value=part.get('qty_unit', ''))
        qty_unit_entry = ttk.Entry(scrollable_frame, textvariable=qty_unit_var, width=40)
        qty_unit_entry.grid(row=12, column=1, sticky="w", padx=5, pady=5)

        # Section 301 Exclusion Tariff
        ttk.Label(scrollable_frame, text="Sec301 Exclusion:").grid(row=13, column=0, sticky="e", padx=5, pady=5)
        sec301_var = tk.StringVar(value=part.get('sec301_exclusion_tariff', ''))
        sec301_entry = ttk.Entry(scrollable_frame, textvariable=sec301_var, width=40)
        sec301_entry.grid(row=13, column=1, sticky="w", padx=5, pady=5)

        # FSC Certified
        ttk.Label(scrollable_frame, text="FSC Certified:").grid(row=14, column=0, sticky="e", padx=5, pady=5)
        fsc_certified_var = tk.StringVar(value=part.get('fsc_certified', ''))
        fsc_certified_entry = ttk.Entry(scrollable_frame, textvariable=fsc_certified_var, width=40)
        fsc_certified_entry.grid(row=14, column=1, sticky="w", padx=5, pady=5)

        # FSC Certificate Code
        ttk.Label(scrollable_frame, text="FSC Certificate Code:").grid(row=15, column=0, sticky="e", padx=5, pady=5)
        fsc_cert_code_var = tk.StringVar(value=part.get('fsc_certificate_code', ''))
        fsc_cert_code_entry = ttk.Entry(scrollable_frame, textvariable=fsc_cert_code_var, width=40)
        fsc_cert_code_entry.grid(row=15, column=1, sticky="w", padx=5, pady=5)

        def save_changes():
            try:
                # Prepare update data
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    UPDATE parts SET
                        description = ?,
                        hts_code = ?,
                        country_origin = ?,
                        mid = ?,
                        client_code = ?,
                        steel_pct = ?,
                        aluminum_pct = ?,
                        copper_pct = ?,
                        wood_pct = ?,
                        auto_pct = ?,
                        non_steel_pct = ?,
                        qty_unit = ?,
                        sec301_exclusion_tariff = ?,
                        fsc_certified = ?,
                        fsc_certificate_code = ?,
                        last_updated = datetime('now')
                    WHERE part_number = ?
                """, (
                    desc_var.get().strip(),
                    hts_var.get().strip(),
                    country_var.get().strip(),
                    mid_var.get().strip(),
                    client_var.get().strip(),
                    int(steel_var.get() or 0),
                    int(aluminum_var.get() or 0),
                    int(copper_var.get() or 0),
                    int(wood_var.get() or 0),
                    int(auto_var.get() or 0),
                    int(non_steel_var.get() or 0),
                    qty_unit_var.get().strip(),
                    sec301_var.get().strip(),
                    fsc_certified_var.get().strip(),
                    fsc_cert_code_var.get().strip(),
                    part_number
                ))
                self.db.conn.commit()
                messagebox.showinfo("Success", f"Part {part_number} updated successfully")
                self._refresh_parts_data()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update part: {e}")

        # Buttons frame
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=16, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=save_changes).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

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

    def _show_settings_dialog(self):
        """Show settings dialog."""
        SettingsDialog(self.root, self.config, on_save=self._apply_column_visibility)

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

        # Save CBP export settings (weight is not saved - auto-populated from CSV)
        self.config.cbp_input_folder = self.cbp_input_var.get()
        self.config.cbp_output_folder = self.cbp_output_var.get()

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
