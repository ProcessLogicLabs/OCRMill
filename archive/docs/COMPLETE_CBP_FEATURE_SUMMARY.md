# Complete CBP Export Feature Summary - December 14, 2025

## Overview
This document provides a complete summary of all CBP Export features implemented on December 14, 2025, including BOL weight extraction, parts database integration, derivative row splitting, and Section 232 classification.

## Feature 1: BOL Weight Extraction

### Purpose
Automatically extract total shipment weight from Bill of Lading documents within PDFs and use for CBP export proration calculations.

### Implementation
- **New Template**: `templates/bill_of_lading.py`
- **Detection**: Scans for BOL markers ("Bill of Lading", "SHIPPER", "CONSIGNEE")
- **Extraction**: Multiple regex patterns for weight in KG
- **CSV Columns Added**:
  - `bol_gross_weight`: Total BOL shipment weight (for proration)
  - `net_weight`: Item-level weight (populated from BOL when not in invoice)

### Workflow
1. PDF is processed through Invoice Processing tab
2. System detects BOL page and extracts gross weight (e.g., 4950.000 kg)
3. Weight is added to all invoice line items in CSV
4. CBP Export tab reads weight from CSV and displays in "Total Shipment Weight" field
5. Weight is used for proration calculations

### Key Features
- **Auto-population**: Total Shipment Weight field is read-only, auto-populated from CSV
- **Non-destructive**: Preserves template-extracted weights when available
- **Flexible**: Works with multi-invoice PDFs, applies weight to all items

**Documentation**: [BOL_IMPLEMENTATION_SUMMARY.md](BOL_IMPLEMENTATION_SUMMARY.md)

---

## Feature 2: Parts Database Schema Update

### Purpose
Expand parts database to support complete material composition tracking (6 material types) and additional metadata for CBP compliance.

### Changes Made
**Old Schema**: Limited to steel/aluminum percentages, historical tracking
**New Schema**: 6 material types, country origin, quantity units, Section 301 exclusion

### New Columns
- `country_origin`: Country of origin code (CZ, BR, DK, etc.)
- `copper_pct`: Copper percentage (0-100)
- `wood_pct`: Wood percentage (0-100)
- `auto_pct`: Auto percentage (0-100)
- `non_steel_pct`: Non-Section 232 percentage (0-100)
- `qty_unit`: Quantity unit (KG, NO, NO/KG)
- `sec301_exclusion_tariff`: Section 301 exclusion code
- `last_updated`: Last update timestamp

### Migration
- **Script**: `rebuild_parts_database.py`
- **Source**: `reports/parts_MMCITE.xlsx`
- **Results**: 255 parts imported, 249 with HTS codes (97.6% coverage)
- **Backup**: Created before migration for rollback

**Documentation**: [PARTS_DATABASE_UPDATE.md](PARTS_DATABASE_UPDATE.md)

---

## Feature 3: CBP Export Derivative Row Splitting

### Purpose
Split invoice line items into multiple rows based on material composition percentages, prorate value and weight, and apply Section 232 declaration codes.

### How It Works

#### Step 1: Parts Database Enrichment
When processing CSV in CBP Export tab:
1. Look up each part in `Resources/parts_database.db`
2. Add material percentages: steel, aluminum, copper, wood, auto, non_steel
3. Add HTS code, MID, country_origin, qty_unit, Section 301 exclusion

**Example**:
```
Original: part_number=STE110-002000, quantity=6, total_price=493.30
Enriched: steel_pct=0, aluminum_pct=0, non_steel_pct=100, hts_code=9403.20.0082, mid=CZMMCCAS907UHE
```

#### Step 2: Derivative Row Splitting (Millworks)
InvoiceProcessor splits each row by material type:

**Input**: 1 row with mixed materials (60% steel, 40% aluminum, value $1000)
**Output**: 2 rows
- Row 1: 60% steel, value $600 (60% of $1000), 232_Status=232_Steel
- Row 2: 40% aluminum, value $400 (40% of $1000), 232_Status=232_Aluminum

#### Step 3: Weight Proration
Total BOL shipment weight distributed **by value proportion**:

**Example**:
- Total shipment: 4950 kg
- Total value: $4000
- Item 1 (steel, $600): 742.5 kg (600/4000 × 4950)
- Item 2 (aluminum, $400): 495.0 kg (400/4000 × 4950)

#### Step 4: Section 232 Classification

Each derivative row gets:

**DecTypeCd** (declaration type code):
- `08` - Steel (does not use 232 toggle)
- `07` - Aluminum (uses 232 toggle in e2Open)
- `09` - Reserved type (uses 232 toggle in e2Open)
- `10` - Wood (uses 232 toggle in e2Open)
- `11` - Copper (uses 232 toggle in e2Open)

**232_Status** (e2Open customs toggle):
- Material flags: `232_Steel`, `232_Aluminum`, `232_Copper`, `232_Wood`, `232_Auto`, `Non_232`
- **Primary Purpose**: Acts as a toggle in e2Open customs management system
- **Applies to**: Declaration types 07, 09, 10, and 11
- **Usage**: Helps customs brokers identify items requiring Section 232 tariff declarations

**Country Codes** (from MID or database):
- `CountryofMelt`: Country where material was melted (e.g., CZ)
- `CountryOfCast`: Country where material was cast (e.g., CZ)
- `PrimCountryOfSmelt`: Primary country of smelt (e.g., CZ)

**Quantity Calculation** (based on qty_unit):
- `KG`: Qty1 = weight in kg
- `NO`: Qty1 = piece count
- `NO/KG`: Qty1 = piece count, Qty2 = weight in kg

#### Step 5: Split by Invoice and Export
- Separate Excel files created per invoice_number
- Each file contains 15 CBP-required columns
- CSV moved to Processed subfolder
- Status updated to "Exported"

**Documentation**: [CBP_DERIVATIVE_SPLITTING.md](CBP_DERIVATIVE_SPLITTING.md)

---

## Feature 4: CBP Export UI Improvements

### Total Shipment Weight Display
**Old Behavior**: User entered weight, saved in config
**New Behavior**:
- Read-only field, auto-populated from selected CSV
- Reads `bol_gross_weight` column from CSV
- Shows "0" if no BOL weight found
- Updates when user selects different CSV file

**Implementation**: `_on_cbp_file_select()` event handler (lines 1295-1333)

### Output Folder Control
**Old Behavior**: Hard-coded subdirectory `cbp_export_processed`
**New Behavior**: Files saved directly to user-selected output folder

**Implementation**: Removed subdirectory creation (line 1459)

### File Status Detection
**Old Behavior**: Looked for original CSV filename
**New Behavior**: Looks for split invoice files with pattern `{invoice_number}_{date}.xlsx`

**Implementation**: Glob pattern matching (lines 1277-1294)

### CSV File Movement
**New Feature**: After successful processing, CSV moved to `Processed/` subfolder

**Features**:
- Creates subfolder if doesn't exist
- Handles duplicate filenames with counter
- Logs movement in processing log

**Implementation**: Post-processing cleanup (lines 1511-1527)

---

## Complete Workflow Example

### Step 1: PDF Processing (Invoice Processing Tab)

**Input**: PDF containing BOL + multiple invoices
```
Page 1: Invoice 2025201881 (8 items)
Page 2: Invoice 2025201883 (6 items)
Page 3: Bill of Lading (GROSS WEIGHT: 4950.000 KG)
```

**Processing**:
1. System detects BOL and extracts weight: 4950.000 kg
2. Processes invoice pages, extracts line items
3. Applies BOL weight to all items

**Output CSV** (`output/Processed/2025201887_20251214.csv`):
```csv
invoice_number,part_number,quantity,total_price,net_weight,bol_gross_weight
2025201881,STE110-002000,6,493.30,4950.000,4950.000
2025201881,ND501,8,63.76,4950.000,4950.000
2025201883,BENCH-A100,2,1200.00,4950.000,4950.000
```

### Step 2: CBP Export Processing (CBP Export Tab)

**User Actions**:
1. Selects CSV from file list
2. Total Shipment Weight auto-populates: "4950.000"
3. Clicks "Process Selected"

**Processing Steps**:
1. **Enrichment**: Look up each part in database
   ```
   STE110-002000: steel_pct=0, aluminum_pct=0, non_steel_pct=100
   ND501: steel_pct=100, aluminum_pct=0, non_steel_pct=0
   BENCH-A100: steel_pct=60, aluminum_pct=40, non_steel_pct=0
   ```

2. **Derivative Splitting**: Expand mixed-material items
   ```
   BENCH-A100 → 2 rows:
     Row 1: 60% steel, value $720 (60% of $1200)
     Row 2: 40% aluminum, value $480 (40% of $1200)
   ```

3. **Weight Proration** (total value = $2,413.30, total weight = 4950 kg):
   ```
   STE110-002000 ($493.30): 1,012.3 kg (20.4%)
   ND501 ($63.76): 130.8 kg (2.6%)
   BENCH-A100 steel ($720): 1,477.0 kg (29.8%)
   BENCH-A100 aluminum ($480): 984.7 kg (19.9%)
   ```

4. **Section 232 Codes**:
   ```
   STE110-002000: DecTypeCd=(empty), 232_Status=Non_232
   ND501: DecTypeCd=08, 232_Status=232_Steel
   BENCH-A100 steel: DecTypeCd=08, 232_Status=232_Steel
   BENCH-A100 aluminum: DecTypeCd=07, 232_Status=232_Aluminum (232 toggle applies)
   ```

5. **Split by Invoice and Export**:
   ```
   Output Files:
   - 2025201881_20251214.xlsx (2 items: STE110-002000, ND501)
   - 2025201883_20251214.xlsx (2 items: BENCH-A100 steel, BENCH-A100 aluminum)
   ```

6. **Cleanup**:
   - CSV moved to `Processed/2025201887_20251214.csv`
   - Status updated to "Exported"

---

## Output Format

### CBP Export Excel Files
Each file contains exactly **15 columns**:

| # | Column | Description | Example |
|---|--------|-------------|---------|
| 1 | Product No | Part number | STE110-002000 |
| 2 | ValueUSD | Value in USD | 493.30 |
| 3 | HTSCode | Harmonized Tariff Schedule | 9403.20.0082 |
| 4 | MID | Manufacturer ID | CZMMCCAS907UHE |
| 5 | Qty1 | Quantity 1 | 6 |
| 6 | Qty2 | Quantity 2 | (blank) |
| 7 | DecTypeCd | Declaration Type Code | 08 |
| 8 | CountryofMelt | Country of Melt | CZ |
| 9 | CountryOfCast | Country of Cast | CZ |
| 10 | PrimCountryOfSmelt | Primary Country of Smelt | CZ |
| 11 | PrimSmeltFlag | Primary Smelt Flag | (blank) |
| 12 | SteelRatio | Steel percentage | 100.0% |
| 13 | AluminumRatio | Aluminum percentage | 0.0% |
| 14 | NonSteelRatio | Non-steel percentage | 0.0% |
| 15 | 232_Status | Section 232 toggle | 232_Steel |

**File Naming**: `{invoice_number}_{date}.xlsx` (e.g., `2025201881_20251214.xlsx`)

---

## Key Technical Details

### 232_Status Field Usage

**Purpose**: Acts as a toggle in the e2Open customs management system

**Applies to Declaration Types**:
- `07` - Aluminum (232 toggle required)
- `09` - Reserved type (232 toggle required)
- `10` - Wood (232 toggle required)
- `11` - Copper (232 toggle required)

**Does NOT apply to**:
- `08` - Steel (uses different mechanism)
- Other types

**Values**:
- `232_Steel` - Steel content (does not use toggle)
- `232_Aluminum` - Aluminum content (uses toggle)
- `232_Copper` - Copper content (uses toggle)
- `232_Wood` - Wood content (uses toggle)
- `232_Auto` - Automotive content (may use toggle)
- `Non_232` - Non-Section 232 materials (no toggle)

### Material Composition Rules

**Sum Must Equal 100%**:
```
steel_pct + aluminum_pct + copper_pct + wood_pct + auto_pct + non_steel_pct = 100
```

**Pure Materials**: Generate single derivative row
```
Input: Part with 100% steel → Output: 1 row (100% steel)
```

**Mixed Materials**: Generate multiple derivative rows
```
Input: Part with 60% steel, 40% wood → Output: 2 rows (60% steel row + 40% wood row)
```

### Country Code Priority

Country codes populated in this order:
1. From parts database (`country_origin` field)
2. From MID prefix (first 2 characters)
   - Example: `CZMMCCAS907UHE` → `CZ`

All three country fields use the same value:
- `CountryofMelt` = country code
- `CountryOfCast` = country code
- `PrimCountryOfSmelt` = country code

---

## Files Modified Summary

### Core Application Files
1. **invoice_processor_gui.py**
   - Lines 50: Added BOL template import
   - Lines 131-145: BOL detection and weight extraction
   - Lines 173-175: Skip BOL pages during invoice processing
   - Lines 191-193, 213-215: Apply BOL weight to items
   - Lines 1153-1158: Total Shipment Weight display (read-only)
   - Lines 1277-1294: File status detection (split invoice files)
   - Lines 1295-1333: CSV file selection event handler
   - Lines 1452-1500: Parts database enrichment
   - Lines 1511-1527: CSV file movement to Processed folder
   - Lines 1525-1545: 232_Status column conversion and percentage formatting

2. **config_manager.py**
   - Lines 21-24: Removed cbp_net_weight from config
   - Removed: cbp_net_weight property methods

3. **parts_database.py**
   - Lines 41-61: Updated schema with new columns
   - Lines 236-296: Simplified update logic for new schema
   - Lines 419-511: Import support for new material columns
   - Lines 639-664: Export with new columns
   - Lines 669-700: Statistics calculation update
   - Lines 721-728: Update HTS with last_updated

### Template Files
4. **templates/bill_of_lading.py** (NEW)
   - Complete BOL template implementation

5. **templates/__init__.py**
   - Added BillOfLadingTemplate to registry

6. **templates/sample_template.py**
   - Added net_weight to example extra_columns

### Utility Scripts
7. **rebuild_parts_database.py** (NEW)
   - Database migration script

### Documentation Files (NEW)
8. **BOL_IMPLEMENTATION_SUMMARY.md** - BOL weight extraction details
9. **PARTS_DATABASE_UPDATE.md** - Parts database schema changes
10. **CBP_DERIVATIVE_SPLITTING.md** - Derivative row splitting process
11. **CBP_EXPORT_WORKFLOW.md** - Complete workflow guide
12. **COMPLETE_CBP_FEATURE_SUMMARY.md** - This document

---

## Testing and Validation

### Test Files
- **Sample PDF**: `C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\2025201887 - mmcité usa - US25A0255 (1).pdf`
- **Sample Parts List**: `C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\parts_MMCITE.xlsx`

### Test Results
- ✅ BOL detection: 100% success
- ✅ Weight extraction: 4950.000 kg correctly extracted
- ✅ Parts database import: 255 parts, 97.6% HTS coverage
- ✅ Material enrichment: All parts successfully looked up
- ✅ Derivative splitting: Mixed materials correctly split
- ✅ Weight proration: Values sum to 100% of total weight
- ✅ Section 232 codes: Correctly assigned per material type
- ✅ File splitting: One file per invoice_number
- ✅ CSV movement: Files moved to Processed folder
- ✅ Status tracking: "Exported" status correctly displayed

---

## Benefits

1. **Automation**: No manual weight entry or material composition entry
2. **Accuracy**: Weight extracted directly from BOL, material data from database
3. **Compliance**: Proper Section 232 classification for CBP
4. **Transparency**: Clear breakdown of mixed-material items
5. **Efficiency**: Automatic file organization and status tracking
6. **Flexibility**: Handles multi-invoice PDFs, pure and mixed materials
7. **Integration**: Seamless workflow from PDF to CBP-ready Excel files

---

## Version Information

- **Implementation Date**: December 14, 2025
- **OCRMill Version**: v2.3.0
- **Millworks Version**: Latest (submodule)
- **Features**: BOL extraction, parts database integration, derivative splitting, Section 232 classification

---

## Related Documentation

- [BOL_IMPLEMENTATION_SUMMARY.md](BOL_IMPLEMENTATION_SUMMARY.md) - BOL weight extraction
- [PARTS_DATABASE_UPDATE.md](PARTS_DATABASE_UPDATE.md) - Database schema update
- [CBP_DERIVATIVE_SPLITTING.md](CBP_DERIVATIVE_SPLITTING.md) - Derivative row splitting
- [CBP_EXPORT_WORKFLOW.md](CBP_EXPORT_WORKFLOW.md) - Complete workflow
- [CBP_EXPORT_FORMAT.md](CBP_EXPORT_FORMAT.md) - Output column specifications
