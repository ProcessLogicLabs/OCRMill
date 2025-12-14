"""
Parts Database Manager for OCRMill
Tracks all parts processed through the invoice system with history, HTS codes, and material composition.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
from part_description_extractor import PartDescriptionExtractor


class PartsDatabase:
    """
    Manages a SQLite database of all parts processed through OCRMill.

    Features:
    - Automatic part registration from invoice processing
    - HTS code mapping and tracking
    - Material composition history (steel/aluminum percentages)
    - Invoice/project association tracking
    - Part usage statistics and reporting
    """

    def __init__(self, db_path: Path = Path("parts_database.db")):
        self.db_path = db_path
        self.conn = None
        self._lock = threading.Lock()
        self.description_extractor = PartDescriptionExtractor()
        self._initialize_database()

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        # Parts master table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                part_number TEXT PRIMARY KEY,
                description TEXT,
                hts_code TEXT,
                hts_description TEXT,
                first_seen_date TEXT,
                last_seen_date TEXT,
                total_quantity REAL DEFAULT 0,
                total_value REAL DEFAULT 0,
                invoice_count INTEGER DEFAULT 0,
                avg_steel_pct REAL,
                avg_aluminum_pct REAL,
                avg_net_weight REAL,
                mid TEXT,
                client_code TEXT,
                notes TEXT
            )
        """)

        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE parts ADD COLUMN mid TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE parts ADD COLUMN client_code TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Part occurrences - tracks each time a part appears on an invoice
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS part_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_number TEXT NOT NULL,
                invoice_number TEXT,
                project_number TEXT,
                quantity REAL,
                total_price REAL,
                unit_price REAL,
                steel_pct REAL,
                steel_kg REAL,
                steel_value REAL,
                aluminum_pct REAL,
                aluminum_kg REAL,
                aluminum_value REAL,
                net_weight REAL,
                ncm_code TEXT,
                hts_code TEXT,
                processed_date TEXT,
                source_file TEXT,
                mid TEXT,
                client_code TEXT,
                FOREIGN KEY (part_number) REFERENCES parts(part_number)
            )
        """)

        # Add new columns to part_occurrences if they don't exist
        try:
            cursor.execute("ALTER TABLE part_occurrences ADD COLUMN mid TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE part_occurrences ADD COLUMN client_code TEXT")
        except sqlite3.OperationalError:
            pass

        # HTS code mapping table (loaded from mmcite_hts.xlsx)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hts_codes (
                hts_code TEXT PRIMARY KEY,
                description TEXT,
                suggested TEXT,
                last_updated TEXT
            )
        """)

        # Part description keywords for fuzzy HTS matching
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS part_descriptions (
                part_number TEXT PRIMARY KEY,
                description_text TEXT,
                keywords TEXT,
                FOREIGN KEY (part_number) REFERENCES parts(part_number)
            )
        """)

        # Manufacturers/MID table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manufacturers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                country TEXT,
                mid TEXT UNIQUE,
                notes TEXT,
                created_date TEXT,
                modified_date TEXT
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_part ON part_occurrences(part_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_invoice ON part_occurrences(invoice_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_project ON part_occurrences(project_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manufacturers_mid ON manufacturers(mid)")

        self.conn.commit()

    def add_part_occurrence(self, part_data: Dict) -> bool:
        """
        Add a new part occurrence from invoice processing.

        Args:
            part_data: Dictionary containing part information:
                - part_number (required)
                - invoice_number
                - project_number
                - quantity
                - total_price
                - unit_price (optional)
                - steel_pct, steel_kg, steel_value
                - aluminum_pct, aluminum_kg, aluminum_value
                - net_weight
                - ncm_code
                - hts_code
                - source_file

        Returns:
            bool: True if successful
        """
        with self._lock:
            cursor = self.conn.cursor()

            part_number = part_data.get('part_number')
            if not part_number:
                return False

            # Extract description if not provided
            if not part_data.get('description'):
                part_data['description'] = self.description_extractor.extract_description(part_number)

            # Try to find HTS code if not provided
            if not part_data.get('hts_code'):
                # First try from description
                hts_code = self.description_extractor.find_hts_from_description(part_data['description'])

                # If not found, check database for existing HTS codes
                if not hts_code:
                    cursor = self.conn.cursor()
                    cursor.execute("SELECT * FROM hts_codes")
                    hts_database = [dict(row) for row in cursor.fetchall()]
                    hts_code = self.description_extractor.match_with_hts_database(
                        part_data['description'], hts_database
                    )

                if hts_code:
                    part_data['hts_code'] = hts_code

            # Calculate unit price if not provided
            unit_price = part_data.get('unit_price')
            if not unit_price and part_data.get('total_price') and part_data.get('quantity'):
                try:
                    unit_price = float(part_data['total_price']) / float(part_data['quantity'])
                except (ValueError, ZeroDivisionError):
                    unit_price = None

            # Insert occurrence
            cursor.execute("""
                INSERT INTO part_occurrences (
                    part_number, invoice_number, project_number, quantity, total_price, unit_price,
                    steel_pct, steel_kg, steel_value,
                    aluminum_pct, aluminum_kg, aluminum_value,
                    net_weight, ncm_code, hts_code, processed_date, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part_number,
                part_data.get('invoice_number'),
                part_data.get('project_number'),
                part_data.get('quantity'),
                part_data.get('total_price'),
                unit_price,
                part_data.get('steel_pct'),
                part_data.get('steel_kg'),
                part_data.get('steel_value'),
                part_data.get('aluminum_pct'),
                part_data.get('aluminum_kg'),
                part_data.get('aluminum_value'),
                part_data.get('net_weight'),
                part_data.get('ncm_code'),
                part_data.get('hts_code'),
                datetime.now().isoformat(),
                part_data.get('source_file')
            ))

            # Update or create part master record
            self._update_part_master(part_number, part_data)

            self.conn.commit()
            return True

    def _update_part_master(self, part_number: str, part_data: Dict):
        """Update the parts master table with aggregated data."""
        cursor = self.conn.cursor()

        # Check if part exists
        cursor.execute("SELECT part_number FROM parts WHERE part_number = ?", (part_number,))
        exists = cursor.fetchone() is not None

        # Calculate aggregates from all occurrences
        cursor.execute("""
            SELECT
                COUNT(*) as invoice_count,
                SUM(quantity) as total_quantity,
                SUM(total_price) as total_value,
                AVG(steel_pct) as avg_steel_pct,
                AVG(aluminum_pct) as avg_aluminum_pct,
                AVG(net_weight) as avg_net_weight,
                MIN(processed_date) as first_seen,
                MAX(processed_date) as last_seen
            FROM part_occurrences
            WHERE part_number = ?
        """, (part_number,))

        stats = cursor.fetchone()

        if exists:
            # Update existing part
            cursor.execute("""
                UPDATE parts SET
                    description = COALESCE(?, description),
                    last_seen_date = ?,
                    total_quantity = ?,
                    total_value = ?,
                    invoice_count = ?,
                    avg_steel_pct = ?,
                    avg_aluminum_pct = ?,
                    avg_net_weight = ?,
                    hts_code = COALESCE(?, hts_code)
                WHERE part_number = ?
            """, (
                part_data.get('description'),
                stats['last_seen'],
                stats['total_quantity'] or 0,
                stats['total_value'] or 0,
                stats['invoice_count'],
                stats['avg_steel_pct'],
                stats['avg_aluminum_pct'],
                stats['avg_net_weight'],
                part_data.get('hts_code'),
                part_number
            ))
        else:
            # Insert new part
            cursor.execute("""
                INSERT INTO parts (
                    part_number, description, hts_code, first_seen_date, last_seen_date,
                    total_quantity, total_value, invoice_count,
                    avg_steel_pct, avg_aluminum_pct, avg_net_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part_number,
                part_data.get('description'),
                part_data.get('hts_code'),
                stats['first_seen'],
                stats['last_seen'],
                stats['total_quantity'] or 0,
                stats['total_value'] or 0,
                stats['invoice_count'],
                stats['avg_steel_pct'],
                stats['avg_aluminum_pct'],
                stats['avg_net_weight']
            ))

    def load_hts_mapping(self, xlsx_path: Path):
        """
        Load HTS code mapping from Excel file.

        Args:
            xlsx_path: Path to mmcite_hts.xlsx file
        """
        try:
            df = pd.read_excel(xlsx_path)
            cursor = self.conn.cursor()

            # Clear existing mappings
            cursor.execute("DELETE FROM hts_codes")

            # Track seen HTS codes to handle duplicates
            seen_hts = set()

            # Insert new mappings
            for _, row in df.iterrows():
                hts_code = str(row.get('HTS', ''))

                # Skip duplicates
                if hts_code in seen_hts or not hts_code:
                    continue

                seen_hts.add(hts_code)

                cursor.execute("""
                    INSERT INTO hts_codes (hts_code, description, suggested, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (
                    hts_code,
                    str(row.get('DESCRIPTION', '')),
                    str(row.get('SUGGESTED', '')),
                    datetime.now().isoformat()
                ))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error loading HTS mapping: {e}")
            return False

    def import_parts_list(self, file_path: Path, update_existing: bool = True) -> Tuple[int, int, List[str]]:
        """
        Import parts from CSV or Excel file with flexible column mapping.

        Supports various column names and formats from different importers.

        Args:
            file_path: Path to CSV or Excel file
            update_existing: If True, update existing parts with new data

        Returns:
            Tuple of (imported_count, updated_count, error_messages)
        """
        # Column name mappings - maps various possible names to our standard fields
        COLUMN_MAPPINGS = {
            'part_number': ['part_number', 'part number', 'partnumber', 'part_no', 'part no', 'partno', 'sku', 'item', 'item_number', 'product_code'],
            'invoice_number': ['invoice_number', 'invoice number', 'invoicenumber', 'invoice_no', 'invoice no', 'invoice', 'inv_number', 'inv_no'],
            'project_number': ['project_number', 'project number', 'projectnumber', 'project_no', 'project no', 'project', 'po_number', 'po number'],
            'hts_code': ['hts_code', 'hts code', 'htscode', 'hts', 'tariff_code', 'tariff code', 'hs_code', 'hs code', 'harmonized_code'],
            'steel_pct': ['steel_ratio', 'steel ratio', 'steel_pct', 'steel pct', 'steel_%', 'steel %', 'steel_percent', 'steel'],
            'aluminum_pct': ['aluminum_ratio', 'aluminum ratio', 'aluminum_pct', 'aluminum pct', 'aluminum_%', 'aluminum %', 'aluminum_percent', 'aluminum', 'aluminium_pct', 'aluminium'],
            'mid': ['mid', 'manufacturer_id', 'manufacturer id', 'mfg_id', 'mfr_id'],
            'client_code': ['client code', 'client_code', 'clientcode', 'client', 'customer_code', 'customer code', 'importer_code', 'importer'],
            'source_file': ['source_file', 'source file', 'sourcefile', 'file', 'filename', 'file_name'],
            'processed_date': ['processed_date', 'processed date', 'processeddate', 'date', 'import_date', 'created_date'],
            'description': ['description', 'desc', 'product_description', 'product description', 'item_description', 'name'],
            'quantity': ['quantity', 'qty', 'amount', 'units'],
            'total_price': ['total_price', 'total price', 'totalprice', 'price', 'value', 'total', 'amount'],
            'net_weight': ['net_weight', 'net weight', 'netweight', 'weight', 'weight_kg', 'net_wt'],
        }

        imported = 0
        updated = 0
        errors = []

        try:
            # Read file based on extension
            file_ext = file_path.suffix.lower()
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                errors.append(f"Unsupported file format: {file_ext}")
                return imported, updated, errors

            # Normalize column names (lowercase, strip whitespace)
            df.columns = [str(col).lower().strip() for col in df.columns]

            # Map columns to standard names
            column_map = {}
            for standard_name, possible_names in COLUMN_MAPPINGS.items():
                for col in df.columns:
                    if col in possible_names:
                        column_map[col] = standard_name
                        break

            # Rename columns
            df = df.rename(columns=column_map)

            # Check for required column
            if 'part_number' not in df.columns:
                errors.append("No part_number column found. File must have a column named: " +
                             ", ".join(COLUMN_MAPPINGS['part_number']))
                return imported, updated, errors

            cursor = self.conn.cursor()

            for idx, row in df.iterrows():
                try:
                    part_number = str(row.get('part_number', '')).strip()
                    if not part_number or part_number == 'nan':
                        continue

                    # Check if part exists
                    cursor.execute("SELECT part_number FROM parts WHERE part_number = ?", (part_number,))
                    exists = cursor.fetchone() is not None

                    # Prepare data
                    hts_code = str(row.get('hts_code', '')) if pd.notna(row.get('hts_code')) else None
                    steel_pct = float(row.get('steel_pct')) if pd.notna(row.get('steel_pct')) else None
                    aluminum_pct = float(row.get('aluminum_pct')) if pd.notna(row.get('aluminum_pct')) else None
                    mid = str(row.get('mid', '')) if pd.notna(row.get('mid')) else None
                    client_code = str(row.get('client_code', '')) if pd.notna(row.get('client_code')) else None
                    description = str(row.get('description', '')) if pd.notna(row.get('description')) else None

                    if exists and update_existing:
                        # Update existing part - only update non-null values
                        updates = []
                        params = []

                        if hts_code and hts_code != 'nan':
                            updates.append("hts_code = ?")
                            params.append(hts_code)
                        if steel_pct is not None:
                            updates.append("avg_steel_pct = ?")
                            params.append(steel_pct)
                        if aluminum_pct is not None:
                            updates.append("avg_aluminum_pct = ?")
                            params.append(aluminum_pct)
                        if mid and mid != 'nan':
                            updates.append("mid = ?")
                            params.append(mid)
                        if client_code and client_code != 'nan':
                            updates.append("client_code = ?")
                            params.append(client_code)
                        if description and description != 'nan':
                            updates.append("description = COALESCE(description, ?)")
                            params.append(description)

                        if updates:
                            params.append(part_number)
                            cursor.execute(f"UPDATE parts SET {', '.join(updates)} WHERE part_number = ?", params)
                            updated += 1

                    elif not exists:
                        # Insert new part
                        cursor.execute("""
                            INSERT INTO parts (part_number, description, hts_code, avg_steel_pct,
                                             avg_aluminum_pct, mid, client_code, first_seen_date, last_seen_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            part_number,
                            description if description and description != 'nan' else None,
                            hts_code if hts_code and hts_code != 'nan' else None,
                            steel_pct,
                            aluminum_pct,
                            mid if mid and mid != 'nan' else None,
                            client_code if client_code and client_code != 'nan' else None,
                            datetime.now().isoformat(),
                            datetime.now().isoformat()
                        ))
                        imported += 1

                except Exception as e:
                    errors.append(f"Row {idx + 1}: {str(e)}")
                    continue

            self.conn.commit()

        except Exception as e:
            errors.append(f"File error: {str(e)}")

        return imported, updated, errors

    def find_hts_code(self, part_number: str, description: str = "") -> Optional[str]:
        """
        Find HTS code for a part using fuzzy matching on description keywords.

        Args:
            part_number: Part number to look up
            description: Optional description text for matching

        Returns:
            HTS code if found, None otherwise
        """
        cursor = self.conn.cursor()

        # First check if part already has HTS code
        cursor.execute("SELECT hts_code FROM parts WHERE part_number = ? AND hts_code IS NOT NULL", (part_number,))
        result = cursor.fetchone()
        if result and result['hts_code']:
            return result['hts_code']

        # Try to match based on part number patterns or description keywords
        # Look for keyword matches in HTS descriptions
        if description:
            keywords = description.upper().split()
            for keyword in keywords:
                if len(keyword) > 3:  # Only meaningful keywords
                    cursor.execute("""
                        SELECT hts_code, description
                        FROM hts_codes
                        WHERE UPPER(description) LIKE ?
                        ORDER BY LENGTH(description)
                        LIMIT 1
                    """, (f'%{keyword}%',))
                    result = cursor.fetchone()
                    if result:
                        return result['hts_code']

        # Check for common part number prefixes
        part_prefixes = {
            'SL': '9403.20.0080',  # Seating
            'BTT': '9401.69.8031',  # Benches
            'STE': '9403.20.0082',  # Bicycle stands
            'LPU': '9403.20.0080',  # Planters
            'ND': '7308.90.6000',   # Bollards
            'PQA': '9403.20.0080',  # Tables
        }

        for prefix, hts in part_prefixes.items():
            if part_number.upper().startswith(prefix):
                return hts

        return None

    def get_part_history(self, part_number: str) -> List[Dict]:
        """Get complete history of a part across all invoices."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM part_occurrences
            WHERE part_number = ?
            ORDER BY processed_date DESC
        """, (part_number,))

        return [dict(row) for row in cursor.fetchall()]

    def get_part_summary(self, part_number: str) -> Optional[Dict]:
        """Get summary information for a part."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM parts WHERE part_number = ?", (part_number,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def get_all_parts(self, order_by: str = "last_seen_date DESC") -> List[Dict]:
        """Get all parts in the database."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM parts ORDER BY {order_by}")
        return [dict(row) for row in cursor.fetchall()]

    def get_parts_by_project(self, project_number: str) -> List[Dict]:
        """Get all unique parts used in a specific project."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p.*, po.quantity, po.total_price
            FROM parts p
            JOIN part_occurrences po ON p.part_number = po.part_number
            WHERE po.project_number = ?
            ORDER BY p.part_number
        """, (project_number,))
        return [dict(row) for row in cursor.fetchall()]

    def get_parts_by_invoice(self, invoice_number: str) -> List[Dict]:
        """Get all parts on a specific invoice."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM part_occurrences
            WHERE invoice_number = ?
            ORDER BY part_number
        """, (invoice_number,))
        return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, output_path: Path, include_history: bool = False):
        """
        Export parts database to CSV.

        Args:
            output_path: Path for output CSV file
            include_history: If True, export part_occurrences; if False, export parts summary
        """
        cursor = self.conn.cursor()

        if include_history:
            cursor.execute("SELECT * FROM part_occurrences ORDER BY processed_date DESC")
            rows = cursor.fetchall()
            if not rows:
                return False
            df = pd.DataFrame([dict(row) for row in rows])
        else:
            # Select specific columns, excluding hts_description, total_quantity, total_value, invoice_count, avg_net_weight
            # Rename avg_steel_pct to steel_pct and avg_aluminum_pct to aluminum_pct
            # Order: part_number, description, hts_code, mid, client_code, steel_pct, aluminum_pct, notes, first_seen_date, last_seen_date
            cursor.execute("""
                SELECT
                    part_number,
                    description,
                    hts_code,
                    mid,
                    client_code,
                    avg_steel_pct as steel_pct,
                    avg_aluminum_pct as aluminum_pct,
                    notes,
                    first_seen_date,
                    last_seen_date
                FROM parts
                ORDER BY part_number
            """)
            rows = cursor.fetchall()
            if not rows:
                return False
            df = pd.DataFrame([dict(row) for row in rows])

        df.to_csv(output_path, index=False)
        return True

    def get_statistics(self) -> Dict:
        """Get database statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM parts")
        total_parts = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM part_occurrences")
        total_occurrences = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(DISTINCT invoice_number) as count FROM part_occurrences")
        total_invoices = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(DISTINCT project_number) as count FROM part_occurrences")
        total_projects = cursor.fetchone()['count']

        cursor.execute("SELECT SUM(total_value) as total FROM parts")
        total_value = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM parts WHERE hts_code IS NOT NULL")
        parts_with_hts = cursor.fetchone()['count']

        return {
            'total_parts': total_parts,
            'total_occurrences': total_occurrences,
            'total_invoices': total_invoices,
            'total_projects': total_projects,
            'total_value': total_value,
            'parts_with_hts': parts_with_hts,
            'hts_coverage_pct': (parts_with_hts / total_parts * 100) if total_parts > 0 else 0
        }

    def search_parts(self, search_term: str) -> List[Dict]:
        """Search parts by part number or description."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM parts
            WHERE part_number LIKE ? OR description LIKE ?
            ORDER BY part_number
        """, (f'%{search_term}%', f'%{search_term}%'))
        return [dict(row) for row in cursor.fetchall()]

    def update_part_description(self, part_number: str, description: str):
        """Update description for a part."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE parts SET description = ?
            WHERE part_number = ?
        """, (description, part_number))
        self.conn.commit()

    def update_part_hts(self, part_number: str, hts_code: str, hts_description: str = ""):
        """Manually update HTS code for a part."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE parts SET hts_code = ?, hts_description = ?
            WHERE part_number = ?
        """, (hts_code, hts_description, part_number))
        self.conn.commit()

    # ==================== Manufacturer/MID Management ====================

    def add_manufacturer(self, company_name: str, country: str = "", mid: str = "", notes: str = "") -> int:
        """Add a new manufacturer/MID entry."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO manufacturers (company_name, country, mid, notes, created_date, modified_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company_name, country, mid if mid else None, notes, now, now))
        self.conn.commit()
        return cursor.lastrowid

    def update_manufacturer(self, id: int, company_name: str, country: str = "", mid: str = "", notes: str = ""):
        """Update an existing manufacturer."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE manufacturers
            SET company_name = ?, country = ?, mid = ?, notes = ?, modified_date = ?
            WHERE id = ?
        """, (company_name, country, mid if mid else None, notes, datetime.now().isoformat(), id))
        self.conn.commit()

    def delete_manufacturer(self, id: int):
        """Delete a manufacturer by ID."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM manufacturers WHERE id = ?", (id,))
        self.conn.commit()

    def get_all_manufacturers(self) -> List[Dict]:
        """Get all manufacturers."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM manufacturers ORDER BY company_name")
        return [dict(row) for row in cursor.fetchall()]

    def get_manufacturer_by_mid(self, mid: str) -> Optional[Dict]:
        """Get manufacturer by MID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM manufacturers WHERE mid = ?", (mid,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def search_manufacturers(self, search_term: str) -> List[Dict]:
        """Search manufacturers by name, country, or MID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM manufacturers
            WHERE company_name LIKE ? OR country LIKE ? OR mid LIKE ?
            ORDER BY company_name
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        return [dict(row) for row in cursor.fetchall()]

    def get_manufacturer_by_name(self, company_name: str) -> Optional[Dict]:
        """
        Get manufacturer by company name (case-insensitive partial match).
        Handles accented characters by normalizing to ASCII.
        Returns the first match if multiple exist.
        """
        if not company_name:
            return None

        # Normalize accented characters (é -> e, etc.)
        import unicodedata
        def normalize(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn'
            ).lower()

        normalized_search = normalize(company_name)

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM manufacturers")

        candidates = []
        for row in cursor.fetchall():
            db_name = row['company_name'] or ''
            normalized_db = normalize(db_name)

            # Exact match - highest priority
            if normalized_db == normalized_search:
                return dict(row)

            # Check if either contains the other
            if normalized_search in normalized_db or normalized_db in normalized_search:
                # Score by how close the lengths are (prefer closer matches)
                score = min(len(normalized_search), len(normalized_db)) / max(len(normalized_search), len(normalized_db))
                candidates.append((score, row))

        # Return best scoring candidate
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return dict(candidates[0][1])

        return None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_parts_report(db: PartsDatabase, output_folder: Path):
    """
    Generate comprehensive parts reports.

    Creates:
    - parts_master.csv: All parts with summary statistics
    - parts_history.csv: Complete occurrence history
    - parts_by_project.csv: Parts grouped by project
    - parts_statistics.txt: Database statistics
    """
    output_folder.mkdir(exist_ok=True)

    # Master parts list
    db.export_to_csv(output_folder / "parts_master.csv", include_history=False)

    # Complete history
    db.export_to_csv(output_folder / "parts_history.csv", include_history=True)

    # Statistics report
    stats = db.get_statistics()
    with open(output_folder / "parts_statistics.txt", 'w') as f:
        f.write("Parts Database Statistics\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total Unique Parts: {stats['total_parts']}\n")
        f.write(f"Total Part Occurrences: {stats['total_occurrences']}\n")
        f.write(f"Total Invoices Processed: {stats['total_invoices']}\n")
        f.write(f"Total Projects: {stats['total_projects']}\n")
        f.write(f"Total Value Processed: ${stats['total_value']:,.2f}\n")
        f.write(f"Parts with HTS Codes: {stats['parts_with_hts']} ({stats['hts_coverage_pct']:.1f}%)\n")

    print(f"Reports generated in {output_folder}")
