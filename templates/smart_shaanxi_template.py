"""
Shaanxi Fangzhi Template

Template for invoices from Shaanxi Fangzhi Pipe Co., Ltd (China).
Extracts part numbers in format like 85-146938, 89-8008167-ND-A.

Updated: 2026-01-13
"""

import re
from typing import List, Dict
from .base_template import BaseTemplate


class SmartShaanxiTemplateTemplate(BaseTemplate):
    """
    Template for Shaanxi Fangzhi invoices.
    Uses custom regex for line item extraction.

    Invoice format:
    PART_NUMBER DESCRIPTION PCS## $/PC##.### $TOTAL
    Example: 85-146938 8x4/6" TS CAP (FINISHED) PIPE PCS54 $/PC40.320 $2,177.280
    """

    name = "Shaanxi Fangzhi"
    description = "Invoices from Shaanxi Fangzhi Pipe Co., Ltd"
    client = "Sigma Corporation"
    version = "2.0.0"
    enabled = True

    extra_columns = ['po_number', 'unit_price', 'description', 'country_origin']

    # Keywords to identify this supplier - specific to Shaanxi Fangzhi
    SUPPLIER_KEYWORDS = [
        'shaanxi fangzhi',
        'fangzhi pipe',
        'xingang port',
        'xingqing road',
        'xi\'an city',
        'shaanxi province',
    ]

    def __init__(self):
        super().__init__()
        self._last_result = None

    def can_process(self, text: str) -> bool:
        """Check if this is a Shaanxi Fangzhi invoice."""
        text_lower = text.lower()

        # Check for supplier keywords (all lowercase)
        for keyword in self.SUPPLIER_KEYWORDS:
            if keyword in text_lower:
                return True

        return False

    def get_confidence_score(self, text: str) -> float:
        """Return confidence score for template matching."""
        text_lower = text.lower()

        # Count how many keywords match
        keyword_matches = 0
        for keyword in self.SUPPLIER_KEYWORDS:
            if keyword in text_lower:
                keyword_matches += 1

        if keyword_matches == 0:
            return 0.0

        # Base score for first match, add for additional matches
        score = 0.7 + (keyword_matches - 1) * 0.05

        # Add confidence for Sigma Corporation (the buyer)
        if 'sigma corporation' in text_lower:
            score += 0.1

        # Add confidence for typical Shaanxi invoice patterns
        # Part number pattern: XX-XXXXXX
        if re.search(r'\b\d{2}-\d{5,7}\b', text):
            score += 0.1

        # PCS pattern (quantity format)
        if re.search(r'PCS\s*\d+', text, re.IGNORECASE):
            score += 0.05

        return min(score, 1.0)

    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number."""
        patterns = [
            r'INVOICE\s*(?:NO\.?)?\s*[:\s]*([A-Z0-9][\w\-/]+)',
            r'Invoice\s*(?:No\.?|#)\s*[:\s]*([A-Z0-9][\w\-/]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "UNKNOWN"

    def extract_project_number(self, text: str) -> str:
        """Extract PO number."""
        patterns = [
            r'P\.?O\.?\s*#?\s*:?\s*(\d{6,})',
            r'Purchase\s*Order[:\s]*(\d+)',
            r'\b(400\d{5})\b',  # Sigma PO format
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return "UNKNOWN"

    def extract_manufacturer_name(self, text: str) -> str:
        """Return the manufacturer name."""
        return "SIGMA_SHAANXI"

    def extract_line_items(self, text: str) -> List[Dict]:
        """
        Extract line items using custom regex patterns.

        Shaanxi Fangzhi invoice format:
        PART_NUMBER DESCRIPTION PCS## $/PC##.### $##,###.##

        Examples:
        85-146938 8x4/6" TS CAP (FINISHED) PIPE PCS54 $/PC40.320 $2,177.280
        89-8008167-ND-A GASKET ONLY FOR DI FLANGE PCS420 $/PC0.900 $378.000
        """
        items = []
        po_number = self.extract_project_number(text)

        # Pattern breakdown:
        # (\d{2}-[\dA-Z\-]+)  - Part number: starts with 2 digits, dash, then alphanumeric
        # (.+?)               - Description: non-greedy match
        # PCS\s*(\d+)         - Quantity: PCS followed by number
        # \$/PC\s*([\d,]+\.?\d*) - Unit price: $/PC followed by amount
        # \$\s*([\d,]+\.\d{2,3}) - Total price: $ followed by amount

        # Main pattern for line items
        pattern = r'(\d{2}-[\dA-Z\-]+(?:-[A-Z]+)?)\s+(.+?)\s+PCS\s*(\d+)\s+\$/PC\s*([\d,]+\.?\d*)\s+\$\s*([\d,]+\.\d{2,3})'

        matches = re.findall(pattern, text, re.IGNORECASE)

        for match in matches:
            part_number, description, quantity, unit_price, total_price = match

            # Clean up values
            part_number = part_number.strip().upper()
            description = description.strip()
            quantity = int(quantity)
            unit_price = float(unit_price.replace(',', ''))
            total_price = float(total_price.replace(',', ''))

            items.append({
                'part_number': part_number,
                'quantity': quantity,
                'total_price': total_price,
                'unit_price': unit_price,
                'description': description,
                'po_number': po_number,
                'country_origin': 'CHINA',
            })

        # If no matches found, try alternative patterns
        if not items:
            items = self._try_alternative_patterns(text, po_number)

        return items

    def _try_alternative_patterns(self, text: str, po_number: str) -> List[Dict]:
        """Try alternative patterns for different invoice formats."""
        items = []

        # Alternative: Part numbers might be on separate lines from pricing
        # Look for lines that start with part number pattern
        lines = text.split('\n')

        for line in lines:
            # Match line starting with part number
            match = re.match(r'^\s*(\d{2}-[\dA-Z\-]+(?:-[A-Z]+)?)\s+(.+)', line, re.IGNORECASE)
            if match:
                part_number = match.group(1).strip().upper()
                rest = match.group(2)

                # Try to extract quantity and prices from the rest
                qty_match = re.search(r'PCS\s*(\d+)', rest, re.IGNORECASE)
                unit_match = re.search(r'\$/PC\s*([\d,]+\.?\d*)', rest, re.IGNORECASE)
                total_match = re.search(r'\$\s*([\d,]+\.\d{2,3})\s*$', rest)

                if qty_match and total_match:
                    quantity = int(qty_match.group(1))
                    total_price = float(total_match.group(1).replace(',', ''))
                    unit_price = float(unit_match.group(1).replace(',', '')) if unit_match else total_price / quantity

                    # Extract description (everything between part number and PCS)
                    desc_match = re.search(r'^(.+?)(?=\s*PCS)', rest, re.IGNORECASE)
                    description = desc_match.group(1).strip() if desc_match else ''

                    items.append({
                        'part_number': part_number,
                        'quantity': quantity,
                        'total_price': total_price,
                        'unit_price': unit_price,
                        'description': description,
                        'po_number': po_number,
                        'country_origin': 'CHINA',
                    })

        return items

    def post_process_items(self, items: List[Dict]) -> List[Dict]:
        """Post-process - deduplicate."""
        if not items:
            return items

        seen = set()
        unique_items = []

        for item in items:
            key = f"{item['part_number']}_{item['quantity']}_{item['total_price']}"
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        return unique_items

    def is_packing_list(self, text: str) -> bool:
        """Check if document is only a packing list."""
        text_lower = text.lower()
        if 'packing list' in text_lower and 'invoice' not in text_lower:
            return True
        return False
