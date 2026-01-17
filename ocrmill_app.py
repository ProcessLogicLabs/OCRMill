#!/usr/bin/env python3
"""
OCRMill - Invoice Processing Suite (PyQt6 Version)

Main entry point for the PyQt6-based OCRMill application.

Usage:
    python ocrmill_app.py
"""

import sys
from pathlib import Path

# Ensure the application directory is in the path
APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from Resources.styles import APP_STYLESHEET
from ui.main_window import OCRMillMainWindow


def main():
    """Main application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("OCRMill")
    app.setOrganizationName("Process Logic Labs")
    app.setOrganizationDomain("processlogiclabs.com")

    # Set application icon
    icon_path = APP_DIR / "Resources" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply global stylesheet
    app.setStyleSheet(APP_STYLESHEET)

    # Create and show main window
    window = OCRMillMainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
