"""Check packing list detection."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import pdfplumber

pdf_path = Path("input/Failed/2025601736 - mmcité usa - US25A0203 (5).pdf")

with pdfplumber.open(pdf_path) as pdf:
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

# Check for packing list text
lower_text = full_text.lower()

if 'packing list' in lower_text:
    print("FOUND 'packing list' in text!")

    # Find the location
    idx = lower_text.find('packing list')
    context_start = max(0, idx - 100)
    context_end = min(len(full_text), idx + 100)

    print("\nContext around 'packing list':")
    print("=" * 80)
    print(full_text[context_start:context_end])
    print("=" * 80)
else:
    print("NO 'packing list' found in text")

# Also check for 'packing slip'
if 'packing slip' in lower_text:
    print("\nFOUND 'packing slip' in text!")
