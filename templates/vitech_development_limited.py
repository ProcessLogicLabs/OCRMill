"""
VitechDevelopmentLimitedTemplate - Template for Vitech Development Limited commercial invoices
"""

import re
from typing import List, Dict
from .base_template import BaseTemplate


class VitechDevelopmentLimitedTemplate(BaseTemplate):
    """
    Template for Vitech Development Limited invoices.

    Invoice format (from PDF text extraction):
    - Line items appear as: PO# PKGS QTY ITEM_CODE HS_CODE COUNTRY NET_WT GR_WT DIMENSION $UNIT_PRICE $TOTAL_VALUE
    - Description text appears on separate lines above/below the data line
    """

    name = "Vitech Development Limited"
    description = "Invoice template for Vitech Development Limited"
    client = "Vitech Development Limited"
    version = "1.0.6"

    enabled = True

    extra_columns = ['po_number', 'packages', 'hs_code', 'country_origin', 'net_weight', 'gross_weight', 'dimensions', 'unit_price']

    def can_process(self, text: str) -> bool:
        """Check if this template can process the given invoice."""
        text_lower = text.lower()
        return ('vitech development limited' in text_lower or
                ('commercial invoice' in text_lower and 'hfvt25-' in text_lower))

    def get_confidence_score(self, text: str) -> float:
        """Return confidence score for template matching."""
        if not self.can_process(text):
            return 0.0

        score = 0.5
        text_lower = text.lower()

        # Add points for each indicator found
        indicators = [
            'vitech development limited',
            'commercial invoice',
            'hfvt25-',
            'sigma corporation',
            '8431.20.0000'
        ]
        for indicator in indicators:
            if indicator in text_lower:
                score += 0.1

        return min(score, 1.0)

    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number."""
        patterns = [
            r'INVOICE\s*#\s*([A-Z0-9-]+)',
            r'HFVT25-[A-Z]\d+',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.lastindex else match.group(0).strip()

        return "UNKNOWN"

    def extract_project_number(self, text: str) -> str:
        """Extract B/L number as project reference."""
        patterns = [
            r'B/L\s*#\s*([A-Z0-9]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "UNKNOWN"

    def extract_line_items(self, text: str) -> List[Dict]:
        """Extract line items from invoice."""
        line_items = []
        seen_items = set()

        # The PDF text extraction produces lines like:
        # FLUX PWR 250464 BRACKET GAUGE BRACKING
        # 40049557 1 315 21-250464 8431.20.0000 CHINA 68 90 77X76X62 $2.18 $686.70
        # SELL ASSEMBLY DWG# 250464 STEEL FAB GRAY
        #
        # The data line has: PO# PKGS QTY ITEM_CODE HS_CODE COUNTRY NET_WT GR_WT DIM $UNIT $TOTAL
        # Description text appears on lines above/below but the main data is on ONE line

        # Pattern to match the complete data line (all key fields on same line)
        line_pattern = re.compile(
            r'(\d{8})\s+'                          # PO# (8 digits like 40049557)
            r'(\d+)\s+'                            # PKGS
            r'([\d,]+)\s+'                         # QTY (may have commas like 2,000)
            r'(\d{2}-\d{6})\s+'                    # ITEM CODE (format: 21-250464)
            r'(\d{4}\.\d{2}\.\d{4})\s+'            # HS CODE (format: 8431.20.0000)
            r'(CHINA)\s+'                          # COUNTRY OF ORIGIN
            r'([\d,]+)\s+'                         # NET WT
            r'([\d,]+)\s+'                         # GR WT
            r'(\d+[Xx]\d+[Xx]\d+)\s+'              # DIMENSION (format: 77X76X62)
            r'\$([\d,.]+)\s+'                      # UNIT PRICE
            r'\$([\d,.]+)',                        # TOTAL VALUE
            re.IGNORECASE
        )

        for match in line_pattern.finditer(text):
            try:
                # Clean up quantity and values (remove commas)
                qty_str = match.group(3).replace(',', '')
                net_wt = match.group(7).replace(',', '')
                gr_wt = match.group(8).replace(',', '')
                unit_price = match.group(10).replace(',', '')
                total_value = match.group(11).replace(',', '')

                item = {
                    'part_number': match.group(4),           # ITEM CODE as part number
                    'description': '',                       # Will be extracted separately
                    'quantity': int(qty_str),
                    'total_price': float(total_value),
                    'po_number': match.group(1),
                    'packages': match.group(2),
                    'hs_code': match.group(5),
                    'country_origin': match.group(6),
                    'net_weight': net_wt,
                    'gross_weight': gr_wt,
                    'dimensions': match.group(9),
                    'unit_price': unit_price,
                }

                # Create deduplication key using part_number, qty, and total_price
                item_key = f"{item['part_number']}_{item['quantity']}_{item['total_price']}"

                if item_key not in seen_items:
                    seen_items.add(item_key)
                    line_items.append(item)

            except (IndexError, AttributeError, ValueError) as e:
                print(f"Error parsing line item: {e}")
                continue

        # Alternative approach: Look for line items row by row using a simpler pattern
        # This handles cases where the PDF extraction doesn't produce clean multi-line text
        if len(line_items) == 0:
            # Pattern for rows that have all key fields on same conceptual line
            # Look for: PO PKGS QTY ITEM_CODE ... HS_CODE CHINA NW GW DIM $UP $TOTAL
            row_pattern = re.compile(
                r'(\d{8})\s+(\d+)\s+([\d,]+)\s+(\d{2}-\d{6})\b'  # PO PKGS QTY ITEM_CODE
            )

            # Find all potential line item starts
            for row_match in row_pattern.finditer(text):
                try:
                    start_pos = row_match.start()
                    po_num = row_match.group(1)
                    pkgs = row_match.group(2)
                    qty_str = row_match.group(3).replace(',', '')
                    item_code = row_match.group(4)

                    # Look for the rest of the data after this point
                    remaining = text[row_match.end():row_match.end() + 500]

                    # Find HS code, weights, dimensions, prices in remaining text
                    detail_pattern = re.compile(
                        r'(\d{4}\.\d{2}\.\d{4})\s+'         # HS CODE
                        r'(CHINA)\s+'                       # COUNTRY
                        r'([\d,]+)\s+'                      # NET WT
                        r'([\d,]+)\s+'                      # GR WT
                        r'(\d+[Xx]\d+[Xx]\d+)\s+'           # DIMENSION
                        r'\$([\d,.]+)\s+'                   # UNIT PRICE
                        r'\$([\d,.]+)',                     # TOTAL VALUE
                        re.IGNORECASE
                    )

                    detail_match = detail_pattern.search(remaining)
                    if detail_match:
                        # Extract description (text between item code and HS code)
                        desc_end = remaining.find(detail_match.group(1))
                        description = ' '.join(remaining[:desc_end].split()) if desc_end > 0 else ''

                        net_wt = detail_match.group(3).replace(',', '')
                        gr_wt = detail_match.group(4).replace(',', '')
                        unit_price = detail_match.group(6).replace(',', '')
                        total_value = detail_match.group(7).replace(',', '')

                        item = {
                            'part_number': item_code,
                            'description': description,
                            'quantity': int(qty_str),
                            'total_price': float(total_value),
                            'po_number': po_num,
                            'packages': pkgs,
                            'hs_code': detail_match.group(1),
                            'country_origin': detail_match.group(2),
                            'net_weight': net_wt,
                            'gross_weight': gr_wt,
                            'dimensions': detail_match.group(5),
                            'unit_price': unit_price,
                        }

                        item_key = f"{item['part_number']}_{item['quantity']}_{item['total_price']}"
                        if item_key not in seen_items:
                            seen_items.add(item_key)
                            line_items.append(item)

                except (IndexError, ValueError):
                    continue

        # Fallback: Try a simpler single-line pattern if no items found
        if len(line_items) == 0:
            # Pattern for single-line format (less common)
            simple_line_pattern = re.compile(
                r'(\d{8})\s+(\d+)\s+([\d,]+)\s+(\d{2}-\d{6})\s+[\s\S]*?'
                r'(\d{4}\.\d{2}\.\d{4})\s+(CHINA)\s+([\d,]+)\s+([\d,]+)\s+'
                r'(\d+[Xx]\d+[Xx]\d+)\s+\$([\d,.]+)\s+\$([\d,.]+)',
                re.IGNORECASE
            )
            for match in simple_line_pattern.finditer(text):
                try:
                    qty_str = match.group(3).replace(',', '')
                    net_wt = match.group(7).replace(',', '')
                    gr_wt = match.group(8).replace(',', '')
                    unit_price = match.group(10).replace(',', '')
                    total_value = match.group(11).replace(',', '')

                    item = {
                        'part_number': match.group(4),
                        'quantity': int(qty_str),
                        'total_price': float(total_value),
                        'po_number': match.group(1),
                        'packages': match.group(2),
                        'hs_code': match.group(5),
                        'country_origin': match.group(6),
                        'net_weight': net_wt,
                        'gross_weight': gr_wt,
                        'dimensions': match.group(9),
                        'unit_price': unit_price,
                    }

                    item_key = f"{item['part_number']}_{item['quantity']}_{item['total_price']}"
                    if item_key not in seen_items:
                        seen_items.add(item_key)
                        line_items.append(item)
                except (IndexError, ValueError):
                    continue

        # Simplified format fallback (e.g., HTS#8432900020-HUB CASTINGS 4 PCS $265.81 $1,063.24)
        if len(line_items) == 0:
            simple_pattern = re.compile(
                r'HTS#(\d{10})-([A-Z\s]+?)\s+'      # HTS code and description
                r'(\d+)\s*PCS?\s+'                  # Quantity
                r'\$([\d,.]+)\s+'                   # Unit price
                r'\$([\d,.]+)',                     # Total value
                re.IGNORECASE
            )
            for match in simple_pattern.finditer(text):
                try:
                    hs_code_raw = match.group(1)
                    # Format as proper HS code: 8432.90.0020
                    hs_code = f"{hs_code_raw[:4]}.{hs_code_raw[4:6]}.{hs_code_raw[6:]}"
                    description = match.group(2).strip()
                    qty = int(match.group(3))
                    unit_price = match.group(4).replace(',', '')
                    total_value = match.group(5).replace(',', '')

                    item = {
                        'part_number': description.replace(' ', '_'),
                        'quantity': qty,
                        'total_price': float(total_value),
                        'po_number': '',
                        'packages': '',
                        'hs_code': hs_code,
                        'country_origin': 'CHINA',
                        'net_weight': '',
                        'gross_weight': '',
                        'dimensions': '',
                        'unit_price': unit_price,
                    }

                    item_key = f"{item['part_number']}_{item['quantity']}_{item['total_price']}"
                    if item_key not in seen_items:
                        seen_items.add(item_key)
                        line_items.append(item)
                except (IndexError, ValueError):
                    continue

        return line_items
