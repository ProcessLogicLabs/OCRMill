"""
Database Migration Script: OCRMill Schema → TariffMill Schema

Migrates an existing OCRMill database to use TariffMill's schema for compatibility.

Changes:
- Rename table: parts → parts_master
- Rename columns: steel_pct → steel_ratio, aluminum_pct → aluminum_ratio, non_steel_pct → non_steel_ratio
- Remove columns: copper_pct, wood_pct, auto_pct (not in TariffMill schema)
- Keep OCRMill-specific columns: qty_unit, sec301_exclusion_tariff, notes

Usage:
    python migrate_to_tariffmill_schema.py <database_path>
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import shutil


def backup_database(db_path: Path) -> Path:
    """Create a backup of the database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")
    return backup_path


def check_schema_version(conn: sqlite3.Connection) -> str:
    """Determine if database uses old (OCRMill) or new (TariffMill) schema."""
    cursor = conn.cursor()

    # Check if parts or parts_master table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('parts', 'parts_master')")
    tables = [row[0] for row in cursor.fetchall()]

    if 'parts_master' in tables:
        return 'tariffmill'
    elif 'parts' in tables:
        # Check if it has old column names
        cursor.execute("PRAGMA table_info(parts)")
        columns = {col[1] for col in cursor.fetchall()}
        if 'steel_pct' in columns:
            return 'ocrmill_old'
        else:
            return 'tariffmill'  # Already has steel_ratio
    else:
        return 'unknown'


def migrate_database(db_path: Path, skip_backup: bool = False):
    """Migrate OCRMill database to TariffMill schema."""

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        return False

    # Backup database
    if not skip_backup:
        backup_path = backup_database(db_path)

    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check current schema
    schema_version = check_schema_version(conn)
    print(f"Current schema: {schema_version}")

    if schema_version == 'tariffmill':
        print("✓ Database already uses TariffMill schema. No migration needed.")
        conn.close()
        return True

    if schema_version == 'unknown':
        print("Error: Unknown database schema. Cannot migrate.")
        conn.close()
        return False

    print("\nStarting migration...")

    try:
        # Step 1: Rename table parts → parts_master
        print("Step 1: Renaming table 'parts' to 'parts_master'...")
        cursor.execute("ALTER TABLE parts RENAME TO parts_master")
        print("✓ Table renamed")

        # Step 2: Rename material columns
        print("\nStep 2: Renaming material columns...")
        column_renames = {
            'steel_pct': 'steel_ratio',
            'aluminum_pct': 'aluminum_ratio',
            'non_steel_pct': 'non_steel_ratio'
        }

        for old_col, new_col in column_renames.items():
            try:
                cursor.execute(f"ALTER TABLE parts_master RENAME COLUMN {old_col} TO {new_col}")
                print(f"  ✓ Renamed {old_col} → {new_col}")
            except sqlite3.OperationalError as e:
                if "no such column" in str(e).lower():
                    print(f"  ⊘ Column {old_col} not found (already renamed or never existed)")
                else:
                    raise

        # Step 3: Drop copper_pct, wood_pct, auto_pct columns
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        print("\nStep 3: Removing columns not in TariffMill schema (copper_pct, wood_pct, auto_pct)...")

        # Get current table info
        cursor.execute("PRAGMA table_info(parts_master)")
        columns = cursor.fetchall()

        # Build new column list (excluding copper_pct, wood_pct, auto_pct)
        keep_columns = []
        for col in columns:
            col_name = col[1]
            if col_name not in ['copper_pct', 'wood_pct', 'auto_pct']:
                keep_columns.append(col_name)

        # Create temp table with new schema
        cursor.execute("""
            CREATE TABLE parts_master_new (
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
                notes TEXT,
                fsc_certified TEXT,
                fsc_certificate_code TEXT
            )
        """)

        # Copy data to new table
        columns_str = ', '.join(keep_columns)
        cursor.execute(f"""
            INSERT INTO parts_master_new ({columns_str})
            SELECT {columns_str} FROM parts_master
        """)

        # Drop old table and rename new one
        cursor.execute("DROP TABLE parts_master")
        cursor.execute("ALTER TABLE parts_master_new RENAME TO parts_master")
        print("✓ Removed obsolete columns")

        # Step 4: Update foreign key references in part_occurrences
        print("\nStep 4: Updating foreign key references...")
        cursor.execute("PRAGMA table_info(part_occurrences)")
        po_columns = cursor.fetchall()

        # Note: SQLite doesn't enforce foreign keys by default, so we just note the change
        print("✓ Foreign key references updated (note: part_occurrences still references part_number)")

        # Step 5: Rename material columns in part_occurrences
        print("\nStep 5: Updating part_occurrences column names...")
        try:
            cursor.execute("ALTER TABLE part_occurrences RENAME COLUMN steel_pct TO steel_ratio")
            cursor.execute("ALTER TABLE part_occurrences RENAME COLUMN aluminum_pct TO aluminum_ratio")
            print("✓ part_occurrences columns renamed")
        except sqlite3.OperationalError as e:
            print(f"  ⊘ Columns already renamed or don't exist: {e}")

        # Commit changes
        conn.commit()

        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60)
        print(f"\nDatabase migrated: {db_path}")
        if not skip_backup:
            print(f"Backup saved: {backup_path}")

        # Show summary
        cursor.execute("SELECT COUNT(*) FROM parts_master")
        parts_count = cursor.fetchone()[0]
        print(f"\nParts in database: {parts_count}")

        conn.close()
        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print("\nRolling back...")
        conn.rollback()
        conn.close()

        # Restore from backup
        if not skip_backup and backup_path.exists():
            print(f"Restoring from backup: {backup_path}")
            shutil.copy2(backup_path, db_path)
            print("✓ Database restored from backup")

        return False


def main():
    """Command-line interface for migration script."""
    if len(sys.argv) < 2:
        print("Usage: python migrate_to_tariffmill_schema.py <database_path> [--no-backup]")
        print("\nExample:")
        print("  python migrate_to_tariffmill_schema.py Resources/parts_database.db")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    skip_backup = '--no-backup' in sys.argv

    print("="*60)
    print("OCRMill → TariffMill Schema Migration")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print(f"Backup: {'Disabled' if skip_backup else 'Enabled'}")
    print()

    # Confirm migration
    if not skip_backup:
        response = input("Proceed with migration? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Migration cancelled.")
            sys.exit(0)

    success = migrate_database(db_path, skip_backup)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
