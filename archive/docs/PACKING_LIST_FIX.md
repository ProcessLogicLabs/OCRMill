# Packing List Detection Fix

## Issue Found
The invoice processor was incorrectly marking PDFs as "packing lists" and skipping them, even when they contained valid invoice data.

**Root Cause**: mmcité PDFs often contain BOTH invoice pages AND packing list pages in the same document. The original `is_packing_list()` method used a simple check:

```python
def is_packing_list(self, text: str) -> bool:
    return 'packing list' in text.lower()
```

This would return `True` for any PDF containing the words "packing list" anywhere, even if the PDF also contained invoices with line items.

## Example
PDF: `2025601736 - mmcité usa - US25A0203 (5).pdf`
- Contains invoice data (69 line items)
- Also contains packing list pages at the end
- Was being skipped entirely
- **Before fix**: Moved to Failed folder with "No items extracted"
- **After fix**: Successfully processed with 69 items extracted

## Solution
Implemented a smarter `is_packing_list()` method in both templates that:

1. Checks if "packing list" text exists
2. **Also** checks for invoice markers like:
   - "Invoice n."
   - "Proforma invoice"
   - "Variable symbol"
   - "Nota Fiscal" (Brazilian)
3. Only returns `True` (skip the PDF) if packing list text exists **AND** no invoice markers found

## Code Changes

### mmcite_czech.py
Added override method:
```python
def is_packing_list(self, text: str) -> bool:
    """
    Check if document is ONLY a packing list.
    mmcité PDFs often contain both invoice and packing list pages.
    Only skip if there's NO invoice data.
    """
    text_lower = text.lower()

    has_packing_list = 'packing list' in text_lower or 'packing slip' in text_lower
    if not has_packing_list:
        return False

    has_invoice_markers = any([
        'invoice n.' in text_lower,
        'proforma invoice' in text_lower,
        'variable symbol' in text_lower,
        bool(re.search(r'invoice\s+(?:number|n)\.?\s*:?\s*\d+', text, re.IGNORECASE))
    ])

    return not has_invoice_markers
```

### mmcite_brazilian.py
Same logic, with Brazilian-specific markers:
```python
has_invoice_markers = any([
    'invoice n.' in text_lower,
    'nota fiscal' in text_lower,
    'variable symbol' in text_lower,
    bool(re.search(r'invoice\s+(?:number|n)\.?\s*:?\s*\d+', text, re.IGNORECASE))
])
```

## Test Results

**Before Fix:**
```
Processing: 2025601736 - mmcité usa - US25A0203 (5).pdf
  Using template: mmcité Czech
  Skipping packing list: 2025601736 - mmcité usa - US25A0203 (5).pdf
  Moved to: Failed/... (No items extracted)
```

**After Fix:**
```
Processing: 2025601736 - mmcité usa - US25A0203 (5).pdf
  Using template: mmcité Czech
  Invoice: 2025601736, Project: US25A0203, Items: 69
  Saved: 2025601736_US25A0203_20251207_191803.csv (69 items)
  Moved to: Processed/2025601736 - mmcité usa - US25A0203 (5).pdf
```

## Impact
- ✅ PDFs with both invoices and packing lists are now processed correctly
- ✅ Pure packing lists (no invoice data) are still skipped
- ✅ All line items, material data, and metadata extracted properly
- ✅ 4 previously failing PDFs now process successfully

## Files Modified
1. `templates/mmcite_czech.py` - Added `is_packing_list()` override
2. `templates/mmcite_brazilian.py` - Added `is_packing_list()` override
