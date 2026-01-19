# OCRMill Quick Start Guide

## Installation

### 1. Install Dependencies

**Using requirements.txt (recommended):**
```bash
pip install -r requirements.txt
```

**Or manually:**
```bash
pip install pdfplumber pillow pystray pandas openpyxl
```

### 2. Verify Installation
```bash
python verify_installation.py
```

This checks all dependencies and confirms everything is configured correctly.

### 3. Load HTS Codes
```bash
python load_hts_mapping.py
```

This loads the HTS code mapping from `reports/mmcite_hts.xlsx` into the parts database.

### 4. Run the Application
```bash
python invoice_processor_gui.py
```

## Basic Usage

### Processing Invoices

1. **Start the Processor**
   - Launch `invoice_processor_gui.py`
   - Click "Start Monitoring" button
   - Or check "Auto-start monitoring on launch" in Settings

2. **Drop PDFs**
   - Place invoice PDFs in the `input/` folder
   - Processor automatically detects and processes them
   - Watch the Activity Log for progress

3. **Check Results**
   - Processed PDFs move to `input/Processed/`
   - CSV files appear in `output/` folder
   - Failed PDFs move to `input/Failed/`

### Viewing Parts Database

1. **Launch the Viewer**
   ```bash
   python parts_database_viewer.py
   ```

2. **Browse Parts**
   - Parts Master tab shows all unique parts
   - Search box filters by part number
   - Filter buttons: All Parts / With HTS / No HTS

3. **View Part Details**
   - Double-click any part to see details
   - Right-click for context menu:
     - View Details
     - Set HTS Code
     - View History

4. **Export Reports**
   - Click "Export Master CSV" for parts summary
   - Click "Export History CSV" for complete usage history
   - Click "Generate Reports" for full report set

## Common Tasks

### Assign HTS Code to a Part

**Method 1: Via Viewer**
1. Open Parts Database Viewer
2. Find the part (use search if needed)
3. Right-click the part
4. Select "Set HTS Code"
5. Enter HTS code and click Save

**Method 2: Via Code**
```python
from parts_database import PartsDatabase

db = PartsDatabase()
db.update_part_hts('SL505-002000', '9403.20.0080', 'Seating furniture')
```

### Generate Monthly Report

1. Open Parts Database Viewer
2. Click "Generate Reports"
3. Select output folder (e.g., `reports/monthly_202512/`)
4. Reports created:
   - `parts_master.csv` - All parts with statistics
   - `parts_history.csv` - Complete transaction history
   - `parts_statistics.txt` - Summary statistics

### Find Parts by Project

**Via Viewer:**
1. Switch to Part History tab
2. Use filter or search for project number

**Via Code:**
```python
from parts_database import PartsDatabase

db = PartsDatabase()
parts = db.get_parts_by_project('US25A0203')

for part in parts:
    print(f"{part['part_number']}: {part['quantity']} @ ${part['total_price']}")
```

### Export Data for Excel

1. Open Parts Database Viewer
2. Click "Export Master CSV"
3. Save to desired location
4. Open in Excel for further analysis

## Settings

### Multi-Invoice Processing

**Split Mode (Default):**
- One CSV per invoice
- Best for separate customs forms

**Consolidated Mode:**
- One CSV per PDF file
- All invoices combined

**To Change:**
1. Go to Settings tab
2. Check/uncheck "Consolidate into one CSV per PDF"
3. Click "Save Settings"

### Template Selection

Enable/disable invoice templates:
1. Go to Templates tab
2. Check/uncheck templates as needed
3. Templates apply to new processing only

### Folders

Configure input and output folders in Settings tab.

## Troubleshooting

### No CSV Files Generated

**Check:**
1. Activity Log shows "No items extracted"
2. PDF might be packing list only
3. PDF might not match any template

**Solution:**
1. Check Failed folder for problematic PDFs
2. Review Activity Log for template matching scores
3. Verify PDF contains invoice data

### Parts Not Appearing in Database

**Check:**
1. Invoice was successfully processed
2. CSV file was generated
3. Database file exists: `parts_database.db`

**Solution:**
- Parts are only added when CSV is successfully saved
- Reprocess the PDF if needed

### HTS Codes Not Assigned

**Check:**
1. HTS codes loaded: `python load_hts_mapping.py`
2. Parts Database Viewer → HTS Codes tab shows codes
3. Parts might need manual assignment

**Solution:**
1. Run `load_hts_mapping.py` to load codes
2. Use Parts Database Viewer to manually assign
3. Add part number prefix patterns to code

### Unicode Errors

**Symptom:** Error with Czech characters or special symbols

**Solution:**
- Already fixed in latest version
- Ensure using UTF-8 encoding
- Update to latest code if still seeing errors

## Tips & Best Practices

### 1. Regular Backups
```bash
copy parts_database.db backups\parts_database_20251209.db
```

### 2. Load HTS Codes Early
Run `python load_hts_mapping.py` before processing invoices to get automatic HTS assignment.

### 3. Review Failed PDFs
Check `input/Failed/` folder periodically and review Activity Log to understand why PDFs failed.

### 4. Use Filters
In Parts Database Viewer, use "No HTS" filter to quickly find parts needing HTS code assignment.

### 5. Export Reports Monthly
Generate monthly reports for record-keeping and analysis.

### 6. Monitor Database Size
Large databases (>100,000 occurrences) may slow down. Consider archiving old data.

### 7. Verify HTS Coverage
Check Statistics tab to see HTS code coverage percentage. Aim for >95%.

## Integration with Millworks

### Workflow

1. **Process Invoices in OCRMill**
   - Invoices processed with material composition
   - Parts added to database with HTS codes

2. **Consolidate for Section 232**
   ```bash
   cd output
   python ../consolidate_and_match.py
   ```

3. **Import to Millworks**
   - Import consolidated CSV
   - HTS codes already assigned
   - Material composition data included

4. **Generate Customs Forms**
   - Use Millworks to calculate tariffs
   - Generate Section 232 forms

## File Locations

```
OCRMill/
├── input/                  # Drop PDFs here
├── output/                 # CSV files created here
├── reports/                # HTS mapping and reports
├── parts_database.db       # Parts tracking database
└── config.json             # Settings
```

## Next Steps

1. **Learn the Parts Database**: Read [PARTS_DATABASE.md](PARTS_DATABASE.md)
2. **Multi-Invoice Options**: Read [MULTI_INVOICE_CONSOLIDATION.md](MULTI_INVOICE_CONSOLIDATION.md)
3. **Item Exclusions**: Read [ITEM_EXCLUSIONS.md](ITEM_EXCLUSIONS.md)
4. **Full Documentation**: Read [README.md](README.md)

## Support

- Check Activity Log for processing details
- Review Failed folder for problematic PDFs
- Use Parts Database Viewer to inspect data
- Consult documentation files for specific features

---

**Version:** 2.1.0
**Last Updated:** December 9, 2025
