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
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

from Resources.styles import APP_STYLESHEET


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

    # Show splash screen during initialization
    from ui.widgets.splash_screen import SpinningSplashScreen
    splash = SpinningSplashScreen()
    splash.center_on_screen()
    splash.show()
    splash.set_status("Starting OCRMill...")
    splash.set_progress(10)
    app.processEvents()

    # Load configuration
    splash.set_status("Loading configuration...")
    splash.set_progress(25)
    app.processEvents()

    from config_manager import ConfigManager
    config = ConfigManager()

    # Initialize database
    splash.set_status("Initializing database...")
    splash.set_progress(45)
    app.processEvents()

    from parts_database import PartsDatabase
    db = PartsDatabase(config.database_path)

    # Load templates
    splash.set_status("Loading invoice templates...")
    splash.set_progress(65)
    app.processEvents()

    from templates import get_all_templates
    get_all_templates()  # Pre-load templates

    # Create main window
    splash.set_status("Creating main window...")
    splash.set_progress(85)
    app.processEvents()

    from ui.main_window import OCRMillMainWindow
    window = OCRMillMainWindow(config=config, db=db)

    # Finish loading
    splash.set_status("Ready!")
    splash.set_progress(100)
    app.processEvents()

    # Show splash screen for 2 seconds while spinner runs
    QTimer.singleShot(2000, lambda: _show_main_window(splash, window))

    # Run event loop
    sys.exit(app.exec())


def _show_main_window(splash, window):
    """Close splash and show main window."""
    splash.finish()
    splash.close()
    window.show()


if __name__ == "__main__":
    main()
