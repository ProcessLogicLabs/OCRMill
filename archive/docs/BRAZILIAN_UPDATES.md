# Brazilian Invoice Processing Updates

## Date: December 7, 2025

## Updates Applied

### 1. Keep Slash in Brazilian Invoice Numbers ✅

**Issue**: Brazilian invoice numbers use slashes (e.g., `2025/1850`) but were being converted to dashes (`2025-1850`) for filesystem compatibility.

**Solution**: Modified [invoice_processor_gui.py:143-157](invoice_processor_gui.py:143-157) to preserve the original invoice number format.

**Before**:
```python
current_invoice = inv_match.group(1).replace('/', '-')
```

**After**:
```python
current_invoice = inv_match.group(1)  # Keep original format (slash for Brazilian)
```

**Result**: Brazilian invoices now keep their slash format: `2025/1850`

### 2. Extract Material Composition Data ✅

**Issue**: Brazilian template was not extracting steel/aluminum composition data that appears in the invoice descriptions.

**Format in Brazilian invoices**:
```
Cost of steel: 109 USD       Weight of steel: 20,72 kg
Cost of aluminium: 0 USD     Weight of aluminium: 0 kg
Net weight: 7,9kg
```

**Solution**: Added material composition extraction to [mmcite_brazilian.py](templates/mmcite_brazilian.py):

1. **Added extra columns** (Lines 24-35):
   - steel_pct, steel_kg, steel_value
   - aluminum_pct, aluminum_kg, aluminum_value
   - net_weight

2. **Added extraction method** (Lines 87-140):
   ```python
   def _extract_steel_aluminum_data(self, text: str) -> Dict:
       """Extract steel and aluminum material composition data."""
   ```

   Extracts:
   - `Cost of steel: X USD` → steel_value
   - `Weight of steel: X kg` → steel_kg
   - `Cost of aluminium: X USD` → aluminum_value
   - `Weight of aluminium: X kg` → aluminum_kg
   - `Net weight: X kg` → net_weight
   - Calculates steel_pct and aluminum_pct from weights

3. **Integrated into line item extraction** (Lines 162-203):
   - Looks ahead 7 lines after each part number
   - Extracts material data from context
   - Adds to each line item

**CSV Output Format**:
```csv
invoice_number,project_number,part_number,quantity,total_price,ncm_code,hts_code,unit_price,steel_pct,steel_kg,steel_value,aluminum_pct,aluminum_kg,aluminum_value,net_weight
2025/1850,US25A0105,SL505,3.00,316.80,94032090,9403.20.0080,105.60,100,16.76,109,0,0,0,7.9
2025/1850,US25A0105,LPC122t_FSC,15.00,5425.20,94017900,9401.69.8031,361.68,53,20.72,109,47,0,0,20.72
```

### 3. Unified Column Structure Across Templates

**Czech Template Columns**:
- Standard: invoice_number, project_number, part_number, quantity, total_price
- Extra: steel_pct, steel_kg, steel_value, aluminum_pct, aluminum_kg, aluminum_value, net_weight

**Brazilian Template Columns** (Updated):
- Standard: invoice_number, project_number, part_number, quantity, total_price
- Extra: ncm_code, hts_code, unit_price
- Material: steel_pct, steel_kg, steel_value, aluminum_pct, aluminum_kg, aluminum_value, net_weight

Both templates now produce CSVs with material composition data required for Section 232 tariff calculations.

## Testing

Test on a Brazilian invoice to verify:

```python
from pathlib import Path
from templates import MMCiteBrazilianTemplate

template = MMCiteBrazilianTemplate()

# Test with your Brazilian invoice PDF text
invoice_num, project_num, items = template.extract_all(pdf_text)

# Verify material data is extracted
for item in items:
    print(f"{item['part_number']}: steel={item.get('steel_kg')}kg @ ${item.get('steel_value')}")
```

## Next Steps: Section 232 Post-Processing

The CSVs now contain the required data for Section 232 derivative calculations. The Millworks application processes these CSVs to:

1. **Match parts to HTS codes** - Links part numbers to tariff classifications
2. **Calculate steel/aluminum ratios** - Uses weight and value data
3. **Determine Section 232 applicability** - Based on material composition
4. **Generate customs forms** - Exports compliance documentation

### Integration Flow:
```
OCR Mill (This System)
├── Extract invoices from PDFs
├── Parse line items with material data
└── Generate CSV files
    ↓
Millworks (Section 232 Processing)
├── Import CSV files
├── Match to parts database
├── Calculate derivative percentages
├── Apply Section 232 rules
└── Export customs documentation
```

## Files Modified

1. **invoice_processor_gui.py** (Lines 143-157)
   - Preserve Brazilian invoice number format (keep slashes)

2. **templates/mmcite_brazilian.py** (Lines 24-203)
   - Added 10 extra columns for material composition
   - Added `_extract_steel_aluminum_data()` method
   - Enhanced `extract_line_items()` with context lookup

## Notes

- All material values are in USD
- All weights are in kg
- Percentages are calculated as (material_kg / net_weight_kg) * 100
- Both "aluminum" and "aluminium" spelling variants are supported
- Material data is optional - items without it will have empty string values
