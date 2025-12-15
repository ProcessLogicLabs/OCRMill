"""
Import Section 232 Actions into parts database.
This script creates a reference table for Section 232 action tariffs and requirements.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Paths
DB_PATH = Path("Resources/parts_database.db")
CSV_PATH = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\Resources\CBP_data\Section_232_Actions.csv")


def create_table():
    """Create section_232_actions table."""
    print("Creating section_232_actions table...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing table if it exists
    cursor.execute("DROP TABLE IF EXISTS section_232_actions")

    # Create new table
    cursor.execute("""
        CREATE TABLE section_232_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tariff_no TEXT NOT NULL,
            action TEXT NOT NULL,
            tariff_description TEXT,
            advalorem_rate TEXT,
            effective_date TEXT,
            expiration_date TEXT,
            specific_rate REAL,
            additional_declaration TEXT,
            note TEXT,
            link TEXT
        )
    """)

    # Create indexes for faster lookups
    cursor.execute("CREATE INDEX idx_232_actions_tariff ON section_232_actions(tariff_no)")
    cursor.execute("CREATE INDEX idx_232_actions_action ON section_232_actions(action)")

    conn.commit()
    conn.close()
    print("Table created successfully")


def import_actions():
    """Import Section 232 actions from CSV file."""
    print(f"\nImporting Section 232 actions from: {CSV_PATH.name}")

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
                INSERT INTO section_232_actions (
                    tariff_no, action, tariff_description, advalorem_rate,
                    effective_date, expiration_date, specific_rate,
                    additional_declaration, note, link
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row['Tariff No']),
                str(row['Action']),
                str(row['Tariff Description']) if pd.notna(row['Tariff Description']) else None,
                str(row['Advalorem Rate']) if pd.notna(row['Advalorem Rate']) else None,
                str(row['Effective Date']) if pd.notna(row['Effective Date']) else None,
                str(row['Expiration Date']) if pd.notna(row['Expiration Date']) else None,
                float(row['Specific Rate']) if pd.notna(row['Specific Rate']) else 0,
                str(row['Additional Declaration Required']) if pd.notna(row['Additional Declaration Required']) else None,
                str(row['Note']) if pd.notna(row['Note']) else None,
                str(row['Link']) if pd.notna(row['Link']) else None
            ))
            imported += 1
        except Exception as e:
            print(f"Error importing row: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nImport complete: {imported} actions imported")


def verify_import():
    """Verify the import was successful."""
    print("\nVerifying import...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM section_232_actions")
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")

    # Count by action type
    cursor.execute("SELECT action, COUNT(*) FROM section_232_actions GROUP BY action")
    print("\nBy action type:")
    for action, count in cursor.fetchall():
        print(f"  {action}: {count}")

    # Sample records
    print("\nSample steel actions:")
    cursor.execute("""
        SELECT tariff_no, tariff_description, advalorem_rate, additional_declaration
        FROM section_232_actions
        WHERE action = '232 STEEL'
        LIMIT 5
    """)
    for tariff_no, desc, rate, decl in cursor.fetchall():
        print(f"  {tariff_no}: {desc[:50]}... (Rate: {rate}, Decl: {decl})")

    print("\nSample aluminum actions:")
    cursor.execute("""
        SELECT tariff_no, tariff_description, advalorem_rate, additional_declaration
        FROM section_232_actions
        WHERE action = '232 ALUMINUM'
        LIMIT 5
    """)
    for tariff_no, desc, rate, decl in cursor.fetchall():
        print(f"  {tariff_no}: {desc[:50]}... (Rate: {rate}, Decl: {decl})")

    conn.close()
    print("\nVerification complete!")


def main():
    """Main execution."""
    print("=" * 80)
    print("Section 232 Actions Import Script")
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
    import_actions()

    # Verify
    verify_import()

    print("\n" + "=" * 80)
    print("Import complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
