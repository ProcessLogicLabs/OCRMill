# Item Exclusion Rules

## Overview

Certain item types are automatically excluded from CSV output to ensure only actual product line items are exported.

## Czech Template Exclusions

The following items are filtered out from Czech invoices:

### 1. **Celkem** - Total Lines
- **Pattern**: Part number = "Celkem"
- **Reason**: Total/summary line, not an actual product
- **Example**: `Celkem,9.648,9648.85` ← Excluded

### 2. **SLU*** - Service Fees
- **Pattern**: Part number starts with "SLU"
- **Reason**: Service fees, not physical products
- **Examples**:
  - `SLU998,8.00,68.63` ← Excluded
  - `SLU899,0.06,66.33` ← Excluded

### 3. **OBAL*** - Packaging Items
- **Pattern**: Part number starts with "OBAL"
- **Reason**: Packaging/crating charges, not products for Section 232 analysis
- **Examples**:
  - `OBAL160,5.00,447.78` ← Excluded
  - `OBAL200,3.00,250.00` ← Excluded

## Brazilian Template Exclusions

Currently no exclusions applied to Brazilian invoices. Brazilian invoices typically don't include summary lines or service fees in the line item format.

If needed, exclusions can be added using the same pattern:
```python
if part_number.upper().startswith('OBAL'):
    continue
```

## Implementation

All exclusions are checked in all 4 extraction patterns:
1. Main pattern (with project code)
2. Proforma pattern (no project code)
3. Simple pattern with USD lookup
4. Proforma simple pattern

**Code Location**: `templates/mmcite_czech.py`
- Lines 208-218 (Main pattern)
- Lines 237-251 (Proforma pattern)
- Lines 265-285 (Simple pattern)
- Lines 297-321 (Proforma simple pattern)

## Before vs After

### Before Exclusions:
```csv
invoice_number,project_number,part_number,quantity,total_price
2025601736,US25A0203,SL505-002000,9.00,972.83
2025601736,US25A0203,SLU899,0.06,66.33          ← Service fee
2025601736,US25A0203,BTT307-002003,4.00,3699.85
2025601736,US25A0203,SLU899,0.06,252.26         ← Service fee
2025601736,US25A0203,ND501,17.00,176.99
2025601736,US25A0203,SLU899,0.06,12.07          ← Service fee
2025601736,US25A0203,OBAL160,5.00,447.78        ← Packaging
2025601736,US25A0203,SLU998,8.00,68.63          ← Service fee
2025601736,US25A0203,Celkem,9.648,9648.85       ← Total line
```

### After Exclusions:
```csv
invoice_number,project_number,part_number,quantity,total_price
2025601736,US25A0203,SL505-002000,9.00,972.83
2025601736,US25A0203,BTT307-002003,4.00,3699.85
2025601736,US25A0203,ND501,17.00,176.99
```

**Items Removed**: 6 (3 SLU, 1 OBAL, 2 Celkem)
**Items Kept**: 3 (actual products)

## Testing

To verify exclusions are working:

```python
from pathlib import Path
from templates import MMCiteCzechTemplate

template = MMCiteCzechTemplate()
invoice_num, project_num, items = template.extract_all(pdf_text)

# Check for excluded items
celkem = [i for i in items if i['part_number'].lower() == 'celkem']
slu = [i for i in items if i['part_number'].upper().startswith('SLU')]
obal = [i for i in items if i['part_number'].upper().startswith('OBAL')]

print(f"Celkem items: {len(celkem)} (should be 0)")
print(f"SLU items: {len(slu)} (should be 0)")
print(f"OBAL items: {len(obal)} (should be 0)")
```

## Adding New Exclusions

To add a new exclusion pattern, edit `templates/mmcite_czech.py` and add a similar check:

```python
# Skip [description] items ([prefix] prefix)
if part_number.upper().startswith('[PREFIX]'):
    continue
```

Add this check in all 4 extraction patterns (search for "Skip total lines" to find the locations).

## Impact on Section 232

These exclusions improve Section 232 compliance by:
- ✅ Excluding non-product items (service fees, packaging)
- ✅ Excluding summary/total lines
- ✅ Ensuring only actual manufactured products are analyzed
- ✅ Providing accurate material composition data for tariff calculations

## Notes

- Exclusions are case-insensitive (converted to uppercase for comparison)
- Prefix matching is used (starts with) rather than exact matching
- All exclusions happen before CSV export
- No configuration needed - exclusions are always active

## Version History

- **v2.0.0** - Added Celkem and SLU exclusions
- **v2.1.0** - Added OBAL exclusion

---

**Last Updated**: December 7, 2025
