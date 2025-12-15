# Archive Directory

This directory contains files that were part of the development process but are no longer actively used in the production application.

**Archived Date**: December 14, 2025

## Structure

### `/tests` - Test Files (9 files)
Test scripts used during development to validate specific features:
- `test_auto_hts.py` - HTS code automation tests
- `test_bol_extraction.py` - Bill of Lading extraction tests
- `test_bol_gross_weight.py` - BOL gross weight calculation tests
- `test_bol_integration.py` - BOL integration tests
- `test_engine.py` - Processing engine tests
- `test_processing.py` - Invoice processing tests
- `test_section_232_actions.py` - Section 232 action tests
- `test_section_232_compiled.py` - Section 232 compiled tariff tests
- `test_section_232_lookup.py` - Section 232 lookup tests

### `/scripts` - Utility Scripts (20 files)
One-time use scripts and deprecated modules:

**Debug/Analysis Scripts:**
- `analyze_multi_invoice.py` - Multi-invoice analysis tool
- `check_packing_list.py` - Packing list validation
- `consolidate_and_match.py` - Data consolidation utility
- `debug_pdf.py` - PDF debugging tool
- `simple_debug.py` - Simple debugging script
- `debug_output.txt` - Debug output logs

**Import/Setup Scripts:**
- `extract_auto_hts.py` - Auto parts HTS code extraction
- `import_232_actions.py` - Import Section 232 actions
- `import_232_tariffs.py` - Import Section 232 tariffs
- `import_232_tariffs_compiled.py` - Import compiled tariffs
- `import_auto_parts_hts.py` - Import automotive HTS codes
- `load_hts_mapping.py` - Load HTS code mappings
- `rebuild_parts_database.py` - Database rebuild utility
- `auto_parts_hts_codes.txt` - Auto parts HTS reference data

**Deprecated Application Files:**
- `invoice_processor.py` - Original CLI processor (replaced by GUI)
- `invoice_processor_tray.py` - System tray version (replaced by GUI)
- `start_all.bat` - Old batch launcher (replaced by individual launchers)

**Unused Utilities:**
- `match_reports.py` - Report matching utility
- `parts_report.py` - Parts reporting tool
- `part_description_extractor.py` - Description extraction utility

### `/docs` - Historical Documentation (19 files)
Development and feature implementation documentation:
- `BOL_IMPLEMENTATION_SUMMARY.md` - Bill of Lading feature summary
- `BRAZILIAN_UPDATES.md` - Brazilian invoice template updates
- `CBP_DERIVATIVE_SPLITTING.md` - CBP derivative splitting feature
- `CBP_EXPORT_FORMAT.md` - CBP export format documentation
- `CBP_EXPORT_WORKFLOW.md` - CBP export workflow guide
- `COMPLETE_CBP_FEATURE_SUMMARY.md` - Complete CBP feature overview
- `COMPLETE_UPDATES_SUMMARY.md` - Complete update history
- `CSV_FORMAT_UPDATE.md` - CSV format change documentation
- `DESCRIPTION_EXTRACTION.md` - Description extraction feature
- `FIXES_APPLIED.md` - Bug fix documentation
- `ITEM_EXCLUSIONS.md` - Item exclusion feature
- `MULTI_INVOICE_AND_FILTERS.md` - Multi-invoice processing
- `MULTI_INVOICE_CONSOLIDATION.md` - Invoice consolidation feature
- `PACKING_LIST_FIX.md` - Packing list bug fixes
- `PARTS_DATABASE.md` - Parts database design
- `PARTS_DATABASE_IMPLEMENTATION.md` - Database implementation guide
- `PARTS_DATABASE_UPDATE.md` - Database update documentation
- `SECTION_232_TARIFF_REFERENCE.md` - Section 232 tariff reference
- `THREADING_FIX.md` - Threading issue fixes

## Active Project Files

The following files remain active in the root directory:

**Core Application (6 Python files):**
- `invoice_processor_gui.py` - Main GUI application
- `parts_database.py` - Parts database management
- `parts_database_viewer.py` - Standalone parts viewer
- `config_manager.py` - Configuration management
- `verify_232_tariffs.py` - Section 232 tariff verification
- `verify_installation.py` - Installation verification

**Launchers (2 Batch files):**
- `start_invoice_processor.bat` - Launch main GUI
- `start_parts_viewer.bat` - Launch parts database viewer

**Documentation (2 Markdown files):**
- `README.md` - Project overview
- `QUICK_START.md` - Quick start guide

## Restoration

If you need to restore any archived file, simply copy it back to the root directory:
```bash
cp archive/scripts/filename.py .
```

## Notes

- All archived files are preserved in their original state
- Test files can be used as reference for understanding feature implementation
- Documentation files contain valuable historical context about feature development
- Deprecated scripts may still be useful for understanding data migration or one-time operations
