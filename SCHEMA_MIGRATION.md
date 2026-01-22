# Database Schema Migration Guide

## Overview

OCRMill v0.99.16+ uses TariffMill's database schema for full compatibility and shared database support.

## What Changed

### Table Names
- **Old:** `parts` table
- **New:** `parts_master` table

### Column Names
| Old (OCRMill) | New (TariffMill) | Notes |
|---------------|------------------|-------|
| `steel_pct` | `steel_ratio` | Same scale (0-100) |
| `aluminum_pct` | `aluminum_ratio` | Same scale (0-100) |
| `non_steel_pct` | `non_steel_ratio` | Same scale (0-100) |
| `copper_pct` | *(removed)* | Not in TariffMill schema |
| `wood_pct` | *(removed)* | Not in TariffMill schema |
| `auto_pct` | *(removed)* | Not in TariffMill schema |

### Columns Kept (OCRMill-specific)
These columns are part of the new schema:
- `qty_unit` - Quantity unit type
- `sec301_exclusion_tariff` - Section 301 exclusion info
- `notes` - Part notes

## Migration Process

### Automatic Migration

Run the migration script before upgrading to v0.99.16:

```bash
python migrate_to_tariffmill_schema.py Resources/parts_database.db
```

**What it does:**
1. Creates a backup: `parts_database_backup_YYYYMMDD_HHMMSS.db`
2. Renames `parts` → `parts_master`
3. Renames columns: `*_pct` → `*_ratio`
4. Removes `copper_pct`, `wood_pct`, `auto_pct` columns
5. Updates foreign key references
6. Updates `part_occurrences` table column names

### Manual Migration (Advanced)

If you prefer manual migration:

```sql
-- 1. Rename table
ALTER TABLE parts RENAME TO parts_master;

-- 2. Rename columns
ALTER TABLE parts_master RENAME COLUMN steel_pct TO steel_ratio;
ALTER TABLE parts_master RENAME COLUMN aluminum_pct TO aluminum_ratio;
ALTER TABLE parts_master RENAME COLUMN non_steel_pct TO non_steel_ratio;

-- 3. Remove obsolete columns (requires table recreation in SQLite)
-- See migrate_to_tariffmill_schema.py for full code

-- 4. Update part_occurrences
ALTER TABLE part_occurrences RENAME COLUMN steel_pct TO steel_ratio;
ALTER TABLE part_occurrences RENAME COLUMN aluminum_pct TO aluminum_ratio;
```

## Compatibility

### Shared Database with TariffMill

After migration, your database is fully compatible with TariffMill:

**config.json:**
```json
{
  "database_path": "Y:/Shared/TariffMill/parts_database.db",
  "shared_templates_folder": "Y:/Shared/TariffMill/Templates"
}
```

Both applications now use the same schema and can share the same database file.

### Import/Export

**CSV Import** - The import function auto-maps both formats:
- Recognizes both `steel_ratio` and `steel_pct` column names
- Automatically stores in correct schema format

**CSV Export** - Exports using TariffMill schema:
- Columns are named `steel_ratio`, `aluminum_ratio`, `non_steel_ratio`

## What to Expect

### Before Migration (v0.99.15 and earlier)

```sql
sqlite> .schema parts
CREATE TABLE parts (
    part_number TEXT PRIMARY KEY,
    description TEXT,
    ...
    steel_pct REAL DEFAULT 0,
    aluminum_pct REAL DEFAULT 0,
    copper_pct REAL DEFAULT 0,
    wood_pct REAL DEFAULT 0,
    auto_pct REAL DEFAULT 0,
    non_steel_pct REAL DEFAULT 0,
    ...
);
```

### After Migration (v0.99.16+)

```sql
sqlite> .schema parts_master
CREATE TABLE parts_master (
    part_number TEXT PRIMARY KEY,
    description TEXT,
    ...
    steel_ratio REAL DEFAULT 0,
    aluminum_ratio REAL DEFAULT 0,
    non_steel_ratio REAL DEFAULT 0,
    qty_unit TEXT DEFAULT 'NO',
    sec301_exclusion_tariff TEXT,
    notes TEXT,
    ...
);
```

## Rollback

If migration fails or you need to rollback:

1. **Automatic Backup** - Migration script creates backups automatically
2. **Restore** - Copy backup file over current database:
   ```bash
   copy parts_database_backup_20260122_120000.db parts_database.db
   ```

## Testing After Migration

1. **Check Schema:**
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('Resources/parts_database.db'); print([r[0] for r in conn.execute('PRAGMA table_info(parts_master)')])"
   ```

2. **Verify Data:**
   - Open OCRMill
   - Go to Parts Database tab
   - Verify parts are displayed correctly
   - Check that material ratios show proper values

3. **Test Export:**
   - Run Section 232 export
   - Verify material composition data is correct

## Troubleshooting

### "Table parts_master doesn't exist"
- Migration didn't complete
- Restore from backup and re-run migration script

### "Column steel_ratio doesn't exist"
- Schema partially migrated
- Check migration log for errors
- Restore from backup and re-run

### "All material ratios show 0"
- Data wasn't copied correctly
- Check `parts_master` table has data:
  ```sql
  SELECT part_number, steel_ratio, aluminum_ratio FROM parts_master LIMIT 5;
  ```

### "Section 232 export shows 0% for all materials"
- Parts database not populated with material data
- Import parts master data with material composition
- Or add material data manually in Parts Database tab

## Shared Database Configuration

After migration, update your `config.json` for shared database:

```json
{
  "database_path": "Y:/Shared/Database/parts_database.db",
  "shared_templates_folder": "Y:/Dev/Tariffmill/Templates"
}
```

See [SHARED_CONFIG.md](SHARED_CONFIG.md) for complete shared database setup.

## Benefits of New Schema

✅ **Full TariffMill Compatibility** - Use same database for both applications
✅ **Standard Schema** - Follows TariffMill's established schema
✅ **Simplified Maintenance** - One schema to maintain
✅ **Direct Data Sharing** - No conversion needed
✅ **Future-Proof** - Aligned with TariffMill development

## Version Compatibility

| OCRMill Version | Schema | Database Table | Shared with TariffMill |
|----------------|--------|----------------|------------------------|
| v0.99.15 and earlier | Old | `parts` | ❌ No (incompatible) |
| v0.99.16+ | New | `parts_master` | ✅ Yes (fully compatible) |

## Migration Checklist

- [ ] Backup your current database
- [ ] Run migration script: `python migrate_to_tariffmill_schema.py Resources/parts_database.db`
- [ ] Verify migration completed successfully
- [ ] Test OCRMill with migrated database
- [ ] Test Section 232 export
- [ ] Update config.json if using shared database
- [ ] Keep backup for 30 days before deleting

## Support

If you encounter issues:
1. Check migration log for errors
2. Restore from backup
3. Review this guide
4. Check TROUBLESHOOTING section above
5. Report issues at https://github.com/ProcessLogicLabs/OCRMill/issues
