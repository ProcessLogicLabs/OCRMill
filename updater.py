"""
OCRMill Auto-Updater
Checks GitHub releases for updates and handles download/installation.
Based on TariffMill's auto-update implementation.
"""

import json
import os
import sys
import subprocess
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Tuple, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# GitHub repository information
GITHUB_OWNER = "ProcessLogicLabs"
GITHUB_REPO = "OCRMill"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parse version string into comparable tuple.
    Handles formats like "2.6.0", "v2.6.0", "2.6", "0.97.01"
    Also handles git describe format: "v0.90.1-6-gaa8bef5"
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('vV')

    # Handle git describe format (strip everything after first hyphen followed by number)
    if '-' in version_str:
        parts = version_str.split('-')
        if len(parts) > 1 and parts[1].isdigit():
            version_str = parts[0]

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
        self.download_filename: Optional[str] = None
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

            # Find Windows installer asset (.exe)
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '')
                # Look for Setup.exe or installer
                if name.lower().endswith('.exe') and ('setup' in name.lower() or 'install' in name.lower()):
                    self.download_url = asset.get('browser_download_url')
                    self.download_filename = name
                    break

            # Fallback: look for any .exe file
            if not self.download_url:
                for asset in assets:
                    name = asset.get('name', '')
                    if name.lower().endswith('.exe'):
                        self.download_url = asset.get('browser_download_url')
                        self.download_filename = name
                        break

            # If still no download URL, use the release page
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

    def download_update(self, progress_callback: Callable[[int, int], None] = None,
                        cancel_check: Callable[[], bool] = None) -> Optional[Path]:
        """
        Download the update installer to a temp directory.

        Args:
            progress_callback: Called with (downloaded_bytes, total_bytes)
            cancel_check: Called periodically, return True to cancel

        Returns:
            Path to downloaded file, or None if failed/cancelled
        """
        if not self.download_url or self.download_url == self.latest_release_url:
            self.last_error = "No direct download available. Please download from GitHub."
            return None

        try:
            # Determine filename
            filename = self.download_filename or 'OCRMill_Setup.exe'

            # Create temp directory path
            temp_dir = Path(tempfile.gettempdir())
            temp_path = temp_dir / filename

            # Create request
            request = Request(
                self.download_url,
                headers={
                    'User-Agent': f'OCRMill/{self.current_version}'
                }
            )

            with urlopen(request, timeout=60) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(temp_path, 'wb') as f:
                    while True:
                        # Check for cancellation
                        if cancel_check and cancel_check():
                            # Clean up partial download
                            f.close()
                            if temp_path.exists():
                                temp_path.unlink()
                            return None

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

            # Verify download completed
            if total_size > 0 and temp_path.stat().st_size < total_size:
                self.last_error = "Download incomplete"
                temp_path.unlink()
                return None

            return temp_path

        except Exception as e:
            self.last_error = f"Download failed: {str(e)}"
            return None

    def install_update(self, installer_path: Path) -> bool:
        """
        Launch the installer and prepare to close the application.

        Args:
            installer_path: Path to the downloaded installer

        Returns:
            True if installer was launched successfully
        """
        try:
            if sys.platform == 'win32':
                # Windows: Use os.startfile for reliable launching
                os.startfile(str(installer_path))
            else:
                # Linux/macOS: Use subprocess
                subprocess.Popen([str(installer_path)], shell=True)

            return True

        except Exception as e:
            self.last_error = f"Failed to launch installer: {str(e)}"
            return False

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
            'download_filename': self.download_filename,
            'release_notes': self.release_notes,
            'has_direct_download': self.download_url and self.download_url != self.latest_release_url,
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

    test_version = "0.90.0"  # Simulate older version
    print(f"Current version: {test_version}")

    checker = UpdateChecker(test_version)
    print("Checking for updates...")

    if checker.check_for_updates():
        print(f"\nUpdate available!")
        info = checker.get_update_info()
        print(f"Latest version: {info['latest_version']}")
        print(f"Download URL: {info['download_url']}")
        print(f"Direct download: {info['has_direct_download']}")
        print(f"\nRelease notes:\n{info['release_notes'][:500]}...")
    else:
        if checker.last_error:
            print(f"Error: {checker.last_error}")
        else:
            print("You have the latest version!")
