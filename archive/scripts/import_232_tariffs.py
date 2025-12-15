"""
Import Section 232 tariff codes into parts database.
This script creates a reference table for Section 232 tariff application.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Paths
DB_PATH = Path("Resources/parts_database.db")
EXCEL_PATH = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\Resources\CBP_data\CBP_232_tariffs.xlsx")


def create_table():
    """Create section_232_tariffs table."""
    print("Creating section_232_tariffs table...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing table if it exists
    cursor.execute("DROP TABLE IF EXISTS section_232_tariffs")

    # Create new table
    cursor.execute("""
        CREATE TABLE section_232_tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hts_code TEXT NOT NULL,
            material_type TEXT NOT NULL,
            notes TEXT
        )
    """)

    # Create index for faster lookups
    cursor.execute("CREATE INDEX idx_232_hts ON section_232_tariffs(hts_code)")
    cursor.execute("CREATE INDEX idx_232_material ON section_232_tariffs(material_type)")

    conn.commit()
    conn.close()
    print("Table created successfully")


def import_tariffs():
    """Import tariff codes from Excel file."""
    print(f"\nImporting tariffs from: {EXCEL_PATH.name}")

    # Read Excel file
    df = pd.read_excel(EXCEL_PATH)
    print(f"Found {len(df)} rows in Excel file")
    print(f"Columns: {df.columns.tolist()}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Import steel tariffs
    steel_count = 0
    for hts_code in df['steel tariffs'].dropna():
        hts_code = str(hts_code).strip()
        if hts_code:
            cursor.execute("""
                INSERT INTO section_232_tariffs (hts_code, material_type, notes)
                VALUES (?, ?, ?)
            """, (hts_code, 'steel', 'Section 232 steel tariff'))
            steel_count += 1

    # Import aluminum tariffs
    aluminum_count = 0
    for hts_code in df['aluminum tariffs'].dropna():
        hts_code = str(hts_code).strip()
        if hts_code:
            cursor.execute("""
                INSERT INTO section_232_tariffs (hts_code, material_type, notes)
                VALUES (?, ?, ?)
            """, (hts_code, 'aluminum', 'Section 232 aluminum tariff'))
            aluminum_count += 1

    conn.commit()
    conn.close()

    print(f"\nImport complete:")
    print(f"  Steel tariffs: {steel_count}")
    print(f"  Aluminum tariffs: {aluminum_count}")
    print(f"  Total: {steel_count + aluminum_count}")


def verify_import():
    """Verify the import was successful."""
    print("\nVerifying import...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM section_232_tariffs")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")

    # Count by material type
    cursor.execute("SELECT material_type, COUNT(*) FROM section_232_tariffs GROUP BY material_type")
    for material, count in cursor.fetchall():
        print(f"  {material}: {count}")

    # Sample records
    print("\nSample records:")
    cursor.execute("SELECT hts_code, material_type FROM section_232_tariffs LIMIT 5")
    for hts, material in cursor.fetchall():
        print(f"  {hts} → {material}")

    conn.close()
    print("\nVerification complete!")


def main():
    """Main execution."""
    print("=" * 80)
    print("Section 232 Tariff Import Script")
    print("=" * 80)

    # Check if Excel file exists
    if not EXCEL_PATH.exists():
        print(f"ERROR: Excel file not found at {EXCEL_PATH}")
        return

    # Check if database exists
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    # Create table
    create_table()

    # Import data
    import_tariffs()

    # Verify
    verify_import()

    print("\n" + "=" * 80)
    print("Import complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
