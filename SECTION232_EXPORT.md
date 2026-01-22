# Section 232 Steel/Aluminum Declaration Export

## Overview

The Section 232 Export feature generates CBP-compliant Steel and Aluminum Declaration exports from processed invoice data. It reads CSV files, enriches them with material composition data from the parts database, and creates properly formatted Excel exports with material-specific row expansion.

## How It Works

### 1. Material Composition Lookup

For each part number in the processed CSVs, the exporter queries the parts database for:
- `steel_pct` - Steel percentage (0-100)
- `aluminum_pct` - Aluminum percentage (0-100)
- `copper_pct` - Copper percentage (0-100)
- `wood_pct` - Wood percentage (0-100)
- `auto_pct` - Automotive percentage (0-100)
- `non_steel_pct` - Non-Section 232 percentage (0-100)

### 2. Row Expansion by Material

Each invoice line item is expanded into multiple "derivative rows" based on material composition:

**Example:**
```
Original Row:
- Part: ABC123
- Value: $1000
- Steel: 60%, Aluminum: 30%, Non-232: 10%

Expanded Rows:
1. Steel row: $600 (60% of $1000) - Flag: 232_Steel
2. Aluminum row: $300 (30% of $1000) - Flag: 232_Aluminum
3. Non-232 row: $100 (10% of $1000) - Flag: Non_232
```

### 3. Declaration Flags

Each derivative row is assigned a declaration flag:
- `232_Steel` - Steel content (DecTypeCd: 08)
- `232_Aluminum` - Aluminum content (DecTypeCd: 07)
- `232_Copper` - Copper content (DecTypeCd: 11)
- `232_Wood` - Wood content (DecTypeCd: 10)
- `232_Auto` - Automotive content
- `Non_232` - Non-Section 232 content

### 4. Country Declarations

Country information is populated based on material type:
- **Steel, Aluminum, Copper**: CountryofMelt
- **Aluminum**: CountryOfCast
- **Aluminum, Copper, Wood**: PrimCountryOfSmelt

### 5. Quantity Calculations (Qty1/Qty2)

Quantities are calculated based on the `qty_unit` from the parts database:

**Weight-only units** (KG, G, T):
- Qty1 = Weight
- Qty2 = Empty

**Count-only units** (NO, PCS, DOZ):
- Qty1 = Quantity
- Qty2 = Weight (for derivative rows per CBP requirement)

**Dual units**:
- Qty1 = Quantity
- Qty2 = Weight

### 6. Excel Export Formatting

The Excel export includes:

**Color Coding** (Font Colors):
- Steel: Dark gray (#4a4a4a)
- Aluminum: Cornflower blue (#6495ED)
- Copper: Copper (#B87333)
- Wood: Saddle brown (#8B4513)
- Auto: Dark slate gray (#2F4F4F)
- Non-232: Red (#FF0000)

**Dual Declaration Highlighting**:
- Rows with both Steel AND Aluminum > 0 are highlighted with light purple fill (#E1BEE7)
- DualDeclaration column shows "07 & 08"

## Usage

### From UI

1. **Process Invoices** - Process PDFs normally to generate CSV files in `output/Processed`
2. **Ensure Parts Database is Populated** - Material composition data must be in the parts database
3. **Click "Section 232 Export"** button in the Invoice Processing tab
4. **Review Output** - Excel files are generated in `output/Section232_Export/`

### From Command Line

```bash
python section232_exporter.py <input_folder> <output_folder> <db_path>
```

**Example:**
```bash
python section232_exporter.py output/Processed output/Section232_Export Resources/parts_database.db
```

## Export Columns

| Column | Description |
|--------|-------------|
| Product No | Part number |
| ValueUSD | Proportional value for this material |
| HTSCode | Harmonized Tariff Code |
| MID | Manufacturer ID |
| Qty1 | Primary quantity (count or weight) |
| Qty2 | Secondary quantity (usually weight) |
| DecTypeCd | Declaration type code (07=Aluminum, 08=Steel, etc.) |
| CountryofMelt | Country of melt (steel/aluminum/copper) |
| CountryOfCast | Country of cast (aluminum) |
| PrimCountryOfSmelt | Primary country of smelt (aluminum/copper/wood) |
| DeclarationFlag | Material flag (232_Steel, 232_Aluminum, Non_232, etc.) |
| SteelRatio | Steel percentage |
| AluminumRatio | Aluminum percentage |
| CopperRatio | Copper percentage |
| WoodRatio | Wood percentage |
| AutoRatio | Automotive percentage |
| NonSteelRatio | Non-Section 232 percentage |
| DualDeclaration | "07 & 08" if both steel and aluminum present |
| 232_Status | Section 232 status |
| CustomerRef | Project/reference number |

## Material Composition Setup

Material percentages must be maintained in the parts database. There are several ways to populate this data:

### 1. Import from CSV/Excel
Use the Parts Database tab to import parts master data with material composition columns:
- steel_pct
- aluminum_pct
- copper_pct
- wood_pct
- auto_pct
- non_steel_pct

### 2. Manual Entry
Edit parts individually in the Parts Database tab and set material percentages.

### 3. Shared Database with TariffMill
If using a shared database (see SHARED_CONFIG.md), material composition data from TariffMill is automatically available.

## Requirements

- **Python packages**: `openpyxl` (for Excel export)
- **Parts database**: Must contain material composition data for parts
- **Processed CSVs**: Must have at least: part_number, total_price, quantity, net_weight

## Troubleshooting

### "No processed CSV files found"
- Process some invoice PDFs first
- Check that CSV files exist in `output/Processed/`

### "All rows show 0% material composition"
- Material data is not in the parts database
- Import parts master data with material percentages
- Or edit parts individually to set composition

### "Quantities are incorrect"
- Check that `qty_unit` is set correctly in parts database
- Verify net_weight and quantity fields in processed CSVs

### "Country fields are empty"
- Ensure `country_origin` or `mid` fields are populated in parts database
- Country is extracted from MID (first 2 characters) or country_origin field

## CBP Compliance Notes

This export follows TariffMill's Section 232 export logic:

1. **Material Expansion** - Each line item is expanded into derivative rows per material type
2. **Value Distribution** - Values are proportionally distributed based on material percentages
3. **Qty2 Requirement** - All derivative rows include Qty2 (weight) per CBP requirement
4. **Declaration Codes** - Proper declaration codes assigned (07=Aluminum, 08=Steel, 11=Copper, 10=Wood)
5. **Country Declarations** - Country information populated based on material-specific requirements
6. **Dual Declarations** - Items with both steel and aluminum are flagged appropriately

## Version History

- **v0.99.14** - Initial Section 232 export implementation
