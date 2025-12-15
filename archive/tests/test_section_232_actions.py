"""Test Section 232 Actions lookup functions."""
from pathlib import Path
from parts_database import PartsDatabase

# Initialize database
db = PartsDatabase(Path("Resources/parts_database.db"))

print("=" * 80)
print("Section 232 Actions Lookup Test")
print("=" * 80)

# Test 1: Get statistics
print("\n1. Section 232 Actions Statistics:")
stats = db.get_section_232_actions_statistics()
for key, value in sorted(stats.items()):
    print(f"   {key}: {value}")

# Test 2: Get all action types
print("\n2. Available Action Types:")
action_types = db.get_section_232_action_types()
for action_type in action_types:
    print(f"   - {action_type}")

# Test 3: Get declaration requirements by action type
print("\n3. Declaration Requirements:")
for action_type in ['232 STEEL', '232 ALUMINUM', '232 Copper']:
    decl = db.get_section_232_declaration_required(action_type)
    print(f"   {action_type}: {decl}")

# Test 4: Lookup specific tariff action
print("\n4. Specific Tariff Action Lookup:")
test_tariffs = ["99038187", "99038502", "99038244"]
for tariff_no in test_tariffs:
    action = db.get_section_232_action(tariff_no)
    if action:
        print(f"   Tariff {tariff_no}:")
        print(f"     Action: {action['action']}")
        print(f"     Description: {action['tariff_description']}")
        print(f"     Rate: {action['advalorem_rate']}")
        print(f"     Declaration: {action['additional_declaration']}")
    else:
        print(f"   Tariff {tariff_no}: Not found")

# Test 5: Get all actions for a specific type
print("\n5. Sample Steel Actions (first 3):")
steel_actions = db.get_section_232_actions_by_type("232 STEEL")
for action in steel_actions[:3]:
    print(f"   {action['tariff_no']}: {action['tariff_description'][:60]}...")
    print(f"     Rate: {action['advalorem_rate']}, Decl: {action['additional_declaration']}")

print("\n6. Sample Aluminum Actions (first 3):")
aluminum_actions = db.get_section_232_actions_by_type("232 ALUMINUM")
for action in aluminum_actions[:3]:
    print(f"   {action['tariff_no']}: {action['tariff_description'][:60]}...")
    print(f"     Rate: {action['advalorem_rate']}, Decl: {action['additional_declaration']}")

# Test 7: Combined materials action
print("\n7. Aluminum & Steel Combined Actions:")
combined_actions = db.get_section_232_actions_by_type("232 Aluminum & Steel")
print(f"   Found {len(combined_actions)} combined actions")
if combined_actions:
    for action in combined_actions[:2]:
        print(f"   {action['tariff_no']}: {action['tariff_description'][:60]}...")

print("\n" + "=" * 80)
print("All tests completed successfully!")
print("=" * 80)
