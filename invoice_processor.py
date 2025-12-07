"""
Invoice PDF Processor
Monitors an input folder for PDF documents, extracts invoice line item data
(part number, quantity, price) using OCR, and saves to CSV files.

Designed for mmcité invoices with format:
type / description | Project | Qty | Price | VAT (%) | Price after taxes
"""

__version__ = "1.3.1"

import os
import re
import csv
import time
import logging
from datetime import datetime
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('invoice_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
INPUT_FOLDER = Path("input")
OUTPUT_FOLDER = Path("output")
PROCESSED_FOLDER = INPUT_FOLDER / "Processed"
POLL_INTERVAL = 60  # seconds


def setup_folders():
    """Create necessary folders if they don't exist."""
    for folder in [INPUT_FOLDER, OUTPUT_FOLDER, PROCESSED_FOLDER]:
        folder.mkdir(exist_ok=True, parents=True)
        logger.info(f"Ensured folder exists: {folder}")


def extract_invoice_number(text: str) -> str:
    """Extract the proforma invoice number from the PDF text."""
    # Look for patterns like "Proforma invoice no.: US25A0240d" or "project n.: US25A0240"
    patterns = [
        r'Proforma\s+invoice\s+no\.?\s*:?\s*([A-Z0-9]+[a-z]?)',
        r'project\s+n\.?\s*:?\s*([A-Z0-9]+[a-z]?)',
        r'variable\s+symbol\s*:?\s*(\d+)',
        r'Invoice\s+n\.?\s*:?\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return "UNKNOWN"


def extract_steel_aluminum_data(text: str) -> dict:
    """
    Extract steel and aluminum data from description text.
    
    Format examples (compact, no spaces):
    - Steel: 100%, 16,76kgValue of steel: 91,88$Aluminum: 0%Net weight: 16,76kg
    - Steel: 9%, 14,54kgValue of steel: 68,82$Aluminum: 2%, 4kgValue of aluminum: 18,93$Net weight: 166,10kg
    
    Format examples (spaced, with "Weight of" prefix):
    - Steel: 0% Aluminum: 100% Weight of aluminum: 7,9kg Value of steel: 172,25$ Net weight: 7,9kg
    - Steel: 53% Weight of steel: 10,4kg Value of steel: 189,24$ Aluminum: 47% Weight of aluminum: 9,3kg Value of alumi-
    """
    data = {
        'steel_pct': '',
        'steel_kg': '',
        'steel_value': '',
        'aluminum_pct': '',
        'aluminum_kg': '',
        'aluminum_value': '',
        'net_weight': ''
    }
    
    # Steel percentage: Steel: 100% or Steel: 53%
    steel_pct_match = re.search(r'Steel:\s*(\d+(?:[,.]?\d*)?)%', text, re.IGNORECASE)
    if steel_pct_match:
        data['steel_pct'] = steel_pct_match.group(1).replace(',', '.')
    
    # Steel weight - two formats:
    # Format 1 (compact): Steel: 100%, 16,76kg (weight immediately after %)
    # Format 2 (spaced): Weight of steel: 10,4kg
    steel_kg_compact = re.search(r'Steel:\s*\d+(?:[,.]?\d*)?%[,\s]*(\d+[,.]?\d*)\s*kg', text, re.IGNORECASE)
    steel_kg_spaced = re.search(r'Weight of steel:\s*(\d+[,.]?\d*)\s*kg', text, re.IGNORECASE)
    if steel_kg_compact:
        data['steel_kg'] = steel_kg_compact.group(1).replace(',', '.')
    elif steel_kg_spaced:
        data['steel_kg'] = steel_kg_spaced.group(1).replace(',', '.')
    
    # Value of steel: 91,88$ or 68,82$
    steel_value_match = re.search(r'Value of steel:\s*(\d+[,.]?\d*)\s*\$', text, re.IGNORECASE)
    if steel_value_match:
        data['steel_value'] = steel_value_match.group(1).replace(',', '.')
    
    # Aluminum percentage: Aluminum: 0% or Aluminum: 47%
    aluminum_pct_match = re.search(r'Aluminum:\s*(\d+(?:[,.]?\d*)?)%', text, re.IGNORECASE)
    if aluminum_pct_match:
        data['aluminum_pct'] = aluminum_pct_match.group(1).replace(',', '.')
    
    # Aluminum weight - two formats:
    # Format 1 (compact): Aluminum: 2%, 4kg (weight immediately after %)
    # Format 2 (spaced): Weight of aluminum: 9,3kg
    aluminum_kg_compact = re.search(r'Aluminum:\s*\d+(?:[,.]?\d*)?%[,\s]*(\d+[,.]?\d*)\s*kg', text, re.IGNORECASE)
    aluminum_kg_spaced = re.search(r'Weight of aluminum:\s*(\d+[,.]?\d*)\s*kg', text, re.IGNORECASE)
    if aluminum_kg_compact:
        data['aluminum_kg'] = aluminum_kg_compact.group(1).replace(',', '.')
    elif aluminum_kg_spaced:
        data['aluminum_kg'] = aluminum_kg_spaced.group(1).replace(',', '.')
    
    # Value of aluminum: 18,93$
    aluminum_value_match = re.search(r'Value of aluminum:\s*(\d+[,.]?\d*)\s*\$', text, re.IGNORECASE)
    if aluminum_value_match:
        data['aluminum_value'] = aluminum_value_match.group(1).replace(',', '.')
    
    # Net weight: 16,76kg or 166,10kg
    net_weight_match = re.search(r'Net weight:\s*(\d+[,.]?\d*)\s*kg', text, re.IGNORECASE)
    if net_weight_match:
        data['net_weight'] = net_weight_match.group(1).replace(',', '.')
    
    return data


def extract_line_items_from_text(text: str) -> list:
    """
    Extract invoice line items from text for mmcité invoices.
    
    Format: PartNumber ProjectCode Qty Price VAT PriceAfterTax
    Example: LPU151-J02000 US25A0238 3,00 ks 11.579,04 CZK 0 1.646,70 USD
    """
    line_items = []
    seen_items = set()  # Track unique items to avoid duplicates
    
    # Split text into lines
    lines = text.split('\n')
    
    # Pattern for mmcité line items:
    # PartNumber (alphanumeric with possible dash) followed by project code (US...) 
    # followed by quantity (X,XX ks or X,XX pc) followed by prices
    
    # Main pattern: part_number project_code quantity unit price_czk vat price_usd
    line_pattern = re.compile(
        r'^([A-Z][A-Z0-9\-]+(?:-[A-Z0-9]+)?)\s+'  # Part number (e.g., LPU151-J02000, OBAL160)
        r'(US\d+[A-Z]\d+)\s+'                      # Project code (e.g., US25A0238)
        r'(\d+[,.]?\d*)\s*(?:ks|pc)?\s+'           # Quantity with optional unit (e.g., 3,00 ks or 8,00)
        r'([\d.,]+)\s*(?:CZK)?\s+'                 # Price in CZK
        r'(\d+)\s+'                                 # VAT
        r'([\d.,]+)\s*USD',                        # Price in USD
        re.IGNORECASE
    )
    
    # Simpler pattern for lines without CZK explicitly (regular invoices)
    simple_pattern = re.compile(
        r'^([A-Z][A-Z0-9\-]+(?:-[A-Z0-9]+)?)\s+'  # Part number
        r'(US\d+[A-Z]\d+)\s+'                      # Project code
        r'(\d+[,.]?\d*)\s*(?:ks|pc)?',             # Quantity with optional unit
        re.IGNORECASE
    )
    
    # Proforma pattern: part_number quantity unit price_czk vat price_usd (no project code)
    proforma_pattern = re.compile(
        r'^([A-Z][A-Z0-9\-]+(?:-[A-Z0-9]+)?)\s+'  # Part number
        r'(\d+[,.]?\d*)\s*(?:ks|pc)\s+'            # Quantity with unit
        r'([\d.,]+)\s*CZK\s+'                      # Price in CZK
        r'(\d+)\s+'                                 # VAT
        r'([\d.,]+)\s*USD',                        # Price in USD
        re.IGNORECASE
    )
    
    # Brazilian format pattern: part_number ncm_code hts_code unit_price_usd vat quantity total_price_usd
    # Example: SL505 94032090 9403.20.0080 105,60 USD 0,00 3,00 316,80 USD
    # Also handles: 350.2.2 73089090 7308.90.6000 1,40 USD 0,00 1690,00 2.366,00 USD
    # Also handles: PQA111t_FSC (pint) 94017900 9401.69.8031 401,00 USD 0,00 2,00 802,00 USD
    brazilian_pattern = re.compile(
        r'^([A-Za-z0-9][A-Za-z0-9\-_\.]+(?:\s*\([^)]+\))?)\s+'  # Part number (can start with letter or digit, may have parentheses)
        r'(\d{8})\s+'                              # NCM code (8 digits)
        r'(\d{4}\.\d{2}\.\d{4})\s+'                # HTS code (format: NNNN.NN.NNNN)
        r'([\d.,]+)\s*USD\s+'                      # Unit price in USD
        r'([\d.,]+)\s+'                            # VAT
        r'([\d.,]+)\s+'                            # Quantity
        r'([\d.,]+)\s*USD',                        # Total price in USD
        re.IGNORECASE
    )
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Skip header lines
        if 'type / desciption' in line.lower() or 'type / description' in line.lower():
            continue
        
        # Look ahead function to find steel/aluminum data in subsequent lines
        def get_material_data_from_context(start_idx):
            """Look at following lines to find Steel/Aluminum data."""
            context_text = ""
            for j in range(start_idx + 1, min(start_idx + 5, len(lines))):  # Look up to 4 lines ahead
                next_line = lines[j].strip()
                context_text += " " + next_line
                if 'Steel:' in next_line or 'Aluminum:' in next_line:
                    return extract_steel_aluminum_data(context_text)
            return extract_steel_aluminum_data(context_text)
            
        # Try the main pattern first (regular invoices with project code)
        match = line_pattern.match(line)
        if match:
            part_number = match.group(1)
            quantity = match.group(3).replace(',', '.')
            price_usd = match.group(6).replace('.', '').replace(',', '.')
            
            # Get material data from following lines
            material_data = get_material_data_from_context(i)
            
            # Create unique key to avoid duplicates
            item_key = f"{part_number}_{quantity}_{price_usd}"
            if item_key not in seen_items:
                seen_items.add(item_key)
                item = {
                    'part_number': part_number,
                    'quantity': quantity,
                    'total_price': price_usd
                }
                item.update(material_data)
                line_items.append(item)
            continue
        
        # Try proforma pattern (no project code)
        proforma_match = proforma_pattern.match(line)
        if proforma_match:
            part_number = proforma_match.group(1)
            quantity = proforma_match.group(2).replace(',', '.')
            price_usd = proforma_match.group(5).replace('.', '').replace(',', '.')
            
            # Get material data from following lines
            material_data = get_material_data_from_context(i)
            
            item_key = f"{part_number}_{quantity}_{price_usd}"
            if item_key not in seen_items:
                seen_items.add(item_key)
                item = {
                    'part_number': part_number,
                    'quantity': quantity,
                    'total_price': price_usd
                }
                item.update(material_data)
                line_items.append(item)
            continue
        
        # Try Brazilian format pattern (invoices from mmcité Brazil)
        brazilian_match = brazilian_pattern.match(line)
        if brazilian_match:
            part_number = brazilian_match.group(1)
            # Total price is group 7 (last USD value), quantity is group 6
            total_price = brazilian_match.group(7).replace('.', '').replace(',', '.')
            quantity = brazilian_match.group(6).replace(',', '.')
            
            # Get material data from following lines
            material_data = get_material_data_from_context(i)
            
            item_key = f"{part_number}_{quantity}_{total_price}"
            if item_key not in seen_items:
                seen_items.add(item_key)
                item = {
                    'part_number': part_number,
                    'quantity': quantity,
                    'total_price': total_price
                }
                item.update(material_data)
                line_items.append(item)
            continue
        
        # Try simpler pattern and look for USD price later in the line
        simple_match = simple_pattern.match(line)
        if simple_match:
            part_number = simple_match.group(1)
            quantity = simple_match.group(3).replace(',', '.')
            
            # Look for USD price at the end of the line
            usd_match = re.search(r'([\d.,]+)\s*USD\s*$', line)
            if usd_match:
                price_usd = usd_match.group(1).replace('.', '').replace(',', '.')
                
                # Get material data from following lines
                material_data = get_material_data_from_context(i)
                
                item_key = f"{part_number}_{quantity}_{price_usd}"
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    item = {
                        'part_number': part_number,
                        'quantity': quantity,
                        'total_price': price_usd
                    }
                    item.update(material_data)
                    line_items.append(item)
            continue
        
        # Try proforma simple pattern (part number followed by qty, then USD at end)
        proforma_simple = re.match(r'^([A-Z][A-Z0-9\-]+(?:-[A-Z0-9]+)?)\s+(\d+[,.]?\d*)\s*(?:ks|pc)?', line, re.IGNORECASE)
        if proforma_simple:
            part_number = proforma_simple.group(1)
            quantity = proforma_simple.group(2).replace(',', '.')
            
            # Look for USD price at the end of the line
            usd_match = re.search(r'([\d.,]+)\s*USD\s*$', line)
            if usd_match:
                price_usd = usd_match.group(1).replace('.', '').replace(',', '.')
                
                # Get material data from following lines
                material_data = get_material_data_from_context(i)
                
                item_key = f"{part_number}_{quantity}_{price_usd}"
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    item = {
                        'part_number': part_number,
                        'quantity': quantity,
                        'total_price': price_usd
                    }
                    item.update(material_data)
                    line_items.append(item)
    
    return line_items


def extract_from_all_pages(pdf) -> tuple:
    """
    Extract all text from PDF and parse line items.
    Also extracts invoice numbers and project numbers for each invoice in the document.
    Skips packing lists only.
    Returns (main_invoice_number, main_project_number, line_items)
    """
    all_line_items = []
    main_invoice = None
    main_project = None
    current_invoice = "UNKNOWN"
    current_project = "UNKNOWN"
    
    for page in pdf.pages:
        page_text = page.extract_text()
        if page_text:
            # Skip packing lists only
            page_lower = page_text.lower()
            if 'packing list' in page_lower or 'packing slip' in page_lower:
                continue
            
            # Look for invoice number on this page (regular or proforma)
            # Czech format: "Invoice n.: 2025201714" or "Proforma invoice n.: 2025201714"
            # Brazilian format: "Invoice number: 2025/1850"
            inv_match = re.search(r'(?:Proforma\s+)?[Ii]nvoice\s+(?:number|n)\.?\s*:?\s*(\d+(?:/\d+)?)', page_text)
            if inv_match:
                current_invoice = inv_match.group(1).replace('/', '-')  # Replace slash for filename safety
                if main_invoice is None:
                    main_invoice = current_invoice
            
            # Look for project number on this page
            # Czech format: "project n.: US25A0196"
            # Brazilian format: "1. Project: US25A0105"
            proj_match = re.search(r'(?:\d+\.\s*)?[Pp]roject\s*(?:n\.?)?\s*:?\s*(US\d+[A-Z]\d+)', page_text, re.IGNORECASE)
            if proj_match:
                current_project = proj_match.group(1).upper()
                if main_project is None:
                    main_project = current_project
            
            # Extract line items from this page and tag with current invoice and project
            page_items = extract_line_items_from_text(page_text)
            for item in page_items:
                item['invoice_number'] = current_invoice
                item['project_number'] = current_project
                all_line_items.append(item)
    
    # Use main invoice/project or fallback
    if main_invoice is None:
        main_invoice = "UNKNOWN"
    if main_project is None:
        main_project = "UNKNOWN"
    
    return main_invoice, main_project, all_line_items


def process_pdf(pdf_path: Path) -> tuple:
    """
    Process a PDF file and extract invoice data.
    Returns (invoice_number, project_number, line_items)
    """
    logger.info(f"Processing PDF: {pdf_path}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Use the new extraction function that handles mmcité format
            invoice_number, project_number, line_items = extract_from_all_pages(pdf)
            
            logger.info(f"Found invoice number: {invoice_number}")
            logger.info(f"Found project number: {project_number}")
            logger.info(f"Extracted {len(line_items)} line items")
            
            return invoice_number, project_number, line_items
            
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}")
        raise


def save_to_csv(invoice_number: str, project_number: str, line_items: list, output_folder: Path) -> Path:
    """Save extracted line items to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{invoice_number}_{timestamp}.csv"
    output_path = output_folder / filename
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['invoice_number', 'project_number', 'part_number', 'quantity', 'total_price',
                      'steel_pct', 'steel_kg', 'steel_value', 'aluminum_pct', 'aluminum_kg', 'aluminum_value', 'net_weight']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        
        writer.writeheader()
        for item in line_items:
            writer.writerow(item)
    
    logger.info(f"Saved CSV to: {output_path}")
    return output_path


def save_to_csv_by_invoice(line_items: list, output_folder: Path) -> list:
    """
    Save extracted line items to separate CSV files, one per unique invoice number.
    Returns list of created file paths.
    """
    from collections import defaultdict
    
    # Group line items by invoice number
    items_by_invoice = defaultdict(list)
    for item in line_items:
        inv_num = item.get('invoice_number', 'UNKNOWN')
        items_by_invoice[inv_num].append(item)
    
    created_files = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for invoice_number, items in items_by_invoice.items():
        # Get the project number from the first item (they should all have the same project for this invoice)
        project_number = items[0].get('project_number', 'UNKNOWN') if items else 'UNKNOWN'
        
        filename = f"{invoice_number}_{project_number}_{timestamp}.csv"
        output_path = output_folder / filename
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['invoice_number', 'project_number', 'part_number', 'quantity', 'total_price',
                          'steel_pct', 'steel_kg', 'steel_value', 'aluminum_pct', 'aluminum_kg', 'aluminum_value', 'net_weight']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            
            writer.writeheader()
            for item in items:
                writer.writerow(item)
        
        logger.info(f"Saved CSV to: {output_path} ({len(items)} items)")
        created_files.append(output_path)
    
    return created_files


def move_to_processed(pdf_path: Path, processed_folder: Path):
    """Move processed PDF to the processed folder."""
    dest_path = processed_folder / pdf_path.name
    
    # Handle duplicate filenames
    counter = 1
    while dest_path.exists():
        stem = pdf_path.stem
        suffix = pdf_path.suffix
        dest_path = processed_folder / f"{stem}_{counter}{suffix}"
        counter += 1
    
    pdf_path.rename(dest_path)
    logger.info(f"Moved PDF to: {dest_path}")


def process_folder():
    """Process all PDF files in the input folder."""
    pdf_files = list(INPUT_FOLDER.glob("*.pdf"))
    
    if not pdf_files:
        logger.debug("No PDF files found in input folder")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF file(s) to process")
    
    for pdf_path in pdf_files:
        try:
            # Process the PDF
            invoice_number, project_number, line_items = process_pdf(pdf_path)
            
            if line_items:
                # Save to separate CSV files per invoice number
                save_to_csv_by_invoice(line_items, OUTPUT_FOLDER)
            else:
                logger.warning(f"No line items extracted from {pdf_path}")
            
            # Move to processed folder
            move_to_processed(pdf_path, PROCESSED_FOLDER)
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            # Optionally move to an error folder
            continue


def main():
    """Main entry point - monitors input folder and processes PDFs."""
    logger.info("=" * 60)
    logger.info("Invoice PDF Processor Started")
    logger.info(f"Monitoring folder: {INPUT_FOLDER.absolute()}")
    logger.info(f"Output folder: {OUTPUT_FOLDER.absolute()}")
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
    logger.info("=" * 60)
    
    # Setup folders
    setup_folders()
    
    print("\n" + "=" * 60)
    print("INVOICE PDF PROCESSOR - RUNNING")
    print("=" * 60)
    print(f"Monitoring: {INPUT_FOLDER.absolute()}")
    print(f"Output to:  {OUTPUT_FOLDER.absolute()}")
    print(f"Poll interval: {POLL_INTERVAL} seconds")
    print("=" * 60)
    print("Press Ctrl+C to stop\n")
    
    try:
        poll_count = 0
        while True:
            poll_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            pdf_count = len(list(INPUT_FOLDER.glob("*.pdf")))
            
            # Show heartbeat every poll
            if pdf_count > 0:
                print(f"[{timestamp}] Poll #{poll_count} - Found {pdf_count} PDF(s) to process...")
            else:
                print(f"[{timestamp}] Poll #{poll_count} - Waiting for PDFs...", end='\r')
            
            process_folder()
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("\n\nProcessor stopped.")


if __name__ == "__main__":
    main()
