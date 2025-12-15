"""
Import comprehensive Section 232 Tariffs from compiled CSV into parts database.
This replaces the previous section_232_tariffs table with a more detailed structure.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Paths
DB_PATH = Path("Resources/parts_database.db")
CSV_PATH = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\Resources\CBP_data\Section_232_Tariffs_Compiled.csv")


def create_table():
    """Create section_232_tariffs table with new schema."""
    print("Creating section_232_tariffs table with new schema...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing table if it exists
    cursor.execute("DROP TABLE IF EXISTS section_232_tariffs")

    # Create new table with comprehensive structure
    cursor.execute("""
        CREATE TABLE section_232_tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hts_code TEXT NOT NULL,
            material TEXT NOT NULL,
            classification TEXT,
            chapter INTEGER,
            chapter_description TEXT,
            declaration_required TEXT,
            notes TEXT
        )
    """)

    # Create indexes for faster lookups
    cursor.execute("CREATE INDEX idx_232_tariffs_hts ON section_232_tariffs(hts_code)")
    cursor.execute("CREATE INDEX idx_232_tariffs_material ON section_232_tariffs(material)")
    cursor.execute("CREATE INDEX idx_232_tariffs_classification ON section_232_tariffs(classification)")

    conn.commit()
    conn.close()
    print("Table created successfully")


def import_tariffs():
    """Import Section 232 tariffs from compiled CSV file."""
    print(f"\nImporting Section 232 tariffs from: {CSV_PATH.name}")

    # Read CSV file
    df = pd.read_csv(CSV_PATH)
    print(f"Found {len(df)} rows in CSV file")
    print(f"Columns: {df.columns.tolist()}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Import each row
    imported = 0
    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO section_232_tariffs (
                    hts_code, material, classification, chapter,
                    chapter_description, declaration_required, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row['HTS Code']),
                str(row['Material']),
                str(row['Classification']) if pd.notna(row['Classification']) else None,
                int(row['Chapter']) if pd.notna(row['Chapter']) else None,
                str(row['Chapter Description']) if pd.notna(row['Chapter Description']) else None,
                str(row['Declaration Required']) if pd.notna(row['Declaration Required']) else None,
                str(row['Notes']) if pd.notna(row['Notes']) else None
            ))
            imported += 1
        except Exception as e:
            print(f"Error importing row: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nImport complete: {imported} tariffs imported")


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
    cursor.execute("SELECT material, COUNT(*) FROM section_232_tariffs GROUP BY material")
    print("\nBy material type:")
    for material, count in cursor.fetchall():
        print(f"  {material}: {count}")

    # Count by classification (top 10)
    cursor.execute("""
        SELECT classification, COUNT(*)
        FROM section_232_tariffs
        GROUP BY classification
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    print("\nTop 10 classifications:")
    for classification, count in cursor.fetchall():
        print(f"  {classification}: {count}")

    # Sample records from each material type
    print("\nSample records:")
    for material in ['Steel', 'Aluminum', 'Copper', 'Wood']:
        cursor.execute("""
            SELECT hts_code, classification, declaration_required
            FROM section_232_tariffs
            WHERE material = ?
            LIMIT 3
        """, (material,))
        print(f"\n  {material}:")
        for hts, classification, decl in cursor.fetchall():
            print(f"    {hts}: {classification[:50]}... ({decl})")

    conn.close()
    print("\nVerification complete!")


def main():
    """Main execution."""
    print("=" * 80)
    print("Section 232 Comprehensive Tariff Import Script")
    print("=" * 80)

    # Check if CSV file exists
    if not CSV_PATH.exists():
        print(f"ERROR: CSV file not found at {CSV_PATH}")
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
