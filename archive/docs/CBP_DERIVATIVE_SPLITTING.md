# CBP Export - Derivative Row Splitting & Section 232 Processing

## Overview
The CBP Export process automatically splits invoice line items into derivative rows based on material composition percentages and applies Section 232 declaration codes, country codes, and weight proration.

## Implementation Date
December 14, 2025

## How It Works

### Step 1: Data Enrichment from Parts Database

When processing a CSV file, the system:

1. **Looks up each part in the parts database** (`Resources/parts_database.db`)
2. **Enriches the row with**:
   - `steel_pct` - Steel percentage (0-100)
   - `aluminum_pct` - Aluminum percentage (0-100)
   - `copper_pct` - Copper percentage (0-100)
   - `wood_pct` - Wood percentage (0-100)
   - `auto_pct` - Auto percentage (0-100)
   - `non_steel_pct` - Non-232 percentage (0-100)
   - `hts_code` - Harmonized Tariff Schedule code
   - `mid` - Manufacturer ID
   - `country_origin` - Country of origin
   - `qty_unit` - Quantity unit (KG, NO, NO/KG)
   - `Sec301_Exclusion_Tariff` - Section 301 exclusion code

**Example**:
```
Original row:
  part_number: STE110-002000
  quantity: 6
  total_price: 493.30

After enrichment:
  part_number: STE110-002000
  quantity: 6
  total_price: 493.30
  steel_pct: 0
  aluminum_pct: 0
  copper_pct: 0
  wood_pct: 0
  auto_pct: 0
  non_steel_pct: 100
  hts_code: 9403.20.0082
  mid: CZMMCCAS907UHE
  qty_unit: NO
```

### Step 2: Derivative Row Splitting

The InvoiceProcessor (Millworks) splits each row based on material composition:

**Input**: 1 row with mixed materials
```
Part: BENCH-A100
Value: $1000.00
Steel: 60%
Aluminum: 40%
```

**Output**: 2 rows (derivatives)
```
Row 1 (Steel derivative):
  Part: BENCH-A100
  Value: $600.00 (60% of $1000)
  Steel: 60%
  Aluminum: 0%
  _content_type: steel

Row 2 (Aluminum derivative):
  Part: BENCH-A100
  Value: $400.00 (40% of $1000)
  Steel: 0%
  Aluminum: 40%
  _content_type: aluminum
```

### Step 3: Weight Proration

Total shipment weight is distributed across derivative rows **by value proportion**:

**Example**:
- Total shipment weight: 4950 kg (from BOL)
- Total invoice value: $4000.00
- Row 1 (steel): $600.00 → 742.5 kg (600/4000 × 4950)
- Row 2 (aluminum): $400.00 → 495.0 kg (400/4000 × 4950)

### Step 4: Section 232 Classification

Each derivative row is assigned:

1. **DecTypeCd** (declaration type code):
   - `08` - Steel declaration
   - `07` - Aluminum declaration (232 toggle applies)
   - `09` - Reserved declaration type (232 toggle applies)
   - `10` - Wood declaration (232 toggle applies)
   - `11` - Copper declaration (232 toggle applies)
   - (empty) - No declaration required

2. **232_Status** (e2Open customs management toggle):
   - Material type flags: `232_Steel`, `232_Aluminum`, `232_Copper`, `232_Wood`, `232_Auto`, `Non_232`
   - **Primary Purpose**: Acts as a toggle in e2Open system for declaration types 07, 09, 10, and 11
   - Used by customs management system to identify items requiring Section 232 declarations

3. **Country Codes** (sourced from MID or database):
   - `CountryofMelt` - Country of melt (e.g., CZ)
   - `CountryOfCast` - Country of cast (e.g., CZ)
   - `PrimCountryOfSmelt` - Primary country of smelt (e.g., CZ)
   - `PrimSmeltFlag` - Primary smelt flag (optional)

### Step 5: Quantity Calculation

Quantity fields are calculated based on `qty_unit`:

- **qty_unit = "KG"**: Qty1 = calculated weight in kg
- **qty_unit = "NO"**: Qty1 = piece count, Qty2 = (empty)
- **qty_unit = "NO/KG"**: Qty1 = piece count, Qty2 = weight in kg

## Complete Example

### Input CSV (from Invoice Processing)
```csv
invoice_number,part_number,quantity,total_price
2025201881,STE110-002000,6,493.30
2025201881,ND501,8,63.76
```

### After Parts Database Enrichment
```csv
invoice_number,part_number,quantity,total_price,steel_pct,aluminum_pct,non_steel_pct,hts_code,mid,qty_unit
2025201881,STE110-002000,6,493.30,0,0,100,9403.20.0082,CZMMCCAS907UHE,NO
2025201881,ND501,8,63.76,100,0,0,7308.90.6000,CZMMCCAS907UHE,NO
```

### After Derivative Splitting (Expanded Rows)
```csv
invoice_number,part_number,value_usd,steel_pct,aluminum_pct,non_steel_pct,_content_type,CalcWtNet
2025201881,STE110-002000,493.30,0,0,100,non_232,4378.6
2025201881,ND501,63.76,100,0,0,steel,565.4
```

### Final CBP Export Output
```csv
Product No,ValueUSD,HTSCode,MID,Qty1,Qty2,DecTypeCd,CountryofMelt,CountryOfCast,PrimCountryOfSmelt,PrimSmeltFlag,SteelRatio,AluminumRatio,NonSteelRatio,232_Status
STE110-002000,493.30,9403.20.0082,CZMMCCAS907UHE,6,,,,CZ,CZ,,0.0%,0.0%,100.0%,Non_232
ND501,63.76,7308.90.6000,CZMMCCAS907UHE,8,,08,CZ,CZ,CZ,,100.0%,0.0%,0.0%,232_Steel
```

## Material Composition Rules

### Percentages Must Add to 100%
The sum of all material percentages should equal 100%:
```
steel_pct + aluminum_pct + copper_pct + wood_pct + auto_pct + non_steel_pct = 100
```

### Pure Materials
Parts with 100% of one material generate a single derivative row:
```
Input:
  Part: BENCH-A100
  Steel: 100%

Output:
  1 row with 100% steel content
```

### Mixed Materials
Parts with multiple materials generate multiple derivative rows:
```
Input:
  Part: TABLE-B200
  Steel: 60%
  Wood: 40%

Output:
  Row 1: 60% value (steel)
  Row 2: 40% value (wood)
```

## Declaration Code Logic

The system applies declaration codes based on material type and HTS code:

1. **Steel (232_Steel)**: DecTypeCd = `08` (does not use 232 toggle)
2. **Aluminum (232_Aluminum)**: DecTypeCd = `07` (uses 232 toggle in e2Open)
3. **Reserved Type**: DecTypeCd = `09` (uses 232 toggle in e2Open)
4. **Wood (232_Wood)**: DecTypeCd = `10` (uses 232 toggle in e2Open)
5. **Copper (232_Copper)**: DecTypeCd = `11` (uses 232 toggle in e2Open)
6. **Auto (232_Auto)**: DecTypeCd = (varies by HTS, may use 232 toggle)
7. **Non-232**: DecTypeCd = (empty or varies by HTS, no 232 toggle)

**Important**: The 232_Status field acts as a toggle in the e2Open customs management system specifically for declaration types 07, 09, 10, and 11. This helps customs brokers identify which items require Section 232 tariff declarations.

## Country Code Logic

Country codes are populated in this priority order:

1. **From parts database** (if `country_origin` is set)
2. **From MID prefix** (first 2 characters)
   - Example: `CZMMCCAS907UHE` → `CZ`

All three country fields use the same value unless specifically overridden:
- `CountryofMelt` = country code
- `CountryOfCast` = country code
- `PrimCountryOfSmelt` = country code

## Files Involved

### Modified Files

1. **invoice_processor_gui.py** (lines 1452-1500)
   - Added parts database enrichment logic
   - Looks up each part and adds material percentages
   - Adds HTS codes, MID, qty_unit, and Section 301 exclusion
   - Logs enrichment statistics

2. **invoice_processor_gui.py** (lines 1525-1545)
   - Renames `_232_flag` to `232_Status` for export
   - Formats material ratios as percentages (e.g., "100%")
   - Logs exported column list

### Millworks Components

1. **Millworks/invoice_processor/core/processor.py**
   - `process_invoice_data()` - Main processing function
   - Expands rows by material content (lines 129-184)
   - Calculates weight proration (lines 188-193)
   - Assigns Section 232 flags (lines 206-261)

2. **Millworks/invoice_processor/core/exporter.py**
   - `export_to_excel()` - Excel export with color coding
   - Applies material-specific font colors
   - Highlights Section 301 exclusions

## Benefits

1. **Compliance**: Each material type is properly declared to CBP
2. **Accuracy**: Value and weight are proportionally distributed
3. **Transparency**: Each row shows exactly one material type
4. **Automation**: No manual splitting required
5. **Audit Trail**: Clear breakdown of mixed-material items

## Troubleshooting

### Issue: "Parts not found in database"
**Cause**: Part numbers in CSV don't match parts database
**Solution**:
1. Import parts list from `parts_MMCITE.xlsx`
2. Or update parts database with missing part numbers

### Issue: "All rows show 100% steel"
**Cause**: Parts database has default values (100% steel)
**Solution**: Update parts database with actual material percentages

### Issue: "Weight is not prorated correctly"
**Cause**: Total shipment weight is 0 or not detected
**Solution**:
1. Ensure BOL gross weight is in CSV (`bol_gross_weight` column)
2. Or manually enter weight in Total Shipment Weight field

### Issue: "DecTypeCd is empty"
**Cause**: HTS code not in tariff database or material type unknown
**Solution**:
1. Update `millworks.db` with missing HTS codes
2. Or ensure parts database has correct material percentages

## Related Documentation

- [CBP_EXPORT_WORKFLOW.md](CBP_EXPORT_WORKFLOW.md) - Complete CBP export workflow
- [CBP_EXPORT_FORMAT.md](CBP_EXPORT_FORMAT.md) - Output column specifications
- [PARTS_DATABASE_UPDATE.md](PARTS_DATABASE_UPDATE.md) - Parts database schema
- [BOL_IMPLEMENTATION_SUMMARY.md](BOL_IMPLEMENTATION_SUMMARY.md) - BOL weight extraction

## Version Information

- **Implementation Date**: December 14, 2025
- **OCRMill Version**: v2.3.0
- **Millworks Version**: Latest (submodule)
- **Feature**: Derivative row splitting with Section 232 classification
