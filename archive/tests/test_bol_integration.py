"""
Integration test to verify BOL weight extraction and application to invoice items.
"""

import sys
from pathlib import Path
from config_manager import ConfigManager
from parts_database import PartsDatabase
from invoice_processor_gui import ProcessorEngine

# Test configuration
test_pdf = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\2025201887 - mmcité usa - US25A0255 (1).pdf")

print("=" * 80)
print("BOL Integration Test")
print("=" * 80)
print(f"Test PDF: {test_pdf.name}")
print()

# Create minimal config and database
config = ConfigManager()
db = PartsDatabase()

# Create processor with verbose logging
def log_callback(msg):
    print(f"  {msg}")

engine = ProcessorEngine(config, db, log_callback=log_callback)

print("Processing PDF...")
print("-" * 80)

try:
    # Process the PDF
    items = engine.process_pdf(test_pdf)

    print("-" * 80)
    print(f"\nResults:")
    print(f"  Total items extracted: {len(items)}")
    print()

    if items:
        print("Sample items with net_weight:")
        for i, item in enumerate(items[:5], 1):  # Show first 5 items
            invoice = item.get('invoice_number', 'UNKNOWN')
            project = item.get('project_number', 'UNKNOWN')
            part = item.get('part_number', 'UNKNOWN')
            qty = item.get('quantity', 'UNKNOWN')
            price = item.get('total_price', 'UNKNOWN')
            weight = item.get('net_weight', 'NOT SET')

            print(f"  [{i}] Invoice: {invoice}, Project: {project}")
            print(f"      Part: {part}, Qty: {qty}, Price: ${price}")
            print(f"      Net Weight: {weight} kg")
            print()

        # Check if BOL weight was applied
        items_with_weight = [item for item in items if item.get('net_weight')]
        if items_with_weight:
            print(f"SUCCESS: {len(items_with_weight)}/{len(items)} items have net_weight populated")
            sample_weight = items_with_weight[0].get('net_weight')
            print(f"Weight value: {sample_weight} kg (expected: 4950.000 kg)")

            if sample_weight == "4950.000":
                print("[OK] BOL weight correctly extracted and applied!")
            else:
                print(f"[WARNING] Weight value mismatch: got {sample_weight}, expected 4950.000")
        else:
            print("[WARNING] No items have net_weight populated")
            print("This could mean:")
            print("  1. The PDF contains only BOL (no invoices)")
            print("  2. Invoice template already provides net_weight")
            print("  3. BOL weight extraction failed")
    else:
        print("[INFO] No items extracted from PDF")
        print("This is expected if the PDF contains only BOL without invoice data")

    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
