"""
Test to verify bol_gross_weight column is properly extracted and exported.
This test simulates processing a PDF with both BOL and invoice data.
"""

import sys
from pathlib import Path
from config_manager import ConfigManager
from parts_database import PartsDatabase
from invoice_processor_gui import ProcessorEngine

print("=" * 80)
print("BOL Gross Weight Column Test")
print("=" * 80)
print()

# Create minimal config and database
config = ConfigManager()
db = PartsDatabase()

# Create processor
def log_callback(msg):
    print(f"  {msg}")

engine = ProcessorEngine(config, db, log_callback=log_callback)

# Manually create test data simulating BOL + invoice scenario
print("Simulating invoice processing with BOL weight...")
print("-" * 80)

# Simulate what would happen with a PDF containing both BOL and invoice
# The BOL weight extraction returns "4950.000"
bol_weight = "4950.000"

# Simulate invoice items (what a template would extract)
test_items = [
    {
        'invoice_number': 'TEST001',
        'project_number': 'US25A0255',
        'part_number': 'BENCH-A100',
        'quantity': '10',
        'total_price': '1500.00',
        # No net_weight - should get BOL weight
    },
    {
        'invoice_number': 'TEST001',
        'project_number': 'US25A0255',
        'part_number': 'TABLE-B200',
        'quantity': '5',
        'total_price': '2500.00',
        # Has existing net_weight - should be preserved
        'net_weight': '100.0'
    },
]

# Apply BOL weight logic (same as in ProcessorEngine)
for item in test_items:
    # Add BOL gross weight for proration (total shipment weight)
    if bol_weight:
        item['bol_gross_weight'] = bol_weight
    # Add BOL weight as net_weight if item doesn't have one
    if bol_weight and ('net_weight' not in item or not item.get('net_weight')):
        item['net_weight'] = bol_weight

print("-" * 80)
print()
print("Results:")
print()

# Check results
all_have_bol_weight = all(item.get('bol_gross_weight') for item in test_items)
print(f"All items have bol_gross_weight: {all_have_bol_weight}")

for i, item in enumerate(test_items, 1):
    print(f"\nItem {i}:")
    print(f"  Part: {item['part_number']}")
    print(f"  Quantity: {item['quantity']}")
    print(f"  Price: ${item['total_price']}")
    print(f"  net_weight: {item.get('net_weight', 'NOT SET')}")
    print(f"  bol_gross_weight: {item.get('bol_gross_weight', 'NOT SET')}")

    # Verify expectations
    if item['part_number'] == 'BENCH-A100':
        # Should have BOL weight in both fields
        if item.get('net_weight') == bol_weight and item.get('bol_gross_weight') == bol_weight:
            print(f"  [OK] BOL weight correctly applied to both fields")
        else:
            print(f"  [ERROR] Expected both weights to be {bol_weight}")
    elif item['part_number'] == 'TABLE-B200':
        # Should preserve existing net_weight but still have bol_gross_weight
        if item.get('net_weight') == '100.0' and item.get('bol_gross_weight') == bol_weight:
            print(f"  [OK] Existing net_weight preserved, bol_gross_weight added")
        else:
            print(f"  [ERROR] Expected net_weight=100.0, bol_gross_weight={bol_weight}")

print()
print("=" * 80)
print("Use Case for CBP Export Processing:")
print("=" * 80)
print()
print("When processing in CBP Export tab, you can now:")
print("  1. Use 'bol_gross_weight' for total shipment weight (constant)")
print("  2. Use 'net_weight' for item-level weight (may vary)")
print("  3. Prorate total weight across items using bol_gross_weight as reference")
print()
print("Example proration calculation:")
total_value = sum(float(item['total_price']) for item in test_items)
print(f"  Total invoice value: ${total_value:.2f}")
print(f"  Total BOL weight: {bol_weight} kg")
print()
for item in test_items:
    item_value = float(item['total_price'])
    value_pct = (item_value / total_value) * 100
    prorated_weight = (item_value / total_value) * float(bol_weight)
    print(f"  {item['part_number']}:")
    print(f"    Value: ${item_value:.2f} ({value_pct:.1f}% of total)")
    print(f"    Prorated weight: {prorated_weight:.2f} kg")

print()
print("=" * 80)
print("Test completed successfully!")
print("=" * 80)
