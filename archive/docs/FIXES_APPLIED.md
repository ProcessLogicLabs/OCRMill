# Invoice Processor GUI - Fixes Applied

## Date: December 7, 2025

## Summary
Fixed two critical issues:
1. **Files moved to Processed even when no CSV created** - Now only successful extractions move to Processed
2. **PDFs with invoices + packing lists incorrectly skipped** - Smarter packing list detection

## Issues Identified

### 1. **PDFs Moved to Processed Folder Even When No CSV Created**
- **Problem**: All PDFs were unconditionally moved to `Processed/` folder, even when:
  - No template matched the invoice
  - Template was disabled
  - PDF was a packing list
  - No items were extracted
- **Result**: Files showed as "processed" but no CSV output was generated

### 2. **No Visibility Into Template Matching**
- **Problem**: No logging to show which templates were evaluated or why they were rejected
- **Result**: Impossible to debug why a PDF wasn't being processed

### 3. **No Separation of Failed PDFs**
- **Problem**: Failed PDFs were mixed with successful ones in the Processed folder
- **Result**: Hard to identify which files need attention

## Fixes Applied

### Fix 1: Conditional File Movement (Lines 201-235)

**Changed `ProcessorEngine.process_folder()` to:**
- Only move PDFs to `Processed/` folder when items are successfully extracted AND CSV is created
- Move PDFs to new `Failed/` folder when:
  - No items extracted
  - Processing errors occur
- Track both success and failure counts
- Log summary with both counts

**Code Change:**
```python
if items:
    self.save_to_csv(items, output_folder)
    self.move_to_processed(pdf_path, processed_folder)
    processed_count += 1
else:
    # No items extracted - move to Failed folder
    self.move_to_failed(pdf_path, failed_folder, "No items extracted")
    failed_count += 1
```

### Fix 2: Detailed Template Matching Logs (Lines 62-89)

**Enhanced `ProcessorEngine.get_best_template()` with:**
- Log when evaluating templates
- Log disabled templates (config vs. template property)
- Log confidence score for each template
- Log which template was selected and why
- Log when no template matches

**Sample Output:**
```
  Evaluating 2 templates...
    - mmcite_czech: Confidence score 0.80
    - mmcite_brazilian: Confidence score 0.00
  Selected template: mmcité Czech (score: 0.80)
```

### Fix 3: Failed PDFs Folder (Lines 185-199)

**Added new `move_to_failed()` method:**
- Creates `input/Failed/` folder automatically
- Moves unprocessable PDFs there with reason
- Handles duplicate filenames
- Logs failure reason for debugging

**Usage:**
```python
self.move_to_failed(pdf_path, failed_folder, "No items extracted")
self.move_to_failed(pdf_path, failed_folder, f"Error: {str(e)[:50]}")
```

### Fix 4: Improved Error Handling (Lines 216-230)

**Added try-except block in processing loop:**
- Catches processing errors gracefully
- Moves errored PDFs to Failed folder
- Logs error details
- Continues processing other PDFs

## Folder Structure After Fixes

```
input/
├── Processed/           # Successfully processed PDFs with CSV output
├── Failed/              # PDFs that couldn't be processed (NEW)
│   ├── PL_US25A0216.pdf (No items extracted)
│   └── BadInvoice.pdf (Error: ...)
└── *.pdf               # PDFs waiting to be processed

output/
└── *.csv               # Generated CSV files (one per invoice)
```

## How to Test

1. **Run the test script:**
   ```bash
   python test_processing.py
   ```

2. **Or use the GUI:**
   - Launch: `python invoice_processor_gui.py`
   - Click "Process Now" button
   - Check the Activity Log for detailed template matching info

3. **Verify results:**
   - Check `input/Processed/` - should only contain PDFs with corresponding CSVs
   - Check `input/Failed/` - should contain PDFs that couldn't be processed
   - Check `output/` - should contain one CSV per successfully processed invoice

## Expected Behavior Changes

### Before:
```
Processing: PL_US25A0216.pdf
  No matching template for PL_US25A0216.pdf
  Moved to: PL_US25A0216.pdf
```
✗ File moved but no CSV created

### After:
```
Processing: PL_US25A0216.pdf
  Evaluating 2 templates...
    - mmcite_czech: Confidence score 0.00
    - mmcite_brazilian: Confidence score 0.00
  No matching template found
  Moved to: Failed/PL_US25A0216.pdf (No items extracted)
```
✓ File moved to Failed folder with clear reason

### Successful Processing:
```
Processing: Invoice_2025200819.pdf
  Evaluating 2 templates...
    - mmcite_czech: Confidence score 0.80
    - mmcite_brazilian: Confidence score 0.00
  Selected template: mmcité Czech (score: 0.80)
  Using template: mmcité Czech
  Invoice: 2025200819, Project: US25A0148, Items: 3
  Saved: 2025200819_US25A0148_20251207_120000.csv (3 items)
  Moved to: Processed/Invoice_2025200819.pdf
```
✓ CSV created AND file moved to Processed

## Files Modified

1. **invoice_processor_gui.py**
   - Enhanced template matching logging
   - Added Failed folder support
   - Fixed conditional file movement
   - Improved error handling

2. **templates/mmcite_czech.py**
   - Added smart `is_packing_list()` detection
   - Now handles PDFs with both invoices and packing lists

3. **templates/mmcite_brazilian.py**
   - Added smart `is_packing_list()` detection
   - Brazilian-specific invoice markers

4. **test_processing.py** (NEW)
   - Quick test script for verification
   - Shows template status
   - Reports results summary

## Additional Notes

- No breaking changes to existing functionality
- CSV output format unchanged
- Config file structure unchanged
- All existing templates still work
- Failed PDFs can be moved back to `input/` folder to retry after fixing issues
