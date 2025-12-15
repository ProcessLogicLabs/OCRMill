"""
Test script to verify BOL weight extraction from sample PDF.
"""

import pdfplumber
from pathlib import Path
from templates.bill_of_lading import BillOfLadingTemplate

# Sample BOL PDF path
pdf_path = Path(r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\2025201887 - mmcité usa - US25A0255 (1).pdf")

print(f"Testing BOL extraction from: {pdf_path.name}")
print("=" * 80)

# Initialize BOL template
bol_template = BillOfLadingTemplate()

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} page(s)")
        print()

        for page_num, page in enumerate(pdf.pages, 1):
            print(f"Page {page_num}:")
            page_text = page.extract_text()

            if not page_text:
                print("  No text extracted")
                continue

            # Check if BOL
            is_bol = bol_template.can_process(page_text)
            print(f"  Is BOL: {is_bol}")

            if is_bol:
                # Get confidence score
                confidence = bol_template.get_confidence_score(page_text)
                print(f"  Confidence: {confidence:.2f}")

                # Extract weight
                weight = bol_template.extract_gross_weight(page_text)
                print(f"  Gross Weight: {weight} kg" if weight else "  Gross Weight: NOT FOUND")

                # Extract bill number
                bill_num = bol_template.extract_bill_number(page_text)
                print(f"  Bill Number: {bill_num}" if bill_num else "  Bill Number: NOT FOUND")

                # Extract container number
                container = bol_template.extract_container_number(page_text)
                print(f"  Container: {container}" if container else "  Container: NOT FOUND")

            print()

    print("=" * 80)
    print("Test completed successfully!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
