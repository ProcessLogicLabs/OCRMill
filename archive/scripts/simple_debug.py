"""Simple debug without unicode issues."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import pdfplumber
from config_manager import ConfigManager
from templates import get_all_templates

pdf_path = Path("input/Failed/2025601736 - mmcité usa - US25A0203 (5).pdf")

# Extract text
with pdfplumber.open(pdf_path) as pdf:
    full_text = ""
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

print(f"Total text: {len(full_text)} chars")

# Test templates
config = ConfigManager()
templates = get_all_templates()

for name, template in templates.items():
    enabled = config.get_template_enabled(name)
    can_proc = template.can_process(full_text)
    score = template.get_confidence_score(full_text)

    print(f"\n{name}:")
    print(f"  Enabled: {enabled}")
    print(f"  Can process: {can_proc}")
    print(f"  Score: {score}")

    if can_proc:
        inv, proj, items = template.extract_all(full_text)
        print(f"  Invoice: {inv}")
        print(f"  Project: {proj}")
        print(f"  Items: {len(items)}")
        if items:
            print(f"  First item: {items[0]}")
