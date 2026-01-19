"""
Login Dialog for OCRMill.

Handles user authentication with email/password or Windows domain auto-login.
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QGroupBox, QFormLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase
from licensing.auth_manager import AuthenticationManager
from core.theme_manager import get_theme_manager


class LoginDialog(QDialog):
    """Login dialog for user authentication."""

    def __init__(self, db: PartsDatabase, parent=None, allow_skip: bool = False):
        super().__init__(parent)
        self.db = db
        self.auth_manager = AuthenticationManager(db)
        self.allow_skip = allow_skip
        self.authenticated_user = None
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("OCRMill - Login")
        self.setMinimumWidth(400)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._setup_ui()
        self._apply_styling()
        self._try_auto_login()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_label = QLabel("Login to OCRMill")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Windows auto-login info
        domain, username = self.auth_manager.get_windows_user_info()
        if domain and username:
            windows_group = QGroupBox("Windows Account")
            windows_layout = QVBoxLayout(windows_group)

            self.windows_label = QLabel(f"Logged in as: {domain}\\{username}")
            windows_layout.addWidget(self.windows_label)

            self.windows_status_label = QLabel("")
            self.windows_status_label.setStyleSheet("color: #666;")
            windows_layout.addWidget(self.windows_status_label)

            self.windows_login_btn = QPushButton("Login with Windows Account")
            self.windows_login_btn.clicked.connect(self._try_windows_login)
            windows_layout.addWidget(self.windows_login_btn)

            layout.addWidget(windows_group)

            # Or separator
            or_layout = QHBoxLayout()
            or_line1 = QFrame()
            or_line1.setFrameShape(QFrame.Shape.HLine)
            or_line1.setFrameShadow(QFrame.Shadow.Sunken)
            or_layout.addWidget(or_line1)
            or_label = QLabel("OR")
            or_label.setStyleSheet("color: #666; padding: 0 10px;")
            or_layout.addWidget(or_label)
            or_line2 = QFrame()
            or_line2.setFrameShape(QFrame.Shape.HLine)
            or_line2.setFrameShadow(QFrame.Shadow.Sunken)
            or_layout.addWidget(or_line2)
            layout.addLayout(or_layout)

        # Email/Password login
        login_group = QGroupBox("Email Login")
        form_layout = QFormLayout(login_group)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Enter your email")
        # Pre-fill with last user
        last_user = self.auth_manager.get_last_user()
        if last_user and '@' in last_user:
            self.email_edit.setText(last_user)
        form_layout.addRow("Email:", self.email_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Enter your password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self._try_email_login)
        form_layout.addRow("Password:", self.password_edit)

        self.remember_check = QCheckBox("Remember my email")
        self.remember_check.setChecked(bool(last_user))
        form_layout.addRow("", self.remember_check)

        layout.addWidget(login_group)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()

        if self.allow_skip:
            skip_btn = QPushButton("Skip")
            skip_btn.clicked.connect(self._skip_login)
            btn_layout.addWidget(skip_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        login_btn = QPushButton("Login")
        login_btn.setDefault(True)
        login_btn.clicked.connect(self._try_email_login)
        btn_layout.addWidget(login_btn)

        layout.addLayout(btn_layout)

    def _try_auto_login(self):
        """Attempt automatic Windows domain login."""
        success, message, user_data = self.auth_manager.try_windows_auth()

        if success:
            self.authenticated_user = self.auth_manager.get_current_user_info()
            self._show_success(message)
            # Auto-close after successful Windows login
            self.accept()
        elif hasattr(self, 'windows_status_label'):
            # Show why Windows login didn't work
            self.windows_status_label.setText(message)

    def _try_windows_login(self):
        """Manually trigger Windows login attempt."""
        self.windows_login_btn.setEnabled(False)
        self.windows_login_btn.setText("Logging in...")

        success, message, user_data = self.auth_manager.try_windows_auth()

        if success:
            self.authenticated_user = self.auth_manager.get_current_user_info()
            self._show_success(message)
            self.accept()
        else:
            self._show_error(message)
            self.windows_login_btn.setEnabled(True)
            self.windows_login_btn.setText("Login with Windows Account")

    def _try_email_login(self):
        """Attempt email/password login."""
        email = self.email_edit.text().strip()
        password = self.password_edit.text()

        if not email:
            self._show_error("Please enter your email")
            self.email_edit.setFocus()
            return

        if not password:
            self._show_error("Please enter your password")
            self.password_edit.setFocus()
            return

        success, message, role = self.auth_manager.authenticate(email, password)

        if success:
            self.authenticated_user = self.auth_manager.get_current_user_info()

            # Save email if remember is checked
            if not self.remember_check.isChecked():
                self.auth_manager._set_config('last_auth_user', '')

            self._show_success(message)
            self.accept()
        else:
            self._show_error(message)
            self.password_edit.setFocus()
            self.password_edit.selectAll()

    def _skip_login(self):
        """Skip login (if allowed)."""
        self.authenticated_user = None
        self.accept()

    def _show_error(self, message: str):
        """Show an error message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #e74c3c;")

    def _show_success(self, message: str):
        """Show a success message."""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #27ae60;")

    def get_authenticated_user(self):
        """Get the authenticated user info (or None if not authenticated)."""
        return self.authenticated_user

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
                QCheckBox {
                    color: #cccccc;
                }
                QFrame[frameShape="4"] {
                    background-color: #3c3c3c;
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
