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

        # Parts master table - TariffMill compatible schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parts_master (
                part_number TEXT PRIMARY KEY,
                description TEXT,
                hts_code TEXT,
                country_origin TEXT,
                mid TEXT,
                client_code TEXT,
                steel_ratio REAL DEFAULT 0,
                aluminum_ratio REAL DEFAULT 0,
                non_steel_ratio REAL DEFAULT 0,
                qty_unit TEXT DEFAULT 'NO',
                sec301_exclusion_tariff TEXT,
                last_updated TEXT,
                notes TEXT
            )
        """)

        # Note: Schema now matches TariffMill's parts_master table
        # Migration from old OCRMill schema handled by migrate_to_tariffmill_schema.py

        # Add FSC certification column if it doesn't exist (migration)
        cursor.execute("PRAGMA table_info(parts_master)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'fsc_certified' not in columns:
            cursor.execute("ALTER TABLE parts_master ADD COLUMN fsc_certified TEXT")
        if 'fsc_certificate_code' not in columns:
            cursor.execute("ALTER TABLE parts_master ADD COLUMN fsc_certificate_code TEXT")

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
                steel_ratio REAL,
                steel_kg REAL,
                steel_value REAL,
                aluminum_ratio REAL,
                aluminum_kg REAL,
                aluminum_value REAL,
                net_weight REAL,
                ncm_code TEXT,
                hts_code TEXT,
                processed_date TEXT,
                source_file TEXT,
                mid TEXT,
                client_code TEXT,
                FOREIGN KEY (part_number) REFERENCES parts_master(part_number)
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
                FOREIGN KEY (part_number) REFERENCES parts_master(part_number)
            )
        """)

        # Manufacturers/MID table (legacy)
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

        # MID table (TariffMill-compatible format)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mid_table (
                mid TEXT PRIMARY KEY,
                manufacturer_name TEXT,
                customer_id TEXT,
                related_parties TEXT DEFAULT 'N',
                created_date TEXT,
                modified_date TEXT
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_part ON part_occurrences(part_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_invoice ON part_occurrences(invoice_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_part_occurrences_project ON part_occurrences(project_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manufacturers_mid ON manufacturers(mid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mid_table_manufacturer ON mid_table(manufacturer_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mid_table_customer ON mid_table(customer_id)")

        # App config table for licensing and settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                modified_date TEXT
            )
        """)

        # Billing records table (matches TariffMill schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_number TEXT,
                export_date TEXT,
                export_time TEXT,
                file_name TEXT,
                line_count INTEGER,
                total_value REAL,
                hts_codes_used TEXT,
                user_name TEXT,
                machine_id TEXT,
                processing_time_ms INTEGER,
                invoice_sent INTEGER DEFAULT 0,
                invoice_month TEXT,
                created_date TEXT
            )
        """)

        # Usage statistics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                event_data TEXT,
                user_name TEXT,
                timestamp TEXT
            )
        """)

        # Export audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                event_date TEXT,
                event_time TEXT,
                file_number TEXT,
                user_name TEXT,
                machine_id TEXT,
                success INTEGER,
                failure_reason TEXT,
                billing_recorded INTEGER DEFAULT 0
            )
        """)

        # Billing duplicate attempts tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_duplicate_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_number TEXT,
                original_export_date TEXT,
                attempt_date TEXT,
                days_since_original INTEGER,
                user_name TEXT,
                machine_id TEXT
            )
        """)

        # Processing history table for admin audit
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_date TEXT,
                file_name TEXT,
                template_used TEXT,
                items_extracted INTEGER DEFAULT 0,
                status TEXT,
                user_name TEXT,
                error_message TEXT,
                processing_time_ms INTEGER
            )
        """)

        # File number divisions table for managing file number patterns per division
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_number_divisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                division_name TEXT NOT NULL,
                prefix TEXT NOT NULL,
                total_length INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for billing/stats tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_file_number ON billing_records(file_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_export_date ON billing_records(export_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_billing_invoice_month ON billing_records(invoice_month)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_stats_event_type ON usage_statistics(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_stats_timestamp ON usage_statistics(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_file_number ON export_audit_log(file_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_history_date ON processing_history(process_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_history_user ON processing_history(user_name)")

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
                - steel_ratio, steel_kg, steel_value
                - aluminum_ratio, aluminum_kg, aluminum_value
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

            # Check for FSC certification in description
            description = part_data.get('description', '')
            if 'FSC 100%' in description or 'FSC100%' in description.replace(' ', ''):
                part_data['fsc_certified'] = 'FSC 100%'
                part_data['fsc_certificate_code'] = 'PBN-COC-065387'
            elif 'FSC' in description.upper():
                # Generic FSC mention without 100%
                part_data['fsc_certified'] = 'FSC'

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
                    steel_ratio, steel_kg, steel_value,
                    aluminum_ratio, aluminum_kg, aluminum_value,
                    net_weight, ncm_code, hts_code, processed_date, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part_number,
                part_data.get('invoice_number'),
                part_data.get('project_number'),
                part_data.get('quantity'),
                part_data.get('total_price'),
                unit_price,
                part_data.get('steel_ratio'),
                part_data.get('steel_kg'),
                part_data.get('steel_value'),
                part_data.get('aluminum_ratio'),
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
        """Update the parts master table with latest occurrence data."""
        cursor = self.conn.cursor()

        # Check if part exists
        cursor.execute("SELECT part_number FROM parts_master WHERE part_number = ?", (part_number,))
        exists = cursor.fetchone() is not None

        # Get latest material percentages from most recent occurrence
        cursor.execute("""
            SELECT
                steel_ratio,
                aluminum_ratio,
                processed_date
            FROM part_occurrences
            WHERE part_number = ?
            ORDER BY processed_date DESC
            LIMIT 1
        """, (part_number,))

        latest = cursor.fetchone()

        if exists:
            # Update existing part with latest occurrence data
            # Only update fields if new data is provided (not NULL and not empty string)
            # HTS_CODE is NEVER updated from PDF - database is master source of truth
            def clean_value(value):
                """Return value if non-empty, otherwise None to prevent overwriting."""
                if value is None:
                    return None
                str_val = str(value).strip()
                return str_val if str_val else None

            new_mid = clean_value(part_data.get('mid'))
            new_country = clean_value(part_data.get('country_origin'))
            new_client = clean_value(part_data.get('client_code'))
            new_fsc_cert = clean_value(part_data.get('fsc_certified'))
            new_fsc_code = clean_value(part_data.get('fsc_certificate_code'))
            new_description = clean_value(part_data.get('description'))

            cursor.execute("""
                UPDATE parts_master SET
                    description = COALESCE(?, description),
                    steel_ratio = COALESCE(?, steel_ratio),
                    aluminum_ratio = COALESCE(?, aluminum_ratio),
                    mid = COALESCE(?, mid),
                    country_origin = COALESCE(?, country_origin),
                    client_code = COALESCE(?, client_code),
                    fsc_certified = COALESCE(?, fsc_certified),
                    fsc_certificate_code = COALESCE(?, fsc_certificate_code),
                    last_updated = ?
                WHERE part_number = ?
            """, (
                new_description,
                latest['steel_ratio'] if latest else part_data.get('steel_ratio'),
                latest['aluminum_ratio'] if latest else part_data.get('aluminum_ratio'),
                new_mid,
                new_country,
                new_client,
                new_fsc_cert,
                new_fsc_code,
                datetime.now().isoformat(),
                part_number
            ))
        else:
            # Insert new part
            cursor.execute("""
                INSERT INTO parts_master (
                    part_number, description, hts_code, steel_ratio, aluminum_ratio,
                    mid, country_origin, client_code, fsc_certified, fsc_certificate_code, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part_number,
                part_data.get('description'),
                part_data.get('hts_code'),
                latest['steel_ratio'] if latest else part_data.get('steel_ratio'),
                latest['aluminum_ratio'] if latest else part_data.get('aluminum_ratio'),
                part_data.get('mid'),
                part_data.get('country_origin'),
                part_data.get('client_code'),
                part_data.get('fsc_certified'),
                part_data.get('fsc_certificate_code'),
                datetime.now().isoformat()
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
            'steel_ratio': ['steel_ratio', 'steel ratio', 'steel_ratio', 'steel pct', 'steel_%', 'steel %', 'steel_percent', 'steel'],
            'aluminum_ratio': ['aluminum_ratio', 'aluminum ratio', 'aluminum_ratio', 'aluminum pct', 'aluminum_%', 'aluminum %', 'aluminum_percent', 'aluminum', 'aluminium_pct', 'aluminium'],
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
                    cursor.execute("SELECT part_number FROM parts_master WHERE part_number = ?", (part_number,))
                    exists = cursor.fetchone() is not None

                    # Prepare data - support both old and new column formats
                    hts_code = str(row.get('hts_code', '')) if pd.notna(row.get('hts_code')) else None
                    country_origin = str(row.get('country_origin', '')) if pd.notna(row.get('country_origin')) else None
                    steel_ratio = float(row.get('steel_ratio')) if pd.notna(row.get('steel_ratio')) else None
                    aluminum_ratio = float(row.get('aluminum_ratio')) if pd.notna(row.get('aluminum_ratio')) else None
                    copper_pct = float(row.get('copper_pct')) if pd.notna(row.get('copper_pct')) else None
                    wood_pct = float(row.get('wood_pct')) if pd.notna(row.get('wood_pct')) else None
                    auto_pct = float(row.get('auto_pct')) if pd.notna(row.get('auto_pct')) else None
                    non_steel_ratio = float(row.get('non_steel_ratio')) if pd.notna(row.get('non_steel_ratio')) else None
                    qty_unit = str(row.get('qty_unit', 'NO')) if pd.notna(row.get('qty_unit')) else 'NO'
                    sec301 = str(row.get('sec301_exclusion_tariff', '')) if pd.notna(row.get('sec301_exclusion_tariff')) else None
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
                        if country_origin and country_origin != 'nan':
                            updates.append("country_origin = ?")
                            params.append(country_origin)
                        if steel_ratio is not None:
                            updates.append("steel_ratio = ?")
                            params.append(steel_ratio)
                        if aluminum_ratio is not None:
                            updates.append("aluminum_ratio = ?")
                            params.append(aluminum_ratio)
                        if non_steel_ratio is not None:
                            updates.append("non_steel_ratio = ?")
                            params.append(non_steel_ratio)
                        # Note: copper_pct, wood_pct, auto_pct not in TariffMill schema - ignored if present in CSV
                        if qty_unit and qty_unit != 'nan':
                            updates.append("qty_unit = ?")
                            params.append(qty_unit)
                        if sec301 and sec301 != 'nan':
                            updates.append("sec301_exclusion_tariff = ?")
                            params.append(sec301)
                        if mid and mid != 'nan':
                            updates.append("mid = ?")
                            params.append(mid)
                        if client_code and client_code != 'nan':
                            updates.append("client_code = ?")
                            params.append(client_code)
                        if description and description != 'nan':
                            updates.append("description = COALESCE(description, ?)")
                            params.append(description)

                        updates.append("last_updated = ?")
                        params.append(datetime.now().isoformat())

                        if updates:
                            params.append(part_number)
                            cursor.execute(f"UPDATE parts_master SET {', '.join(updates)} WHERE part_number = ?", params)
                            updated += 1

                    elif not exists:
                        # Insert new part (TariffMill schema - no copper/wood/auto columns)
                        cursor.execute("""
                            INSERT INTO parts_master (part_number, description, hts_code, country_origin,
                                             steel_ratio, aluminum_ratio, non_steel_ratio,
                                             qty_unit, sec301_exclusion_tariff, mid, client_code, last_updated)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            part_number,
                            description if description and description != 'nan' else None,
                            hts_code if hts_code and hts_code != 'nan' else None,
                            country_origin if country_origin and country_origin != 'nan' else None,
                            steel_ratio,
                            aluminum_ratio,
                            non_steel_ratio,
                            qty_unit,
                            sec301 if sec301 and sec301 != 'nan' else None,
                            mid if mid and mid != 'nan' else None,
                            client_code if client_code and client_code != 'nan' else None,
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
        cursor.execute("SELECT hts_code FROM parts_master WHERE part_number = ? AND hts_code IS NOT NULL", (part_number,))
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
        cursor.execute("SELECT * FROM parts_master WHERE part_number = ?", (part_number,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def get_all_parts(self, order_by: str = "last_updated DESC") -> List[Dict]:
        """Get all parts in the database."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM parts_master ORDER BY {order_by}")
        return [dict(row) for row in cursor.fetchall()]

    def get_parts_by_project(self, project_number: str) -> List[Dict]:
        """Get all unique parts used in a specific project."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p.*, po.quantity, po.total_price
            FROM parts_master p
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
            # Export parts master table with all current columns
            cursor.execute("""
                SELECT
                    part_number,
                    description,
                    hts_code,
                    country_origin,
                    mid,
                    client_code,
                    steel_ratio,
                    aluminum_ratio,
                    non_steel_ratio,
                    qty_unit,
                    sec301_exclusion_tariff,
                    last_updated
                FROM parts_master
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

        cursor.execute("SELECT COUNT(*) as count FROM parts_master")
        total_parts = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM part_occurrences")
        total_occurrences = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(DISTINCT invoice_number) as count FROM part_occurrences")
        total_invoices = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(DISTINCT project_number) as count FROM part_occurrences")
        total_projects = cursor.fetchone()['count']

        # Calculate total value from occurrences (parts table no longer tracks this)
        cursor.execute("SELECT SUM(total_price) as total FROM part_occurrences")
        total_value = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT COUNT(*) as count FROM parts_master WHERE hts_code IS NOT NULL")
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
            SELECT * FROM parts_master
            WHERE part_number LIKE ? OR description LIKE ?
            ORDER BY part_number
        """, (f'%{search_term}%', f'%{search_term}%'))
        return [dict(row) for row in cursor.fetchall()]

    def update_part_description(self, part_number: str, description: str):
        """Update description for a part."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE parts_master SET description = ?
            WHERE part_number = ?
        """, (description, part_number))
        self.conn.commit()

    def update_part_hts(self, part_number: str, hts_code: str, hts_description: str = ""):
        """Manually update HTS code for a part (hts_description parameter kept for backward compatibility but not used)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE parts_master SET hts_code = ?, last_updated = ?
            WHERE part_number = ?
        """, (hts_code, datetime.now().isoformat(), part_number))
        self.conn.commit()

    # ==================== Section 232 Tariff Management ====================

    def is_section_232_tariff(self, hts_code: str, material_type: str = None) -> bool:
        """
        Check if an HTS code is subject to Section 232 tariffs.

        Args:
            hts_code: HTS code to check
            material_type: Optional material type to check ('Steel', 'Aluminum', 'Copper', 'Wood')

        Returns:
            True if HTS code is in Section 232 tariff list
        """
        cursor = self.conn.cursor()

        if material_type:
            # Case-insensitive comparison
            cursor.execute("""
                SELECT COUNT(*) FROM section_232_tariffs
                WHERE hts_code = ? AND LOWER(material) = LOWER(?)
            """, (hts_code, material_type))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM section_232_tariffs
                WHERE hts_code = ?
            """, (hts_code,))

        count = cursor.fetchone()[0]
        return count > 0

    def get_section_232_material_type(self, hts_code: str) -> Optional[str]:
        """
        Get the Section 232 material type for an HTS code.

        Args:
            hts_code: HTS code to look up

        Returns:
            Material type ('Steel', 'Aluminum', 'Copper', 'Wood') or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT material FROM section_232_tariffs
            WHERE hts_code = ?
            LIMIT 1
        """, (hts_code,))

        result = cursor.fetchone()
        return result[0] if result else None

    def get_section_232_details(self, hts_code: str) -> List[Dict]:
        """
        Get all Section 232 details for an HTS code (may have multiple materials).

        Args:
            hts_code: HTS code to look up

        Returns:
            List of tariff records for this HTS code
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM section_232_tariffs
            WHERE hts_code = ?
        """, (hts_code,))

        return [dict(row) for row in cursor.fetchall()]

    def get_all_section_232_tariffs(self, material_type: str = None) -> List[Dict]:
        """
        Get all Section 232 tariff codes.

        Args:
            material_type: Optional filter by material type ('Steel', 'Aluminum', 'Copper', 'Wood')

        Returns:
            List of tariff records
        """
        cursor = self.conn.cursor()

        if material_type:
            cursor.execute("""
                SELECT * FROM section_232_tariffs
                WHERE LOWER(material) = LOWER(?)
                ORDER BY hts_code
            """, (material_type,))
        else:
            cursor.execute("""
                SELECT * FROM section_232_tariffs
                ORDER BY material, hts_code
            """)

        return [dict(row) for row in cursor.fetchall()]

    def get_section_232_statistics(self) -> Dict[str, int]:
        """
        Get statistics about Section 232 tariff codes.

        Returns:
            Dictionary with counts by material type
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT material, COUNT(*)
            FROM section_232_tariffs
            GROUP BY material
        """)

        stats = {}
        for material, count in cursor.fetchall():
            stats[material] = count

        # Add total
        stats['total'] = sum(stats.values())

        return stats

    def get_section_232_declaration_code(self, hts_code: str, material_type: str = None) -> Optional[str]:
        """
        Get the declaration code required for an HTS code.

        Args:
            hts_code: HTS code to look up
            material_type: Optional material type filter

        Returns:
            Declaration code (e.g., '08 - MELT & POUR') or None
        """
        cursor = self.conn.cursor()

        if material_type:
            cursor.execute("""
                SELECT declaration_required FROM section_232_tariffs
                WHERE hts_code = ? AND LOWER(material) = LOWER(?)
                LIMIT 1
            """, (hts_code, material_type))
        else:
            cursor.execute("""
                SELECT declaration_required FROM section_232_tariffs
                WHERE hts_code = ?
                LIMIT 1
            """, (hts_code,))

        result = cursor.fetchone()
        return result[0] if result else None

    # ==================== Section 232 Actions Management ====================

    def get_section_232_action(self, tariff_no: str) -> Optional[Dict]:
        """
        Get Section 232 action details by tariff number.

        Args:
            tariff_no: Tariff number to look up (e.g., "99038187")

        Returns:
            Action record or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM section_232_actions
            WHERE tariff_no = ?
        """, (tariff_no,))

        result = cursor.fetchone()
        return dict(result) if result else None

    def get_section_232_actions_by_type(self, action_type: str) -> List[Dict]:
        """
        Get all Section 232 actions by type.

        Args:
            action_type: Action type to filter by (e.g., "232 STEEL", "232 ALUMINUM")

        Returns:
            List of action records
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM section_232_actions
            WHERE action = ?
            ORDER BY tariff_no
        """, (action_type,))

        return [dict(row) for row in cursor.fetchall()]

    def get_all_section_232_actions(self) -> List[Dict]:
        """
        Get all Section 232 action records.

        Returns:
            List of all action records
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM section_232_actions
            ORDER BY action, tariff_no
        """)

        return [dict(row) for row in cursor.fetchall()]

    def get_section_232_action_types(self) -> List[str]:
        """
        Get list of all unique Section 232 action types.

        Returns:
            List of action type strings
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT action FROM section_232_actions
            ORDER BY action
        """)

        return [row[0] for row in cursor.fetchall()]

    def get_section_232_actions_statistics(self) -> Dict[str, int]:
        """
        Get statistics about Section 232 actions.

        Returns:
            Dictionary with counts by action type
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT action, COUNT(*)
            FROM section_232_actions
            GROUP BY action
        """)

        stats = {}
        for action, count in cursor.fetchall():
            stats[action] = count

        # Add total
        stats['total'] = sum(stats.values())

        return stats

    def get_section_232_declaration_required(self, action_type: str) -> Optional[str]:
        """
        Get the typical declaration code required for an action type.

        Args:
            action_type: Action type (e.g., "232 STEEL")

        Returns:
            Declaration code (e.g., "08 MELT & POUR REQ") or None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT additional_declaration FROM section_232_actions
            WHERE action = ? AND additional_declaration IS NOT NULL
            LIMIT 1
        """, (action_type,))

        result = cursor.fetchone()
        return result[0] if result else None

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

    def import_manufacturers_from_excel(self, excel_path: str) -> tuple[int, int]:
        """
        Import manufacturers from Excel file.
        Expected columns: MANUFACTURER NAME, MID, CUSTOMER ID, RELATED
        Returns: (imported_count, updated_count)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for Excel import")

        df = pd.read_excel(excel_path)

        # Validate required columns
        required_cols = ['MANUFACTURER NAME', 'MID']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        imported = 0
        updated = 0
        cursor = self.conn.cursor()

        for _, row in df.iterrows():
            company_name = str(row['MANUFACTURER NAME']).strip()
            mid = str(row['MID']).strip() if pd.notna(row['MID']) else ''
            customer_id = str(row.get('CUSTOMER ID', '')).strip() if pd.notna(row.get('CUSTOMER ID')) else ''
            related = str(row.get('RELATED', '')).strip() if pd.notna(row.get('RELATED')) else ''

            if not company_name or company_name == 'nan':
                continue

            # Infer country from MID (first 2 letters) or manufacturer name
            country = ''

            # First try to get country from MID (first 2 letters)
            if mid and len(mid) >= 2:
                country = mid[:2].upper()

            # If no MID or invalid, infer from manufacturer name
            if not country or len(country) != 2:
                company_lower = company_name.lower()
                if 'czech' in company_lower or 'czech republic' in company_lower:
                    country = 'CZ'
                elif 'brazil' in company_lower or 'brasil' in company_lower:
                    country = 'BR'
                elif 'denmark' in company_lower or 'danish' in company_lower:
                    country = 'DK'
                elif 'usa' in company_lower or 'united states' in company_lower:
                    country = 'US'
                else:
                    country = ''

            # Build notes from CUSTOMER ID and RELATED
            notes_parts = []
            if customer_id and customer_id != 'nan':
                notes_parts.append(f"Customer: {customer_id}")
            if related and related != 'nan':
                notes_parts.append(f"Related: {related}")
            notes = '; '.join(notes_parts)

            # Check if manufacturer already exists
            cursor.execute("SELECT id FROM manufacturers WHERE company_name = ?", (company_name,))
            existing = cursor.fetchone()

            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE manufacturers
                    SET mid = ?, country = ?, notes = ?, modified_date = ?
                    WHERE id = ?
                """, (mid if mid and mid != 'nan' else None, country, notes, datetime.now().isoformat(), existing['id']))
                updated += 1
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO manufacturers (company_name, country, mid, notes, created_date, modified_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (company_name, country, mid if mid and mid != 'nan' else None, notes,
                      datetime.now().isoformat(), datetime.now().isoformat()))
                imported += 1

        self.conn.commit()
        return (imported, updated)

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

    # ========== MID Table Methods (TariffMill-compatible) ==========

    def get_all_mids(self) -> List[Dict]:
        """Get all MIDs from mid_table, ordered by manufacturer name."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT manufacturer_name, mid, customer_id, related_parties
            FROM mid_table
            ORDER BY manufacturer_name, mid
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_mid_by_code(self, mid: str) -> Optional[Dict]:
        """Get a single MID entry by its MID code."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM mid_table WHERE mid = ?", (mid,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def get_mid_by_manufacturer_name(self, manufacturer_name: str) -> Optional[Dict]:
        """
        Get MID entry by manufacturer name (case-insensitive partial match).
        Handles accented characters by normalizing to ASCII.
        Returns the first/best match if multiple exist.

        This is the new method that uses mid_table instead of manufacturers table.
        """
        if not manufacturer_name:
            return None

        import unicodedata
        def normalize(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn'
            ).lower()

        normalized_search = normalize(manufacturer_name)

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM mid_table")

        candidates = []
        for row in cursor.fetchall():
            db_name = row['manufacturer_name'] or ''
            normalized_db = normalize(db_name)

            # Exact match - highest priority
            if normalized_db == normalized_search:
                return dict(row)

            # Check if either contains the other
            if normalized_search in normalized_db or normalized_db in normalized_search:
                score = min(len(normalized_search), len(normalized_db)) / max(len(normalized_search), len(normalized_db)) if normalized_db else 0
                candidates.append((score, row))

        # Return best scoring candidate
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return dict(candidates[0][1])

        return None

    def add_mid(self, mid: str, manufacturer_name: str = "", customer_id: str = "",
                related_parties: str = "N") -> bool:
        """Add a new MID entry. Returns True if successful."""
        if not mid:
            return False
        try:
            now = datetime.now().isoformat()
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO mid_table
                (mid, manufacturer_name, customer_id, related_parties, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, manufacturer_name, customer_id, related_parties, now, now))
            self.conn.commit()
            return True
        except Exception:
            return False

    def update_mid(self, mid: str, manufacturer_name: str = "", customer_id: str = "",
                   related_parties: str = "N") -> bool:
        """Update an existing MID entry. Returns True if successful."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE mid_table
                SET manufacturer_name = ?, customer_id = ?, related_parties = ?, modified_date = ?
                WHERE mid = ?
            """, (manufacturer_name, customer_id, related_parties, datetime.now().isoformat(), mid))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def delete_mid(self, mid: str) -> bool:
        """Delete a MID entry. Returns True if successful."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM mid_table WHERE mid = ?", (mid,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def clear_all_mids(self) -> int:
        """Delete all MIDs from mid_table. Returns count of deleted rows."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM mid_table")
        self.conn.commit()
        return cursor.rowcount

    def save_mids_batch(self, mids: List[Dict]) -> int:
        """
        Save a batch of MIDs, replacing all existing data.
        Each dict should have: mid, manufacturer_name, customer_id, related_parties
        Returns the number of records saved.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM mid_table")

        saved = 0
        now = datetime.now().isoformat()
        for entry in mids:
            mid = entry.get('mid', '').strip()
            if not mid:
                continue
            cursor.execute("""
                INSERT OR REPLACE INTO mid_table
                (mid, manufacturer_name, customer_id, related_parties, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                mid,
                entry.get('manufacturer_name', '').strip(),
                entry.get('customer_id', '').strip(),
                entry.get('related_parties', 'N').strip().upper(),
                now, now
            ))
            saved += 1

        self.conn.commit()
        return saved

    def search_mids(self, customer_filter: str = "", mid_filter: str = "",
                    manufacturer_filter: str = "") -> List[Dict]:
        """Search MIDs with optional filters for customer ID, MID, and manufacturer."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT manufacturer_name, mid, customer_id, related_parties
            FROM mid_table
            ORDER BY manufacturer_name, mid
        """)

        results = []
        customer_filter = customer_filter.upper()
        mid_filter = mid_filter.upper()
        manufacturer_filter = manufacturer_filter.upper()

        for row in cursor.fetchall():
            row_dict = dict(row)
            manufacturer = (row_dict.get('manufacturer_name') or '').upper()
            mid = (row_dict.get('mid') or '').upper()
            customer_id = (row_dict.get('customer_id') or '').upper()

            # Apply filters
            if customer_filter and customer_filter not in customer_id:
                continue
            if mid_filter and mid_filter not in mid:
                continue
            if manufacturer_filter and manufacturer_filter not in manufacturer:
                continue

            results.append(row_dict)

        return results

    def import_mids_from_file(self, file_path: str, append_mode: bool = True) -> Tuple[int, int]:
        """
        Import MIDs from Excel/CSV file (TariffMill format).
        Expected columns: Manufacturer Name, MID, Customer ID, Related Parties (Y/N)

        Args:
            file_path: Path to Excel or CSV file
            append_mode: If True, append to existing; if False, replace all

        Returns: (imported_count, skipped_count)
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for file import")

        # Read file
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False)

        df = df.fillna("").rename(columns=str.strip)

        # Map column names (case-insensitive)
        col_map = {}
        for col in df.columns:
            col_lower = col.lower().replace('_', ' ').replace('-', ' ')
            if 'manufacturer' in col_lower and 'name' in col_lower:
                col_map[col] = 'manufacturer_name'
            elif col_lower == 'mid' or col_lower == 'manufacturer id':
                col_map[col] = 'mid'
            elif 'customer' in col_lower and 'id' in col_lower:
                col_map[col] = 'customer_id'
            elif 'related' in col_lower or 'parties' in col_lower:
                col_map[col] = 'related_parties'

        df = df.rename(columns=col_map)

        # Check for required MID column
        if 'mid' not in df.columns:
            raise ValueError("File must contain a 'MID' column.")

        # Get existing MIDs if in append mode
        existing_mids = set()
        if append_mode:
            for entry in self.get_all_mids():
                existing_mids.add(entry.get('mid', '').strip().upper())
        else:
            self.clear_all_mids()

        imported = 0
        skipped = 0
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()

        for _, row in df.iterrows():
            mid = str(row.get('mid', '')).strip()
            if not mid:
                continue

            # Skip duplicates in append mode
            if mid.upper() in existing_mids:
                skipped += 1
                continue

            manufacturer_name = str(row.get('manufacturer_name', '')).strip()
            customer_id = str(row.get('customer_id', '')).strip()
            related_parties = str(row.get('related_parties', 'N')).strip().upper()
            if related_parties not in ('Y', 'N'):
                related_parties = 'N'

            cursor.execute("""
                INSERT OR REPLACE INTO mid_table
                (mid, manufacturer_name, customer_id, related_parties, created_date, modified_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mid, manufacturer_name, customer_id, related_parties, now, now))
            imported += 1
            existing_mids.add(mid.upper())

        self.conn.commit()
        return (imported, skipped)

    def export_mids_to_excel(self, file_path: str) -> int:
        """
        Export all MIDs to Excel file.
        Returns the number of records exported.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for Excel export")

        mids = self.get_all_mids()
        if not mids:
            return 0

        df = pd.DataFrame(mids)
        # Rename columns to match TariffMill format
        df = df.rename(columns={
            'manufacturer_name': 'Manufacturer Name',
            'mid': 'MID',
            'customer_id': 'Customer ID',
            'related_parties': 'Related Parties'
        })

        df.to_excel(file_path, index=False)
        return len(mids)

    # ========== App Config Methods ==========

    def get_app_config(self, key: str, default: str = None) -> Optional[str]:
        """Get a configuration value from app_config table."""
        cursor = self.conn.execute(
            "SELECT value FROM app_config WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else default

    def set_app_config(self, key: str, value: str) -> None:
        """Set a configuration value in app_config table."""
        from datetime import datetime
        self.conn.execute(
            """INSERT OR REPLACE INTO app_config (key, value, modified_date)
               VALUES (?, ?, ?)""",
            (key, value, datetime.now().isoformat())
        )
        self.conn.commit()

    def delete_app_config(self, key: str) -> None:
        """Delete a configuration value from app_config table."""
        self.conn.execute("DELETE FROM app_config WHERE key = ?", (key,))
        self.conn.commit()

    # ========== Billing Records Methods ==========

    def add_billing_record(self, file_number: str, file_name: str, line_count: int,
                          total_value: float, hts_codes_used: str, user_name: str,
                          machine_id: str, processing_time_ms: int) -> int:
        """Add a billing record. Returns the record ID."""
        from datetime import datetime
        now = datetime.now()
        cursor = self.conn.execute(
            """INSERT INTO billing_records
               (file_number, export_date, export_time, file_name, line_count,
                total_value, hts_codes_used, user_name, machine_id,
                processing_time_ms, invoice_sent, invoice_month, created_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (file_number, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
             file_name, line_count, total_value, hts_codes_used, user_name,
             machine_id, processing_time_ms, now.strftime('%Y-%m'), now.isoformat())
        )
        self.conn.commit()
        return cursor.lastrowid

    def is_file_already_billed(self, file_number: str) -> bool:
        """Check if a file number has already been billed."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM billing_records WHERE file_number = ?",
            (file_number,)
        )
        return cursor.fetchone()['count'] > 0

    def record_duplicate_attempt(self, file_number: str, user_name: str, machine_id: str) -> None:
        """Record an attempt to bill a duplicate file number."""
        from datetime import datetime
        now = datetime.now()
        self.conn.execute(
            """INSERT INTO billing_duplicate_attempts
               (file_number, attempt_date, attempt_time, user_name, machine_id)
               VALUES (?, ?, ?, ?, ?)""",
            (file_number, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
             user_name, machine_id)
        )
        self.conn.commit()

    def record_processing_history(self, file_name: str, template_used: str = None,
                                   items_extracted: int = 0, status: str = 'SUCCESS',
                                   user_name: str = None, error_message: str = None,
                                   processing_time_ms: int = None) -> None:
        """Record a PDF processing event in the processing history."""
        from datetime import datetime
        import getpass
        if not user_name:
            user_name = getpass.getuser()
        now = datetime.now()
        self.conn.execute(
            """INSERT INTO processing_history
               (process_date, file_name, template_used, items_extracted, status,
                user_name, error_message, processing_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (now.strftime('%Y-%m-%d %H:%M:%S'), file_name, template_used,
             items_extracted, status, user_name, error_message, processing_time_ms)
        )
        self.conn.commit()

    def get_billing_records(self, start_date: str = None, end_date: str = None,
                           invoice_month: str = None) -> List[Dict]:
        """Get billing records with optional date filtering."""
        query = "SELECT * FROM billing_records WHERE 1=1"
        params = []

        if start_date:
            query += " AND export_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND export_date <= ?"
            params.append(end_date)
        if invoice_month:
            query += " AND invoice_month = ?"
            params.append(invoice_month)

        query += " ORDER BY export_date DESC, export_time DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_monthly_billing_summary(self, year: int, month: int) -> Dict:
        """Get billing summary for a specific month."""
        invoice_month = f"{year:04d}-{month:02d}"
        cursor = self.conn.execute(
            """SELECT
                COUNT(*) as total_files,
                SUM(line_count) as total_lines,
                SUM(total_value) as total_value,
                COUNT(DISTINCT user_name) as unique_users
               FROM billing_records
               WHERE invoice_month = ?""",
            (invoice_month,)
        )
        row = cursor.fetchone()
        return {
            'invoice_month': invoice_month,
            'total_files': row['total_files'] or 0,
            'total_lines': row['total_lines'] or 0,
            'total_value': row['total_value'] or 0.0,
            'unique_users': row['unique_users'] or 0
        }

    def mark_invoiced(self, invoice_month: str) -> int:
        """Mark all records for a month as invoiced. Returns count updated."""
        cursor = self.conn.execute(
            """UPDATE billing_records SET invoice_sent = 1
               WHERE invoice_month = ? AND invoice_sent = 0""",
            (invoice_month,)
        )
        self.conn.commit()
        return cursor.rowcount

    # ========== Usage Statistics Methods ==========

    def track_event(self, event_type: str, event_data: str, user_name: str = None) -> None:
        """Track a usage event."""
        from datetime import datetime
        self.conn.execute(
            """INSERT INTO usage_statistics (event_type, event_data, user_name, timestamp)
               VALUES (?, ?, ?, ?)""",
            (event_type, event_data, user_name, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_usage_statistics(self, event_type: str = None, days: int = 30) -> List[Dict]:
        """Get usage statistics with optional filtering."""
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        query = "SELECT * FROM usage_statistics WHERE timestamp >= ?"
        params = [cutoff_date]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_event_counts(self, days: int = 30) -> Dict[str, int]:
        """Get counts by event type for the specified period."""
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.conn.execute(
            """SELECT event_type, COUNT(*) as count
               FROM usage_statistics
               WHERE timestamp >= ?
               GROUP BY event_type""",
            (cutoff_date,)
        )
        return {row['event_type']: row['count'] for row in cursor.fetchall()}

    # ========== Export Audit Log Methods ==========

    def log_export_event(self, event_type: str, file_number: str, user_name: str,
                        machine_id: str, success: bool, failure_reason: str = None) -> None:
        """Log an export event to the audit log."""
        from datetime import datetime
        now = datetime.now()
        self.conn.execute(
            """INSERT INTO export_audit_log
               (event_type, event_date, event_time, file_number, user_name,
                machine_id, success, failure_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_type, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
             file_number, user_name, machine_id, 1 if success else 0, failure_reason)
        )
        self.conn.commit()

    def get_audit_log(self, start_date: str = None, end_date: str = None,
                     event_type: str = None) -> List[Dict]:
        """Get export audit log with optional filtering."""
        query = "SELECT * FROM export_audit_log WHERE 1=1"
        params = []

        if start_date:
            query += " AND event_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND event_date <= ?"
            params.append(end_date)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY event_date DESC, event_time DESC"
        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

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
