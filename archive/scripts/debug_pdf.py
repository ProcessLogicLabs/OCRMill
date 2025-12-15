"""
Debug script to test why a specific PDF is failing.
"""
from pathlib import Path
import pdfplumber
from config_manager import ConfigManager
from invoice_processor_gui import ProcessorEngine

def debug_pdf(pdf_path):
    """Debug a specific PDF."""
    print(f"Debugging: {pdf_path}")
    print("=" * 80)

    # Create config and engine
    config = ConfigManager()

    def log_to_console(msg):
        print(msg)

    engine = ProcessorEngine(config, log_callback=log_to_console)

    # Extract text
    print("\n1. EXTRACTING TEXT FROM PDF...")
    print("-" * 80)
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text += text + "\n"
                print(f"Page {i+1}: {len(text)} characters extracted")

    print(f"\nTotal text length: {len(full_text)} characters")
    print("\nFirst 500 characters:")
    print("-" * 80)
    try:
        print(full_text[:500])
    except UnicodeEncodeError:
        print(full_text[:500].encode('utf-8', errors='replace').decode('utf-8'))
    print("-" * 80)

    # Test template matching
    print("\n2. TESTING TEMPLATE MATCHING...")
    print("-" * 80)
    template = engine.get_best_template(full_text)

    if template:
        print(f"\n3. PROCESSING WITH TEMPLATE: {template.name}")
        print("-" * 80)

        # Check if packing list
        is_pl = template.is_packing_list(full_text)
        print(f"Is packing list: {is_pl}")

        if not is_pl:
            # Extract data
            invoice_num, project_num, items = template.extract_all(full_text)
            print(f"\nInvoice Number: {invoice_num}")
            print(f"Project Number: {project_num}")
            print(f"Items extracted: {len(items)}")

            if items:
                print("\nFirst item:")
                print(items[0])
            else:
                print("\nNO ITEMS EXTRACTED!")
                print("\nTrying manual extraction to debug...")

                # Try to see what extract_line_items returns
                raw_items = template.extract_line_items(full_text)
                print(f"Raw items from extract_line_items: {len(raw_items)}")
                if raw_items:
                    print("First raw item:")
                    print(raw_items[0])
    else:
        print("\nNO TEMPLATE MATCHED!")
        print("\nChecking templates manually:")
        for name, tmpl in engine.templates.items():
            enabled = config.get_template_enabled(name) and tmpl.enabled
            can_process = tmpl.can_process(full_text)
            score = tmpl.get_confidence_score(full_text)
            print(f"  {name}:")
            print(f"    - Enabled: {enabled}")
            print(f"    - Can process: {can_process}")
            print(f"    - Score: {score}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
    else:
        # Default to the PDF in input folder
        input_folder = Path("input")
        pdfs = list(input_folder.glob("*.pdf"))
        if pdfs:
            pdf_path = pdfs[0]
        else:
            print("No PDF found. Usage: python debug_pdf.py <path_to_pdf>")
            sys.exit(1)

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)

    debug_pdf(pdf_path)
