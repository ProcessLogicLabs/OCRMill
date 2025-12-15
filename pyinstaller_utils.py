"""
PyInstaller Runtime Utilities
Provides path resolution for PyInstaller-packaged executables
"""

import sys
from pathlib import Path


def get_application_path() -> Path:
    """
    Get the application's base path, accounting for PyInstaller.

    When running as a PyInstaller executable, sys._MEIPASS points to the
    temporary extraction folder. For normal Python execution, returns the
    script's directory.

    Returns:
        Path: The application's base directory
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running as normal Python script
        return Path(__file__).parent


def get_resource_path(relative_path: str) -> Path:
    """
    Get the absolute path to a resource file.

    For PyInstaller bundles, resources are in sys._MEIPASS.
    For normal execution, they're relative to the script.

    Args:
        relative_path: Path relative to application base

    Returns:
        Path: Absolute path to the resource
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle - resources in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Running as normal Python script
        base_path = Path(__file__).parent

    return base_path / relative_path


def ensure_data_directories():
    """
    Ensure all required data directories exist in the application folder.

    Creates directories next to the executable (or script) for user data:
    - input/
    - output/
    - output/Processed/
    - output/CBP_Export/
    - reports/
    - Resources/
    """
    app_path = get_application_path()

    directories = [
        app_path / "input",
        app_path / "output",
        app_path / "output" / "Processed",
        app_path / "output" / "CBP_Export",
        app_path / "reports",
        app_path / "Resources",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
