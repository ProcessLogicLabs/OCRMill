"""
Import Automotive Parts HTS codes into section_232_tariffs table.
These codes are added as Auto/232_Auto material type.
"""

import sqlite3
from pathlib import Path

# Paths
DB_PATH = Path("Resources/parts_database.db")
HTS_FILE = Path("auto_parts_hts_codes.txt")


def import_auto_hts():
    """Import automotive parts HTS codes into database."""
    print("=" * 80)
    print("Automotive Parts HTS Import Script")
    print("=" * 80)

    # Read HTS codes
    print(f"\nReading HTS codes from: {HTS_FILE}")
    with open(HTS_FILE, 'r') as f:
        hts_codes = [line.strip() for line in f if line.strip()]

    print(f"Found {len(hts_codes)} automotive HTS codes")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check existing Auto entries
    cursor.execute("""
        SELECT COUNT(*) FROM section_232_tariffs
        WHERE LOWER(material) = 'auto'
    """)
    existing_count = cursor.fetchone()[0]
    print(f"Existing Auto entries in database: {existing_count}")

    # Import each HTS code
    imported = 0
    skipped = 0
    updated = 0

    for hts_code in hts_codes:
        # Check if this HTS code already exists for Auto material
        cursor.execute("""
            SELECT COUNT(*) FROM section_232_tariffs
            WHERE hts_code = ? AND LOWER(material) = 'auto'
        """, (hts_code,))

        if cursor.fetchone()[0] > 0:
            skipped += 1
            continue

        # Check if this HTS exists for other materials
        cursor.execute("""
            SELECT material FROM section_232_tariffs
            WHERE hts_code = ? AND LOWER(material) != 'auto'
        """, (hts_code,))

        other_materials = cursor.fetchall()

        # Insert the Auto entry
        try:
            cursor.execute("""
                INSERT INTO section_232_tariffs (
                    hts_code, material, classification, chapter,
                    chapter_description, declaration_required, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                hts_code,
                'Auto',
                'Automotive Parts',
                None,  # Chapter not specified
                'Automotive and Transportation Equipment',
                '12 - AUTO PARTS',  # Placeholder declaration code
                'Section 232 Automotive Parts - U.S. note 33 to subchapter III of chapter 99'
            ))
            imported += 1

            if other_materials:
                materials = ', '.join([m[0] for m in other_materials])
                print(f"  Added Auto to {hts_code} (also: {materials})")

        except Exception as e:
            print(f"Error importing {hts_code}: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"\nImport complete:")
    print(f"  Imported: {imported}")
    print(f"  Skipped (already exist): {skipped}")

    # Verify
    print("\nVerifying import...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM section_232_tariffs
        WHERE LOWER(material) = 'auto'
    """)
    total = cursor.fetchone()[0]
    print(f"Total Auto entries in database: {total}")

    # Show sample
    cursor.execute("""
        SELECT hts_code, classification, declaration_required
        FROM section_232_tariffs
        WHERE LOWER(material) = 'auto'
        LIMIT 10
    """)
    print("\nSample Auto entries:")
    for hts, classification, decl in cursor.fetchall():
        print(f"  {hts}: {classification} ({decl})")

    # Check for multi-material HTS codes
    cursor.execute("""
        SELECT hts_code, GROUP_CONCAT(material, ', ') as materials, COUNT(*) as count
        FROM section_232_tariffs
        WHERE hts_code IN (
            SELECT hts_code FROM section_232_tariffs
            WHERE LOWER(material) = 'auto'
        )
        GROUP BY hts_code
        HAVING COUNT(*) > 1
        LIMIT 10
    """)
    multi_material = cursor.fetchall()
    if multi_material:
        print(f"\nMulti-material HTS codes (showing up to 10):")
        for hts, materials, count in multi_material:
            print(f"  {hts}: {materials} ({count} materials)")

    conn.close()

    print("\n" + "=" * 80)
    print("Import complete!")
    print("=" * 80)


if __name__ == "__main__":
    import_auto_hts()
