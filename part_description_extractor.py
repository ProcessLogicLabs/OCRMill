"""
Part Description Extractor
Extracts human-readable descriptions from mmcité part numbers and improves HTS code matching.
"""

import re
from typing import Optional, Dict, List


class PartDescriptionExtractor:
    """
    Extracts product descriptions from mmcité part numbers.

    mmcité uses a structured part numbering system where prefixes indicate product types.
    """

    # Part number prefix to description mapping
    PREFIX_DESCRIPTIONS = {
        # Seating
        'SL': 'Seat/Seating element',
        'SLE': 'Seat element',
        'SLU': 'Seating unit',

        # Benches
        'BTT': 'Bench',
        'BEN': 'Bench',

        # Bicycle-related
        'STE': 'Bicycle stand/rack',
        'BIKE': 'Bicycle rack',

        # Planters
        'LPU': 'Planter/Flower pot',
        'PLT': 'Planter',

        # Bollards
        'ND': 'Bollard',
        'BOL': 'Bollard',

        # Tables
        'PQA': 'Table',
        'TAB': 'Table',
        'TBL': 'Table',

        # Litter bins
        'KSA': 'Litter bin/Waste receptacle',
        'BIN': 'Litter bin',
        'WASTE': 'Waste receptacle',

        # Tree grates
        'MRU': 'Tree grate',
        'TREE': 'Tree grate',

        # Barriers/Fencing
        'BAR': 'Barrier',
        'FENCE': 'Fence/Fencing',

        # Lighting
        'LIGHT': 'Light/Lighting',
        'LAMP': 'Lamp',

        # Accessories
        'ACC': 'Accessory',
        'MOUNT': 'Mounting accessory',
        'ANCHOR': 'Anchor/Fixing',

        # Packaging (excluded but documented)
        'OBAL': 'Packaging/Crating',

        # Miscellaneous
        'SIGN': 'Signage',
        'POST': 'Post',
    }

    # HTS code mapping based on product types
    DESCRIPTION_TO_HTS = {
        'SEAT': '9403.20.0080',
        'BENCH': '9401.69.8031',
        'BICYCLE': '9403.20.0082',
        'BIKE': '9403.20.0082',
        'STAND': '9403.20.0082',
        'RACK': '9403.20.0082',
        'PLANTER': '9403.20.0080',
        'FLOWER': '9403.20.0080',
        'POT': '9403.20.0080',
        'BOLLARD': '7308.90.6000',
        'TABLE': '9403.20.0080',
        'LITTER': '7310.29.0050',
        'WASTE': '7310.29.0050',
        'BIN': '7310.29.0050',
        'RECEPTACLE': '7310.29.0050',
        'TREE GRATE': '7326.90.8688',
        'GRATE': '7326.90.8688',
        'BARRIER': '7308.90.9590',
        'FENCE': '7308.90.9590',
        'FENCING': '7308.90.9590',
        'LIGHT': '9405.40.8000',
        'LAMP': '9405.40.8000',
        'LIGHTING': '9405.40.8000',
        'SIGN': '9405.60.8000',
        'SIGNAGE': '9405.60.8000',
        'POST': '7308.90.3000',
        'ANCHOR': '7318.15.2095',
        'BOLT': '7318.15.2095',
        'FIXING': '7318.15.2095',
        'MOUNT': '7326.90.8688',
    }

    def extract_description(self, part_number: str) -> str:
        """
        Extract description from part number.

        Args:
            part_number: mmcité part number (e.g., "SL505-002000")

        Returns:
            Human-readable description
        """
        if not part_number:
            return ""

        part_upper = part_number.upper()

        # Try exact prefix match (longest first)
        for prefix in sorted(self.PREFIX_DESCRIPTIONS.keys(), key=len, reverse=True):
            if part_upper.startswith(prefix):
                base_desc = self.PREFIX_DESCRIPTIONS[prefix]

                # Try to extract additional details from the part number
                details = self._extract_details(part_number, prefix)
                if details:
                    return f"{base_desc} - {details}"
                return base_desc

        # If no prefix match, return a generic description
        return f"mmcité product {part_number}"

    def _extract_details(self, part_number: str, prefix: str) -> str:
        """
        Extract additional details from part number beyond the prefix.

        Args:
            part_number: Full part number
            prefix: Matched prefix

        Returns:
            Additional details string
        """
        # Remove the prefix to get the detail part
        detail_part = part_number[len(prefix):]

        # Look for model numbers (typically 3-4 digits)
        model_match = re.search(r'(\d{3,4})', detail_part)
        if model_match:
            model = model_match.group(1)
            return f"Model {model}"

        # Look for color codes
        if '-' in detail_part:
            parts = detail_part.split('-')
            if len(parts) > 1:
                color_code = parts[-1]
                # Common color code patterns
                if re.match(r'^\d{6}$', color_code):
                    return f"Color {color_code}"

        return ""

    def find_hts_from_description(self, description: str) -> Optional[str]:
        """
        Find HTS code based on product description.

        Args:
            description: Product description text

        Returns:
            HTS code if found, None otherwise
        """
        if not description:
            return None

        desc_upper = description.upper()

        # Try exact keyword matches (longest first for specificity)
        for keyword in sorted(self.DESCRIPTION_TO_HTS.keys(), key=len, reverse=True):
            if keyword in desc_upper:
                return self.DESCRIPTION_TO_HTS[keyword]

        return None

    def match_with_hts_database(self, description: str, hts_database: List[Dict]) -> Optional[str]:
        """
        Match description against HTS database entries.

        Args:
            description: Product description
            hts_database: List of dicts with 'hts_code' and 'description' keys

        Returns:
            Best matching HTS code, or None
        """
        if not description or not hts_database:
            return None

        desc_words = set(description.upper().split())
        best_match = None
        best_score = 0

        for entry in hts_database:
            hts_desc = entry.get('description', '')
            if not hts_desc:
                continue

            hts_words = set(hts_desc.upper().split())

            # Calculate overlap score (number of matching words)
            overlap = len(desc_words & hts_words)

            if overlap > best_score:
                best_score = overlap
                best_match = entry.get('hts_code')

        # Only return if we have a reasonable match (at least 1 word overlap)
        return best_match if best_score > 0 else None

    def enrich_part_data(self, part_number: str, existing_description: str = "") -> Dict[str, str]:
        """
        Enrich part data with extracted description and HTS code.

        Args:
            part_number: Part number to enrich
            existing_description: Any existing description (will be preserved if present)

        Returns:
            Dict with 'description' and 'suggested_hts' keys
        """
        # Use existing description if available, otherwise extract
        description = existing_description or self.extract_description(part_number)

        # Try to find HTS code from description
        suggested_hts = self.find_hts_from_description(description)

        return {
            'description': description,
            'suggested_hts': suggested_hts
        }


# Global instance for easy import
extractor = PartDescriptionExtractor()


def extract_description(part_number: str) -> str:
    """Convenience function to extract description."""
    return extractor.extract_description(part_number)


def find_hts_code(part_number: str, description: str = "") -> Optional[str]:
    """
    Convenience function to find HTS code.

    Args:
        part_number: Part number
        description: Optional description (will be extracted if not provided)

    Returns:
        HTS code if found
    """
    if not description:
        description = extract_description(part_number)

    return extractor.find_hts_from_description(description)
