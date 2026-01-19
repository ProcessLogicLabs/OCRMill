"""
License Dialog for OCRMill.

Displays license status and allows license activation.
"""

import sys
import webbrowser
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QFrame, QMessageBox,
    QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase
from licensing.license_manager import LicenseManager, GUMROAD_PRODUCT_URL
from core.theme_manager import get_theme_manager


class LicenseDialog(QDialog):
    """Dialog for viewing and managing license."""

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.license_manager = LicenseManager(db)
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("OCRMill - License")
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._setup_ui()
        self._apply_styling()
        self._update_status_display()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # License Status Group
        status_group = QGroupBox("License Status")
        status_layout = QVBoxLayout(status_group)

        # Status indicator
        self.status_icon_label = QLabel()
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setFont(QFont("Segoe UI", 32))
        status_layout.addWidget(self.status_icon_label)

        self.status_text_label = QLabel()
        self.status_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        status_layout.addWidget(self.status_text_label)

        self.status_detail_label = QLabel()
        self.status_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_detail_label.setWordWrap(True)
        status_layout.addWidget(self.status_detail_label)

        layout.addWidget(status_group)

        # License Info Group
        info_group = QGroupBox("License Information")
        info_layout = QFormLayout(info_group)

        self.email_label = QLabel("-")
        info_layout.addRow("Email:", self.email_label)

        self.key_label = QLabel("-")
        self.key_label.setWordWrap(True)
        info_layout.addRow("License Key:", self.key_label)

        self.verified_label = QLabel("-")
        info_layout.addRow("Last Verified:", self.verified_label)

        self.machine_label = QLabel(self.license_manager.get_machine_id())
        self.machine_label.setStyleSheet("color: #666; font-family: monospace;")
        info_layout.addRow("Machine ID:", self.machine_label)

        layout.addWidget(info_group)

        # Activation Group
        activate_group = QGroupBox("Activate License")
        activate_layout = QVBoxLayout(activate_group)

        key_layout = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Enter your license key")
        self.key_edit.returnPressed.connect(self._activate_license)
        key_layout.addWidget(self.key_edit)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.clicked.connect(self._activate_license)
        key_layout.addWidget(self.activate_btn)

        activate_layout.addLayout(key_layout)

        self.activate_status_label = QLabel("")
        self.activate_status_label.setWordWrap(True)
        activate_layout.addWidget(self.activate_status_label)

        layout.addWidget(activate_group)

        # Purchase Group
        purchase_group = QGroupBox("Get a License")
        purchase_layout = QVBoxLayout(purchase_group)

        purchase_info = QLabel(
            "OCRMill includes a 30-day free trial.\n"
            "After the trial, a license is required for continued use."
        )
        purchase_info.setWordWrap(True)
        purchase_layout.addWidget(purchase_info)

        if GUMROAD_PRODUCT_URL:
            buy_btn = QPushButton("Buy License")
            buy_btn.clicked.connect(self._open_purchase_page)
            purchase_layout.addWidget(buy_btn)
        else:
            no_url_label = QLabel("(Product not yet available for purchase)")
            no_url_label.setStyleSheet("color: #666; font-style: italic;")
            purchase_layout.addWidget(no_url_label)

        layout.addWidget(purchase_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _update_status_display(self):
        """Update the license status display."""
        info = self.license_manager.get_license_info()
        status = info['status']

        if status == 'active':
            self.status_icon_label.setText("\u2714")  # Checkmark
            self.status_icon_label.setStyleSheet("color: #27ae60;")
            self.status_text_label.setText("Licensed")
            self.status_text_label.setStyleSheet("color: #27ae60;")
            self.status_detail_label.setText("Your license is active.")
        elif status == 'trial':
            days = info['trial_days_remaining']
            self.status_icon_label.setText("\u23F3")  # Hourglass
            if days > 7:
                self.status_icon_label.setStyleSheet("color: #3498db;")
                self.status_text_label.setStyleSheet("color: #3498db;")
            else:
                self.status_icon_label.setStyleSheet("color: #f39c12;")
                self.status_text_label.setStyleSheet("color: #f39c12;")
            self.status_text_label.setText(f"Trial - {days} days remaining")
            self.status_detail_label.setText(
                "You are using OCRMill in trial mode.\n"
                "Enter a license key to activate full access."
            )
        elif status == 'expired':
            self.status_icon_label.setText("\u2716")  # X mark
            self.status_icon_label.setStyleSheet("color: #e74c3c;")
            self.status_text_label.setText("Trial Expired")
            self.status_text_label.setStyleSheet("color: #e74c3c;")
            self.status_detail_label.setText(
                "Your trial period has ended.\n"
                "Please enter a license key to continue using OCRMill."
            )
        else:
            self.status_icon_label.setText("?")
            self.status_icon_label.setStyleSheet("color: #666;")
            self.status_text_label.setText("Unknown")
            self.status_text_label.setStyleSheet("color: #666;")
            self.status_detail_label.setText("Unable to determine license status.")

        # Update info labels
        if info['license_email']:
            self.email_label.setText(info['license_email'])
        else:
            self.email_label.setText("-")

        if info['license_key']:
            # Mask the license key
            key = info['license_key']
            masked = key[:8] + "..." + key[-4:] if len(key) > 12 else key
            self.key_label.setText(masked)
        else:
            self.key_label.setText("-")

        if info['last_verified']:
            self.verified_label.setText(info['last_verified'][:19].replace('T', ' '))
        else:
            self.verified_label.setText("-")

    def _activate_license(self):
        """Attempt to activate the entered license key."""
        key = self.key_edit.text().strip()
        if not key:
            self._show_activate_error("Please enter a license key")
            return

        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Validating...")
        QApplication.processEvents()

        success, message = self.license_manager.activate_license(key)

        if success:
            self._show_activate_success(message)
            self._update_status_display()
            self.key_edit.clear()
            QMessageBox.information(
                self, "License Activated",
                "Your license has been activated successfully!\n\n"
                "Thank you for supporting OCRMill."
            )
        else:
            self._show_activate_error(message)

        self.activate_btn.setEnabled(True)
        self.activate_btn.setText("Activate")

    def _open_purchase_page(self):
        """Open the purchase page in browser."""
        if GUMROAD_PRODUCT_URL:
            webbrowser.open(GUMROAD_PRODUCT_URL)

    def _show_activate_error(self, message: str):
        """Show activation error."""
        self.activate_status_label.setText(message)
        self.activate_status_label.setStyleSheet("color: #e74c3c;")

    def _show_activate_success(self, message: str):
        """Show activation success."""
        self.activate_status_label.setText(message)
        self.activate_status_label.setStyleSheet("color: #27ae60;")

    def _apply_styling(self):
        """Apply theme-aware styling."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: #252526;
                    color: #cccccc;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #4ec9b0;
                }
                QLabel {
                    color: #cccccc;
                }
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #0e639c;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #5f9ea0;
                }
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #5f9ea0;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #4f8e90;
                }
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    background-color: white;
                }
            """)


class LicenseExpiredDialog(QDialog):
    """Dialog shown when trial has expired and no valid license."""

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.license_manager = LicenseManager(db)
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("OCRMill - License Required")
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() &
            ~Qt.WindowType.WindowContextHelpButtonHint &
            ~Qt.WindowType.WindowCloseButtonHint
        )

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_label = QLabel("Trial Period Expired")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(title_label)

        # Message
        message_label = QLabel(
            "Your 30-day trial of OCRMill has ended.\n\n"
            "To continue using OCRMill, please enter a valid license key.\n"
            "If you don't have a license, you can purchase one below."
        )
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # License Key Entry
        key_group = QGroupBox("Enter License Key")
        key_layout = QVBoxLayout(key_group)

        key_input_layout = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX")
        self.key_edit.returnPressed.connect(self._try_activate)
        key_input_layout.addWidget(self.key_edit)

        self.activate_btn = QPushButton("Activate")
        self.activate_btn.clicked.connect(self._try_activate)
        key_input_layout.addWidget(self.activate_btn)

        key_layout.addLayout(key_input_layout)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        key_layout.addWidget(self.feedback_label)

        layout.addWidget(key_group)

        # Buttons
        btn_layout = QHBoxLayout()

        if GUMROAD_PRODUCT_URL:
            buy_btn = QPushButton("Buy License")
            buy_btn.clicked.connect(lambda: webbrowser.open(GUMROAD_PRODUCT_URL))
            btn_layout.addWidget(buy_btn)

        btn_layout.addStretch()

        exit_btn = QPushButton("Exit Application")
        exit_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        exit_btn.clicked.connect(self._exit_app)
        btn_layout.addWidget(exit_btn)

        layout.addLayout(btn_layout)

    def _try_activate(self):
        """Try to activate the entered license key."""
        key = self.key_edit.text().strip()
        if not key:
            self.feedback_label.setText("Please enter a license key")
            self.feedback_label.setStyleSheet("color: #e74c3c;")
            return

        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("Validating...")
        QApplication.processEvents()

        success, message = self.license_manager.activate_license(key)

        if success:
            self.feedback_label.setText(message)
            self.feedback_label.setStyleSheet("color: #27ae60;")
            QMessageBox.information(
                self, "License Activated",
                "Your license has been activated successfully!\n\n"
                "Thank you for purchasing OCRMill."
            )
            self.accept()
        else:
            self.feedback_label.setText(message)
            self.feedback_label.setStyleSheet("color: #e74c3c;")

        self.activate_btn.setEnabled(True)
        self.activate_btn.setText("Activate")

    def _exit_app(self):
        """Exit the application."""
        QApplication.quit()
        import sys
        sys.exit(0)

    def _apply_styling(self):
        """Apply theme-aware styling."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: #252526;
                    color: #cccccc;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #4ec9b0;
                }
                QLabel {
                    color: #cccccc;
                }
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #0e639c;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 10px;
                    background-color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #5f9ea0;
                }
                QPushButton {
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: #5f9ea0;
                    color: white;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #4f8e90;
                }
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #d0d0d0;
                    border-radius: 4px;
                    background-color: white;
                }
            """)
