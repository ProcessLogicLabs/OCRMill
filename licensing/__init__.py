"""
OCRMill Licensing Module

Handles license validation via Gumroad and user authentication.
"""

from .license_manager import LicenseManager
from .auth_manager import AuthenticationManager

__all__ = ['LicenseManager', 'AuthenticationManager']
