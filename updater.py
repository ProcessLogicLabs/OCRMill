"""
OCRMill Auto-Updater
Checks GitHub releases for updates and handles download/installation.
"""

import json
import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Tuple, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# GitHub repository information
GITHUB_OWNER = "ProcessLogicLabs"
GITHUB_REPO = "OCRInvoiceMill"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parse version string into comparable tuple.
    Handles formats like "2.6.0", "v2.6.0", "2.6"
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('vV')

    # Split by dots and convert to integers
    parts = []
    for part in version_str.split('.'):
        try:
            # Extract only numeric portion
            numeric = ''.join(c for c in part if c.isdigit())
            if numeric:
                parts.append(int(numeric))
        except ValueError:
            pass

    # Ensure at least 3 parts for comparison
    while len(parts) < 3:
        parts.append(0)

    return tuple(parts)


def compare_versions(current: str, latest: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if current < latest, 0 if equal, 1 if current > latest
    """
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)

    if current_tuple < latest_tuple:
        return -1
    elif current_tuple > latest_tuple:
        return 1
    return 0


class UpdateChecker:
    """Handles checking for and downloading updates from GitHub."""

    def __init__(self, current_version: str):
        self.current_version = current_version
        self.latest_version: Optional[str] = None
        self.latest_release_url: Optional[str] = None
        self.release_notes: Optional[str] = None
        self.download_url: Optional[str] = None
        self.last_error: Optional[str] = None

    def check_for_updates(self, timeout: int = 10) -> bool:
        """
        Check GitHub for the latest release.

        Returns:
            True if a newer version is available, False otherwise
        """
        try:
            # Create request with User-Agent header (required by GitHub API)
            request = Request(
                GITHUB_API_URL,
                headers={
                    'User-Agent': f'OCRMill/{self.current_version}',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )

            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Extract release information
            self.latest_version = data.get('tag_name', '').lstrip('vV')
            self.latest_release_url = data.get('html_url', GITHUB_RELEASES_URL)
            self.release_notes = data.get('body', 'No release notes available.')

            # Find Windows executable asset
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '').lower()
                if 'windows' in name and name.endswith('.zip'):
                    self.download_url = asset.get('browser_download_url')
                    break

            # If no specific Windows asset, use the release page
            if not self.download_url:
                self.download_url = self.latest_release_url

            # Compare versions
            if self.latest_version:
                return compare_versions(self.current_version, self.latest_version) < 0

            return False

        except HTTPError as e:
            if e.code == 404:
                self.last_error = "No releases found on GitHub"
            elif e.code == 403:
                self.last_error = "GitHub API rate limit exceeded. Try again later."
            else:
                self.last_error = f"HTTP error: {e.code}"
            return False

        except URLError as e:
            self.last_error = f"Network error: {e.reason}"
            return False

        except json.JSONDecodeError:
            self.last_error = "Invalid response from GitHub"
            return False

        except Exception as e:
            self.last_error = f"Error checking for updates: {str(e)}"
            return False

    def check_for_updates_async(self, callback: Callable[[bool, Optional[str]], None]):
        """
        Check for updates in a background thread.

        Args:
            callback: Function called with (update_available, error_message)
        """
        def _check():
            update_available = self.check_for_updates()
            callback(update_available, self.last_error)

        thread = threading.Thread(target=_check, daemon=True)
        thread.start()

    def open_download_page(self):
        """Open the download page in the default browser."""
        url = self.download_url or self.latest_release_url or GITHUB_RELEASES_URL
        webbrowser.open(url)

    def open_releases_page(self):
        """Open the GitHub releases page."""
        webbrowser.open(GITHUB_RELEASES_URL)

    def get_update_info(self) -> dict:
        """Get information about the available update."""
        return {
            'current_version': self.current_version,
            'latest_version': self.latest_version,
            'release_url': self.latest_release_url,
            'download_url': self.download_url,
            'release_notes': self.release_notes,
            'update_available': compare_versions(
                self.current_version,
                self.latest_version or self.current_version
            ) < 0
        }


def check_for_updates_simple(current_version: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Simple synchronous update check.

    Args:
        current_version: Current application version

    Returns:
        Tuple of (update_available, latest_version, error_message)
    """
    checker = UpdateChecker(current_version)
    update_available = checker.check_for_updates()
    return (update_available, checker.latest_version, checker.last_error)


# For testing
if __name__ == "__main__":
    print("OCRMill Update Checker Test")
    print("-" * 40)

    test_version = "2.5.0"  # Simulate older version
    print(f"Current version: {test_version}")

    checker = UpdateChecker(test_version)
    print("Checking for updates...")

    if checker.check_for_updates():
        print(f"\nUpdate available!")
        print(f"Latest version: {checker.latest_version}")
        print(f"Download URL: {checker.download_url}")
        print(f"\nRelease notes:\n{checker.release_notes[:500]}...")
    else:
        if checker.last_error:
            print(f"Error: {checker.last_error}")
        else:
            print("You have the latest version!")
