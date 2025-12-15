"""Extract HTS codes from automotive parts list."""
import re

# Read the file
with open(r'C:\Users\hpayne\Documents\CBP_INFO\Attachment 2_Auto Parts HTS List.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract HTS codes using regex
hts_codes = re.findall(r'\b\d{4}\.\d{2}(?:\.\d{2,4})?\b', content)

print(f"Total HTS codes found: {len(hts_codes)}")
print(f"Unique codes: {len(set(hts_codes))}")

print("\nFirst 20 codes:")
for code in hts_codes[:20]:
    print(f"  {code}")

print("\nLast 20 codes:")
for code in hts_codes[-20:]:
    print(f"  {code}")

# Save unique codes to file
unique_codes = sorted(set(hts_codes))
with open('auto_parts_hts_codes.txt', 'w') as f:
    for code in unique_codes:
        f.write(f"{code}\n")

print(f"\nSaved {len(unique_codes)} unique codes to auto_parts_hts_codes.txt")
