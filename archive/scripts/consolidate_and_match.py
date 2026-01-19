"""
Section 232 Consolidation Script
Prepares OCR Mill CSV outputs for Millworks Section 232 processing.

This script:
1. Consolidates multiple invoice CSVs into a single file
2. Adds columns required by Millworks
3. Validates material composition data
4. Generates a report ready for Section 232 tariff calculations
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def consolidate_invoices(output_folder: Path, output_file: Path):
    """
    Consolidate all CSV files in output folder into a single master file.

    Args:
        output_folder: Folder containing individual invoice CSVs
        output_file: Path to write consolidated CSV
    """
    print("Section 232 Consolidation Utility")
    print("=" * 80)

    csv_files = list(output_folder.glob("*.csv"))
    if not csv_files:
        print("No CSV files found in output folder")
        return

    print(f"\nFound {len(csv_files)} CSV file(s)")

    # Collect all items
    all_items = []
    invoices_processed = set()

    # Standard columns that should be in every CSV
    required_columns = [
        'invoice_number', 'project_number', 'part_number',
        'quantity', 'total_price'
    ]

    # Material composition columns for Section 232
    material_columns = [
        'steel_pct', 'steel_kg', 'steel_value',
        'aluminum_pct', 'aluminum_kg', 'aluminum_value',
        'net_weight'
    ]

    # Additional columns
    extra_columns = ['ncm_code', 'hts_code', 'unit_price']

    for csv_file in csv_files:
        print(f"\nProcessing: {csv_file.name}")

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                file_items = list(reader)

                if file_items:
                    invoice = file_items[0].get('invoice_number', 'UNKNOWN')
                    project = file_items[0].get('project_number', 'UNKNOWN')
                    print(f"  Invoice: {invoice}, Project: {project}, Items: {len(file_items)}")

                    # Check for material data
                    has_material_data = any(
                        item.get('steel_kg') or item.get('aluminum_kg')
                        for item in file_items
                    )

                    if has_material_data:
                        material_count = sum(
                            1 for item in file_items
                            if item.get('steel_kg') or item.get('aluminum_kg')
                        )
                        print(f"  √ Material composition data: {material_count}/{len(file_items)} items")
                    else:
                        print(f"  ! No material composition data found")

                    all_items.extend(file_items)
                    invoices_processed.add(invoice)

        except Exception as e:
            print(f"  X Error: {e}")

    if not all_items:
        print("\nX No items to consolidate")
        return

    # Determine all columns present in the data
    all_columns = set()
    for item in all_items:
        all_columns.update(item.keys())

    # Order columns logically
    ordered_columns = required_columns.copy()

    # Add material columns if present
    for col in material_columns:
        if col in all_columns:
            ordered_columns.append(col)

    # Add extra columns if present
    for col in extra_columns:
        if col in all_columns:
            ordered_columns.append(col)

    # Add any remaining columns
    for col in sorted(all_columns):
        if col not in ordered_columns:
            ordered_columns.append(col)

    # Write consolidated file
    print(f"\n{'=' * 80}")
    print("Writing consolidated file...")
    print(f"Output: {output_file}")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=ordered_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_items)

    print(f"\n{'=' * 80}")
    print("CONSOLIDATION COMPLETE")
    print(f"{'=' * 80}")
    print(f"Invoices processed: {len(invoices_processed)}")
    print(f"Total line items: {len(all_items)}")
    print(f"Output file: {output_file}")

    # Generate statistics
    print(f"\n{'=' * 80}")
    print("MATERIAL COMPOSITION SUMMARY")
    print(f"{'=' * 80}")

    items_with_steel = sum(1 for item in all_items if item.get('steel_kg'))
    items_with_aluminum = sum(1 for item in all_items if item.get('aluminum_kg'))
    items_with_material = sum(
        1 for item in all_items
        if item.get('steel_kg') or item.get('aluminum_kg')
    )

    print(f"Items with steel data: {items_with_steel} ({items_with_steel/len(all_items)*100:.1f}%)")
    print(f"Items with aluminum data: {items_with_aluminum} ({items_with_aluminum/len(all_items)*100:.1f}%)")
    print(f"Items with any material data: {items_with_material} ({items_with_material/len(all_items)*100:.1f}%)")

    if items_with_material > 0:
        total_steel_value = sum(
            float(item.get('steel_value', 0) or 0)
            for item in all_items
        )
        total_aluminum_value = sum(
            float(item.get('aluminum_value', 0) or 0)
            for item in all_items
        )

        print(f"\nTotal steel value: ${total_steel_value:,.2f}")
        print(f"Total aluminum value: ${total_aluminum_value:,.2f}")
        print(f"Combined material value: ${total_steel_value + total_aluminum_value:,.2f}")

    # Group by project
    print(f"\n{'=' * 80}")
    print("BY PROJECT")
    print(f"{'=' * 80}")

    by_project = defaultdict(list)
    for item in all_items:
        proj = item.get('project_number', 'UNKNOWN')
        by_project[proj].append(item)

    for project in sorted(by_project.keys()):
        items = by_project[project]
        invoices = set(item.get('invoice_number') for item in items)
        print(f"{project}: {len(items)} items across {len(invoices)} invoice(s)")

    print(f"\n{'=' * 80}")
    print("NEXT STEPS: Import into Millworks")
    print(f"{'=' * 80}")
    print("1. Open Millworks application")
    print("2. Navigate to Import -> Invoice Data")
    print(f"3. Select file: {output_file.name}")
    print("4. Map columns to parts database")
    print("5. Run Section 232 analysis")
    print("6. Export customs forms")


def main():
    """Main entry point."""
    # Default to output folder in current directory
    if len(sys.argv) > 1:
        output_folder = Path(sys.argv[1])
    else:
        output_folder = Path("output")

    if not output_folder.exists():
        print(f"Error: Folder not found: {output_folder}")
        print("Usage: python consolidate_and_match.py [output_folder]")
        return

    # Create consolidated filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    consolidated_file = output_folder / f"consolidated_invoices_{timestamp}.csv"

    print(f"Output folder: {output_folder}")
    print(f"Consolidated file: {consolidated_file.name}\n")

    consolidate_invoices(output_folder, consolidated_file)


if __name__ == "__main__":
    main()
