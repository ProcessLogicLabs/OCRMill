"""
International Invoice Template

Template for international commercial invoices with customs-related fields.
Handles various international invoice formats with HS codes, country of origin,
weights, and multi-currency values.
"""

import re
from typing import List, Dict
from .base_template import BaseTemplate


class InternationalInvoiceTemplate(BaseTemplate):
    """
    Template for international commercial invoices.

    Best for:
    - Export/Import invoices
    - Invoices with HS/HTS codes
    - Documents with country of origin
    - Multi-currency invoices
    """

    name = "International Invoice"
    description = "International commercial invoice with customs fields (HS codes, origin, weights)"
    client = "Universal"
    version = "1.0.0"
    enabled = True

    extra_columns = ['unit_price', 'description', 'hs_code', 'country_of_origin', 'net_weight']

    def can_process(self, text: str) -> bool:
        """Check if this is an international commercial invoice."""
        text_lower = text.lower()

        # Must have invoice indicator
        has_invoice = any([
            'commercial invoice' in text_lower,
            'export invoice' in text_lower,
            'proforma invoice' in text_lower,
        ])

        # Should have international trade indicators
        intl_indicators = [
            'country of origin' in text_lower,
            'hs code' in text_lower or 'hts' in text_lower,
            'customs' in text_lower,
            'export' in text_lower or 'import' in text_lower,
            'fob' in text_lower or 'cif' in text_lower or 'exw' in text_lower,
            'incoterm' in text_lower,
        ]

        return has_invoice and any(intl_indicators)

    def get_confidence_score(self, text: str) -> float:
        """Return confidence score for international invoices."""
        if not self.can_process(text):
            return 0.0

        score = 0.45
        text_lower = text.lower()

        # Boost for specific international trade markers
        if 'commercial invoice' in text_lower:
            score += 0.1
        if re.search(r'\b\d{4,10}\.?\d*\b', text) and 'hs' in text_lower:
            score += 0.1  # HS code format
        if 'country of origin' in text_lower:
            score += 0.05
        if re.search(r'\b(fob|cif|exw|ddp|dap)\b', text_lower):
            score += 0.05
        if 'net weight' in text_lower or 'gross weight' in text_lower:
            score += 0.05

        return min(score, 0.75)

    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number."""
        patterns = [
            r'Invoice\s*(?:No\.?|#|Number)[:\s]*([A-Z0-9][\w\-/]+)',
            r'Commercial\s+Invoice[:\s]*(?:No\.?|#)?[:\s]*([A-Z0-9][\w\-/]+)',
            r'Proforma\s*(?:No\.?|#)?[:\s]*([A-Z0-9][\w\-/]+)',
            r'Export\s+Invoice[:\s]*([A-Z0-9][\w\-/]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "UNKNOWN"

    def extract_project_number(self, text: str) -> str:
        """Extract PO/project number."""
        patterns = [
            r'P\.?O\.?\s*(?:No\.?|#|Number)?[:\s]*([A-Z0-9][\w\-/]+)',
            r'Order\s*(?:No\.?|#)?[:\s]*([A-Z0-9][\w\-/]+)',
            r'Contract\s*(?:No\.?|#)?[:\s]*([A-Z0-9][\w\-/]+)',
            r'Buyer[\'s]?\s*(?:Ref|Reference)[:\s]*([A-Z0-9][\w\-/]+)',
            r'Customer\s*(?:Ref|Reference|PO)[:\s]*([A-Z0-9][\w\-/]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "UNKNOWN"

    def _extract_hs_code(self, line: str) -> str:
        """Extract HS/HTS code from a line."""
        # HS codes are typically 6-10 digits, may have dots
        patterns = [
            r'\b(\d{4}\.\d{2}(?:\.\d{2,4})?)\b',  # 8544.42.9000
            r'\b(\d{6,10})\b',                     # 854442900
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                code = match.group(1)
                # Validate it looks like an HS code (not just any number)
                if len(code.replace('.', '')) >= 6:
                    return code

        return ""

    def _extract_country_origin(self, text: str) -> str:
        """Extract country of origin from text."""
        patterns = [
            r'Country\s*(?:of)?\s*Origin[:\s]*([A-Z][A-Za-z\s]+?)(?:\n|$)',
            r'Origin[:\s]*([A-Z][A-Za-z\s]+?)(?:\n|$)',
            r'Made\s+in[:\s]*([A-Z][A-Za-z\s]+?)(?:\n|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                country = match.group(1).strip()
                # Clean up and validate
                country = re.sub(r'\s+', ' ', country)
                if len(country) >= 2 and len(country) <= 50:
                    return country.upper()

        return ""

    def extract_line_items(self, text: str) -> List[Dict]:
        """Extract line items from international invoice."""
        items = []
        seen = set()
        lines = text.split('\n')

        # Get document-level country of origin
        default_origin = self._extract_country_origin(text)

        # Pattern for international invoice line items
        # Part# | Description | HS Code | Qty | Unit Price | Total | Weight
        intl_pattern = re.compile(
            r'([A-Z0-9][\w\-/\.]+)\s+'            # Part number
            r'(.+?)\s+'                            # Description
            r'(\d{4}\.?\d{2}\.?\d{0,4})?\s*'      # HS code (optional)
            r'(\d+(?:\.\d+)?)\s+'                  # Quantity
            r'[\$\€\£]?([\d,]+\.?\d*)\s*'         # Unit price
            r'[\$\€\£]?([\d,]+\.?\d*)',           # Total
            re.IGNORECASE
        )

        # Simpler pattern
        simple_pattern = re.compile(
            r'([A-Z0-9][\w\-/\.]+)\s+'            # Part number
            r'(\d+(?:\.\d+)?)\s+'                  # Quantity
            r'[\$\€\£]?([\d,]+\.?\d*)',           # Total
            re.IGNORECASE
        )

        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue

            # Skip header/total lines
            if re.search(r'^(total|subtotal|grand|tax|freight|shipping)', line, re.IGNORECASE):
                continue

            # Try detailed pattern
            match = intl_pattern.search(line)
            if match:
                part_num = match.group(1)
                desc = match.group(2).strip()
                hs_code = match.group(3) or self._extract_hs_code(line)
                qty = match.group(4)
                unit_price = match.group(5).replace(',', '')
                total = match.group(6).replace(',', '')

                key = f"{part_num}_{qty}_{total}"
                if key not in seen:
                    seen.add(key)
                    items.append({
                        'part_number': part_num,
                        'description': desc,
                        'quantity': qty,
                        'unit_price': unit_price,
                        'total_price': total,
                        'hs_code': hs_code,
                        'country_of_origin': default_origin,
                        'net_weight': '',
                    })
                continue

            # Try simple pattern
            match = simple_pattern.search(line)
            if match:
                part_num = match.group(1)
                qty = match.group(2)
                total = match.group(3).replace(',', '')

                key = f"{part_num}_{qty}_{total}"
                if key not in seen:
                    seen.add(key)
                    items.append({
                        'part_number': part_num,
                        'description': '',
                        'quantity': qty,
                        'unit_price': '',
                        'total_price': total,
                        'hs_code': self._extract_hs_code(line),
                        'country_of_origin': default_origin,
                        'net_weight': '',
                    })

        return items

    def is_packing_list(self, text: str) -> bool:
        """Check if this is only a packing list."""
        text_lower = text.lower()
        if 'packing list' in text_lower:
            if 'invoice' not in text_lower and 'commercial' not in text_lower:
                return True
        return False
