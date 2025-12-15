"""Test Section 232 Compiled Tariff lookup functions."""
from pathlib import Path
from parts_database import PartsDatabase

# Initialize database
db = PartsDatabase(Path("Resources/parts_database.db"))

print("=" * 80)
print("Section 232 Compiled Tariff Lookup Test")
print("=" * 80)

# Test 1: Get statistics
print("\n1. Section 232 Tariff Statistics:")
stats = db.get_section_232_statistics()
for key, value in sorted(stats.items()):
    print(f"   {key}: {value}")

# Test 2: Check specific HTS codes
print("\n2. Testing specific HTS codes:")
test_codes = [
    "7301.20.10",  # Should be steel
    "7610.10.00",  # Should be aluminum
    "7406.10.00",  # Should be copper
    "4403.11.00",  # Should be wood
    "9403.20.0082",  # Should not be 232
]

for code in test_codes:
    is_232 = db.is_section_232_tariff(code)
    material = db.get_section_232_material_type(code)
    decl = db.get_section_232_declaration_code(code)
    print(f"   {code}: {'YES' if is_232 else 'NO'} ({material if material else 'N/A'}, Decl: {decl if decl else 'None'})")

# Test 3: Get full details for HTS code
print("\n3. Full details for multi-material HTS code (0402.99.68):")
details = db.get_section_232_details("0402.99.68")
for detail in details:
    print(f"   Material: {detail['material']}")
    print(f"   Classification: {detail['classification']}")
    print(f"   Declaration: {detail['declaration_required']}")
    print(f"   Chapter: {detail['chapter']} - {detail['chapter_description']}")
    print()

# Test 4: Check with material type filter
print("4. Testing HTS code with material type filter:")
code = "0402.99.68"
for material in ['Steel', 'Aluminum', 'Copper']:
    is_match = db.is_section_232_tariff(code, material)
    print(f"   {code} is {material} tariff: {is_match}")

# Test 5: Get tariffs by material type (first 5 each)
print("\n5. Sample tariffs by material:")
for material in ['Steel', 'Aluminum', 'Copper', 'Wood']:
    tariffs = db.get_all_section_232_tariffs(material)
    print(f"\n   {material} tariffs ({len(tariffs)} total, showing first 5):")
    for tariff in tariffs[:5]:
        print(f"     {tariff['hts_code']}: {tariff['classification'][:60]}...")

# Test 6: Declaration codes
print("\n6. Declaration codes by material type:")
test_hts_by_material = {
    'Steel': '0402.99.68',
    'Aluminum': '0402.99.68',
    'Copper': '7406.10.00',
    'Wood': '4403.11.00'
}

for material, hts in test_hts_by_material.items():
    decl = db.get_section_232_declaration_code(hts, material)
    print(f"   {material} ({hts}): {decl}")

print("\n" + "=" * 80)
print("All tests completed successfully!")
print("=" * 80)
