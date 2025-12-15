"""Test automotive HTS codes integration."""
from pathlib import Path
from parts_database import PartsDatabase

db = PartsDatabase(Path("Resources/parts_database.db"))

print("=" * 80)
print("Automotive HTS Codes Test")
print("=" * 80)

# Get statistics
print("\nSection 232 Statistics (with Auto):")
stats = db.get_section_232_statistics()
for k, v in sorted(stats.items()):
    print(f"  {k}: {v}")

# Test specific auto HTS codes
print("\nTesting specific automotive HTS codes:")
test_codes = [
    "4009.12.0020",  # Should be Auto only
    "8708.10.30",    # Should be Auto + Aluminum + Steel
    "8708.10.60",    # Should be Auto + Aluminum
    "7320.20.10",    # Should be Auto + Steel
]

for code in test_codes:
    details = db.get_section_232_details(code)
    materials = [d['material'] for d in details]
    print(f"\n  {code}:")
    print(f"    Materials: {', '.join(materials)}")
    for detail in details:
        print(f"    - {detail['material']}: {detail['classification']}, Decl: {detail['declaration_required']}")

# Get all auto HTS codes
print("\nAuto HTS codes sample (first 20):")
auto_tariffs = db.get_all_section_232_tariffs('Auto')
for tariff in auto_tariffs[:20]:
    print(f"  {tariff['hts_code']}: {tariff['classification']}")

print(f"\nTotal Auto HTS codes: {len(auto_tariffs)}")

print("\n" + "=" * 80)
print("Test complete!")
print("=" * 80)
