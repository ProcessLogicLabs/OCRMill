"""
Consolidated Parts Report Generator

Reads all CSV files from the output directory and generates a consolidated
parts report with totals by part number.
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict


OUTPUT_FOLDER = Path("output")
REPORTS_FOLDER = Path("reports")


def generate_parts_report():
    """
    Generate a consolidated parts report from all CSV files in output folder.
    Aggregates quantities and calculates total value by part number.
    """
    # Ensure reports folder exists
    REPORTS_FOLDER.mkdir(exist_ok=True)
    
    # Dictionary to aggregate parts data
    # Key: part_number, Value: {'quantity': total_qty, 'total_value': sum, 'invoices': set(), 'projects': set()}
    parts_data = defaultdict(lambda: {
        'quantity': 0.0,
        'total_value': 0.0,
        'invoices': set(),
        'projects': set(),
        'prices': []
    })
    
    # Find all CSV files in output folder
    csv_files = list(OUTPUT_FOLDER.glob("*.csv"))
    
    if not csv_files:
        print("No CSV files found in output folder.")
        return None
    
    print(f"Processing {len(csv_files)} CSV file(s)...")
    
    # Process each CSV file
    for csv_file in csv_files:
        print(f"  Reading: {csv_file.name}")
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    part_number = row.get('part_number', '')
                    if not part_number:
                        continue
                    
                    try:
                        quantity = float(row.get('quantity', 0))
                        total_price = float(row.get('total_price', 0))
                    except ValueError:
                        continue
                    
                    invoice = row.get('invoice_number', '')
                    project = row.get('project_number', '')
                    
                    # Aggregate data
                    parts_data[part_number]['quantity'] += quantity
                    parts_data[part_number]['total_value'] += total_price
                    parts_data[part_number]['prices'].append(total_price)
                    if invoice:
                        parts_data[part_number]['invoices'].add(invoice)
                    if project:
                        parts_data[part_number]['projects'].add(project)
                        
        except Exception as e:
            print(f"  Error reading {csv_file.name}: {e}")
    
    if not parts_data:
        print("No parts data found in CSV files.")
        return None
    
    # Generate report filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"parts_report_{timestamp}.csv"
    report_path = REPORTS_FOLDER / report_filename
    
    # Write consolidated report
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['part_number', 'total_quantity', 'avg_price', 'total_value', 'invoice_count', 'invoices', 'projects']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort by part number
        for part_number in sorted(parts_data.keys()):
            data = parts_data[part_number]
            avg_price = sum(data['prices']) / len(data['prices']) if data['prices'] else 0
            
            writer.writerow({
                'part_number': part_number,
                'total_quantity': round(data['quantity'], 2),
                'avg_price': round(avg_price, 2),
                'total_value': round(data['total_value'], 2),
                'invoice_count': len(data['invoices']),
                'invoices': '; '.join(sorted(data['invoices'])),
                'projects': '; '.join(sorted(data['projects']))
            })
    
    print(f"\nConsolidated report generated: {report_path}")
    print(f"Total unique parts: {len(parts_data)}")
    
    # Print summary
    total_value = sum(d['total_value'] for d in parts_data.values())
    total_qty = sum(d['quantity'] for d in parts_data.values())
    print(f"Total quantity: {total_qty:,.2f}")
    print(f"Total value: ${total_value:,.2f} USD")
    
    return report_path


if __name__ == "__main__":
    generate_parts_report()
