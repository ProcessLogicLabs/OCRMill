import csv
import os

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

main_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\unique_parts_report.csv"
ref_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\HLP_ENTRY_PARTSPULL_20251207221256.csv"
out_path = r"C:\Users\hpayne\Documents\DevHouston\OCRMill\reports\unique_parts_report_with_tariff.csv"

with open(main_path, newline='', encoding='utf-8') as main_file, \
     open(ref_path, newline='', encoding='utf-8') as ref_file, \
     open(out_path, 'w', newline='', encoding='utf-8') as out_file:
    main_reader = csv.DictReader(main_file)
    ref_reader = list(csv.DictReader(ref_file))
    fieldnames = main_reader.fieldnames + ['tariff_no']
    writer = csv.DictWriter(out_file, fieldnames=fieldnames)
    writer.writeheader()
    for row in main_reader:
        part_number = row.get('part_number', '')
        if part_number.startswith('SLU') or part_number.startswith('Celkem'):
            continue
        tariff_no = ''
        for ref_row in ref_reader:
            if fuzzy_match(row, ref_row):
                tariff_no = ref_row.get('Tariff No', '')
                break
        row['tariff_no'] = tariff_no
        writer.writerow(row)
print(f"Report updated: {out_path}")
