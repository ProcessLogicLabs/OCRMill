"""Analyze a PDF for multiple invoices."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import pdfplumber
import re

pdf_path = Path("input/Processed/PL US25A0216 (1).pdf")

print(f"Analyzing: {pdf_path.name}")
print("=" * 80)

with pdfplumber.open(pdf_path) as pdf:
    print(f"\nTotal pages: {len(pdf.pages)}")
    print("\n" + "=" * 80)
    print("INVOICE NUMBERS FOUND PER PAGE:")
    print("=" * 80)

    all_invoices = set()
    all_projects = set()

    for i, page in enumerate(pdf.pages, 1):
        text = page.extract_text()
        if text:
            # Look for invoice numbers
            inv_matches = re.findall(r'(?:Proforma\s+)?[Ii]nvoice\s+(?:number|n)\.?\s*:?\s*(\d+(?:/\d+)?)', text)

            # Look for project numbers
            proj_matches = re.findall(r'(?:\d+\.\s*)?[Pp]roject\s*(?:n\.?)?\s*:?\s*(US\d+[A-Z]\d+)', text, re.IGNORECASE)

            # Look for packing list
            is_pl = 'packing list' in text.lower()

            page_type = "PACKING LIST" if is_pl else "INVOICE"

            if inv_matches or proj_matches:
                print(f"\nPage {i:3d} ({page_type}):")
                if inv_matches:
                    print(f"  Invoices: {', '.join(inv_matches)}")
                    all_invoices.update(inv_matches)
                if proj_matches:
                    print(f"  Projects: {', '.join(proj_matches)}")
                    all_projects.update(proj_matches)

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Unique invoices found: {len(all_invoices)}")
    for inv in sorted(all_invoices):
        print(f"  - {inv}")
    print(f"\nUnique projects found: {len(all_projects)}")
    for proj in sorted(all_projects):
        print(f"  - {proj}")
