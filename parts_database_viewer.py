"""
Parts Database Viewer and Manager
GUI application for viewing, searching, and managing the parts database.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
import os

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from parts_database import PartsDatabase, create_parts_report


class PartsViewerApp:
    """GUI application for parts database management."""

    def __init__(self, root):
        self.root = root
        self.root.title("Parts Database Viewer - OCRMill")
        self.root.geometry("1200x700")

        self.db = PartsDatabase()
        self._create_menu()
        self._create_widgets()
        self._load_initial_data()

    def _create_menu(self):
        """Create the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Parts List...", command=self._load_hts)
        file_menu.add_command(label="Export Master CSV...", command=self._export_master)
        file_menu.add_command(label="Export History CSV...", command=self._export_history)
        file_menu.add_separator()
        file_menu.add_command(label="Generate Reports...", command=self._generate_reports)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Lists menu
        lists_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Lists", menu=lists_menu)
        lists_menu.add_command(label="Manufacturers/MID...", command=self._show_manufacturers_dialog)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _create_widgets(self):
        """Create the GUI layout."""
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding="5")
        toolbar.pack(fill="x", side="top")

        ttk.Button(toolbar, text="Refresh", command=self._refresh_data).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export Master CSV", command=self._export_master).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Export History CSV", command=self._export_history).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Import Parts List", command=self._load_hts).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Generate Reports", command=self._generate_reports).pack(side="left", padx=2)

        # Search bar
        search_frame = ttk.Frame(self.root, padding="5")
        search_frame.pack(fill="x", side="top")

        ttk.Label(search_frame, text="Search:").pack(side="left", padx=2)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._search_parts())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side="left", padx=2)

        ttk.Label(search_frame, text="Filter:").pack(side="left", padx=(20, 2))
        self.filter_var = tk.StringVar(value="all")
        ttk.Radiobutton(search_frame, text="All Parts", variable=self.filter_var,
                       value="all", command=self._refresh_data).pack(side="left")
        ttk.Radiobutton(search_frame, text="With HTS", variable=self.filter_var,
                       value="with_hts", command=self._refresh_data).pack(side="left")
        ttk.Radiobutton(search_frame, text="No HTS", variable=self.filter_var,
                       value="no_hts", command=self._refresh_data).pack(side="left")

        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Tab 1: Parts Master List
        self.parts_tab = ttk.Frame(notebook)
        notebook.add(self.parts_tab, text="Parts Master")
        self._create_parts_tab()

        # Tab 2: Part History
        self.history_tab = ttk.Frame(notebook)
        notebook.add(self.history_tab, text="Part History")
        self._create_history_tab()

        # Tab 3: Statistics
        self.stats_tab = ttk.Frame(notebook)
        notebook.add(self.stats_tab, text="Statistics")
        self._create_stats_tab()

        # Tab 4: HTS Management
        self.hts_tab = ttk.Frame(notebook)
        notebook.add(self.hts_tab, text="HTS Codes")
        self._create_hts_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

    def _create_parts_tab(self):
        """Create the parts master list tab."""
        # Treeview for parts list
        tree_frame = ttk.Frame(self.parts_tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("part_number", "description", "hts_code", "country_origin", "mid", "client_code",
                  "steel_ratio", "aluminum_ratio", "last_updated")

        self.parts_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.parts_tree.yview)
        hsb.config(command=self.parts_tree.xview)

        # Column headings
        self.parts_tree.heading("part_number", text="Part Number")
        self.parts_tree.heading("description", text="Description")
        self.parts_tree.heading("hts_code", text="HTS Code")
        self.parts_tree.heading("country_origin", text="Country of Melt")
        self.parts_tree.heading("mid", text="MID")
        self.parts_tree.heading("client_code", text="Client")
        self.parts_tree.heading("steel_ratio", text="Steel %")
        self.parts_tree.heading("aluminum_ratio", text="Aluminum %")
        self.parts_tree.heading("last_updated", text="Last Updated")

        # Column widths
        self.parts_tree.column("part_number", width=140)
        self.parts_tree.column("description", width=180)
        self.parts_tree.column("hts_code", width=100)
        self.parts_tree.column("country_origin", width=100)
        self.parts_tree.column("mid", width=130)
        self.parts_tree.column("client_code", width=80)
        self.parts_tree.column("steel_ratio", width=60)
        self.parts_tree.column("aluminum_ratio", width=70)
        self.parts_tree.column("last_updated", width=90)

        # Layout
        self.parts_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Double-click to view details
        self.parts_tree.bind("<Double-1>", self._show_part_details)

        # Context menu
        self.parts_menu = tk.Menu(self.parts_tree, tearoff=0)
        self.parts_menu.add_command(label="View Details", command=self._show_part_details)
        self.parts_menu.add_command(label="Set HTS Code", command=self._set_hts_code)
        self.parts_menu.add_command(label="View History", command=self._view_part_history)
        self.parts_tree.bind("<Button-3>", self._show_parts_menu)

    def _create_history_tab(self):
        """Create the part history tab."""
        tree_frame = ttk.Frame(self.history_tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("part_number", "invoice_number", "project_number", "quantity",
                  "total_price", "hts_code", "processed_date")

        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                        yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.config(command=self.history_tree.yview)
        hsb.config(command=self.history_tree.xview)

        # Column headings
        self.history_tree.heading("part_number", text="Part Number")
        self.history_tree.heading("invoice_number", text="Invoice")
        self.history_tree.heading("project_number", text="Project")
        self.history_tree.heading("quantity", text="Quantity")
        self.history_tree.heading("total_price", text="Price")
        self.history_tree.heading("hts_code", text="HTS")
        self.history_tree.heading("processed_date", text="Processed")

        # Layout
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def _create_stats_tab(self):
        """Create the statistics tab."""
        self.stats_text = scrolledtext.ScrolledText(self.stats_tab, wrap=tk.WORD, width=80, height=30)
        self.stats_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Refresh button
        ttk.Button(self.stats_tab, text="Refresh Statistics",
                  command=self._update_statistics).pack(pady=5)

    def _create_hts_tab(self):
        """Create the HTS codes management tab."""
        # Drop zone at top
        self._create_drop_zone()

        tree_frame = ttk.Frame(self.hts_tab)
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

    def _create_drop_zone(self):
        """Create a drag-and-drop zone for importing HTS/product files."""
        drop_frame = ttk.LabelFrame(self.hts_tab, text="Import HTS/Product List", padding="10")
        drop_frame.pack(fill="x", padx=5, pady=5)

        # Create the drop zone label
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

        # Bind click to browse
        self.drop_label.bind("<Button-1>", lambda e: self._load_hts())

        # Set up drag-and-drop if available
        if HAS_DND:
            self._setup_drag_drop()
        else:
            self.drop_label.config(text="Click to browse for Excel (.xlsx) or CSV (.csv) file\n(Install tkinterdnd2 for drag-and-drop support)")

    def _setup_drag_drop(self):
        """Set up drag-and-drop handlers."""
        try:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self._on_drop)
            self.drop_label.dnd_bind('<<DragEnter>>', self._on_drag_enter)
            self.drop_label.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        except Exception as e:
            print(f"Could not set up drag-drop: {e}")
            self.drop_label.config(text="Click to browse for Excel (.xlsx) or CSV (.csv) file")

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

        # Parse dropped file path(s)
        files = self._parse_drop_data(event.data)

        if not files:
            messagebox.showerror("Error", "No valid file dropped")
            return

        # Process the first valid file
        for filepath in files:
            filepath = Path(filepath)
            if filepath.suffix.lower() in ['.xlsx', '.csv']:
                self._import_hts_file(filepath)
                return

        messagebox.showerror("Error", "Please drop an Excel (.xlsx) or CSV (.csv) file")

    def _parse_drop_data(self, data):
        """Parse the dropped file data string into file paths."""
        files = []
        # Handle Windows paths with curly braces for paths with spaces
        if '{' in data:
            import re
            # Extract paths enclosed in curly braces
            matches = re.findall(r'\{([^}]+)\}', data)
            files.extend(matches)
            # Also get paths not in braces
            remaining = re.sub(r'\{[^}]+\}', '', data).strip()
            if remaining:
                files.extend(remaining.split())
        else:
            files = data.split()

        # Clean up paths
        cleaned = []
        for f in files:
            f = f.strip()
            if f:
                cleaned.append(f)

        return cleaned

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
                self._refresh_data()
                self._load_hts_list()
                self._update_statistics()
                self.status_var.set(f"Imported {imported} new, updated {updated} parts from {filepath.name}")

        except Exception as e:
            messagebox.showerror("Error", f"Error importing file: {e}")
            self.status_var.set("Import error")

    def _load_initial_data(self):
        """Load initial data into the viewer."""
        self._refresh_data()
        self._update_statistics()
        self._load_hts_list()

    def _refresh_data(self):
        """Refresh the parts list."""
        # Clear existing items
        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        # Get filter
        filter_type = self.filter_var.get()

        # Load parts
        parts = self.db.get_all_parts()

        # Apply filter
        if filter_type == "with_hts":
            parts = [p for p in parts if p.get('hts_code')]
        elif filter_type == "no_hts":
            parts = [p for p in parts if not p.get('hts_code')]

        # Populate treeview
        for part in parts:
            values = (
                part.get('part_number', ''),
                part.get('description', ''),
                part.get('hts_code', ''),
                part.get('country_origin', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('steel_ratio', 0):.0f}%" if part.get('steel_ratio') else '',
                f"{part.get('aluminum_ratio', 0):.0f}%" if part.get('aluminum_ratio') else '',
                part.get('last_updated', '')[:10] if part.get('last_updated') else ''
            )
            self.parts_tree.insert("", "end", values=values)

        self.status_var.set(f"Loaded {len(parts)} parts")

    def _search_parts(self):
        """Search parts based on search term."""
        search_term = self.search_var.get()

        if not search_term:
            self._refresh_data()
            return

        # Clear existing items
        for item in self.parts_tree.get_children():
            self.parts_tree.delete(item)

        # Search
        parts = self.db.search_parts(search_term)

        # Populate treeview
        for part in parts:
            values = (
                part.get('part_number', ''),
                part.get('description', ''),
                part.get('hts_code', ''),
                part.get('country_origin', ''),
                part.get('mid', ''),
                part.get('client_code', ''),
                f"{part.get('steel_ratio', 0):.0f}%" if part.get('steel_ratio') else '',
                f"{part.get('aluminum_ratio', 0):.0f}%" if part.get('aluminum_ratio') else '',
                part.get('last_updated', '')[:10] if part.get('last_updated') else ''
            )
            self.parts_tree.insert("", "end", values=values)

        self.status_var.set(f"Found {len(parts)} parts matching '{search_term}'")

    def _update_statistics(self):
        """Update the statistics display."""
        self.stats_text.delete("1.0", tk.END)

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
        self.stats_text.insert("1.0", report)

        # Get top parts (TariffMill schema: parts_master table)
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT part_number, invoice_count, total_quantity, total_value, hts_code
            FROM parts_master
            ORDER BY total_value DESC
            LIMIT 10
        """)

        for i, row in enumerate(cursor.fetchall(), 1):
            line = f"{i:2d}. {row['part_number']:15s}  ${row['total_value']:>10,.2f}  (Qty: {row['total_quantity']:>6.0f}, Invoices: {row['invoice_count']:>3d})"
            if row['hts_code']:
                line += f"  HTS: {row['hts_code']}"
            self.stats_text.insert(tk.END, line + "\n")

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

    def _show_parts_menu(self, event):
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

        # Get part summary
        part = self.db.get_part_summary(part_number)
        if not part:
            return

        # Create details window
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

Material Composition (TariffMill Schema)
{'-' * 60}
Steel:              {part.get('steel_ratio', 0):.0f}%
Aluminum:           {part.get('aluminum_ratio', 0):.0f}%
Non-Steel:          {part.get('non_steel_ratio', 0):.0f}%

Timeline
{'-' * 60}
Last Updated:       {part.get('last_updated', 'N/A')}
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
        current_hts = item['values'][1]

        # Dialog to enter HTS code
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
                self._refresh_data()
                dialog.destroy()

        ttk.Button(dialog, text="Save", command=save_hts).pack(pady=10)

    def _view_part_history(self):
        """View history for selected part."""
        selection = self.parts_tree.selection()
        if not selection:
            return

        item = self.parts_tree.item(selection[0])
        part_number = item['values'][0]

        # Clear history tree
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Load history
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
        self.root.nametowidget('.!notebook').select(1)
        self.status_var.set(f"Showing {len(history)} occurrences of {part_number}")

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

    def _load_hts(self):
        """Load parts/HTS codes from Excel or CSV file."""
        filepath = filedialog.askopenfilename(
            title="Select Parts/HTS Mapping File",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir="reports"
        )

        if filepath:
            self._import_hts_file(Path(filepath))

    def _generate_reports(self):
        """Generate comprehensive parts reports."""
        folder = filedialog.askdirectory(title="Select Output Folder", initialdir="reports")

        if folder:
            create_parts_report(self.db, Path(folder))
            messagebox.showinfo("Success", f"Reports generated in {folder}")

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About Parts Database Viewer",
            "Parts Database Viewer - OCRMill\n\n"
            "Manage parts, HTS codes, and manufacturer information.\n\n"
            "Version 1.0"
        )

    def _show_manufacturers_dialog(self):
        """Show the manufacturers/MID management dialog."""
        ManufacturersDialog(self.root, self.db)


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
        # Top frame with buttons
        btn_frame = ttk.Frame(self.dialog, padding="5")
        btn_frame.pack(fill="x", side="top")

        ttk.Button(btn_frame, text="Add New", command=self._add_new).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._load_data).pack(side="left", padx=2)

        # Search
        ttk.Label(btn_frame, text="Search:").pack(side="left", padx=(20, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._search())
        search_entry = ttk.Entry(btn_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=2)

        # Treeview
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

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.dialog, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

        # Close button
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

        # Company Name
        ttk.Label(form_frame, text="Company Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.company_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.company_var, width=40).grid(row=0, column=1, pady=5, sticky="ew")

        # Country
        ttk.Label(form_frame, text="Country:").grid(row=1, column=0, sticky="w", pady=5)
        self.country_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.country_var, width=40).grid(row=1, column=1, pady=5, sticky="ew")

        # MID
        ttk.Label(form_frame, text="MID:").grid(row=2, column=0, sticky="w", pady=5)
        self.mid_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.mid_var, width=40).grid(row=2, column=1, pady=5, sticky="ew")

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=3, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(form_frame, width=40, height=4)
        self.notes_text.grid(row=3, column=1, pady=5, sticky="ew")

        form_frame.grid_columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(self.dialog, padding="10")
        btn_frame.pack(fill="x", side="bottom")

        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right", padx=5)

    def _load_data(self):
        """Load existing manufacturer data."""
        # Get manufacturer from database
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


def main():
    """Main entry point."""
    # Use TkinterDnD for drag-and-drop support if available
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = PartsViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
