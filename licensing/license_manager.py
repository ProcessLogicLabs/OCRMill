"""
OCRMill License Manager

Handles license validation with Gumroad integration, trial period management,
and hybrid online/offline validation.
"""

import json
import logging
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from parts_database import PartsDatabase

logger = logging.getLogger(__name__)

# License Configuration - Update GUMROAD_PRODUCT_ID after creating Gumroad product
GUMROAD_PRODUCT_ID = ""  # Set your Gumroad product ID here
GUMROAD_PRODUCT_URL = ""  # Set your Gumroad product URL here
GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
TRIAL_DAYS = 30
OFFLINE_GRACE_DAYS = 7  # Days to allow offline use before requiring re-validation

# Version for API requests
VERSION = "0.99.03"


class LicenseManager:
    """Manages license validation with Gumroad integration and trial period"""

    def __init__(self, db: PartsDatabase):
        self.db = db
        self.license_key: Optional[str] = None
        self.license_email: Optional[str] = None
        self.license_status: str = 'unknown'  # 'trial', 'active', 'expired', 'invalid'
        self.trial_start_date: Optional[datetime] = None
        self.last_verified: Optional[datetime] = None
        self.error: Optional[str] = None

    def _get_config(self, key: str) -> Optional[str]:
        """Get a value from app_config table"""
        try:
            return self.db.get_app_config(key)
        except Exception as e:
            logger.warning(f"Failed to get config {key}: {e}")
            return None

    def _set_config(self, key: str, value: str) -> bool:
        """Set a value in app_config table"""
        try:
            self.db.set_app_config(key, str(value))
            return True
        except Exception as e:
            logger.warning(f"Failed to set config {key}: {e}")
            return False

    def get_machine_id(self) -> str:
        """Generate a unique machine identifier for tracking (not for locking)"""
        import hashlib
        import platform

        # Combine various system identifiers
        identifiers = [
            platform.node(),  # Computer network name
            platform.machine(),  # Machine type
            platform.processor(),  # Processor info
            platform.system(),  # OS name
            platform.release(),  # OS release
        ]

        # Try to get Windows-specific identifiers
        if sys.platform == 'win32':
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography"
                )
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                identifiers.append(machine_guid)
            except Exception:
                pass

        # Create hash of combined identifiers
        combined = '|'.join(identifiers)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def get_trial_start_date(self) -> datetime:
        """Get the trial start date, initializing it if this is first launch"""
        stored = self._get_config('trial_start_date')
        if stored:
            try:
                return datetime.fromisoformat(stored)
            except Exception:
                pass

        # First launch - initialize trial
        now = datetime.now()
        self._set_config('trial_start_date', now.isoformat())
        logger.info(f"Trial period started: {now.isoformat()}")
        return now

    def get_trial_days_remaining(self) -> int:
        """Calculate remaining days in trial period"""
        start_date = self.get_trial_start_date()
        elapsed = datetime.now() - start_date
        remaining = TRIAL_DAYS - elapsed.days
        return max(0, remaining)

    def is_trial_expired(self) -> bool:
        """Check if trial period has ended"""
        return self.get_trial_days_remaining() <= 0

    def get_stored_license(self) -> Optional[str]:
        """Retrieve stored license information"""
        self.license_key = self._get_config('license_key')
        self.license_email = self._get_config('license_email')
        last_verified = self._get_config('license_last_verified')
        if last_verified:
            try:
                self.last_verified = datetime.fromisoformat(last_verified)
            except Exception:
                self.last_verified = None
        return self.license_key

    def store_license(self, license_key: str, email: Optional[str] = None,
                     purchase_data: Optional[Dict] = None) -> None:
        """Save license information to database"""
        self._set_config('license_key', license_key)
        if email:
            self._set_config('license_email', email)
        self._set_config('license_activated_date', datetime.now().isoformat())
        self._set_config('license_last_verified', datetime.now().isoformat())
        if purchase_data:
            self._set_config('license_purchase_data', json.dumps(purchase_data))
        self.license_key = license_key
        self.license_email = email
        self.last_verified = datetime.now()
        logger.info("License stored successfully")

    def validate_online(self, license_key: str) -> Tuple[Optional[bool], Any]:
        """
        Verify license with Gumroad API.

        Returns:
            (True, purchase_data) if valid
            (False, error_message) if explicitly invalid
            (None, error_message) if network/server error
        """
        if not GUMROAD_PRODUCT_ID:
            # Product ID not configured - skip online validation
            logger.warning("Gumroad product ID not configured, skipping online validation")
            return None, "Product not configured for online validation"

        try:
            data = urllib.parse.urlencode({
                'product_id': GUMROAD_PRODUCT_ID,
                'license_key': license_key,
                'increment_uses_count': 'false'
            }).encode('utf-8')

            request = urllib.request.Request(
                GUMROAD_VERIFY_URL,
                data=data,
                method='POST',
                headers={'User-Agent': f'OCRMill/{VERSION}'}
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                purchase = result.get('purchase', {})

                # Check if refunded or disputed
                if purchase.get('refunded') or purchase.get('disputed'):
                    return False, "License has been refunded or disputed"

                # Check subscription status for memberships
                if purchase.get('subscription_cancelled_at') or purchase.get('subscription_failed_at'):
                    return False, "Subscription is no longer active"

                # Valid license
                email = purchase.get('email', '')
                return True, {'email': email, 'purchase': purchase}
            else:
                return False, result.get('message', 'Invalid license key')

        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, "Invalid license key"
            return None, f"Server error: {e.code}"
        except urllib.error.URLError as e:
            return None, f"Network error: {str(e)}"
        except Exception as e:
            return None, f"Validation error: {str(e)}"

    def validate_offline(self) -> Tuple[bool, str]:
        """Check if stored license is still valid for offline use"""
        if not self.license_key:
            self.get_stored_license()

        if not self.license_key:
            return False, "No license key stored"

        if not self.last_verified:
            return False, "License has never been verified online"

        # Check if within offline grace period
        days_since_verified = (datetime.now() - self.last_verified).days
        if days_since_verified <= OFFLINE_GRACE_DAYS:
            return True, f"Offline mode ({OFFLINE_GRACE_DAYS - days_since_verified} days remaining)"

        return False, "Offline grace period expired, please connect to internet to re-verify"

    def validate_license(self, license_key: Optional[str] = None) -> Tuple[bool, str]:
        """
        Hybrid validation: try online first, fall back to offline.

        Returns: (is_valid, message)
        """
        key_to_check = license_key or self.license_key or self.get_stored_license()

        if not key_to_check:
            return False, "No license key provided"

        # Try online validation first
        online_result, online_data = self.validate_online(key_to_check)

        if online_result is True:
            # Valid online - update stored data
            email = online_data.get('email', '') if isinstance(online_data, dict) else None
            self.store_license(key_to_check, email, online_data)
            self.license_status = 'active'
            return True, "License validated successfully"

        elif online_result is False:
            # Explicitly invalid
            self.license_status = 'invalid'
            return False, online_data  # online_data contains error message

        else:
            # Online check failed (network issue) - try offline
            logger.info(f"Online validation unavailable: {online_data}, trying offline")
            offline_result, offline_msg = self.validate_offline()
            if offline_result:
                self.license_status = 'active'
                return True, offline_msg
            else:
                self.license_status = 'invalid'
                return False, f"Online: {online_data}. Offline: {offline_msg}"

    def activate_license(self, license_key: str) -> Tuple[bool, str]:
        """Activate a new license key"""
        license_key = license_key.strip()
        if not license_key:
            return False, "Please enter a license key"

        # Validate the license
        is_valid, message = self.validate_license(license_key)

        if is_valid:
            logger.info("License activated successfully")
            return True, "License activated successfully!"
        else:
            logger.warning(f"License activation failed: {message}")
            return False, message

    def get_license_status(self) -> Tuple[str, Optional[int]]:
        """
        Determine current license status.

        Returns: ('trial', days_remaining) or ('active', None) or ('expired', None)
        """
        # Check for valid license first
        stored_key = self.get_stored_license()
        if stored_key:
            is_valid, _ = self.validate_license(stored_key)
            if is_valid:
                return 'active', None

        # No valid license - check trial
        if not self.is_trial_expired():
            days = self.get_trial_days_remaining()
            return 'trial', days

        # Trial expired and no valid license
        return 'expired', None

    def clear_license(self) -> None:
        """Clear stored license (for testing or re-activation)"""
        self.db.delete_app_config('license_key')
        self.db.delete_app_config('license_email')
        self.db.delete_app_config('license_activated_date')
        self.db.delete_app_config('license_last_verified')
        self.db.delete_app_config('license_purchase_data')
        self.license_key = None
        self.license_email = None
        self.last_verified = None
        self.license_status = 'unknown'
        logger.info("License cleared")

    def get_license_info(self) -> Dict[str, Any]:
        """Get comprehensive license information for display"""
        status, days = self.get_license_status()

        info = {
            'status': status,
            'status_display': status.title(),
            'license_key': self.license_key,
            'license_email': self.license_email,
            'trial_days_remaining': days if status == 'trial' else None,
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'machine_id': self.get_machine_id(),
        }

        if status == 'trial':
            info['message'] = f"{days} days remaining in trial"
        elif status == 'active':
            info['message'] = "Licensed"
        elif status == 'expired':
            info['message'] = "Trial expired - please activate a license"
        else:
            info['message'] = "Unknown license status"

        return info
