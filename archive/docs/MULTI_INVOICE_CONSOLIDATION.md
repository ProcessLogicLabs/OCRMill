# Multi-Invoice Consolidation Feature

## Overview

Added a toggle to control how multi-invoice PDFs are exported:
- **Split Mode** (Default): One CSV per invoice number
- **Consolidated Mode**: One CSV per PDF file containing all invoices

## Configuration

### GUI Setting
1. Open Invoice Processor GUI
2. Go to Settings tab
3. Find "Multi-Invoice PDFs:" option
4. Check/uncheck "Consolidate into one CSV per PDF"
5. Click "Save Settings"

### Config File
Edit `config.json`:
```json
{
  "consolidate_multi_invoice": false
}
```

**Values:**
- `false` (Default) - Separate CSV per invoice
- `true` - Consolidated CSV per PDF

## Behavior

### Split Mode (consolidate_multi_invoice = false)

**Default behavior** - Each invoice gets its own CSV file.

**Example**: PDF with 4 invoices generates 4 CSVs
```
Input: PL_US25A0216.pdf (contains 4 invoices)

Output:
├── 2025601757_US25A0231_20251207_193643.csv (6 items)
├── 2025601769_US25A0216_20251207_193643.csv (8 items)
├── 2025601770_US25A0241_20251207_193643.csv (10 items)
└── 2025201803_US25A0237_20251207_193643.csv (3 items)
```

**Filename Format**: `{invoice_number}_{project_number}_{timestamp}.csv`

**Log Output**:
```
Processing: PL_US25A0216.pdf
  Found 4 invoice(s), 27 total items
    - Invoice 2025601757 (Project US25A0231): 6 items
    - Invoice 2025601769 (Project US25A0216): 8 items
    - Invoice 2025601770 (Project US25A0241): 10 items
    - Invoice 2025201803 (Project US25A0237): 3 items
  Saved: 2025601757_US25A0231_20251207_193643.csv (6 items)
  Saved: 2025601769_US25A0216_20251207_193643.csv (8 items)
  Saved: 2025601770_US25A0241_20251207_193643.csv (10 items)
  Saved: 2025201803_US25A0237_20251207_193643.csv (3 items)
```

### Consolidated Mode (consolidate_multi_invoice = true)

**All invoices in one CSV** - Useful for batch processing or when the PDF represents a single shipment.

**Example**: Same PDF generates 1 CSV
```
Input: PL_US25A0216.pdf (contains 4 invoices)

Output:
└── PL_US25A0216_20251207_193643.csv (27 items total)
```

**Filename Format**: `{pdf_name}_{timestamp}.csv`

**CSV Structure**: All invoices combined with invoice_number column differentiating them
```csv
invoice_number,project_number,part_number,quantity,total_price,...
2025601757,US25A0231,STE411-0029,10.00,835.14,...
2025601757,US25A0231,LPU151-J02000,3.00,1646.70,...
2025601769,US25A0216,BTT307-002003,4.00,3699.85,...
2025601769,US25A0216,ND501,17.00,176.99,...
2025601770,US25A0241,OBAL160,5.00,447.78,...
2025201803,US25A0237,PQA151-212000,4.00,5505.28,...
```

**Log Output**:
```
Processing: PL_US25A0216.pdf
  Found 4 invoice(s), 27 total items
    - Invoice 2025601757 (Project US25A0231): 6 items
    - Invoice 2025601769 (Project US25A0216): 8 items
    - Invoice 2025601770 (Project US25A0241): 10 items
    - Invoice 2025201803 (Project US25A0237): 3 items
  Saved: PL_US25A0216_20251207_193643.csv (27 items from 4 invoices: 2025201803, 2025601757, 2025601769, 2025601770)
```

## Use Cases

### Use Split Mode When:
- ✅ Each invoice needs separate customs forms
- ✅ Invoices are for different customers/projects
- ✅ You need to track invoices individually in accounting systems
- ✅ Importing into DerivativeMill with invoice-level matching
- ✅ Section 232 analysis requires per-invoice tracking

### Use Consolidated Mode When:
- ✅ PDF represents a single shipment with multiple invoices
- ✅ All invoices are for the same overall order
- ✅ You want simplified file management (fewer CSV files)
- ✅ Batch processing all items together
- ✅ Creating master reports across all invoices in the PDF

## Single-Invoice PDFs

**Behavior is identical in both modes** - Only one CSV is created regardless of setting.

```
Input: Invoice_2025601757.pdf (1 invoice)

Output (both modes):
└── 2025601757_US25A0231_20251207_193643.csv
```

## Column Structure

Both modes produce the same columns:

**Standard Columns**:
- invoice_number
- project_number
- part_number
- quantity
- total_price

**Material Composition** (Section 232):
- steel_pct, steel_kg, steel_value
- aluminum_pct, aluminum_kg, aluminum_value
- net_weight

**Brazilian Invoices Only**:
- ncm_code
- hts_code
- unit_price

## Switching Modes

You can switch between modes at any time:

1. Change the setting in GUI or config.json
2. Process new PDFs - they will use the new mode
3. Previously processed PDFs are not affected

**Note**: The consolidation mode is determined at processing time, so the same PDF processed twice with different settings will produce different outputs.

## Examples

### Example 1: Split Mode (Default)
```
Config: "consolidate_multi_invoice": false

PDF: Multi_Invoice_Batch_2025.pdf
Contains: 8 invoices

Result:
├── 2025601735_US25A0082_20251207_120000.csv (5 items)
├── 2025601736_US25A0203_20251207_120000.csv (4 items)
├── 2025601737_US25A0221_20251207_120000.csv (3 items)
├── 2025601738_US25A0236_20251207_120000.csv (2 items)
├── 2025601739_US25A0229_20251207_120000.csv (5 items)
├── 2025601740_US25A0197_20251207_120000.csv (10 items)
├── 2025601741_US25A0243_20251207_120000.csv (5 items)
└── 2025750331_US25A0075_20251207_120000.csv (3 items)

8 CSV files, 37 total items
```

### Example 2: Consolidated Mode
```
Config: "consolidate_multi_invoice": true

PDF: Multi_Invoice_Batch_2025.pdf
Contains: 8 invoices

Result:
└── Multi_Invoice_Batch_2025_20251207_120000.csv (37 items)

1 CSV file with all items, invoice_number column differentiates invoices
```

## Technical Details

### Implementation
- File: `invoice_processor_gui.py`
- Method: `ProcessorEngine.save_to_csv()`
- Lines: 187-249

### Logic Flow
```python
if consolidate_multi_invoice and multiple_invoices:
    # Save all items to one CSV named after PDF
    filename = f"{pdf_name}_{timestamp}.csv"
else:
    # Save each invoice separately (default)
    for each invoice:
        filename = f"{invoice_num}_{project_num}_{timestamp}.csv"
```

### Config Property
- Manager: `ConfigManager.consolidate_multi_invoice`
- Default: `False`
- Type: `bool`
- Saved to: `config.json`

## Files Modified

1. **config_manager.py**
   - Added `consolidate_multi_invoice` to DEFAULT_CONFIG
   - Added property getter/setter (Lines 125-132)

2. **invoice_processor_gui.py**
   - Added GUI toggle in Settings tab (Lines 393-398)
   - Added `_save_consolidate()` method (Lines 536-540)
   - Updated `save_to_csv()` to support both modes (Lines 187-249)
   - Pass PDF name to `save_to_csv()` (Line 301)

3. **config.json**
   - Added `"consolidate_multi_invoice": false` setting

## Troubleshooting

### CSV Not Consolidating
- Check config: `"consolidate_multi_invoice": true`
- Verify checkbox is checked in GUI Settings
- Restart GUI after changing config manually
- PDF must contain multiple invoices (≥2)

### Too Many CSV Files
- Set `"consolidate_multi_invoice": true` if you want one CSV per PDF
- Default is `false` (one CSV per invoice)

### Can't Find Consolidated CSV
- Check output folder
- Filename matches PDF name (not invoice number)
- Look for log message: "items from X invoices"

## FAQ

**Q: Does this affect Section 232 processing?**
A: No, both modes produce the same data. Use the `consolidate_and_match.py` script to combine CSVs if needed.

**Q: Can I consolidate after processing?**
A: Yes, use the `consolidate_and_match.py` script in the output folder.

**Q: What about Brazilian invoice numbers with slashes?**
A: Preserved in both modes. The invoice_number column will show `2025/1850`.

**Q: Does this affect single-invoice PDFs?**
A: No, single-invoice PDFs always produce one CSV regardless of the setting.

**Q: Which mode is better?**
A: Depends on your workflow. Default (split) mode is better for most use cases, especially Section 232 compliance. Use consolidated mode for simplified file management.

---

**Feature Added**: December 7, 2025
**Version**: 2.1.0
