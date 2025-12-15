# Section 232 Reference Tables

## Overview
Added two reference tables to the parts database for Section 232 tariff application:
1. **section_232_tariffs**: HTS codes subject to Section 232 tariffs (steel and aluminum)
2. **section_232_actions**: Section 232 action tariffs with rates, declaration requirements, and effective dates

These tables allow the system to automatically identify which products require Section 232 declarations and what additional tariffs apply.

## Implementation Date
December 14, 2025

## What Was Added

### 1. Database Table: section_232_tariffs

**Schema**:
```sql
CREATE TABLE section_232_tariffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hts_code TEXT NOT NULL,
    material_type TEXT NOT NULL,
    notes TEXT
)
```

**Indexes**:
- `idx_232_hts`: Index on hts_code for fast lookups
- `idx_232_material`: Index on material_type for filtering

**Data Source**: `C:\Users\hpayne\Documents\DevHouston\OCRMill\Resources\CBP_data\CBP_232_tariffs.xlsx`

**Statistics**:
- Total records: 475
- Steel tariffs: 285
- Aluminum tariffs: 190

### 2. Database Table: section_232_actions

**Schema**:
```sql
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
```

**Indexes**:
- `idx_232_actions_tariff`: Index on tariff_no for fast lookups
- `idx_232_actions_action`: Index on action type for filtering

**Data Source**: `C:\Users\hpayne\Documents\DevHouston\OCRMill\Resources\CBP_data\Section_232_Actions.csv`

**Statistics**:
- Total records: 63
- Steel actions: 19
- Aluminum actions: 17
- Aluminum & Steel combined: 16
- Copper actions: 2
- Lumber/Furniture/Wood actions: 9

**Action Types**:
- `232 STEEL` - Steel tariff actions (declaration code: 08 MELT & POUR REQ)
- `232 ALUMINUM` - Aluminum tariff actions (declaration code: 07 SMELT & CAST)
- `232 Aluminum & Steel` - Combined material actions
- `232 Copper` - Copper tariff actions (declaration code: 11 COPPER CONTENT)
- `232 Lumber Furniture Wood` - Wood tariff actions

### 3. API Methods in PartsDatabase

#### Section 232 Tariffs (HTS Code Lookups)

#### is_section_232_tariff(hts_code, material_type=None)
Check if an HTS code is subject to Section 232 tariffs.

**Parameters**:
- `hts_code` (str): HTS code to check
- `material_type` (str, optional): Filter by 'steel' or 'aluminum'

**Returns**: bool - True if HTS code is in Section 232 list

**Example**:
```python
from parts_database import PartsDatabase
from pathlib import Path

db = PartsDatabase(Path("Resources/parts_database.db"))

# Check if HTS code is Section 232
is_232 = db.is_section_232_tariff("7301.20.10")
# Returns: True

# Check if specific material type
is_steel = db.is_section_232_tariff("7301.20.10", "steel")
# Returns: True

is_aluminum = db.is_section_232_tariff("7301.20.10", "aluminum")
# Returns: False
```

#### get_section_232_material_type(hts_code)
Get the Section 232 material type for an HTS code.

**Parameters**:
- `hts_code` (str): HTS code to look up

**Returns**: str or None - Material type ('steel' or 'aluminum') or None if not found

**Example**:
```python
material = db.get_section_232_material_type("7610.10.00")
# Returns: "aluminum"

material = db.get_section_232_material_type("9403.20.0082")
# Returns: None (not a Section 232 tariff)
```

#### get_all_section_232_tariffs(material_type=None)
Get all Section 232 tariff codes.

**Parameters**:
- `material_type` (str, optional): Filter by 'steel' or 'aluminum'

**Returns**: List[Dict] - List of tariff records

**Example**:
```python
# Get all steel tariffs
steel_tariffs = db.get_all_section_232_tariffs("steel")
# Returns: [{'id': 1, 'hts_code': '7301.20.10', 'material_type': 'steel', 'notes': '...'}, ...]

# Get all tariffs
all_tariffs = db.get_all_section_232_tariffs()
# Returns: All 475 tariff records
```

#### get_section_232_statistics()
Get statistics about Section 232 tariff codes.

**Returns**: Dict[str, int] - Dictionary with counts by material type

**Example**:
```python
stats = db.get_section_232_statistics()
# Returns: {'aluminum': 190, 'steel': 285, 'total': 475}
```

## Usage in CBP Export

### Automatic Section 232 Detection

The Section 232 tariff table can be used during CBP export processing to:

1. **Validate Material Classification**: Confirm that HTS codes match expected material types
2. **Auto-detect Section 232 Items**: Flag items requiring Section 232 declarations
3. **Apply Correct Declaration Codes**: Automatically assign DecTypeCd based on HTS

**Example Integration**:
```python
# During CBP export enrichment
for _, row in df.iterrows():
    hts_code = row.get('hts_code', '')

    # Check if HTS code is Section 232
    if db.is_section_232_tariff(hts_code):
        material = db.get_section_232_material_type(hts_code)

        # Apply Section 232 flags
        if material == 'steel':
            row['232_Status'] = '232_Steel'
            row['DecTypeCd'] = '08'
        elif material == 'aluminum':
            row['232_Status'] = '232_Aluminum'
            row['DecTypeCd'] = '07'

        # Set country codes for 232 items
        row['CountryofMelt'] = row.get('country_origin', 'CZ')
        row['CountryOfCast'] = row.get('country_origin', 'CZ')
        row['PrimCountryOfSmelt'] = row.get('country_origin', 'CZ')
```

### Validation and Reporting

The tariff table can also be used for:

**Validation**:
```python
# Warn if steel percentage doesn't match HTS classification
if row['steel_pct'] > 50 and not db.is_section_232_tariff(hts_code, 'steel'):
    print(f"WARNING: Part {part_number} has {steel_pct}% steel but HTS {hts_code} is not 232 steel")
```

**Reporting**:
```python
# Count Section 232 items in shipment
steel_232_items = [item for item in items if db.is_section_232_tariff(item['hts_code'], 'steel')]
aluminum_232_items = [item for item in items if db.is_section_232_tariff(item['hts_code'], 'aluminum')]

print(f"Section 232 items: {len(steel_232_items)} steel, {len(aluminum_232_items)} aluminum")
```

## Section 232 Actions API Methods

#### get_section_232_action(tariff_no)
Get Section 232 action details by tariff number.

**Parameters**:
- `tariff_no` (str): Tariff number (e.g., "99038187")

**Returns**: Dict or None - Action record with all details

**Example**:
```python
action = db.get_section_232_action("99038187")
# Returns: {
#   'tariff_no': '99038187',
#   'action': '232 STEEL',
#   'tariff_description': 'STL NT 16(J) ALL CTRIES',
#   'advalorem_rate': '50%',
#   'additional_declaration': '08 MELT & POUR REQ',
#   ...
# }
```

#### get_section_232_actions_by_type(action_type)
Get all actions for a specific type.

**Parameters**:
- `action_type` (str): Action type (e.g., "232 STEEL", "232 ALUMINUM")

**Returns**: List[Dict] - List of action records

**Example**:
```python
steel_actions = db.get_section_232_actions_by_type("232 STEEL")
# Returns list of 19 steel action records
```

#### get_all_section_232_actions()
Get all Section 232 action records.

**Returns**: List[Dict] - All 63 action records

#### get_section_232_action_types()
Get list of unique action types.

**Returns**: List[str] - Action type names

**Example**:
```python
types = db.get_section_232_action_types()
# Returns: ['232 ALUMINUM', '232 Aluminum & Steel', '232 Copper',
#           '232 Lumber Furniture Wood', '232 STEEL']
```

#### get_section_232_actions_statistics()
Get statistics about Section 232 actions.

**Returns**: Dict[str, int] - Counts by action type

**Example**:
```python
stats = db.get_section_232_actions_statistics()
# Returns: {
#   '232 STEEL': 19,
#   '232 ALUMINUM': 17,
#   '232 Aluminum & Steel': 16,
#   '232 Copper': 2,
#   '232 Lumber Furniture Wood': 9,
#   'total': 63
# }
```

#### get_section_232_declaration_required(action_type)
Get typical declaration code for an action type.

**Parameters**:
- `action_type` (str): Action type

**Returns**: str or None - Declaration code

**Example**:
```python
decl = db.get_section_232_declaration_required("232 STEEL")
# Returns: "08 MELT & POUR REQ"

decl = db.get_section_232_declaration_required("232 ALUMINUM")
# Returns: "07 SMELT & CAST"
```

## Import Scripts

### import_232_tariffs.py

**Purpose**: Import Section 232 tariff codes from Excel into database

**Usage**:
```bash
python import_232_tariffs.py
```

**What it does**:
1. Creates `section_232_tariffs` table (drops if exists)
2. Imports steel tariffs from "steel tariffs" column
3. Imports aluminum tariffs from "aluminum tariffs" column
4. Creates indexes for fast lookups
5. Verifies import success

**Output**:
```
================================================================================
Section 232 Tariff Import Script
================================================================================
Creating section_232_tariffs table...
Table created successfully

Importing tariffs from: CBP_232_tariffs.xlsx
Found 285 rows in Excel file
Columns: ['steel tariffs', 'aluminum tariffs']

Import complete:
  Steel tariffs: 285
  Aluminum tariffs: 190
  Total: 475

Verifying import...
Total records: 475
  aluminum: 190
  steel: 285

Sample records:
  7301.20.10 - steel
  7301.20.50 - steel
  7302.30.00 - steel
  7307.21.10 - steel
  7307.21.50 - steel

================================================================================
Import complete!
================================================================================
```

### import_232_actions.py

**Purpose**: Import Section 232 action tariffs from CSV into database

**Usage**:
```bash
python import_232_actions.py
```

**What it does**:
1. Creates `section_232_actions` table (drops if exists)
2. Imports all 63 action records from CSV
3. Creates indexes for fast lookups
4. Verifies import success

**Output**:
```
================================================================================
Section 232 Actions Import Script
================================================================================
Creating section_232_actions table...
Table created successfully

Importing Section 232 actions from: Section_232_Actions.csv
Found 63 rows in CSV file
Columns: ['Tariff No', 'Action', 'Tariff Description', ...]

Import complete: 63 actions imported

Verifying import...
Total records: 63

By action type:
  232 ALUMINUM: 17
  232 Aluminum & Steel: 16
  232 Copper: 2
  232 Lumber Furniture Wood: 9
  232 STEEL: 19

Sample steel actions:
  99038187: STL NT 16(J) ALL CTRIES... (Rate: 50%, Decl: 08 MELT & POUR REQ)
  ...

================================================================================
Import complete!
================================================================================
```

## Test Scripts

### test_section_232_lookup.py

**Purpose**: Test Section 232 tariff lookup functionality

**Usage**:
```bash
python test_section_232_lookup.py
```

**Tests performed**:
1. Get statistics (counts by material type)
2. Check specific HTS codes
3. Filter by material type
4. Retrieve all tariffs by type

### test_section_232_actions.py

**Purpose**: Test Section 232 actions lookup functionality

**Usage**:
```bash
python test_section_232_actions.py
```

**Tests performed**:
1. Get action statistics (counts by action type)
2. Get available action types
3. Get declaration requirements by type
4. Lookup specific tariff actions
5. Get actions filtered by type
6. Test combined material actions

## Data Structure

### Excel File Format

**File**: `Resources/CBP_data/CBP_232_tariffs.xlsx`

**Columns**:
- `steel tariffs`: HTS codes for steel Section 232 tariffs (285 codes)
- `aluminum tariffs`: HTS codes for aluminum Section 232 tariffs (190 codes)

**Example**:
```
| steel tariffs | aluminum tariffs |
|---------------|------------------|
| 7301.20.10    | 7610.10.00      |
| 7301.20.50    | 7610.90.00      |
| 7302.30.00    | 7612.90.10      |
| 7307.21.10    | 7615.10.2015    |
```

### CSV File Format

**File**: `Resources/CBP_data/Section_232_Actions.csv`

**Columns**:
- `Tariff No`: Tariff number (e.g., "99038187")
- `Action`: Action type (e.g., "232 STEEL", "232 ALUMINUM")
- `Tariff Description`: Description of tariff application
- `Advalorem Rate`: Ad valorem rate percentage (e.g., "50%")
- `Effective Date`: When tariff becomes effective
- `Expiration Date`: When tariff expires
- `Specific Rate`: Specific rate (usually 0)
- `Additional Declaration Required`: Declaration code (e.g., "08 MELT & POUR REQ")
- `Note`: Additional notes about the tariff
- `Link`: Reference link (if any)

**Example**:
```
| Tariff No | Action     | Tariff Description      | Advalorem Rate | Additional Declaration  |
|-----------|------------|-------------------------|----------------|-------------------------|
| 99038187  | 232 STEEL  | STL NT 16(J) ALL CTRIES | 50%            | 08 MELT & POUR REQ     |
| 99038502  | 232 ALUMINUM | ALU NT19(G) ALL CTRIES | 50%            | 07 SMELT & CAST        |
```

### Database Tables

**Table**: `section_232_tariffs`

**Sample Data**:
```
| id | hts_code    | material_type | notes                           |
|----|-------------|---------------|---------------------------------|
| 1  | 7301.20.10  | steel         | Section 232 steel tariff        |
| 2  | 7301.20.50  | steel         | Section 232 steel tariff        |
| 3  | 7610.10.00  | aluminum      | Section 232 aluminum tariff     |
| 4  | 7610.90.00  | aluminum      | Section 232 aluminum tariff     |
```

**Table**: `section_232_actions`

**Sample Data**:
```
| id | tariff_no | action     | tariff_description      | advalorem_rate | additional_declaration |
|----|-----------|------------|-------------------------|----------------|------------------------|
| 1  | 99038187  | 232 STEEL  | STL NT 16(J) ALL CTRIES | 50%            | 08 MELT & POUR REQ    |
| 2  | 99038502  | 232 ALUMINUM | ALU NT19(G) ALL CTRIES | 50%            | 07 SMELT & CAST       |
```

## Section 232 Background

### What is Section 232?

Section 232 of the Trade Expansion Act of 1962 allows the President to impose tariffs on imports that threaten national security. Currently applies to:

- **Steel products**: 25% tariff on most steel imports
- **Aluminum products**: 10% tariff on most aluminum imports

### Declaration Requirements

When importing products subject to Section 232 tariffs, importers must declare:

1. **Material Type**: Steel or aluminum content
2. **Country Codes**:
   - Country of Melt (steel/aluminum was melted)
   - Country of Cast (steel/aluminum was cast)
   - Primary Country of Smelt (aluminum only)
3. **Declaration Type Code**:
   - `08` for steel
   - `07` for aluminum

### HTS Code Coverage

Not all steel/aluminum products are subject to Section 232. The tariff list contains specific HTS codes that are covered.

**Example**:
- `7308.90.6000` - Structural steel (covered by Section 232)
- `9403.20.0082` - Metal furniture (not covered, even if contains steel)

## Benefits

1. **Automated Compliance**: Automatically identify Section 232 items
2. **Validation**: Cross-check material percentages against HTS classification
3. **Reporting**: Generate Section 232 summary reports
4. **Accuracy**: Reduce manual lookup errors
5. **Speed**: Fast database lookups (indexed)

## Maintenance

### Updating the Tariff List

When CBP updates Section 232 tariff codes:

1. Update `Resources/CBP_data/CBP_232_tariffs.xlsx` with new codes
2. Run `python import_232_tariffs.py` to reimport
3. Test with `python test_section_232_lookup.py`

### Updating the Actions List

When CBP updates Section 232 actions:

1. Update `Resources/CBP_data/Section_232_Actions.csv` with new actions
2. Run `python import_232_actions.py` to reimport
3. Test with `python test_section_232_actions.py`

### Adding New Material Types

To add copper, wood, or other Section 232 materials to tariff list:

1. Add new column to Excel file (e.g., "copper tariffs")
2. Update `import_232_tariffs.py` to import new column
3. Update API methods to handle new material type

Note: Copper and wood actions are already included in the actions table.

## Related Documentation

- [CBP_DERIVATIVE_SPLITTING.md](CBP_DERIVATIVE_SPLITTING.md) - Derivative row splitting process
- [CBP_EXPORT_WORKFLOW.md](CBP_EXPORT_WORKFLOW.md) - Complete workflow
- [PARTS_DATABASE_UPDATE.md](PARTS_DATABASE_UPDATE.md) - Parts database schema
- [COMPLETE_CBP_FEATURE_SUMMARY.md](COMPLETE_CBP_FEATURE_SUMMARY.md) - All CBP features

## Version Information

- **Implementation Date**: December 14, 2025
- **OCRMill Version**: v2.3.0
- **Data Sources**:
  - CBP Section 232 tariff list (475 HTS codes: 285 steel, 190 aluminum)
  - CBP Section 232 actions list (63 action tariffs)
- **Database Tables**: 2 (section_232_tariffs, section_232_actions)
- **API Methods**: 12 (7 for tariffs, 5 for actions)
