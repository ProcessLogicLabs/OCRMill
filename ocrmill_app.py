#!/usr/bin/env python3
"""
OCRMill - Invoice Processing Suite (PyQt6 Version)

Main entry point for the PyQt6-based OCRMill application.

Usage:
    python ocrmill_app.py

================================================================================
                        PROPRIETARY SOFTWARE LICENSE
================================================================================

Copyright (c) 2025-2026 Process Logic Labs, LLC. All Rights Reserved.

CONFIDENTIAL AND PROPRIETARY

This software and its source code are the exclusive property of Process Logic
Labs, LLC. Unauthorized copying, modification, distribution, or use of this
software, in whole or in part, is strictly prohibited without prior written
authorization from Process Logic Labs, LLC.

DISCLAIMER OF WARRANTIES:
THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. PROCESS LOGIC LABS, LLC
MAKES NO WARRANTIES REGARDING THE ACCURACY, RELIABILITY, OR COMPLETENESS OF
ANY DATA PROCESSED BY THIS SOFTWARE.

LIMITATION OF LIABILITY:
IN NO EVENT SHALL PROCESS LOGIC LABS, LLC BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

DATA PROCESSING DISCLAIMER:
This software performs optical character recognition (OCR) and data extraction.
Users are solely responsible for verifying the accuracy of all extracted data
before use. Process Logic Labs, LLC assumes no responsibility for errors in
data extraction, classification, or any decisions made based on processed data.

INTELLECTUAL PROPERTY:
OCRMill, the OCRMill logo, and all related trademarks, service marks, and trade
names are the property of Process Logic Labs, LLC. All rights reserved.

Contact: admin@processlogiclabs.com
Website: https://processlogiclabs.com
================================================================================
"""

import sys
import traceback
import logging
from datetime import datetime
from pathlib import Path

# Ensure the application directory is in the path
APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer, qInstallMessageHandler
from PyQt6.QtGui import QIcon

from core.theme_manager import get_theme_manager

# Set up crash logging
CRASH_LOG_PATH = APP_DIR / "crash_log.txt"

def setup_crash_logging():
    """Set up logging for crash diagnostics."""
    logging.basicConfig(
        filename=str(CRASH_LOG_PATH),
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    Global exception handler to catch unhandled exceptions.
    Logs the error and shows a message box to the user.
    """
    # Don't intercept keyboard interrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Format the exception
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log to file
    try:
        with open(CRASH_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH REPORT - {timestamp}\n")
            f.write(f"{'='*60}\n")
            f.write(error_msg)
            f.write("\n")
    except Exception:
        pass  # Fail silently if we can't write to log

    # Log using logging module as well
    logging.error(f"Unhandled exception:\n{error_msg}")

    # Print to console
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"UNHANDLED EXCEPTION - {timestamp}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(error_msg, file=sys.stderr)

    # Show message box if QApplication exists
    app = QApplication.instance()
    if app:
        try:
            QMessageBox.critical(
                None,
                "OCRMill Error",
                f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}\n\n"
                f"Details have been logged to:\n{CRASH_LOG_PATH}\n\n"
                "The application may be unstable. Please save your work and restart."
            )
        except Exception:
            pass  # Fail silently if we can't show the message box

    # Call the default handler
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def qt_message_handler(mode, context, message):
    """Handle Qt internal messages for debugging."""
    if mode == 3:  # QtCriticalMsg or QtFatalMsg
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(CRASH_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(f"\n[{timestamp}] Qt Critical: {message}\n")
                if context.file:
                    f.write(f"  File: {context.file}, Line: {context.line}\n")
        except Exception:
            pass
        print(f"Qt Critical: {message}", file=sys.stderr)


def main():
    """Main application entry point."""
    # Install global exception handler FIRST - catches silent crashes
    sys.excepthook = global_exception_handler
    setup_crash_logging()

    # Install Qt message handler for Qt-level errors
    qInstallMessageHandler(qt_message_handler)

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

    # Apply saved theme (uses theme manager for comprehensive styling)
    theme_manager = get_theme_manager()
    saved_theme = theme_manager.load_saved_theme()
    theme_manager.apply_theme(saved_theme)

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

    # Check license status
    splash.set_status("Checking license...")
    splash.set_progress(55)
    app.processEvents()

    from licensing.license_manager import LicenseManager
    license_mgr = LicenseManager(db)
    license_status, license_days = license_mgr.get_license_status()

    # Authentication check (same flow as TariffMill)
    splash.set_status("Checking authentication...")
    splash.set_progress(60)
    app.processEvents()

    from licensing.auth_manager import AuthenticationManager
    auth_manager = AuthenticationManager(db)

    # Only perform authentication if require_login is enabled
    if config.require_login:
        # Try Windows domain authentication first
        windows_auth_success, windows_msg, _ = auth_manager.try_windows_auth()

        if windows_auth_success:
            # Windows auth successful - continue
            logging.info(f"Windows auth successful: {auth_manager.current_user}")
        else:
            # Windows auth failed - show login dialog
            logging.debug(f"Windows auth not available: {windows_msg}")

            # Hide splash temporarily to show login dialog
            splash.hide()
            app.processEvents()

            from ui.dialogs.login_dialog import LoginDialog
            login_dialog = LoginDialog(db, allow_skip=config.allow_skip_login)
            login_dialog.setWindowIcon(app.windowIcon())

            if login_dialog.exec() != 1:  # Dialog rejected (cancel clicked)
                logging.info("User cancelled login, exiting application")
                sys.exit(0)

            # Check if user authenticated or skipped
            if login_dialog.authenticated_user:
                # Update auth_manager state from login dialog
                auth_manager.current_user = login_dialog.authenticated_user.get('email')
                auth_manager.current_name = login_dialog.authenticated_user.get('name')
                auth_manager.current_role = login_dialog.authenticated_user.get('role')
                auth_manager.is_authenticated = True
                logging.info(f"User authenticated: {auth_manager.current_user}")
            else:
                # User skipped login (if allowed)
                logging.info("User skipped login")

            # Show splash again
            splash.show()
            splash.center_on_screen()
            app.processEvents()
    else:
        logging.info("Login not required (config.require_login=False)")

    # Load templates
    splash.set_status("Loading invoice templates...")
    splash.set_progress(65)
    app.processEvents()

    from templates import get_all_templates
    get_all_templates()  # Pre-load templates

    # Track app startup event
    splash.set_status("Initializing statistics...")
    splash.set_progress(75)
    app.processEvents()

    from stats_tracking.stats_tracker import StatisticsTracker, EventTypes
    stats_tracker = StatisticsTracker(db)
    stats_tracker.track_event(EventTypes.APP_STARTED, {'version': '0.99.04'})

    # Create main window
    splash.set_status("Creating main window...")
    splash.set_progress(85)
    app.processEvents()

    from ui.main_window import OCRMillMainWindow
    window = OCRMillMainWindow(config=config, db=db)
    window.auth_manager = auth_manager  # Pass auth manager for user info display

    # Sync user state from auth_manager to main window
    if auth_manager.is_authenticated:
        window.current_user = {
            'email': auth_manager.current_user,
            'name': auth_manager.current_name,
            'role': auth_manager.current_role,
            'is_authenticated': True
        }
        window._update_user_status()

    # Finish loading
    splash.set_status("Ready!")
    splash.set_progress(100)
    app.processEvents()

    # Check if license is expired - show activation dialog
    if license_status == 'expired':
        splash.finish()
        splash.close()
        from ui.dialogs.license_dialog import LicenseExpiredDialog
        expired_dialog = LicenseExpiredDialog(db)
        if expired_dialog.exec() != 1:  # Dialog rejected (exit clicked)
            sys.exit(0)
        # Re-check license after potential activation
        license_status, license_days = license_mgr.get_license_status()
        if license_status == 'expired':
            sys.exit(0)
        window.show()
    else:
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
