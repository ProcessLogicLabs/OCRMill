"""
Rebuild parts database from parts_MMCITE.xlsx with new schema.
This script:
1. Backs up the existing database
2. Creates a new database with updated schema
3. Imports data from parts_MMCITE.xlsx
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil

# Paths
DB_PATH = Path("Resources/parts_database.db")
EXCEL_PATH = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\parts_MMCITE.xlsx")
BACKUP_PATH = Path(f"Resources/parts_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

def backup_database():
    """Create a backup of the existing database."""
    if DB_PATH.exists():
        print(f"Creating backup: {BACKUP_PATH.name}")
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print("Backup created successfully")
    else:
        print("No existing database to backup")

def create_new_schema():
    """Create new database schema matching parts_MMCITE.xlsx format."""
    print("\nCreating new database schema...")

    # Remove old database if it exists
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Create new database with updated schema
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE parts (
            part_number TEXT PRIMARY KEY,
            description TEXT,
            hts_code TEXT,
            country_origin TEXT,
            mid TEXT,
            client_code TEXT,
            steel_pct REAL DEFAULT 0,
            aluminum_pct REAL DEFAULT 0,
            copper_pct REAL DEFAULT 0,
            wood_pct REAL DEFAULT 0,
            auto_pct REAL DEFAULT 0,
            non_steel_pct REAL DEFAULT 0,
            qty_unit TEXT DEFAULT 'NO',
            sec301_exclusion_tariff TEXT,
            last_updated TEXT,
            notes TEXT
        )
    """)

    # Create index for faster lookups
    cursor.execute("CREATE INDEX idx_part_number ON parts(part_number)")
    cursor.execute("CREATE INDEX idx_hts_code ON parts(hts_code)")

    conn.commit()
    conn.close()
    print("New schema created successfully")

def import_excel_data():
    """Import data from parts_MMCITE.xlsx."""
    print("\nImporting data from Excel...")

    # Read Excel file
    df = pd.read_excel(EXCEL_PATH)
    print(f"Found {len(df)} parts in Excel file")

    # Rename columns to match database schema (remove spaces, convert to lowercase)
    column_mapping = {
        'steel_%': 'steel_pct',
        'aluminum_%': 'aluminum_pct',
        'copper_%': 'copper_pct',
        'wood_%': 'wood_pct',
        'auto_%': 'auto_pct',
        'non_steel_%': 'non_steel_pct',
        'Sec301_Exclusion_Tariff': 'sec301_exclusion_tariff'
    }
    df = df.rename(columns=column_mapping)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Import data (replace existing records)
    df.to_sql('parts', conn, if_exists='replace', index=False)

    conn.commit()
    conn.close()
    print(f"Successfully imported {len(df)} parts")

def verify_import():
    """Verify the import was successful."""
    print("\nVerifying import...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check total count
    cursor.execute("SELECT COUNT(*) FROM parts")
    count = cursor.fetchone()[0]
    print(f"Total parts in database: {count}")

    # Show sample records
    cursor.execute("SELECT part_number, description, hts_code, steel_pct, aluminum_pct FROM parts LIMIT 3")
    print("\nSample records:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} | HTS: {row[2]} | Steel: {row[3]}% | Aluminum: {row[4]}%")

    # Check column names
    cursor.execute("PRAGMA table_info(parts)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"\nDatabase columns: {', '.join(columns)}")

    conn.close()
    print("\nVerification complete!")

def main():
    """Main execution."""
    print("=" * 80)
    print("Parts Database Rebuild Script")
    print("=" * 80)

    # Check if Excel file exists
    if not EXCEL_PATH.exists():
        print(f"ERROR: Excel file not found at {EXCEL_PATH}")
        return

    # Backup existing database
    backup_database()

    # Create new schema
    create_new_schema()

    # Import data
    import_excel_data()

    # Verify
    verify_import()

    print("\n" + "=" * 80)
    print("Database rebuild complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
