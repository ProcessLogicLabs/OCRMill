"""Test Section 232 tariff lookup functions."""
from pathlib import Path
from parts_database import PartsDatabase

# Initialize database
db = PartsDatabase(Path("Resources/parts_database.db"))

print("=" * 80)
print("Section 232 Tariff Lookup Test")
print("=" * 80)

# Test 1: Get statistics
print("\n1. Section 232 Statistics:")
stats = db.get_section_232_statistics()
for key, value in stats.items():
    print(f"   {key}: {value}")

# Test 2: Check if specific HTS codes are Section 232
print("\n2. Testing specific HTS codes:")
test_codes = [
    "7301.20.10",  # Should be steel
    "7610.10.00",  # Should be aluminum
    "9403.20.0082",  # Should not be 232
    "7308.90.6000",  # Should be steel
]

for code in test_codes:
    is_232 = db.is_section_232_tariff(code)
    material = db.get_section_232_material_type(code)
    print(f"   {code}: {'YES' if is_232 else 'NO'} ({material if material else 'N/A'})")

# Test 3: Check with material type filter
print("\n3. Testing HTS code with material type:")
code = "7301.20.10"
is_steel = db.is_section_232_tariff(code, 'steel')
is_aluminum = db.is_section_232_tariff(code, 'aluminum')
print(f"   {code} is steel tariff: {is_steel}")
print(f"   {code} is aluminum tariff: {is_aluminum}")

# Test 4: Get all steel tariffs (first 10)
print("\n4. Sample steel tariffs (first 10):")
steel_tariffs = db.get_all_section_232_tariffs('steel')
for tariff in steel_tariffs[:10]:
    print(f"   {tariff['hts_code']}")

# Test 5: Get all aluminum tariffs (first 10)
print("\n5. Sample aluminum tariffs (first 10):")
aluminum_tariffs = db.get_all_section_232_tariffs('aluminum')
for tariff in aluminum_tariffs[:10]:
    print(f"   {tariff['hts_code']}")

print("\n" + "=" * 80)
print("All tests completed successfully!")
print("=" * 80)
