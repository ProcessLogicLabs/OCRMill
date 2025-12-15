"""
Verify OCRMill Installation and Parts Database Setup
Checks all dependencies and configurations are correct.
"""

import sys
from pathlib import Path

def check_dependencies():
    """Check if all required packages are installed."""
    print("Checking dependencies...")

    required_packages = {
        'pdfplumber': 'PDF processing',
        'PIL': 'Image handling',
        'pandas': 'Data processing',
        'openpyxl': 'Excel file reading',
        'tkinter': 'GUI framework'
    }

    missing = []

    for package, purpose in required_packages.items():
        try:
            if package == 'PIL':
                import PIL
            elif package == 'tkinter':
                import tkinter
            else:
                __import__(package)
            print(f"  [OK] {package:15s} - {purpose}")
        except ImportError:
            print(f"  [MISSING] {package:15s} - {purpose}")
            missing.append(package)

    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False

    print("\n[OK] All dependencies installed")
    return True


def check_modules():
    """Check if OCRMill modules import correctly."""
    print("\nChecking OCRMill modules...")

    modules = {
        'config_manager': 'Configuration management',
        'parts_database': 'Parts database system',
        'invoice_processor_gui': 'Main GUI application',
        'templates.mmcite_czech': 'Czech invoice template',
        'templates.mmcite_brazilian': 'Brazilian invoice template'
    }

    errors = []

    for module, description in modules.items():
        try:
            __import__(module)
            print(f"  [OK] {module:30s} - {description}")
        except Exception as e:
            print(f"  [ERROR] {module:30s} - {e}")
            errors.append(module)

    if errors:
        print(f"\nModule errors: {', '.join(errors)}")
        return False

    print("\n[OK] All modules loaded successfully")
    return True


def check_folders():
    """Check if required folders exist."""
    print("\nChecking folder structure...")

    folders = {
        'input': 'PDF input folder',
        'output': 'CSV output folder',
        'reports': 'HTS codes and reports',
        'templates': 'Invoice templates'
    }

    missing = []

    for folder, description in folders.items():
        folder_path = Path(folder)
        if folder_path.exists():
            print(f"  [OK] {folder:15s} - {description}")
        else:
            print(f"  [CREATE] {folder:15s} - {description}")
            folder_path.mkdir(exist_ok=True)

    print("\n[OK] All folders ready")
    return True


def check_database():
    """Check if parts database is initialized."""
    print("\nChecking parts database...")

    try:
        from parts_database import PartsDatabase

        db = PartsDatabase()
        stats = db.get_statistics()

        print(f"  [OK] Database initialized")
        print(f"  Total parts: {stats['total_parts']}")
        print(f"  Total occurrences: {stats['total_occurrences']}")
        print(f"  Total invoices: {stats['total_invoices']}")
        print(f"  HTS codes loaded: {stats['parts_with_hts']}")

        # Check HTS codes
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM hts_codes")
        hts_count = cursor.fetchone()['count']

        if hts_count == 0:
            print(f"\n  [WARNING] No HTS codes loaded")
            print(f"  Run: python load_hts_mapping.py")
        else:
            print(f"  [OK] {hts_count} HTS codes loaded")

        db.close()
        return True

    except Exception as e:
        print(f"  [ERROR] Database check failed: {e}")
        return False


def check_config():
    """Check if config file exists."""
    print("\nChecking configuration...")

    config_file = Path("config.json")

    if config_file.exists():
        print(f"  [OK] config.json exists")

        try:
            from config_manager import ConfigManager
            config = ConfigManager()

            print(f"  Input folder: {config.input_folder}")
            print(f"  Output folder: {config.output_folder}")
            print(f"  Poll interval: {config.poll_interval}s")
            print(f"  Consolidate multi-invoice: {config.consolidate_multi_invoice}")

            return True
        except Exception as e:
            print(f"  [ERROR] Config error: {e}")
            return False
    else:
        print(f"  [CREATE] Creating default config.json")
        from config_manager import ConfigManager
        config = ConfigManager()
        print(f"  [OK] Default configuration created")
        return True


def check_hts_file():
    """Check if HTS mapping file exists."""
    print("\nChecking HTS mapping file...")

    hts_file = Path("reports/mmcite_hts.xlsx")

    if hts_file.exists():
        print(f"  [OK] mmcite_hts.xlsx found")
        return True
    else:
        print(f"  [WARNING] mmcite_hts.xlsx not found in reports/")
        print(f"  Place the HTS mapping Excel file in the reports/ folder")
        print(f"  Then run: python load_hts_mapping.py")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("OCRMill Installation Verification")
    print("=" * 60)
    print()

    checks = [
        check_dependencies,
        check_modules,
        check_folders,
        check_config,
        check_hts_file,
        check_database
    ]

    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"\n[ERROR] Check failed: {e}")
            results.append(False)
        print()

    print("=" * 60)

    if all(results):
        print("[SUCCESS] OCRMill is fully configured and ready to use!")
        print()
        print("Quick Start:")
        print("  1. Load HTS codes: python load_hts_mapping.py")
        print("  2. Start GUI: python invoice_processor_gui.py")
        print("  3. View parts database: python parts_database_viewer.py")
    else:
        print("[WARNING] Some checks failed or need attention")
        print()
        print("Review the messages above and address any issues")
        print("Most warnings can be resolved by running:")
        print("  python load_hts_mapping.py")

    print("=" * 60)


if __name__ == "__main__":
    main()
