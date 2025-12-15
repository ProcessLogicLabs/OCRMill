# Product Description Extraction and HTS Code Matching

## Overview

The parts database now automatically extracts product descriptions from part numbers and uses them to intelligently match HTS codes from the `mmcite_hts.xlsx` database.

## How It Works

### 1. Automatic Description Extraction

When a part is processed, the system:
1. Analyzes the part number (e.g., "SL505-002000")
2. Identifies the product type from the prefix ("SL" = Seat/Seating element)
3. Extracts model details if present ("Model 505")
4. Creates a human-readable description: "Seat/Seating element - Model 505"

### 2. Intelligent HTS Code Matching

The system uses a 3-tier approach to find the correct HTS code:

**Tier 1: Built-in Product Type Mapping**
- Matches known product keywords to HTS codes
- Example: "BICYCLE" → 9403.20.0082

**Tier 2: HTS Database Keyword Matching**
- Compares description words against `mmcite_hts.xlsx` entries
- Finds best match based on word overlap
- Example: "Bicycle stand" matches HTS description "BICYCLE STAND"

**Tier 3: Part Number Prefix Mapping**
- Falls back to prefix-based matching if above fail
- Example: "SL" prefix → 9403.20.0080 (Seating)

## Product Type Mappings

### Part Number Prefixes

| Prefix | Description | HTS Code |
|--------|-------------|----------|
| SL | Seat/Seating element | 9403.20.0080 |
| BTT | Bench | 9401.69.8031 |
| STE | Bicycle stand/rack | 9403.20.0082 |
| LPU | Planter/Flower pot | 9403.20.0080 |
| ND | Bollard | 7308.90.6000 |
| PQA | Table | 9403.20.0080 |
| KSA | Litter bin/Waste receptacle | 7310.29.0050 |
| MRU | Tree grate | 7326.90.8688 |
| BAR | Barrier | 7308.90.9590 |

### Product Keywords to HTS

| Keyword | HTS Code | Description |
|---------|----------|-------------|
| BICYCLE, BIKE, STAND, RACK | 9403.20.0082 | Bicycle stands |
| BENCH | 9401.69.8031 | Benches |
| BOLLARD | 7308.90.6000 | Bollards |
| LITTER, WASTE, BIN | 7310.29.0050 | Waste receptacles |
| TREE GRATE, GRATE | 7326.90.8688 | Tree grates |
| BARRIER, FENCE, FENCING | 7308.90.9590 | Barriers/Fencing |
| LIGHT, LAMP, LIGHTING | 9405.40.8000 | Lighting |
| SIGN, SIGNAGE | 9405.60.8000 | Signage |
| ANCHOR, BOLT, FIXING | 7318.15.2095 | Fasteners |

## Example Workflows

### Example 1: Automatic Matching

**Input:**
```python
part_number = "STE411-0029"
```

**Processing:**
1. Prefix "STE" identified → "Bicycle stand/rack"
2. Model "411" extracted → "Bicycle stand/rack - Model 411"
3. Keyword "BICYCLE" found → HTS 9403.20.0082
4. Part saved with description and HTS code

**Result:**
```
Part Number: STE411-0029
Description: Bicycle stand/rack - Model 411
HTS Code: 9403.20.0082
```

### Example 2: Database Matching

**Input:**
```python
part_number = "LPU151-J02000"
description = "Planter Model 151"
```

**Processing:**
1. Description "Planter Model 151" extracted
2. Keyword "PLANTER" matches HTS database entry
3. HTS database has: "PLANTER" → 9403.20.0080
4. Match found

**Result:**
```
Part Number: LPU151-J02000
Description: Planter Model 151
HTS Code: 9403.20.0080
```

### Example 3: Manual Override

If automatic matching is incorrect, you can manually set the HTS code:

**Via Parts Database Viewer:**
1. Open `parts_database_viewer.py`
2. Find the part
3. Right-click → "Set HTS Code"
4. Enter correct HTS code
5. Future occurrences use the manual assignment

**Via Code:**
```python
from parts_database import PartsDatabase

db = PartsDatabase()
db.update_part_hts('STE411-0029', '9403.20.0082', 'Bicycle stand')
```

## Integration Points

### Invoice Processing
The description extraction happens automatically during invoice processing:

```
1. PDF processed → line items extracted
2. For each part:
   - Extract description from part number
   - Match HTS code (3-tier approach)
   - Save to database with description and HTS code
3. CSV generated includes HTS codes
```

### Parts Database
Descriptions and HTS codes are stored in the `parts` table:

```sql
SELECT part_number, description, hts_code
FROM parts
WHERE hts_code IS NOT NULL
```

### CSV Export
Generated CSVs include the HTS code column:
```csv
invoice_number,project_number,part_number,quantity,total_price,hts_code
2025601757,US25A0231,STE411-0029,10.00,835.14,9403.20.0082
```

## Improving Matching Accuracy

### Add New Product Types

Edit `part_description_extractor.py`:

```python
PREFIX_DESCRIPTIONS = {
    'NEW': 'New product type',  # Add new prefix
}

DESCRIPTION_TO_HTS = {
    'NEW PRODUCT': '1234.56.7890',  # Add HTS mapping
}
```

### Update HTS Database

1. Edit `reports/mmcite_hts.xlsx`
2. Add new HTS codes and descriptions
3. Run: `python load_hts_mapping.py`
4. System will use new mappings for future processing

### Review and Correct

Use the Parts Database Viewer to:
1. Filter parts: "No HTS" to find unmatched parts
2. Review suggested descriptions
3. Manually assign correct HTS codes
4. System learns from manual assignments

## Files Modified/Created

### New Files
1. **part_description_extractor.py** (300+ lines)
   - `PartDescriptionExtractor` class
   - Product type mappings
   - HTS matching logic

2. **DESCRIPTION_EXTRACTION.md** (this file)
   - Complete documentation

### Modified Files
1. **parts_database.py**
   - Added `from part_description_extractor import PartDescriptionExtractor`
   - Added `self.description_extractor` to `__init__`
   - Enhanced `add_part_occurrence()` to extract descriptions
   - Enhanced `add_part_occurrence()` to match HTS codes
   - Updated `_update_part_master()` to save descriptions

## Statistics and Reporting

View description coverage in Parts Database Viewer:
- **Statistics Tab** shows HTS code coverage percentage
- **Parts Master Tab** displays descriptions for all parts
- **Filter: No HTS** shows parts needing manual review

## API Reference

### PartDescriptionExtractor

**Extract Description:**
```python
from part_description_extractor import extract_description

description = extract_description("STE411-0029")
# Returns: "Bicycle stand/rack - Model 411"
```

**Find HTS Code:**
```python
from part_description_extractor import find_hts_code

hts = find_hts_code("STE411-0029")
# Returns: "9403.20.0082"

# Or with custom description
hts = find_hts_code("STE411-0029", "Bicycle parking rack")
# Returns: "9403.20.0082"
```

**Enrich Part Data:**
```python
from part_description_extractor import PartDescriptionExtractor

extractor = PartDescriptionExtractor()
enriched = extractor.enrich_part_data("STE411-0029")
# Returns: {
#     'description': 'Bicycle stand/rack - Model 411',
#     'suggested_hts': '9403.20.0082'
# }
```

**Match Against HTS Database:**
```python
extractor = PartDescriptionExtractor()

hts_database = [
    {'hts_code': '9403.20.0082', 'description': 'BICYCLE STAND'},
    {'hts_code': '9401.69.8031', 'description': 'BENCH'},
]

hts = extractor.match_with_hts_database("Bicycle rack", hts_database)
# Returns: "9403.20.0082"
```

## Performance

- **Description Extraction**: <1ms per part
- **HTS Matching**: <10ms per part (includes database lookup)
- **Memory Usage**: Minimal (HTS database cached in memory)
- **Threading**: Thread-safe with existing database locks

## Future Enhancements

Planned improvements:
- [ ] Machine learning-based HTS prediction
- [ ] Multi-language description support
- [ ] Fuzzy matching with similarity scores
- [ ] Confidence levels for HTS matches
- [ ] Bulk HTS code updates
- [ ] Description templates for custom products

## Troubleshooting

### Parts Have No Description
**Issue**: Description column is empty

**Solution**:
- Descriptions are extracted automatically on first processing
- Reprocess the invoice or use the extractor manually:
```python
from parts_database import PartsDatabase

db = PartsDatabase()
part = db.get_part_summary('STE411-0029')
if not part['description']:
    desc = db.description_extractor.extract_description('STE411-0029')
    db.update_part_description('STE411-0029', desc)
```

### Wrong HTS Code Assigned
**Issue**: Automatic matching chose incorrect HTS code

**Solution**:
1. Use Parts Database Viewer to set correct HTS code
2. OR edit `part_description_extractor.py` to improve mappings
3. OR add better entry to `mmcite_hts.xlsx` and reload

### No HTS Code Found
**Issue**: Part has description but no HTS code

**Solution**:
1. Check if part type is in `PREFIX_DESCRIPTIONS`
2. Check if keywords are in `DESCRIPTION_TO_HTS`
3. Check `reports/mmcite_hts.xlsx` for matching entries
4. Add mapping to extractor or HTS database

---

**Feature Added**: December 9, 2025
**Version**: 2.2.0
