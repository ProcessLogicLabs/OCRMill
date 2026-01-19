# OCRMill - Build Instructions

## Building the Windows Executable

### Prerequisites
- Python 3.13+ with virtual environment
- All dependencies installed from requirements.txt
- PyInstaller 6.17.0+ (auto-installed by build script)

### Quick Build

**Option 1: Use the Build Script (Recommended)**
```cmd
build_exe.bat
```

This will:
1. Activate the virtual environment
2. Clean previous builds
3. Build the executable using PyInstaller
4. Output to `dist\OCRMill\`

**Option 2: Manual Build**
```cmd
# Activate virtual environment
.venv\Scripts\activate

# Install PyInstaller if needed
pip install pyinstaller

# Clean previous builds
rmdir /s /q build dist

# Build executable
pyinstaller --clean OCRMill.spec
```

### Build Output

After building, you'll find:
```
dist\
└── OCRMill\
    ├── OCRMill.exe          # Main executable (11MB)
    ├── _internal\           # Required dependencies
    ├── config.json          # Auto-generated on first run
    ├── parts_database.db    # Auto-generated on first run
    ├── input\               # Auto-created input folder
    ├── output\              # Auto-created output folder
    ├── reports\             # Auto-created reports folder
    └── Resources\           # Auto-created resources folder
```

### Creating Distribution Package

Run the distribution preparation script:
```cmd
prepare_distribution.bat
```

This will:
1. Copy runtime files (database, config) to dist folder
2. Create directory structure
3. Generate `OCRMill-v2.5.0-Windows.zip`

The zip file contains everything end users need - just extract and run!

### Testing the Executable

1. Navigate to `dist\OCRMill\`
2. Double-click `OCRMill.exe`
3. Application should launch without errors
4. Check that directories are auto-created
5. Try processing a test PDF invoice

### Troubleshooting Build Issues

**PyInstaller Not Found**
```cmd
.venv\Scripts\pip install pyinstaller
```

**Module Not Found Errors**
- Check that all dependencies are in requirements.txt
- Update the hiddenimports list in OCRMill.spec
- Verify virtual environment is activated

**Build Directory Locked**
- Close any running instances of OCRMill.exe
- Delete build/ and dist/ folders manually
- Try build again

**Missing Data Files**
- Check the datas section in OCRMill.spec
- Ensure templates/ folder exists
- Verify Millworks submodule is present

### Build Configuration

The build is configured in [OCRMill.spec](OCRMill.spec):

**Key Settings:**
- `console=False` - No console window (GUI app)
- `upx=True` - Compression enabled
- `exclude_binaries=True` - Separate DLLs in _internal folder

**Included Data Files:**
- config.json - Configuration
- parts_database.db - Database
- templates/ - Invoice templates
- Resources/ - Additional resources
- Millworks/ - Invoice processor submodule

**Hidden Imports:**
All template modules and dependencies are explicitly listed to ensure
they're included in the build.

### Version Information

Current version: **2.5.0**
- Python: 3.13.9
- PyInstaller: 6.17.0
- Platform: Windows 64-bit

### Distribution

The final executable can be distributed as:
1. Zip file (created by prepare_distribution.bat)
2. Direct folder copy (copy entire dist\OCRMill\ folder)
3. Installer (future enhancement - NSIS or Inno Setup)

End users need:
- Windows 10 or later (64-bit)
- 4GB RAM minimum
- 500MB disk space
- No Python installation required!

### Next Steps

See [DISTRIBUTION.md](DISTRIBUTION.md) for end-user installation instructions.
