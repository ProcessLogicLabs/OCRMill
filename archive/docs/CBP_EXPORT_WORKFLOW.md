# CBP Export Workflow - Complete Guide

## Overview
The CBP Export process takes consolidated invoice CSV files and creates separate Excel files per invoice with Section 232 classification and weight proration.

## Complete Workflow

### Step 1: Invoice Processing (PDF → CSV)
**Tab**: Invoice Processing

1. PDFs are processed through OCRMill
2. BOL (Bill of Lading) gross weight is automatically extracted (e.g., 4950.000 kg)
3. Invoice line items are extracted
4. Output CSV includes columns:
   - `bol_gross_weight`: Total shipment weight from BOL (same value for all items)
   - `net_weight`: Item-level weight (populated from BOL if not in invoice)
   - Standard columns: invoice_number, part_number, quantity, total_price, etc.

**Output Location**: `output/Processed/`
**Example File**: `Mmcite ISF_CHARLOTTE UEUR2917125002_20251213_233517.csv`

### Step 2: CBP Export Processing (CSV → Split Excel Files)
**Tab**: CBP Export

**Settings**:
- **Input Folder**: `output/Processed/` (or `output/` - where CSV files are)
- **Output Folder**: `output/CBP_Export/`
- **Total Shipment Weight**: Leave as `0` to auto-detect from CSV

**Process**:
1. Reads consolidated CSV file (may contain multiple invoices)
2. Detects `bol_gross_weight` column and uses first value as total shipment weight
3. Processes through InvoiceProcessor (DerivativeMill):
   - Looks up HTS codes in tariff database
   - Calculates Section 232 status (Steel, Aluminum, Non-232, etc.)
   - Prorates total shipment weight across line items by value
   - Adds DecTypeCd, CountryofMelt, and other CBP fields
4. Splits by `invoice_number` into separate Excel files
5. Exports only 15 CBP-required columns per file

**Output Location**: User-selected Output Folder (e.g., `output/CBP_Export/`)
**Output Files**: One file per invoice
- `2025601840_20251214.xlsx`
- `2025601843_20251214.xlsx`
- `2025601844_20251214.xlsx`
- etc.

## Weight Proration Logic

### How Total Shipment Weight is Used

The `bol_gross_weight` (e.g., 4950.000 kg) is the **total shipment weight** that needs to be distributed across all line items in the invoice.

**Proration Formula** (by value):
```
Item Weight = (Item Value / Total Invoice Value) × Total Shipment Weight
```

**Example**:
- Total Shipment Weight: 4950.000 kg
- Total Invoice Value: $4,000.00

| Item | Value | % of Total | Prorated Weight |
|------|-------|------------|-----------------|
| BENCH-A100 | $1,500.00 | 37.5% | 1,856.25 kg |
| TABLE-B200 | $2,500.00 | 62.5% | 3,093.75 kg |
| **Total** | **$4,000.00** | **100%** | **4,950.00 kg** |

## Understanding the Weight Fields

### bol_gross_weight
- **Source**: Extracted from Bill of Lading in PDF
- **Value**: Total shipment weight (e.g., "4950.000")
- **Usage**: Reference weight for proration calculations
- **Location**: Saved in consolidated CSV from Invoice Processing

### net_weight (in CSV)
- **Source**: BOL gross weight or invoice template extraction
- **Value**: May be same as bol_gross_weight if invoice doesn't specify item weights
- **Usage**: Fallback if no proration is needed

### Total Shipment Weight (GUI field)
- **Purpose**: Override weight for CBP processing
- **Default**: 0 (auto-detect from `bol_gross_weight` column)
- **When to use**: Manually specify weight if CSV doesn't have BOL data
- **How it works**: This weight is passed to InvoiceProcessor for proration

## CBP Export Output Format

Each exported Excel file contains exactly **15 columns**:

| # | Column | Description | Example |
|---|--------|-------------|---------|
| 1 | Product No | Part number | STE110-002000 |
| 2 | ValueUSD | Value in USD | 493.30 |
| 3 | HTSCode | Harmonized Tariff Schedule | 9403.20.0082 |
| 4 | MID | Manufacturer ID | CZMMCCAS907UHE |
| 5 | Qty1 | Quantity 1 | 6 |
| 6 | Qty2 | Quantity 2 | (blank) |
| 7 | DecTypeCd | Declaration Type | 8 |
| 8 | CountryofMelt | Country of Melt | CZ |
| 9 | CountryOfCast | Country of Cast | CZ |
| 10 | PrimCountryOfSmelt | Primary Country of Smelt | CZ |
| 11 | PrimSmeltFlag | Primary Smelt Flag | (blank) |
| 12 | SteelRatio | Steel percentage | 100.0% |
| 13 | AluminumRatio | Aluminum percentage | 0.0% |
| 14 | NonSteelRatio | Non-steel percentage | 0.0% |
| 15 | 232_Status | Section 232 status | 232_Steel, Non_232 |

**Excluded Columns**: description, invoice_number, project_number, net_weight, bol_gross_weight, and all internal processing columns

## File Naming Convention

**CSV Files** (from Invoice Processing):
- Format: `{original_pdf_name}_{timestamp}.csv`
- Example: `Mmcite ISF_CHARLOTTE UEUR2917125002_20251213_233517.csv`

**Excel Files** (from CBP Export):
- Format: `{invoice_number}_{date}.xlsx`
- Example: `2025601840_20251214.xlsx`
- Date is current date in YYYYMMDD format

## Troubleshooting

### "Total Shipment Weight is 0"
**Cause**: CSV file doesn't have `bol_gross_weight` column
**Solution**:
1. Re-process the PDF through Invoice Processing (with updated BOL template)
2. OR manually enter weight in "Total Shipment Weight" field

### "No invoice_number column"
**Cause**: CSV file is missing invoice_number
**Solution**: Ensure the PDF was processed with a template that extracts invoice numbers

### "No items extracted"
**Cause**: BOL template was selected instead of invoice template
**Solution**: Already fixed - BOL template now returns confidence score of 0.0

## Related Documentation

- [BOL_IMPLEMENTATION_SUMMARY.md](BOL_IMPLEMENTATION_SUMMARY.md) - BOL weight extraction details
- [CBP_EXPORT_FORMAT.md](CBP_EXPORT_FORMAT.md) - Column specifications
- [COMPLETE_UPDATES_SUMMARY.md](COMPLETE_UPDATES_SUMMARY.md) - All system updates

## Version Information

- **Last Updated**: December 14, 2025
- **OCRMill Version**: v2.3.0
- **Feature**: BOL weight extraction + CBP export split by invoice
