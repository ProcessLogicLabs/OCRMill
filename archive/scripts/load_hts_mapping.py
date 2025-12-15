"""
Load HTS Code Mapping into Parts Database
Reads mmcite_hts.xlsx and populates the HTS codes table.
"""

from pathlib import Path
from parts_database import PartsDatabase


def load_hts_mapping():
    """Load HTS code mapping from Excel file into database."""
    db = PartsDatabase()

    hts_file = Path("reports/mmcite_hts.xlsx")

    if not hts_file.exists():
        print(f"Error: HTS mapping file not found at {hts_file}")
        print("Please ensure mmcite_hts.xlsx is in the reports/ folder")
        return False

    print(f"Loading HTS codes from {hts_file}...")

    if db.load_hts_mapping(hts_file):
        print("[OK] HTS codes loaded successfully")

        # Show statistics
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM hts_codes")
        count = cursor.fetchone()['count']
        print(f"  Total HTS codes in database: {count}")

        # Show sample
        cursor.execute("SELECT * FROM hts_codes LIMIT 5")
        print("\n  Sample HTS codes:")
        for row in cursor.fetchall():
            print(f"    {row['hts_code']}: {row['description']}")

        return True
    else:
        print("[ERROR] Failed to load HTS codes")
        return False


if __name__ == "__main__":
    load_hts_mapping()
