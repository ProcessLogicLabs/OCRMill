# OCRMill - Invoice Processing System

**Version 2.4.0** - Automated invoice PDF processing with OCR extraction, parts database management, and CBP export integration.

## Features

### Core Processing
- **GUI Application** - Full-featured desktop interface with tabbed navigation
- **Folder Monitoring** - Automatically processes PDFs placed in the input folder
- **Modular Templates** - Easily add support for new invoice formats
- **Multi-Invoice Processing** - Handles PDFs containing multiple invoices
- **Consolidation Options** - Split or consolidate multi-invoice PDFs

### Data Management
- **Parts Database** - Comprehensive tracking of all processed parts with:
  - HTS code assignments (protected from PDF overwrites)
  - Material composition data (steel, aluminum, copper percentages)
  - Country of origin (auto-extracted from MID)
  - Manufacturer information (MID tracking)
  - FSC certification tracking
  - Usage history and statistics
- **Protected HTS Codes** - Database HTS codes never overwritten by PDF processing
- **CSV Output** - Organized output files with extracted line items

### CBP Integration
- **CBP Export Tab** - Integrated Millworks processing for customs forms
- **Auto-Refresh** - Automatically refreshes when tab is selected
- **Section 232 Compliance** - Material composition data for tariff calculations
- **Qty1/Qty2 Processing** - Conditional quantity handling based on unit type

### File Management
- **Output Files Browser** - Browse, open, and manage processed CSV files
- **Quick Access** - Double-click to open files, Excel integration
- **Real-time Refresh** - File list updates automatically

## Quick Start

### Installation
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the installer verification:
   ```bash
   python verify_installation.py
   ```

### Launch Application
```bash
# Main GUI (recommended)
start_invoice_processor.bat
# or
python invoice_processor_gui.py

# Parts Database Viewer
start_parts_viewer.bat
# or
python parts_database_viewer.py
```

### Basic Workflow
1. Drop PDF invoices in the `input/` folder
2. Application automatically:
   - Detects invoice format
   - Extracts line items
   - Adds parts to database
   - Generates CSV files
   - Moves PDFs to `input/Processed/`
3. View results in `output/` folder
4. Review parts database for HTS codes and material data

## Application Tabs

### Invoice Processing
- Configure input/output folders
- Enable/disable templates
- Set poll interval and auto-start
- Monitor processing log
- Browse output files

### Parts Master
- View all parts in database
- Edit HTS codes, material percentages
- Track country of origin and MID
- Search and filter parts
- Export reports

### CBP Export
- Process CSV files for customs forms
- Auto-refresh file list
- Generate CBP-compliant Excel output
- Track processed files

### Manufacturers
- Manage manufacturer database
- Import manufacturer data from Excel
- Track MID and country information
- View manufacturer statistics

## Parts Database

OCRMill automatically builds and maintains a comprehensive parts database:

**Tracked Information:**
- Part numbers and descriptions
- HTS code assignments (protected)
- Material composition (steel, aluminum, copper percentages)
- Country of origin (auto-extracted from MID)
- Manufacturer information (MID)
- FSC certification (FSC 100%, certificate code)
- Client codes and quantity units
- Usage statistics and history

**Key Features:**
- **HTS Code Protection** - Database HTS codes never overwritten by PDFs
- **Auto-Population** - Country of origin from manufacturer or MID
- **Material Tracking** - Section 232 compliance data
- **FSC Certification** - Automatic detection of FSC 100% parts

**Database Operations:**
- Manual editing via Parts Master tab
- HTS code import from Excel
- Manufacturer data import
- Export reports to CSV

## Supported Invoice Formats

### mmcité Czech
- Czech invoices with CZK/USD pricing
- Material composition extraction
- Steel/aluminum percentage tracking

### mmcité Brazilian
- Brazilian invoices with NCM/HTS codes
- Multi-currency support
- Item exclusion rules

## Configuration

Settings stored in `config.json`:
```json
{
  "input_folder": "input",
  "output_folder": "output",
  "database_path": "Resources/parts_database.db",
  "poll_interval": 60,
  "auto_start": false,
  "consolidate_multi_invoice": false,
  "cbp_export": {
    "input_folder": "output/Processed",
    "output_folder": "output/CBP_Export"
  },
  "templates": {
    "mmcite_czech": {"enabled": true},
    "mmcite_brazilian": {"enabled": true}
  }
}
```

## File Structure

```
OCRMill/
├── input/                      # Drop PDFs here
│   ├── Processed/              # Successfully processed PDFs
│   └── Failed/                 # PDFs that couldn't be processed
├── output/                     # Generated CSV files
│   ├── Processed/              # Processed CSVs
│   ├── Test/                   # Test output
│   └── CBP_Export/             # CBP export files
├── Resources/                  # Database and resources
│   ├── parts_database.db       # Parts tracking database
│   └── CBP_data/               # Section 232 tariff data
├── templates/                  # Invoice templates
│   ├── mmcite_czech.py
│   ├── mmcite_brazilian.py
│   └── bill_of_lading.py
├── archive/                    # Archived development files
│   ├── tests/                  # Test files
│   ├── scripts/                # Utility scripts
│   └── docs/                   # Historical documentation
├── invoice_processor_gui.py    # Main GUI application
├── parts_database.py           # Parts database manager
├── parts_database_viewer.py    # Parts database viewer
├── config_manager.py           # Configuration manager
└── config.json                 # Application settings
```

## Adding New Templates

1. Create a new file in `templates/` folder
2. Inherit from `BaseTemplate`
3. Implement required methods:
   - `can_process(text)` - Identify if template matches
   - `extract_invoice_number(text)` - Extract invoice number
   - `extract_project_number(text)` - Extract project/PO number
   - `extract_line_items(text)` - Extract line item data
4. Register in `templates/__init__.py`

See `templates/sample_template.py` for a complete example.

## Multi-Invoice Processing

**Split Mode (Default):** Creates separate CSV for each invoice
```
Input: invoice_batch.pdf (4 invoices)
Output:
  - 2025601757_US25A0231_timestamp.csv
  - 2025601769_US25A0216_timestamp.csv
  - 2025601770_US25A0241_timestamp.csv
  - 2025201803_US25A0237_timestamp.csv
```

**Consolidated Mode:** Creates one CSV per PDF
```
Input: invoice_batch.pdf (4 invoices)
Output:
  - invoice_batch_timestamp.csv (all invoices combined)
```

Toggle in Settings tab or set in `config.json`.

## CBP Export Workflow

1. Process invoices through main application
2. CSV files saved to `output/Processed/`
3. Switch to CBP Export tab (auto-refreshes)
4. Select CSV files to process
5. Click "Process Selected" or "Process All"
6. CBP-compliant Excel files generated in `output/CBP_Export/`
7. Files include:
   - Qty1/Qty2 based on qty_unit
   - Material composition data
   - HTS codes from database
   - Section 232 tariff calculations

## Version History

### v2.4.0 (December 2025)
- **HTS Code Protection** - Database HTS codes never overwritten by PDFs
- **Output Files Browser** - Browse and open processed files
- **Auto-Refresh CBP Export** - Tab refreshes automatically when selected
- **Country of Origin** - Auto-populated from manufacturer or MID
- **FSC Certification** - Track FSC 100% certified parts
- **Project Cleanup** - Archived 48 unused files, organized structure

### v2.3.0 (December 2025)
- **CBP Export Integration** - Millworks processing integrated
- **Unified GUI** - Tabbed interface with all features

### v2.2.0
- **Drag-Drop Support** - Drop files directly on GUI
- **Bill of Lading** - BOL extraction support

### v2.1.0
- **Parts Database System** - Comprehensive parts tracking
- **HTS Code Management** - Automatic and manual HTS code assignment

### v2.0.0
- **Multi-Invoice Processing** - Handle multiple invoices per PDF
- **Item Exclusions** - Filter out service fees and packaging
- **Consolidation Toggle** - Choose split or consolidated output

### v1.0.0
- Initial release with Czech and Brazilian templates

## Documentation

- [QUICK_START.md](QUICK_START.md) - Quick start guide
- [archive/docs/](archive/docs/) - Historical documentation and feature summaries

## License

MIT License - See LICENSE file for details

## Support

For issues, feature requests, or questions, please open an issue on GitHub.

---

**🤖 Powered by Claude Code** - Automated invoice processing for customs compliance
