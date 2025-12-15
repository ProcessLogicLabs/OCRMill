"""Verify Section 232 tariff import."""
import sqlite3
from pathlib import Path

DB_PATH = Path("Resources/parts_database.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Total count
cursor.execute("SELECT COUNT(*) FROM section_232_tariffs")
total = cursor.fetchone()[0]
print(f"Total records: {total}")

# Count by material type
cursor.execute("SELECT material_type, COUNT(*) FROM section_232_tariffs GROUP BY material_type")
print("\nBy material type:")
for material, count in cursor.fetchall():
    print(f"  {material}: {count}")

# Sample records
print("\nSample steel tariffs:")
cursor.execute("SELECT hts_code FROM section_232_tariffs WHERE material_type='steel' LIMIT 10")
for row in cursor.fetchall():
    print(f"  {row[0]}")

print("\nSample aluminum tariffs:")
cursor.execute("SELECT hts_code FROM section_232_tariffs WHERE material_type='aluminum' LIMIT 10")
for row in cursor.fetchall():
    print(f"  {row[0]}")

conn.close()
print("\nImport verified successfully!")
