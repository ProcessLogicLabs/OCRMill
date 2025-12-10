"""
Invoice Processor GUI Application
Main window for managing the invoice processing service.
"""

__version__ = "2.0.0"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import time
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

try:
    import pdfplumber
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber

from config_manager import ConfigManager
from templates import get_all_templates, TEMPLATE_REGISTRY
from parts_database import PartsDatabase


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

    def __init__(self, config: ConfigManager, log_callback=None):
        self.config = config
        self.log_callback = log_callback or print
        self.templates = {}
        self.parts_db = PartsDatabase()
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
                    # Note: Keep slashes in Brazilian invoice numbers (e.g., 2025/1850)
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
                        current_invoice = inv_match.group(1)  # Keep original format (slash for Brazilian, no modification)
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

                # Count unique invoices
                unique_invoices = set(item.get('invoice_number', 'UNKNOWN') for item in all_items)
                self.log(f"  Found {len(unique_invoices)} invoice(s), {len(all_items)} total items")
                for inv in sorted(unique_invoices):
                    inv_items = [item for item in all_items if item.get('invoice_number') == inv]
                    proj = inv_items[0].get('project_number', 'UNKNOWN') if inv_items else 'UNKNOWN'
                    self.log(f"    - Invoice {inv} (Project {proj}): {len(inv_items)} items")

                return all_items

        except Exception as e:
            self.log(f"  Error processing {pdf_path.name}: {e}")
            return []
    
    def save_to_csv(self, items: List[Dict], output_folder: Path, pdf_name: str = None):
        """
        Save items to CSV files and add to parts database.

        Args:
            items: List of invoice line items
            output_folder: Folder to save CSV files
            pdf_name: Name of the source PDF (used for consolidated mode)
        """
        if not items:
            return

        # Add items to parts database
        for item in items:
            part_data = item.copy()
            part_data['source_file'] = pdf_name or 'unknown'
            self.parts_db.add_part_occurrence(part_data)

        # Group by invoice number
        by_invoice = {}
        for item in items:
            inv_num = item.get('invoice_number', 'UNKNOWN')
            if inv_num not in by_invoice:
                by_invoice[inv_num] = []
            by_invoice[inv_num].append(item)

        # Determine columns from items
        columns = ['invoice_number', 'project_number', 'part_number', 'quantity', 'total_price']
        for item in items:
            for key in item.keys():
                if key not in columns:
                    columns.append(key)

        # Check consolidation mode
        consolidate = self.config.consolidate_multi_invoice

        if consolidate and len(by_invoice) > 1:
            # Consolidate all invoices into one CSV per PDF
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Use PDF name or first invoice number for filename
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
            # Save each invoice to its own CSV (default behavior)
            for inv_num, inv_items in by_invoice.items():
                proj_num = inv_items[0].get('project_number', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Replace forward slashes in invoice number to avoid path issues
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
        # Handle duplicate filenames
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
        # Handle duplicate filenames
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
                    # No items extracted - move to Failed folder
                    self.move_to_failed(pdf_path, failed_folder, "No items extracted")
                    failed_count += 1
            except Exception as e:
                self.log(f"  Error processing {pdf_path.name}: {e}")
                self.move_to_failed(pdf_path, failed_folder, f"Error: {str(e)[:50]}")
                failed_count += 1

        if failed_count > 0:
            self.log(f"Summary: {processed_count} processed successfully, {failed_count} failed")

        return processed_count


class InvoiceProcessorGUI:
    """Main GUI Application."""
    
    def __init__(self):
        self.config = ConfigManager()
        self.root = tk.Tk()
        self.root.title(f"Invoice Processor v{__version__}")
        self.root.geometry(f"{self.config.get('window.width', 900)}x{self.config.get('window.height', 650)}")
        
        # Processing state
        self.running = False
        self.processing_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.files_processed = 0
        self.last_check: Optional[str] = None
        
        # Log queue for thread-safe logging
        self.log_queue = queue.Queue()
        
        # Create the processor engine
        self.engine = ProcessorEngine(self.config, log_callback=self._queue_log)
        
        # Build the UI
        self._create_ui()
        
        # Start log consumer
        self._consume_logs()
        
        # Auto-start if configured
        if self.config.auto_start:
            self.root.after(1000, self.start_processing)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
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
        
        # Schedule next check
        self.root.after(100, self._consume_logs)
    
    def _append_log(self, message: str):
        """Append a message to the log display."""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
    
    def _create_ui(self):
        """Create the main user interface."""
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        
        # === Header Frame ===
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.grid(row=0, column=0, sticky="ew")
        
        ttk.Label(header_frame, text="Invoice Processor", font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(header_frame, text="● Stopped", foreground="red", font=('Helvetica', 12))
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # === Settings Frame ===
        settings_frame = ttk.LabelFrame(self.root, text="Settings", padding="10")
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

        # === Control Frame ===
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=1, column=0, sticky="e", padx=10, pady=5)

        # This will be inside settings frame at the bottom
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ Start", command=self.start_processing, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="■ Stop", command=self.stop_processing, width=15, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="⟳ Process Now", command=self.process_now, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Save Settings", command=self._save_settings, width=15).pack(side=tk.LEFT, padx=5)
        
        # === Main Content - Notebook ===
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # --- Log Tab ---
        log_frame = ttk.Frame(notebook, padding="5")
        notebook.add(log_frame, text="Activity Log")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.grid(row=1, column=0, sticky="e", pady=5)
        ttk.Button(log_btn_frame, text="Clear Log", command=self._clear_log).pack(side=tk.RIGHT)
        
        # --- Templates Tab ---
        template_frame = ttk.Frame(notebook, padding="5")
        notebook.add(template_frame, text="Templates")
        template_frame.grid_columnconfigure(0, weight=1)
        template_frame.grid_rowconfigure(0, weight=1)
        
        # Template list with checkboxes
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
        
        # Template info
        info_frame = ttk.LabelFrame(template_frame, text="Template Information", padding="10")
        info_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        info_text = """Templates are used to recognize and extract data from different invoice formats.
        
To add a new template:
1. Create a new Python file in the 'templates' folder
2. Inherit from BaseTemplate class
3. Implement required methods: can_process(), extract_invoice_number(), 
   extract_project_number(), extract_line_items()
4. Register in templates/__init__.py

See templates/base_template.py for documentation."""
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # --- Statistics Tab ---
        stats_frame = ttk.Frame(notebook, padding="5")
        notebook.add(stats_frame, text="Statistics")
        
        self.stats_labels = {}
        stats_info = ttk.LabelFrame(stats_frame, text="Processing Statistics", padding="10")
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
            self.stats_labels[key] = ttk.Label(stats_info, text=default)
            self.stats_labels[key].grid(row=i, column=1, sticky="w", padx=10, pady=2)
        
        ttk.Button(stats_frame, text="Refresh Statistics", command=self._update_statistics).pack(pady=10)
        
        # === Status Bar ===
        status_bar = ttk.Frame(self.root)
        status_bar.grid(row=3, column=0, sticky="ew")
        
        self.status_bar_label = ttk.Label(status_bar, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar_label.pack(fill=tk.X, padx=2, pady=2)
        
        # Initial log message
        self._queue_log("Invoice Processor GUI started")
        self._queue_log(f"Input folder: {self.config.input_folder}")
        self._queue_log(f"Output folder: {self.config.output_folder}")
    
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
    
    def _update_statistics(self):
        """Update the statistics display."""
        input_folder = Path(self.input_var.get())
        output_folder = Path(self.output_var.get())
        
        # Count files
        input_count = len(list(input_folder.glob("*.pdf"))) if input_folder.exists() else 0
        output_count = len(list(output_folder.glob("*.csv"))) if output_folder.exists() else 0
        
        self.stats_labels["files_processed"].config(text=str(self.files_processed))
        self.stats_labels["last_check"].config(text=self.last_check or "Never")
        self.stats_labels["status"].config(text="Running" if self.running else "Stopped")
        self.stats_labels["input_count"].config(text=f"{input_count} PDFs waiting")
        self.stats_labels["output_count"].config(text=f"{output_count} CSVs generated")
    
    def start_processing(self):
        """Start the background processing thread."""
        if self.running:
            return
        
        self._save_settings()
        
        self.running = True
        self.stop_event.clear()
        
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="● Running", foreground="green")
        self.status_bar_label.config(text="Processing active...")
        
        self._queue_log("Processing started")
        
        # Start background thread
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
        self.status_label.config(text="● Stopped", foreground="red")
        self.status_bar_label.config(text="Processing stopped")
        
        self._queue_log("Processing stopped")
    
    def process_now(self):
        """Process files immediately (one-time)."""
        self._queue_log("Manual processing triggered")
        
        input_folder = Path(self.input_var.get())
        output_folder = Path(self.output_var.get())
        
        count = self.engine.process_folder(input_folder, output_folder)
        self.files_processed += count
        self.last_check = datetime.now().strftime("%H:%M:%S")
        
        self._update_statistics()
        self._queue_log(f"Manual processing complete: {count} files processed")
    
    def _processing_loop(self):
        """Background processing loop."""
        input_folder = Path(self.input_var.get())
        output_folder = Path(self.output_var.get())
        
        while not self.stop_event.is_set():
            try:
                # Process files
                count = self.engine.process_folder(input_folder, output_folder)
                self.files_processed += count
                self.last_check = datetime.now().strftime("%H:%M:%S")
                
                # Update UI (thread-safe)
                self.root.after(0, self._update_statistics)
                
                # Wait for next poll
                poll_interval = int(self.poll_var.get())
                for _ in range(poll_interval):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self._queue_log(f"Error in processing loop: {e}")
                time.sleep(5)
    
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


def main():
    """Main entry point."""
    app = InvoiceProcessorGUI()
    app.run()


if __name__ == "__main__":
    main()
