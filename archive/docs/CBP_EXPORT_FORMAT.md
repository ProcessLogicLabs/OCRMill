# CBP Export Format - Column Configuration

## Overview
The CBP Export functionality now produces Excel files matching the exact format required for customs documentation, excluding unnecessary columns and maintaining the correct column order.

## Implementation Date
December 14, 2025

## Required Output Format

The CBP export produces files with exactly **15 columns** in this order:

| # | Column Name | Description | Example |
|---|-------------|-------------|---------|
| 1 | Product No | Part number | STE110-002000 |
| 2 | ValueUSD | Value in USD | 493.30 |
| 3 | HTSCode | Harmonized Tariff Schedule code | 9403.20.0082 |
| 4 | MID | Manufacturer ID | CZMMCCAS907UHE |
| 5 | Qty1 | Quantity 1 | 6 |
| 6 | Qty2 | Quantity 2 | (blank or value) |
| 7 | DecTypeCd | Declaration Type Code | 8 |
| 8 | CountryofMelt | Country of Melt | CZ |
| 9 | CountryOfCast | Country of Cast | CZ |
| 10 | PrimCountryOfSmelt | Primary Country of Smelt | CZ |
| 11 | PrimSmeltFlag | Primary Smelt Flag | (blank or value) |
| 12 | SteelRatio | Steel percentage | 100.0% |
| 13 | AluminumRatio | Aluminum percentage | 0.0% |
| 14 | NonSteelRatio | Non-steel percentage | 0.0% |
| 15 | 232_Status | Section 232 status | 232_Steel, Non_232, etc. |

## Columns Excluded

The following columns are **intentionally excluded** from the CBP export:

- ❌ `description` - Not required for CBP documentation
- ❌ `CopperRatio` - Not in CBP format
- ❌ `WoodRatio` - Not in CBP format
- ❌ `AutoRatio` - Not in CBP format
- ❌ `invoice_number` - Handled by file splitting
- ❌ `project_number` - Handled by file splitting
- ❌ Internal processing columns (`_232_flag`, `_content_type`, `_not_in_db`, etc.)

## Implementation Details

### File Modified
**[invoice_processor_gui.py](invoice_processor_gui.py:1391-1403)** - CBP Export column filtering

### Code Implementation
```python
# Define CBP export column order (matches required output format)
cbp_columns = [
    'Product No', 'ValueUSD', 'HTSCode', 'MID', 'Qty1', 'Qty2',
    'DecTypeCd', 'CountryofMelt', 'CountryOfCast', 'PrimCountryOfSmelt',
    'PrimSmeltFlag', 'SteelRatio', 'AluminumRatio', 'NonSteelRatio', '232_Status'
]

# Filter to only columns that exist in the data
export_columns = [col for col in cbp_columns if col in result.data.columns]
export_result = processor.export(result.data, str(output_path), columns=export_columns)
```

## How It Works

1. **Column Definition**: A predefined list of exactly 15 CBP-required columns in the correct order
2. **Filtering**: Only includes columns that actually exist in the processed data
3. **Export**: Passes the filtered column list to the InvoiceProcessor export method
4. **Result**: Clean Excel files with only the necessary columns

## Benefits

1. **Compliance**: Matches CBP documentation requirements exactly
2. **Clean Output**: No extraneous columns to confuse or clutter the spreadsheet
3. **Consistency**: Same format every time, regardless of processing variations
4. **Maintainability**: Easy to update if CBP requirements change

## Example Output

Reference file: `C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\2025201881_20251214.xlsx`

Sample data:
```
Product No      ValueUSD  HTSCode       MID              Qty1  DecTypeCd  SteelRatio  232_Status
STE110-002000   493.30    9403.20.0082  CZMMCCAS907UHE   6     8          0.0%        Non_232
ND501           63.76     7308.90.6000  CZMMCCAS907UHE   8     8          100.0%      232_Steel
```

## Notes

- Column order is preserved exactly as defined in `cbp_columns` list
- Missing columns are gracefully handled (only exports columns that exist)
- All material type ratios are included (Steel, Aluminum, NonSteel)
- Section 232 status column provides material classification
- DecTypeCd typically defaults to "8" (Country of Origin declaration)

## Related Documentation

- [BOL_IMPLEMENTATION_SUMMARY.md](BOL_IMPLEMENTATION_SUMMARY.md) - BOL weight extraction for net_weight calculations
- Sample output: `reports/2025201881_20251214.xlsx` - Reference format
