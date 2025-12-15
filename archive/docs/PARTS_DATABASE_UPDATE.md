# Parts Database Schema Update - December 14, 2025

## Overview
Updated the parts database schema to match the format in `parts_MMCITE.xlsx`, adding support for additional material composition fields and country of origin tracking.

## Changes Made

### 1. Database Schema Update

**Old Schema** (removed columns):
- `hts_description` - HTS description text
- `first_seen_date` - First appearance date
- `last_seen_date` - Last appearance date
- `total_quantity` - Aggregate quantity across all invoices
- `total_value` - Aggregate value across all invoices
- `invoice_count` - Number of invoices containing this part
- `avg_steel_pct` - Average steel percentage
- `avg_aluminum_pct` - Average aluminum percentage
- `avg_net_weight` - Average net weight

**New Schema** (added/renamed columns):
- `country_origin` - Country of origin code (e.g., CZ, BR, DK)
- `steel_pct` - Steel percentage (renamed from avg_steel_pct)
- `aluminum_pct` - Aluminum percentage (renamed from avg_aluminum_pct)
- `copper_pct` - Copper percentage
- `wood_pct` - Wood percentage
- `auto_pct` - Auto percentage
- `non_steel_pct` - Non-steel percentage
- `qty_unit` - Quantity unit (KG, NO, etc.)
- `sec301_exclusion_tariff` - Section 301 exclusion tariff code
- `last_updated` - Last update timestamp (replaces last_seen_date)

**Preserved Columns**:
- `part_number` - Primary key
- `description` - Part description
- `hts_code` - Harmonized Tariff Schedule code
- `mid` - Manufacturer ID
- `client_code` - Client code
- `notes` - Additional notes

### 2. Files Modified

#### `rebuild_parts_database.py` (NEW)
- Creates backup of existing database
- Drops old schema and creates new schema
- Imports all 255 parts from `parts_MMCITE.xlsx`
- Verifies import success

#### `parts_database.py`
- Updated `_initialize_database()` to use new schema (lines 41-61)
- Updated `_update_part_master()` to use current columns instead of aggregates (lines 236-296)
- Updated `import_parts_list()` to support new material composition fields (lines 419-511)
- Updated `export_to_csv()` to export all new columns (lines 639-664)
- Updated `get_statistics()` to calculate total_value from occurrences table (lines 669-700)
- Updated `update_part_hts()` to use last_updated instead of hts_description (lines 721-728)

### 3. Migration Process

**Step 1: Backup**
```
Resources/parts_database_backup_20251214_183131.db
```

**Step 2: Rebuild**
```bash
python rebuild_parts_database.py
```

**Step 3: Verify**
- 255 parts imported successfully
- 249 parts have HTS codes (97.6% coverage)
- All new columns populated from Excel source

## Data Import Results

**Source**: `C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\parts_MMCITE.xlsx`

**Results**:
- Total Parts: 255
- Parts with HTS Codes: 249 (97.6%)
- Material Composition Fields: 6 (steel, aluminum, copper, wood, auto, non_steel)
- Country Origins: Tracked (CZ, BR, DK, etc.)
- Quantity Units: Tracked (KG, NO)

## Key Differences

### Historical Tracking
**Old Approach**: Parts table stored aggregates (total_quantity, total_value, invoice_count, averages)
**New Approach**: Parts table stores current/latest values; history tracked in `part_occurrences` table

### Material Composition
**Old Approach**: Only steel and aluminum percentages
**New Approach**: 6 material types (steel, aluminum, copper, wood, auto, non_steel)

### Updates
**Old Approach**: first_seen_date and last_seen_date
**New Approach**: Single last_updated timestamp

## Backward Compatibility

The `part_occurrences` table remains unchanged, preserving all historical data. This means:
- Historical invoice processing data is intact
- Aggregate statistics can still be calculated from occurrences
- Both old and new parts can coexist during transition

## Usage

### Importing Parts
```python
from parts_database import PartsDatabase
from pathlib import Path

db = PartsDatabase(Path("Resources/parts_database.db"))

# Import from Excel with new format
imported, updated, errors = db.import_parts_list(
    Path("reports/parts_MMCITE.xlsx"),
    update_existing=True
)
```

### Querying Parts
```python
# Get part details
part = db.get_part_summary("350.2.2")
print(f"HTS: {part['hts_code']}")
print(f"Steel: {part['steel_pct']}%")
print(f"Copper: {part['copper_pct']}%")
print(f"Origin: {part['country_origin']}")
```

### Exporting Parts
```python
# Export to CSV with all new columns
db.export_to_csv(Path("parts_export.csv"), include_history=False)
```

## Notes

- Backup file created before migration: `parts_database_backup_20251214_183131.db`
- Original data preserved in case rollback needed
- Script `rebuild_parts_database.py` can be re-run to reimport from Excel
- Material percentages should add up to 100% for proper Section 232 classification
