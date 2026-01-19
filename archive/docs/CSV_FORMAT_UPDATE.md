# CSV Format Update - Product Description Column

## Overview

CSV exports now include a **description** column between part_number and quantity, providing human-readable product descriptions for each line item.

## New CSV Format

### Column Order

```csv
invoice_number,project_number,part_number,description,quantity,total_price,hts_code,...
```

**Standard Columns (in order):**
1. `invoice_number` - Invoice number
2. `project_number` - Project/PO number
3. `part_number` - mmcité part number
4. **`description`** - **NEW** Product description
5. `quantity` - Quantity ordered
6. `total_price` - Total line price (USD)
7. Additional columns (HTS codes, material composition, etc.)

### Example Output

**Czech Invoice CSV:**
```csv
invoice_number,project_number,part_number,description,quantity,total_price,hts_code,steel_pct,steel_kg,steel_value,aluminum_pct,aluminum_kg,aluminum_value,net_weight
2025601757,US25A0231,STE411-0029,"Bicycle stand/rack - Model 411",10.00,835.14,9403.20.0082,93,7.51,65.82,0,,,8.10
2025601757,US25A0231,LPU151-J02000,"Planter - Model 151",3.00,1646.70,9403.20.0080,0,,,100,5.2,110.5,5.2
2025601757,US25A0231,BTT307-002003,"Bench - Model 307",4.00,3699.85,9401.69.8031,85,45.3,500.2,15,7.8,125.3,53.1
```

**Brazilian Invoice CSV:**
```csv
invoice_number,project_number,part_number,description,quantity,total_price,ncm_code,hts_code,unit_price,steel_pct,steel_kg,steel_value,aluminum_pct,aluminum_kg,aluminum_value,net_weight
2025/1850,US25A0105,SL505,"Seat/Seating element - Model 505",3.00,316.80,94032090,9403.20.0080,105.60,100,16.76,109,0,0,0,7.9
2025/1850,US25A0105,ND501,"Bollard - Model 501",5.00,890.50,73089060,7308.90.6000,178.10,100,45.2,620.5,0,0,0,45.2
```

## Description Content

Descriptions are automatically extracted from part numbers:

### Format
```
[Product Type] - Model [Number]
```

### Examples

| Part Number | Description |
|-------------|-------------|
| STE411-0029 | Bicycle stand/rack - Model 411 |
| LPU151-J02000 | Planter - Model 151 |
| BTT307-002003 | Bench - Model 307 |
| ND501 | Bollard - Model 501 |
| SL505-002000 | Seat/Seating element - Model 505 |
| PQA151-212000 | Table - Model 151 |
| KSA301 | Litter bin/Waste receptacle - Model 301 |

## Benefits

### 1. Improved Readability
CSVs are now self-documenting - no need to look up part numbers

### 2. Better HTS Code Matching
Descriptions help match correct HTS codes from the database

### 3. Customs Documentation
Descriptions can be used directly on customs forms

### 4. Easier Review
Reviewers can quickly identify what products are on each invoice

### 5. Database Integration
Descriptions are stored in parts database for future reference

## Import Compatibility

### Millworks Integration
The description column is ignored by Millworks but provides useful context for manual review.

### Excel Import
When opening CSV in Excel:
- Description appears between part number and quantity
- Can be used for filtering and sorting
- Provides context for tariff calculations

### Database Import
Most database systems handle the extra column automatically:
- SQL: `LOAD DATA` with column specification
- Pandas: `pd.read_csv()` automatically detects columns
- Access: Import wizard handles variable columns

## Migration Notes

### Existing CSVs
Old CSV files without description column will continue to work:
- Systems expecting specific column positions should use column names
- Import scripts should reference columns by name, not index

### Regenerating CSVs
To add descriptions to previously processed invoices:
1. Move PDFs from `input/Processed/` back to `input/`
2. Reprocess through the system
3. New CSVs will include descriptions

### Backward Compatibility
The system maintains backward compatibility:
- If description cannot be extracted, column is left blank
- HTS codes still populate correctly
- All other columns remain unchanged

## Column Position Reference

### Before (Old Format)
```
Position 0: invoice_number
Position 1: project_number
Position 2: part_number
Position 3: quantity
Position 4: total_price
Position 5+: Additional columns
```

### After (New Format)
```
Position 0: invoice_number
Position 1: project_number
Position 2: part_number
Position 3: description (NEW)
Position 4: quantity
Position 5: total_price
Position 6+: Additional columns
```

**⚠️ Important:** Always reference columns by name, not by position!

## Code Examples

### Reading CSVs with Pandas

**Correct (Name-Based):**
```python
import pandas as pd

df = pd.read_csv('invoice.csv')
part_numbers = df['part_number']
descriptions = df['description']
quantities = df['quantity']
```

**Incorrect (Position-Based):**
```python
# Don't do this - breaks if columns change!
df = pd.read_csv('invoice.csv', header=None)
part_numbers = df[2]  # ❌ Wrong!
quantities = df[3]     # ❌ Was 3, now 4!
```

### SQL Import

**Correct:**
```sql
LOAD DATA INFILE 'invoice.csv'
INTO TABLE invoices
FIELDS TERMINATED BY ','
IGNORE 1 LINES
(invoice_number, project_number, part_number, description, quantity, total_price, @dummy)
SET hts_code = @dummy;
```

### Excel VBA

**Correct:**
```vba
' Use WorksheetFunction.Match to find column by name
Dim partCol As Long
Dim descCol As Long

partCol = Application.WorksheetFunction.Match("part_number", Range("1:1"), 0)
descCol = Application.WorksheetFunction.Match("description", Range("1:1"), 0)
```

## Testing

To verify the new format:

**1. Process a Test Invoice:**
```bash
# Place a test PDF in input/
python invoice_processor_gui.py
# Check CSV has description column
```

**2. Check Column Order:**
```python
import pandas as pd

df = pd.read_csv('output/test_invoice.csv')
print(df.columns.tolist())
# Should show: ['invoice_number', 'project_number', 'part_number',
#               'description', 'quantity', 'total_price', ...]
```

**3. Verify Descriptions:**
```python
# Check descriptions are populated
print(df[['part_number', 'description']].head())
```

## Support

If you encounter issues with the description column:

1. **Empty Descriptions**: Check part number format - must match mmcité patterns
2. **Missing Column**: Ensure using latest version of invoice_processor_gui.py
3. **Import Errors**: Update import scripts to use column names instead of positions

---

**Update Applied**: December 9, 2025
**Version**: 2.2.0
**Breaking Change**: Column positions shifted (use names instead of positions)
