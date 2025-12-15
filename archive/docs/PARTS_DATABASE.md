# Parts Database System

## Overview

The Parts Database System automatically tracks all parts processed through OCRMill, building a comprehensive database of parts with:
- Complete usage history across all invoices and projects
- HTS code mapping and assignment
- Material composition tracking (steel/aluminum percentages)
- Statistical analysis and reporting

## Features

### Automatic Tracking
- **Automatic Registration**: Every part from processed invoices is automatically added to the database
- **Historical Record**: Complete timeline of when and where each part was used
- **Material Data**: Tracks steel/aluminum composition for Section 232 compliance
- **Project Association**: Links parts to specific projects and invoices

### HTS Code Management
- **Mapping Import**: Load HTS codes from `mmcite_hts.xlsx` file
- **Automatic Lookup**: Fuzzy matching to assign HTS codes based on part descriptions
- **Manual Assignment**: GUI interface to manually set HTS codes for parts
- **Coverage Tracking**: Statistics on HTS code assignment coverage

### Analysis & Reporting
- **Part Statistics**: Usage frequency, total quantities, total values
- **Project Analysis**: See all parts used in specific projects
- **Material Composition**: Average steel/aluminum percentages per part
- **Export Capabilities**: Export to CSV for further analysis

## Database Structure

### Tables

#### 1. `parts` - Master Parts Table
Primary table containing one record per unique part number.

| Column | Type | Description |
|--------|------|-------------|
| part_number | TEXT (PK) | Unique part number |
| description | TEXT | Part description |
| hts_code | TEXT | Assigned HTS code |
| hts_description | TEXT | HTS code description |
| first_seen_date | TEXT | First time part appeared |
| last_seen_date | TEXT | Most recent appearance |
| total_quantity | REAL | Sum of all quantities |
| total_value | REAL | Sum of all dollar values |
| invoice_count | INTEGER | Number of invoices containing this part |
| avg_steel_pct | REAL | Average steel percentage |
| avg_aluminum_pct | REAL | Average aluminum percentage |
| avg_net_weight | REAL | Average net weight (kg) |
| notes | TEXT | User notes |

#### 2. `part_occurrences` - Part Usage History
Detailed record of each time a part appears on an invoice.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER (PK) | Auto-increment ID |
| part_number | TEXT (FK) | Reference to parts table |
| invoice_number | TEXT | Invoice this part appeared on |
| project_number | TEXT | Project code |
| quantity | REAL | Quantity on this invoice |
| total_price | REAL | Total line price |
| unit_price | REAL | Price per unit |
| steel_pct | REAL | Steel percentage |
| steel_kg | REAL | Steel weight (kg) |
| steel_value | REAL | Steel value (USD) |
| aluminum_pct | REAL | Aluminum percentage |
| aluminum_kg | REAL | Aluminum weight (kg) |
| aluminum_value | REAL | Aluminum value (USD) |
| net_weight | REAL | Net weight (kg) |
| ncm_code | TEXT | Brazilian NCM code |
| hts_code | TEXT | HTS code at time of processing |
| processed_date | TEXT | When invoice was processed |
| source_file | TEXT | PDF filename |

#### 3. `hts_codes` - HTS Code Mapping
Lookup table for HTS code descriptions and keywords.

| Column | Type | Description |
|--------|------|-------------|
| hts_code | TEXT (PK) | HTS code |
| description | TEXT | Product description/keywords |
| suggested | TEXT | Suggested usage notes |
| last_updated | TEXT | When mapping was loaded |

#### 4. `part_descriptions` - Search Keywords
Optional table for enhanced fuzzy matching.

| Column | Type | Description |
|--------|------|-------------|
| part_number | TEXT (PK) | Reference to parts table |
| description_text | TEXT | Full description text |
| keywords | TEXT | Extracted keywords |

## Installation

The parts database is automatically initialized when the invoice processor runs. No manual setup required.

### Database Location
- Default: `parts_database.db` in the OCRMill root folder
- SQLite format (can be opened with any SQLite viewer)

### Dependencies
The parts database requires:
```bash
pip install pandas openpyxl
```

These are used for HTS code Excel import and CSV export.

## Usage

### 1. Automatic Tracking (No Action Required)

When you process invoices through OCRMill, parts are automatically added to the database:

```
1. Drop PDF in input/ folder
2. Invoice processor extracts line items
3. Each part is automatically:
   - Added to parts_database.db
   - Linked to invoice and project
   - Material composition recorded
   - Usage statistics updated
```

### 2. Loading HTS Codes

**Method A: Using the Script**
```bash
python load_hts_mapping.py
```

**Method B: Using the Viewer GUI**
```bash
python parts_database_viewer.py
```
Then click "Load HTS Codes" button and select `reports/mmcite_hts.xlsx`

### 3. Viewing the Database

**Launch the Parts Database Viewer:**
```bash
python parts_database_viewer.py
```

**Features:**
- **Parts Master Tab**: View all unique parts with statistics
- **Part History Tab**: See complete usage history for any part
- **Statistics Tab**: Database-wide statistics and top parts
- **HTS Codes Tab**: View all loaded HTS code mappings

### 4. Searching for Parts

In the Parts Database Viewer:
1. Use the search box at the top
2. Type part number or description
3. Results update automatically

**Filters:**
- **All Parts**: Show everything
- **With HTS**: Only parts with HTS codes assigned
- **No HTS**: Parts missing HTS codes (need manual assignment)

### 5. Assigning HTS Codes

**Automatic Assignment:**
The system attempts to automatically assign HTS codes based on:
- Part number prefixes (e.g., SL → 9403.20.0080)
- Description keyword matching

**Manual Assignment:**
1. In Parts Database Viewer, right-click a part
2. Select "Set HTS Code"
3. Enter HTS code
4. Click Save

### 6. Exporting Data

**Export Parts Master:**
1. Click "Export Master CSV"
2. Choose location
3. File includes: part_number, HTS code, statistics, material composition

**Export Complete History:**
1. Click "Export History CSV"
2. Choose location
3. File includes: all occurrences with invoice/project details

**Generate Reports:**
1. Click "Generate Reports"
2. Select output folder
3. Creates:
   - `parts_master.csv`
   - `parts_history.csv`
   - `parts_statistics.txt`

## HTS Code Mapping File

### File Format: `mmcite_hts.xlsx`

The HTS mapping file should be in `reports/` folder with this structure:

| HTS | DESCRIPTION | SUGGESTED |
|-----|-------------|-----------|
| 7318.15.2095 | BOLTS/parts | Standard bolts |
| 9403.20.0082 | BICYCLE STAND | Bike parking |
| 7308.90.6000 | BOLLARDS | Security bollards |

**Columns:**
- **HTS**: HTS code (10 digits with periods)
- **DESCRIPTION**: Product description/keywords for matching
- **SUGGESTED**: Optional notes or suggestions

### Adding New HTS Codes

1. Open `reports/mmcite_hts.xlsx` in Excel
2. Add new row with HTS code and description
3. Save file
4. In Parts Database Viewer, click "Load HTS Codes"
5. Select the updated file

## Integration with Invoice Processing

### Workflow

```
┌─────────────────────────────────────────┐
│ 1. PDF Dropped in input/ folder         │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 2. Invoice Processor Extracts Data      │
│    - Invoice number                      │
│    - Project number                      │
│    - Part numbers, quantities, prices    │
│    - Material composition                │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 3. Parts Database Records Each Part     │
│    - Creates/updates part master record  │
│    - Adds occurrence to history          │
│    - Attempts HTS code lookup            │
│    - Updates statistics                  │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ 4. CSV Generated with HTS Codes         │
│    (if HTS code available)               │
└─────────────────────────────────────────┘
```

### Automatic HTS Assignment

When a part is processed, the system attempts to find an HTS code using:

1. **Existing Assignment**: If part was seen before with HTS code
2. **Part Prefix Matching**: Common prefixes mapped to HTS codes
3. **Description Keyword Matching**: Fuzzy match against HTS descriptions

**Default Part Prefix Mappings:**
```python
'SL'  → 9403.20.0080  # Seating
'BTT' → 9401.69.8031  # Benches
'STE' → 9403.20.0082  # Bicycle stands
'LPU' → 9403.20.0080  # Planters
'ND'  → 7308.90.6000  # Bollards
'PQA' → 9403.20.0080  # Tables
```

## API Reference

### PartsDatabase Class

**Initialization:**
```python
from parts_database import PartsDatabase

db = PartsDatabase()  # Uses default location
# or
db = PartsDatabase(Path("custom_location.db"))
```

**Add Part Occurrence:**
```python
part_data = {
    'part_number': 'SL505-002000',
    'invoice_number': '2025601736',
    'project_number': 'US25A0203',
    'quantity': 9.0,
    'total_price': 972.83,
    'steel_pct': 100,
    'steel_kg': 45.5,
    'steel_value': 500.00,
    'hts_code': '9403.20.0080',
    'source_file': 'invoice_2025.pdf'
}

db.add_part_occurrence(part_data)
```

**Get Part Summary:**
```python
part = db.get_part_summary('SL505-002000')
print(f"Total value: ${part['total_value']:,.2f}")
print(f"Used on {part['invoice_count']} invoices")
```

**Get Part History:**
```python
history = db.get_part_history('SL505-002000')
for record in history:
    print(f"Invoice: {record['invoice_number']}, Qty: {record['quantity']}")
```

**Search Parts:**
```python
results = db.search_parts('bicycle')
for part in results:
    print(f"{part['part_number']}: {part['description']}")
```

**Export to CSV:**
```python
db.export_to_csv(Path("parts_master.csv"), include_history=False)
db.export_to_csv(Path("parts_history.csv"), include_history=True)
```

**Load HTS Mapping:**
```python
db.load_hts_mapping(Path("reports/mmcite_hts.xlsx"))
```

**Find HTS Code:**
```python
hts = db.find_hts_code('SL505-002000', 'Bicycle rack seating')
```

**Get Statistics:**
```python
stats = db.get_statistics()
print(f"Total parts: {stats['total_parts']}")
print(f"HTS coverage: {stats['hts_coverage_pct']:.1f}%")
```

## Reports

### Parts Master Report

**Filename:** `parts_master.csv`

Contains one row per unique part with summary statistics:
- Part number
- HTS code
- Invoice count
- Total quantities and values
- Average material composition
- First/last seen dates

**Use Case:** Overview of all parts, HTS code assignments, usage patterns

### Parts History Report

**Filename:** `parts_history.csv`

Contains one row per part occurrence (every time a part appears on an invoice):
- Part number
- Invoice and project numbers
- Quantity and price on that invoice
- Material composition for that occurrence
- When processed

**Use Case:** Detailed audit trail, project-specific part lists, historical pricing

### Statistics Report

**Filename:** `parts_statistics.txt`

Text summary including:
- Total unique parts
- Total invoices processed
- Total value
- HTS code coverage percentage
- Top parts by value
- Parts without HTS codes

**Use Case:** Executive summary, database health check

## Common Tasks

### Task 1: Find All Parts Used in a Project

```python
from parts_database import PartsDatabase

db = PartsDatabase()
parts = db.get_parts_by_project('US25A0203')

for part in parts:
    print(f"{part['part_number']}: Qty {part['quantity']}, ${part['total_price']}")
```

### Task 2: Identify Parts Missing HTS Codes

In Parts Database Viewer:
1. Select filter "No HTS"
2. List shows all parts without HTS codes
3. Right-click each part to assign HTS code

Or programmatically:
```python
db = PartsDatabase()
parts = db.get_all_parts()
missing_hts = [p for p in parts if not p.get('hts_code')]

print(f"Parts missing HTS codes: {len(missing_hts)}")
for part in missing_hts:
    print(f"  {part['part_number']}")
```

### Task 3: Generate Monthly Parts Report

```python
from parts_database import PartsDatabase, create_parts_report
from pathlib import Path
from datetime import datetime

db = PartsDatabase()

# Create reports folder with timestamp
output_folder = Path(f"reports/monthly_{datetime.now().strftime('%Y%m')}")
create_parts_report(db, output_folder)

print(f"Reports generated in {output_folder}")
```

### Task 4: Update HTS Code for Multiple Parts

```python
db = PartsDatabase()

# Update all SL505 variants to same HTS code
parts = db.search_parts('SL505')
for part in parts:
    db.update_part_hts(part['part_number'], '9403.20.0080', 'Seating furniture')

print(f"Updated {len(parts)} parts")
```

## Troubleshooting

### Database is Empty
**Symptom:** Parts Database Viewer shows 0 parts

**Solution:**
1. Process at least one invoice through OCRMill
2. Parts are only added when invoices are processed
3. Check that invoice processing completed successfully (check Activity Log)

### HTS Codes Not Appearing
**Symptom:** HTS codes are blank in exports

**Solution:**
1. Verify `mmcite_hts.xlsx` exists in `reports/` folder
2. Run `python load_hts_mapping.py`
3. Check HTS Codes tab in viewer to confirm codes loaded
4. Manually assign HTS codes if automatic matching fails

### Duplicate Parts
**Symptom:** Same part appears multiple times with different capitalization

**Solution:**
- Parts are matched exactly on part_number
- Ensure consistent part number format in source invoices
- The database will treat "SL505" and "sl505" as different parts

### Performance Issues with Large Database
**Symptom:** Viewer is slow with thousands of parts

**Solution:**
1. Use search/filter to limit displayed parts
2. Database has indexes on key fields for performance
3. Export to CSV and use Excel/Python for bulk analysis
4. Consider archiving old data if database exceeds 100,000 occurrences

## Database Maintenance

### Backup Database

**Manual Backup:**
```bash
copy parts_database.db parts_database_backup_20250101.db
```

**Automated Backup Script:**
```python
from pathlib import Path
from datetime import datetime
import shutil

db_file = Path("parts_database.db")
backup_file = Path(f"backups/parts_database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
backup_file.parent.mkdir(exist_ok=True)
shutil.copy(db_file, backup_file)
```

### Archive Old Data

To keep database performant, periodically archive data:

```python
# Export complete history
db = PartsDatabase()
archive_file = Path(f"archives/parts_history_{datetime.now().strftime('%Y%m')}.csv")
db.export_to_csv(archive_file, include_history=True)

# Then optionally delete old occurrences
cursor = db.conn.cursor()
cursor.execute("""
    DELETE FROM part_occurrences
    WHERE processed_date < date('now', '-2 years')
""")
db.conn.commit()
```

### Rebuild Statistics

If statistics seem incorrect:

```python
db = PartsDatabase()
cursor = db.conn.cursor()

# Get all unique parts
cursor.execute("SELECT DISTINCT part_number FROM part_occurrences")
parts = cursor.fetchall()

# Rebuild each part's statistics
for part_row in parts:
    part_num = part_row['part_number']
    db._update_part_master(part_num, {})

print(f"Rebuilt statistics for {len(parts)} parts")
```

## Integration with DerivativeMill

The parts database enhances Section 232 processing by:

1. **HTS Code Pre-Assignment**: Parts already have HTS codes before DerivativeMill import
2. **Historical Data**: Review past HTS assignments for consistency
3. **Material Composition**: Steel/aluminum data ready for tariff calculations
4. **Audit Trail**: Complete history of part classifications

**Workflow:**
```
OCRMill → Parts Database → Consolidated CSV → DerivativeMill → Customs Forms
```

The `consolidate_and_match.py` script can query the parts database to enrich consolidated data.

## Future Enhancements

Planned features for future versions:

- [ ] Part description auto-extraction from PDFs
- [ ] Machine learning for HTS code prediction
- [ ] Integration with external HTS code databases
- [ ] Multi-language description support
- [ ] Part image storage and recognition
- [ ] Pricing trend analysis
- [ ] Supplier tracking
- [ ] Web interface for remote access

## Support

For questions or issues with the parts database:

1. Check this documentation
2. Review the Activity Log in Invoice Processor GUI
3. Use Parts Database Viewer to inspect data
4. Export to CSV for manual analysis
5. Check SQLite database directly with DB Browser for SQLite

---

**System Version:** 2.1.0
**Last Updated:** December 9, 2025
**Database Schema Version:** 1.0
