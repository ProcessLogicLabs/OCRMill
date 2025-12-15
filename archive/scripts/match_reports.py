"""
Match Reports Generator

Matches invoice data from output CSVs with partspull data from reports
based on invoice numbers, values, or project numbers.

Output fields: part_number, MID (manufacturer), tariff_number, customer_id, file_number, declaration_type
"""

import csv
from pathlib import Path
from datetime import datetime
from glob import glob


OUTPUT_FOLDER = Path("output")
REPORTS_FOLDER = Path("reports")


def load_invoice_data():
    """Load all invoice line items from output CSVs."""
    invoice_data = []
    
    csv_files = list(OUTPUT_FOLDER.glob("*.csv"))
    print(f"Loading {len(csv_files)} invoice CSV file(s)...")
    
    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    invoice_data.append({
                        'invoice_number': row.get('invoice_number', ''),
                        'project_number': row.get('project_number', ''),
                        'part_number': row.get('part_number', ''),
                        'quantity': float(row.get('quantity', 0) or 0),
                        'total_price': float(row.get('total_price', 0) or 0)
                    })
        except Exception as e:
            print(f"  Error reading {csv_file.name}: {e}")
    
    print(f"  Loaded {len(invoice_data)} invoice line items")
    return invoice_data


def load_partspull_data():
    """Load partspull data from reports folder."""
    partspull_data = []
    
    # Find partspull file(s)
    partspull_files = list(REPORTS_FOLDER.glob("*[Pp][Aa][Rr][Tt][Ss][Pp][Uu][Ll][Ll]*"))
    
    if not partspull_files:
        print("No partspull file found in reports folder.")
        return []
    
    print(f"Loading {len(partspull_files)} partspull file(s)...")
    
    for pp_file in partspull_files:
        print(f"  Reading: {pp_file.name}")
        try:
            with open(pp_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Clean up value field (remove quotes, handle decimals)
                    value_str = row.get('Value', '0').strip()
                    try:
                        value = float(value_str) if value_str else 0
                    except ValueError:
                        value = 0
                    
                    partspull_data.append({
                        'customer_id': row.get('Customer ID', ''),
                        'comm_inv_no': row.get('Comm. Inv. No', ''),
                        'entry_no': row.get('Entry No.', ''),
                        'part_number': row.get('Part Number', ''),
                        'manufacturer': row.get('Manufacturer', ''),
                        'manufacturer_name': row.get('Manufacturer Name', ''),
                        'tariff_no': row.get('Tariff No', ''),
                        'file_no': row.get('File No.', ''),
                        'declaration_type': row.get('Declaration Type Cd', ''),
                        'value': value,
                        'cust_ref': row.get('Cust Ref', '')
                    })
        except Exception as e:
            print(f"  Error reading {pp_file.name}: {e}")
    
    print(f"  Loaded {len(partspull_data)} partspull records")
    return partspull_data


def match_records(invoice_data, partspull_data):
    """
    Match invoice data with partspull data based on:
    1. Invoice number match (Comm. Inv. No)
    2. Value match
    3. Project number match (Cust Ref)
    """
    matched_records = []
    
    # Create lookup indices for faster matching
    # Index partspull by invoice number
    pp_by_invoice = {}
    for pp in partspull_data:
        inv_no = pp['comm_inv_no']
        if inv_no:
            if inv_no not in pp_by_invoice:
                pp_by_invoice[inv_no] = []
            pp_by_invoice[inv_no].append(pp)
    
    # Index partspull by value (rounded to 2 decimal places)
    pp_by_value = {}
    for pp in partspull_data:
        val_key = round(pp['value'], 2)
        if val_key > 0:
            if val_key not in pp_by_value:
                pp_by_value[val_key] = []
            pp_by_value[val_key].append(pp)
    
    # Index partspull by cust ref (which may contain project numbers)
    pp_by_custref = {}
    for pp in partspull_data:
        cust_ref = pp['cust_ref'].upper().strip()
        if cust_ref:
            if cust_ref not in pp_by_custref:
                pp_by_custref[cust_ref] = []
            pp_by_custref[cust_ref].append(pp)
    
    print(f"\nMatching records...")
    matches_found = 0
    
    for inv in invoice_data:
        inv_number = inv['invoice_number']
        project = inv['project_number'].upper().strip()
        part_number = inv['part_number']
        total_price = round(inv['total_price'], 2)
        
        matched_pp = None
        match_type = None
        
        # Try matching by invoice number first
        if inv_number in pp_by_invoice:
            for pp in pp_by_invoice[inv_number]:
                matched_pp = pp
                match_type = 'invoice_number'
                break
        
        # Try matching by project number in cust_ref
        if not matched_pp and project in pp_by_custref:
            for pp in pp_by_custref[project]:
                matched_pp = pp
                match_type = 'project_number'
                break
        
        # Try matching by total price
        if not matched_pp and total_price in pp_by_value:
            for pp in pp_by_value[total_price]:
                matched_pp = pp
                match_type = 'total_price'
                break
        
        if matched_pp:
            matches_found += 1
            matched_records.append({
                'part_number': part_number,
                'MID': matched_pp['manufacturer'],
                'tariff_number': matched_pp['tariff_no'],
                'customer_id': matched_pp['customer_id'],
                'file_number': matched_pp['file_no'],
                'declaration_type': matched_pp['declaration_type'],
                'match_type': match_type,
                'invoice_number': inv_number,
                'project_number': project
            })
        else:
            # Include unmatched records with empty partspull fields
            matched_records.append({
                'part_number': part_number,
                'MID': '',
                'tariff_number': '',
                'customer_id': '',
                'file_number': '',
                'declaration_type': '',
                'match_type': 'NO_MATCH',
                'invoice_number': inv_number,
                'project_number': project
            })
    
    print(f"  Found {matches_found} matches out of {len(invoice_data)} invoice records")
    return matched_records


def generate_match_report(matched_records):
    """Generate the final match report CSV."""
    if not matched_records:
        print("No records to write.")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"match_report_{timestamp}.csv"
    report_path = REPORTS_FOLDER / report_filename
    
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['part_number', 'MID', 'tariff_number', 'customer_id', 'file_number', 'declaration_type']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for record in matched_records:
            writer.writerow(record)
    
    print(f"\nMatch report generated: {report_path}")
    print(f"Total records: {len(matched_records)}")
    
    # Count matches vs non-matches
    matches = sum(1 for r in matched_records if r.get('match_type') != 'NO_MATCH')
    print(f"Matched: {matches}, Unmatched: {len(matched_records) - matches}")
    
    return report_path


def main():
    """Main function to run the matching process."""
    print("=" * 60)
    print("Match Reports Generator")
    print("=" * 60)
    
    # Load data
    invoice_data = load_invoice_data()
    if not invoice_data:
        print("No invoice data found. Exiting.")
        return
    
    partspull_data = load_partspull_data()
    if not partspull_data:
        print("No partspull data found. Exiting.")
        return
    
    # Match records
    matched_records = match_records(invoice_data, partspull_data)
    
    # Generate report
    generate_match_report(matched_records)


if __name__ == "__main__":
    main()
