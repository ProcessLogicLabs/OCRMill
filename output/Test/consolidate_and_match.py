import csv
import os
from glob import glob

def fuzzy_match(main_row, ref_row):
    try:
        main_value = float(main_row['total_price'])
        ref_value = float(ref_row['Value'].replace(',', ''))
    except (ValueError, KeyError):
        return False
    return (
        main_row['project_number'] == ref_row['Cust Ref'] and
        abs(main_value - ref_value) <= 5
    )

def consolidate_all_parts(output_dir, consolidated_path):
    csv_files = glob(os.path.join(output_dir, '*.csv'))
    all_fieldnames = set()
    rows = []
    for file in csv_files:
        with open(file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_fieldnames.update(reader.fieldnames)
            for row in reader:
                rows.append(row)
    fieldnames = list(all_fieldnames)
    with open(consolidated_path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Consolidated report saved: {consolidated_path}")

def run_tariff_matching(consolidated_path, ref_path, out_path):
    with open(consolidated_path, newline='', encoding='utf-8') as main_file, \
         open(ref_path, newline='', encoding='utf-8') as ref_file, \
         open(out_path, 'w', newline='', encoding='utf-8') as out_file:
        main_reader = csv.DictReader(main_file)
        ref_reader = list(csv.DictReader(ref_file))
        # Ensure only aluminum_pct and steel_pct are included, not aluminum_value or steel_value
        fieldnames = [fn for fn in main_reader.fieldnames if fn not in ('aluminum_value', 'steel_value')] + ['tariff_no', 'file_no']
        writer = csv.DictWriter(out_file, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in main_reader:
            part_number = row.get('part_number', '')
            if part_number.startswith('SLU') or part_number.startswith('Celkem'):
                continue
            tariff_no = ''
            file_no = ''
            for ref_row in ref_reader:
                if fuzzy_match(row, ref_row):
                    tariff_no = ref_row.get('Tariff No', '')
                    file_no = ref_row.get('File No.', '')
                    break
            row['tariff_no'] = tariff_no
            row['file_no'] = file_no
            writer.writerow(row)
    print(f"Matching report saved: {out_path}")

output_dir = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\output"
consolidated_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\output\all_parts_consolidated.csv"
ref_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\HLP_ENTRY_PARTSPULL_20251207221256.csv"
matched_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\output\all_parts_consolidated_with_tariff.csv"

consolidate_all_parts(output_dir, consolidated_path)
run_tariff_matching(consolidated_path, ref_path, matched_path)
