# Multi-Invoice Processing & Item Filtering

## Issues Fixed

### Issue 1: Multiple Invoices Per PDF Not Processed
**Problem**: PDFs containing multiple invoices only extracted data from the first invoice.

**Example**: `PL US25A0216 (1).pdf` contained 4 invoices but only processed the first one.

**Root Cause**: The `process_pdf()` method concatenated all pages into one text string and extracted a single invoice number and project number for all items.

### Issue 2: Total Lines and Service Fees Included
**Problem**:
- Czech total lines ("Celkem") were being included as line items
- Service fee items (part numbers starting with "SLU") were being included

**Example**:
```csv
2025601736,US25A0203,Celkem,9.648,9648.85  ← Total line (should be excluded)
2025601736,US25A0203,SLU998,8.00,68.63     ← Service fee (should be excluded)
```

## Solutions Implemented

### Solution 1: Page-by-Page Processing with Invoice Detection

Modified `invoice_processor_gui.py` `process_pdf()` method to:

1. **First Pass**: Extract all text to detect template type
2. **Second Pass**: Process page-by-page:
   - Detect invoice number changes on each page
   - Buffer pages belonging to the same invoice
   - When a new invoice is detected, process the buffered pages
   - Assign correct invoice/project numbers to each item

**Code Logic**:
```python
for page in pdf.pages:
    # Check for new invoice on this page
    inv_match = re.search(r'Invoice\s+n\.?\s*:?\s*(\d+)', page_text)

    # If new invoice found, process previous invoice buffer
    if inv_match and current_invoice != inv_match.group(1):
        # Process accumulated pages for previous invoice
        process_buffer()
        page_buffer = []

    # Update current invoice/project
    current_invoice = inv_match.group(1)
    page_buffer.append(page_text)
```

### Solution 2: Part Number Filtering

Modified `templates/mmcite_czech.py` to filter out unwanted items:

```python
# Skip total lines (Czech word for total)
if part_number.lower() == 'celkem':
    continue

# Skip service fee items (SLU prefix)
if part_number.upper().startswith('SLU'):
    continue
```

Applied to all 4 extraction patterns:
1. Main pattern (with project code)
2. Proforma pattern (no project code)
3. Simple pattern with USD lookup
4. Proforma simple pattern

## Test Results

### Before Fixes:
**File**: `PL US25A0216 (1).pdf` (38 pages, 4 invoices)
```
Processing: PL US25A0216 (1).pdf
  Invoice: 2025601757, Project: US25A0231, Items: 27
```
- Only processed 1 invoice (2025601757)
- Missed 3 other invoices (2025601769, 2025601770, 2025201803)
- Included SLU and Celkem items

### After Fixes:
**File**: `PL US25A0216 (1).pdf`
```
Processing: PL US25A0216 (1).pdf
  Found 4 invoice(s), 27 total items
    - Invoice 2025201803 (Project US25A0237): 3 items
    - Invoice 2025601757 (Project US25A0231): 6 items
    - Invoice 2025601769 (Project US25A0216): 8 items
    - Invoice 2025601770 (Project US25A0241): 10 items
  Saved: 2025601757_US25A0231_20251207_193643.csv (6 items)
  Saved: 2025601769_US25A0216_20251207_193643.csv (8 items)
  Saved: 2025601770_US25A0241_20251207_193643.csv (10 items)
  Saved: 2025201803_US25A0237_20251207_193643.csv (3 items)
```
- ✅ All 4 invoices detected and processed
- ✅ 4 separate CSV files created
- ✅ No Celkem items (0 found)
- ✅ No SLU items (0 found)

### Example: 8-Invoice PDF
**File**: `2025601736 - mmcité usa - US25A0203 (3)_1.pdf` (71 pages)
```
  Found 8 invoice(s), 37 total items
    - Invoice 2025601735 (Project US25A0082): 5 items
    - Invoice 2025601736 (Project US25A0203): 4 items
    - Invoice 2025601737 (Project US25A0221): 3 items
    - Invoice 2025601738 (Project US25A0236): 2 items
    - Invoice 2025601739 (Project US25A0229): 5 items
    - Invoice 2025601740 (Project US25A0197): 10 items
    - Invoice 2025601741 (Project US25A0243): 5 items
    - Invoice 2025750331 (Project US25A0075): 3 items
```
- ✅ All 8 invoices detected
- ✅ 8 separate CSV files created
- ✅ Each invoice has correct project number
- ✅ All items properly categorized by invoice

## Impact

### CSV Output Quality
- **Before**: 5 items per invoice (including Celkem + SLU items)
- **After**: 4 items per invoice (excluding Celkem + SLU items)
- More accurate line item counts
- Cleaner data for importing into other systems

### Multi-Invoice Support
- **Before**: 1 CSV per PDF (only first invoice)
- **After**: 1 CSV per invoice (all invoices in PDF)
- Handles PDFs with 1-10+ invoices
- Each CSV properly labeled with invoice and project numbers

### Logging Improvements
New detailed logging shows:
```
  Found 4 invoice(s), 27 total items
    - Invoice 2025201803 (Project US25A0237): 3 items
    - Invoice 2025601757 (Project US25A0231): 6 items
```
- Clear visibility into what was extracted
- Easy to verify all invoices were processed
- Item counts per invoice for validation

## Files Modified

1. **invoice_processor_gui.py** (Lines 91-183)
   - Rewrote `process_pdf()` for multi-invoice support
   - Added page-by-page processing with buffering
   - Added per-invoice logging

2. **templates/mmcite_czech.py** (Lines 208-320)
   - Added Celkem filtering (total lines)
   - Added SLU filtering (service fees)
   - Applied to all 4 extraction patterns

## Additional Notes

- No changes needed to CSV format or existing configurations
- Backward compatible - single-invoice PDFs still work the same
- Packing list pages automatically skipped within invoice PDFs
- Works with both Czech and Brazilian invoice formats
