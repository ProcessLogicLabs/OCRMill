# OCRMill Distribution Package

## Overview
This is a standalone Windows executable version of OCRMill. No Python installation required!

## Installation

### Option 1: Use the Executable Directly
1. Copy the entire `dist\OCRMill\` folder to your desired location
2. Double-click `OCRMill.exe` to launch the application

### Option 2: Create a Desktop Shortcut
1. Navigate to the folder containing `OCRMill.exe`
2. Right-click on `OCRMill.exe`
3. Select "Create Shortcut"
4. Move the shortcut to your Desktop or Start Menu

## First Run Setup

When you first run OCRMill, it will create the following folders in the same directory as the executable:

- **input/** - Place PDF invoices here for processing
- **output/** - Processed CSV files will be saved here
- **output/CBP_Export/** - CBP export Excel files
- **reports/** - Generated reports
- **Resources/** - Database and configuration files

## System Requirements

- Windows 10 or later (64-bit)
- Minimum 4GB RAM
- 500MB free disk space
- Excel (optional, for opening exported files)

## Usage

1. **Launch OCRMill.exe**
2. **Invoice Processing Tab**:
   - Drag and drop PDF invoices onto the drop zone, OR
   - Click "Add Files" to select PDFs manually
   - Click "Start Processing" to begin
   - View results in the Output Files sub-tab

3. **Parts Database Tab**:
   - View and manage all processed parts
   - Edit HTS codes, descriptions, material percentages
   - Import parts lists from Excel
   - Generate reports

4. **CBP Export Tab**:
   - Generate CBP-compliant Excel export files
   - Automatically refreshes when selected
   - Export files saved to output/CBP_Export/

## Configuration

The application creates a `config.json` file on first run. You can modify:
- Input/output folder paths
- Template settings
- Column visibility preferences

## Database Location

Parts database: `parts_database.db` (created automatically)

## Troubleshooting

### Application won't start
- Run as Administrator
- Check Windows Defender/antivirus hasn't blocked it
- Ensure you have write permissions in the installation folder

### Missing DLL errors
- The `_internal` folder must stay in the same directory as `OCRMill.exe`
- Don't move files out of the `_internal` folder

### Template not working
- Check Settings tab to enable/disable templates
- Verify PDF is not password-protected or corrupted

## Building from Source

If you want to rebuild the executable:

```cmd
# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Build executable
pyinstaller --clean OCRMill.spec

# Or use the build script
build_exe.bat
```

## Distribution Package Contents

```
OCRMill/
├── OCRMill.exe          # Main executable
├── _internal/           # Required dependencies (don't modify)
├── config.json          # Configuration (created on first run)
├── parts_database.db    # Parts database (created on first run)
├── templates/           # Invoice templates
└── Resources/           # Additional resources
```

## Version Information

**Version**: 2.4.0
**Build Date**: December 2025
**Python Version**: 3.13.9
**PyInstaller Version**: 6.17.0

## Features

- ✅ PDF invoice processing with OCR
- ✅ Parts database with HTS code management
- ✅ CBP export generation
- ✅ Drag-and-drop file support
- ✅ Multi-template support
- ✅ Section 232 tracking (steel/aluminum/copper)
- ✅ Country of origin tracking
- ✅ FSC certification tracking
- ✅ Output file browser with Excel integration

## Support

For issues or questions:
- GitHub: https://github.com/royalpayne/OCRInvoiceMill
- Report bugs in the Issues tab

## License

See project repository for license information.
