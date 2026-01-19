"""
OCRMill Authentication Manager

Manages user authentication with Windows domain auth, remote user list (shared with TariffMill),
and local credential caching for offline use.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from parts_database import PartsDatabase

logger = logging.getLogger(__name__)

# GitHub API URL for shared user list (same as TariffMill)
AUTH_CONFIG_URL = "https://api.github.com/repos/ProcessLogicLabs/TariffMill/contents/auth_users.json"

# Personal Access Token for private repo (read-only, contents scope)
# Set OCRMILL_GITHUB_TOKEN or TARIFFMILL_GITHUB_TOKEN environment variable
AUTH_GITHUB_TOKEN = os.environ.get('OCRMILL_GITHUB_TOKEN',
                                    os.environ.get('TARIFFMILL_GITHUB_TOKEN', ''))

# Version for API requests
VERSION = "0.99.04"


class AuthenticationManager:
    """Manages user authentication with Windows domain auth, remote user list, and local caching."""

    def __init__(self, db: PartsDatabase):
        self.db = db
        self.current_user: Optional[str] = None
        self.current_role: Optional[str] = None
        self.current_name: Optional[str] = None
        self.is_authenticated: bool = False
        self.auth_method: Optional[str] = None  # 'windows' or 'password'

    def _get_config(self, key: str) -> Optional[str]:
        """Get a value from app_config table."""
        try:
            return self.db.get_app_config(key)
        except Exception as e:
            logger.warning(f"Failed to get auth config {key}: {e}")
            return None

    def _set_config(self, key: str, value: str) -> bool:
        """Set a value in app_config table."""
        try:
            self.db.set_app_config(key, str(value))
            return True
        except Exception as e:
            logger.warning(f"Failed to set auth config {key}: {e}")
            return False

    def get_allowed_domains(self) -> List[str]:
        """Get allowed Windows domains from settings."""
        try:
            domains = self._get_config('allowed_domains')
            if domains:
                return [d.strip() for d in domains.split(',') if d.strip()]
        except Exception:
            pass
        return []  # No domains configured = no auto-login allowed

    def set_allowed_domains(self, domains: List[str]) -> None:
        """Set allowed Windows domains."""
        self._set_config('allowed_domains', ','.join(domains))

    def get_windows_user_info(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current Windows domain and username.

        Returns (domain, username) or (None, None) if not available.
        """
        domain = os.environ.get('USERDOMAIN', '')
        username = os.environ.get('USERNAME', '')
        return (domain, username) if domain and username else (None, None)

    def try_windows_auth(self) -> Tuple[bool, str, Optional[Dict]]:
        """Try to authenticate using Windows domain credentials.

        Returns (success: bool, message: str, user_data: dict or None)
        """
        try:
            username = os.environ.get('USERNAME', '')
            domain = os.environ.get('USERDOMAIN', '')

            if not username or not domain:
                return False, "Windows credentials not available", None

            # Check if domain is in allowed list
            allowed_domains = self.get_allowed_domains()
            if not allowed_domains:
                logger.debug("No allowed domains configured")
                return False, "No domains configured for auto-login", None
            if domain.upper() not in [d.upper() for d in allowed_domains]:
                logger.debug(f"Domain {domain} not in allowed list")
                return False, f"Domain {domain} not authorized for auto-login", None

            # Build the Windows user identifier
            windows_user = f"{domain.upper()}\\{username.lower()}"
            logger.info(f"Attempting Windows auth for: {windows_user}")

            # Fetch remote users
            remote_users = self._fetch_remote_users()
            if remote_users is None:
                logger.warning("Failed to fetch remote users")
                return False, "Could not fetch user list", None

            logger.debug(f"Fetched {len(remote_users)} users")

            # Look for Windows user in user list (case-insensitive)
            for user_key, user_data in remote_users.items():
                # Check if this is a Windows-style user (contains backslash)
                if '\\' in user_key:
                    if user_key.upper() == windows_user.upper():
                        # Windows user found - check if suspended
                        if user_data.get('suspended', False):
                            return False, "Your account has been suspended. Contact your administrator.", None

                        role = user_data.get('role', 'user')
                        name = user_data.get('name', username)

                        self.current_user = user_key
                        self.current_role = role
                        self.current_name = name
                        self.is_authenticated = True
                        self.auth_method = 'windows'

                        # Store last login
                        self._set_config('last_auth_user', user_key)
                        self._set_config('last_auth_time', datetime.now().isoformat())
                        self._set_config('last_auth_method', 'windows')

                        logger.info(f"Windows auth successful for {windows_user}")
                        return True, f"Welcome, {name}!", user_data

            # Windows user not in allowed list
            logger.debug(f"Windows user {windows_user} not found in user list")
            return False, f"Windows user {windows_user} not authorized", None

        except Exception as e:
            logger.warning(f"Windows auth failed: {e}")
            return False, str(e), None

    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash a password using SHA-256 with salt.

        Returns (hash, salt) tuple.
        """
        if salt is None:
            salt = secrets.token_hex(16)

        # Combine password with salt and hash
        salted = f"{salt}{password}".encode('utf-8')
        password_hash = hashlib.sha256(salted).hexdigest()

        return password_hash, salt

    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify a password against stored hash and salt."""
        computed_hash, _ = self._hash_password(password, salt)
        return computed_hash == stored_hash

    def _fetch_remote_users(self) -> Optional[Dict]:
        """Fetch user list from remote GitHub-hosted JSON (supports private repos).

        Expected JSON format:
        {
            "users": {
                "admin@processlogiclabs.com": {
                    "password_hash": "abc123...",
                    "salt": "def456...",
                    "role": "admin",
                    "name": "Admin User"
                },
                "customer@example.com": {
                    "password_hash": "ghi789...",
                    "salt": "jkl012...",
                    "role": "user",
                    "name": "Customer Name"
                }
            }
        }
        """
        import time

        try:
            headers = {
                'User-Agent': f'OCRMill/{VERSION}',
                'Accept': 'application/vnd.github.v3+json',
                'Cache-Control': 'no-cache'
            }

            # Add authorization header if token is configured
            if AUTH_GITHUB_TOKEN and not AUTH_GITHUB_TOKEN.startswith('ghp_REPLACE'):
                headers['Authorization'] = f'token {AUTH_GITHUB_TOKEN}'

            # Add cache-busting parameter with timestamp to force fresh content
            cache_bust_url = f"{AUTH_CONFIG_URL}?_={int(time.time())}"
            req = urllib.request.Request(cache_bust_url, headers=headers)

            with urllib.request.urlopen(req, timeout=10) as response:
                api_response = json.loads(response.read().decode('utf-8'))

                # GitHub API returns content as base64 encoded
                if 'content' in api_response:
                    # Decode base64 content from GitHub API response
                    content_b64 = api_response['content'].replace('\n', '')
                    content_bytes = base64.b64decode(content_b64)
                    data = json.loads(content_bytes.decode('utf-8'))
                else:
                    # Direct JSON response (for raw URLs)
                    data = api_response

                logger.info("Successfully fetched remote user list")
                return data.get('users', {})

        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.warning("GitHub authentication failed - check AUTH_GITHUB_TOKEN")
            elif e.code == 404:
                logger.warning("Auth config file not found in GitHub repo")
            else:
                logger.warning(f"GitHub API error: {e.code} {e.reason}")
            return self._load_local_auth_file()
        except urllib.error.URLError as e:
            logger.warning(f"Failed to fetch remote user list: {e}")
            return self._load_local_auth_file()
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid auth users JSON: {e}")
            return self._load_local_auth_file()
        except Exception as e:
            logger.warning(f"Error fetching remote user list: {e}")
            return self._load_local_auth_file()

    def _load_local_auth_file(self) -> Optional[Dict]:
        """Load user list from local auth_users.json file as fallback.

        This is used when remote fetch fails or for development/testing.
        """
        try:
            # Check in project root directory
            local_auth_path = Path(__file__).parent.parent / 'auth_users.json'
            if local_auth_path.exists():
                with open(local_auth_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded local auth file: {local_auth_path}")
                    return data.get('users', {})

            # Also check in same directory as script
            alt_path = Path(__file__).parent / 'auth_users.json'
            if alt_path.exists():
                with open(alt_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded local auth file: {alt_path}")
                    return data.get('users', {})

            logger.warning("No local auth_users.json found")
            return None
        except Exception as e:
            logger.warning(f"Failed to load local auth file: {e}")
            return None

    def _cache_credentials(self, email: str, password_hash: str, salt: str,
                          role: str, name: str, suspended: bool = False) -> None:
        """Cache user credentials locally for offline authentication."""
        try:
            cached_users_str = self._get_config('cached_auth_users')
            if cached_users_str:
                users = json.loads(cached_users_str)
            else:
                users = {}

            users[email.lower()] = {
                'password_hash': password_hash,
                'salt': salt,
                'role': role,
                'name': name,
                'suspended': suspended,
                'cached_at': datetime.now().isoformat()
            }

            self._set_config('cached_auth_users', json.dumps(users))
            logger.debug(f"Cached credentials for {email}")
        except Exception as e:
            logger.warning(f"Failed to cache credentials: {e}")

    def _get_cached_user(self, email: str) -> Optional[Dict]:
        """Get cached user credentials for offline authentication."""
        try:
            cached_users_str = self._get_config('cached_auth_users')
            if cached_users_str:
                users = json.loads(cached_users_str)
                return users.get(email.lower())
        except Exception as e:
            logger.warning(f"Failed to get cached user: {e}")
        return None

    def authenticate(self, email: str, password: str) -> Tuple[bool, str, Optional[str]]:
        """Authenticate user against remote user list or cached credentials.

        Returns (success: bool, message: str, role: str or None)
        """
        email = email.strip().lower()
        if not email or not password:
            return False, "Email and password are required", None

        # Try remote authentication first
        remote_users = self._fetch_remote_users()

        if remote_users is not None:
            # Online authentication
            user_data = None
            for user_email, data in remote_users.items():
                if user_email.lower() == email:
                    user_data = data
                    break

            if user_data:
                # Check if user is suspended
                if user_data.get('suspended', False):
                    return False, "Your account has been suspended. Contact your administrator.", None

                stored_hash = user_data.get('password_hash', '')
                salt = user_data.get('salt', '')
                role = user_data.get('role', 'user')
                name = user_data.get('name', email)

                if self._verify_password(password, stored_hash, salt):
                    # Cache credentials for offline use
                    self._cache_credentials(email, stored_hash, salt, role, name, suspended=False)

                    self.current_user = email
                    self.current_role = role
                    self.current_name = name
                    self.is_authenticated = True
                    self.auth_method = 'password'

                    # Store last login
                    self._set_config('last_auth_user', email)
                    self._set_config('last_auth_time', datetime.now().isoformat())
                    self._set_config('last_auth_method', 'password')

                    logger.info(f"User {email} authenticated successfully (online)")
                    return True, f"Welcome, {name}!", role
                else:
                    return False, "Invalid email or password", None
            else:
                return False, "User not found", None

        else:
            # Offline authentication - use cached credentials
            logger.info("Remote auth unavailable, trying cached credentials")
            cached_user = self._get_cached_user(email)

            if cached_user:
                # Check if user is suspended
                if cached_user.get('suspended', False):
                    return False, ("Your account has been suspended. Contact your administrator.\n\n"
                                   "If your suspension has been lifted, please connect to the network and try again."), None

                stored_hash = cached_user.get('password_hash', '')
                salt = cached_user.get('salt', '')
                role = cached_user.get('role', 'user')
                name = cached_user.get('name', email)

                if self._verify_password(password, stored_hash, salt):
                    self.current_user = email
                    self.current_role = role
                    self.current_name = name
                    self.is_authenticated = True
                    self.auth_method = 'password'

                    self._set_config('last_auth_user', email)
                    self._set_config('last_auth_time', datetime.now().isoformat())

                    logger.info(f"User {email} authenticated successfully (offline/cached)")
                    return True, f"Welcome, {name}! (Offline mode)", role
                else:
                    return False, "Invalid email or password", None
            else:
                return False, "Cannot authenticate: No network connection and no cached credentials", None

    def logout(self) -> None:
        """Clear current authentication state."""
        self.current_user = None
        self.current_role = None
        self.current_name = None
        self.is_authenticated = False
        self.auth_method = None
        logger.info("User logged out")

    def is_admin(self) -> bool:
        """Check if current user has admin role."""
        return self.is_authenticated and self.current_role == 'admin'

    def get_last_user(self) -> str:
        """Get the last authenticated user email for convenience."""
        return self._get_config('last_auth_user') or ''

    def get_current_user_info(self) -> Dict:
        """Get information about currently authenticated user."""
        return {
            'email': self.current_user,
            'name': self.current_name,
            'role': self.current_role,
            'is_authenticated': self.is_authenticated,
            'auth_method': self.auth_method,
            'is_admin': self.is_admin()
        }

    @staticmethod
    def generate_password_hash(password: str) -> Dict[str, str]:
        """Utility to generate password hash for adding new users.

        Returns dict with 'password_hash' and 'salt' to add to auth_users.json
        """
        salt = secrets.token_hex(16)
        salted = f"{salt}{password}".encode('utf-8')
        password_hash = hashlib.sha256(salted).hexdigest()

        return {
            'password_hash': password_hash,
            'salt': salt
        }
