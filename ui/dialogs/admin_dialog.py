"""
OCRMill Administration Dialog

Comprehensive admin panel with:
- Billing Configuration (rate, email settings)
- User Management (add, edit, suspend, delete users)
- Division Management (file number patterns)
- Audit Log (processing history)
- System Info
- User Statistics

Shares the same auth_users.json with TariffMill for unified user management.

Author: OCRMill Team
"""

import json
import hashlib
import secrets
import logging
import subprocess
import platform
import getpass
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QWidget, QTabWidget, QGroupBox, QLabel, QPushButton, QLineEdit,
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView, QStyle, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon

logger = logging.getLogger(__name__)


class AdminDialog(QDialog):
    """
    Administration Dialog - comprehensive admin panel for OCRMill.

    Provides user management, billing configuration, audit logs, and system info.
    Accessible via Ctrl+Shift+A for administrators only.
    """

    def __init__(self, parent=None, config=None, db=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = config
        self.db = db

        self.setWindowTitle("Administration")
        self.setMinimumSize(1000, 700)

        # Size dialog to 75% of user's screen
        screen = QApplication.primaryScreen().availableGeometry()
        width = max(1100, int(screen.width() * 0.75))
        height = max(800, int(screen.height() * 0.75))
        self.resize(width, height)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Header with warning
        header_layout = QHBoxLayout()
        warning_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        icon_label = QLabel()
        icon_label.setPixmap(warning_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        header_label = QLabel("<b>Administration Panel</b> - Restricted Access")
        header_label.setStyleSheet("color: #dc3545; font-size: 14px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Create tab widget
        self.tabs = QTabWidget()

        # Billing Configuration tab (includes User Management)
        tab_billing = QWidget()
        self._setup_billing_tab(tab_billing)
        self.tabs.addTab(tab_billing, "Billing Configuration")

        # Audit Log tab
        tab_audit = QWidget()
        self._setup_audit_tab(tab_audit)
        self.tabs.addTab(tab_audit, "Audit Log")

        # System Info tab
        tab_system = QWidget()
        self._setup_system_tab(tab_system)
        self.tabs.addTab(tab_system, "System Info")

        # User Statistics tab
        tab_stats = QWidget()
        self._setup_stats_tab(tab_stats)
        self.tabs.addTab(tab_stats, "User Statistics")

        layout.addWidget(self.tabs)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    # =========================================================================
    # BILLING CONFIGURATION TAB
    # =========================================================================

    def _setup_billing_tab(self, tab_widget):
        """Setup the Billing Configuration tab with user and division management."""
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        # Buttons row at top
        btn_layout = QHBoxLayout()

        btn_test_email = QPushButton("Test Email")
        btn_test_email.clicked.connect(self._test_billing_email)
        btn_layout.addWidget(btn_test_email)

        btn_layout.addStretch()

        btn_view_report = QPushButton("View Billing Report")
        btn_view_report.setStyleSheet(self._get_button_style("primary"))
        btn_view_report.clicked.connect(self._show_billing_report)
        btn_layout.addWidget(btn_view_report)

        btn_view_audit = QPushButton("View Audit Log")
        btn_view_audit.setStyleSheet(self._get_button_style("primary"))
        btn_view_audit.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        btn_layout.addWidget(btn_view_audit)

        btn_save = QPushButton("Save Settings")
        btn_save.setStyleSheet(self._get_button_style("success"))
        btn_save.clicked.connect(self._save_billing_settings)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        # User Management Section
        user_group = QGroupBox("User Management")
        user_layout = QVBoxLayout()

        # User table
        self.user_table = QTableWidget()
        self.user_table.setColumnCount(5)
        self.user_table.setHorizontalHeaderLabels(["Email", "Name", "Role", "Division", "Actions"])
        self.user_table.horizontalHeader().setStretchLastSection(False)
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.user_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.user_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.user_table.setColumnWidth(1, 120)  # Name
        self.user_table.setColumnWidth(2, 100)  # Role
        self.user_table.setColumnWidth(3, 100)  # Division
        self.user_table.setColumnWidth(4, 130)  # Actions - icon buttons (TariffMill style)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.user_table.setMinimumHeight(200)
        self.user_table.setAlternatingRowColors(True)
        user_layout.addWidget(self.user_table)

        # User management buttons
        user_btn_layout = QHBoxLayout()

        btn_refresh_users = QPushButton("Refresh")
        btn_refresh_users.clicked.connect(self._refresh_user_list)
        user_btn_layout.addWidget(btn_refresh_users)

        btn_add_user = QPushButton("Add User")
        btn_add_user.setStyleSheet(self._get_button_style("primary"))
        btn_add_user.clicked.connect(self._add_user_dialog)
        user_btn_layout.addWidget(btn_add_user)

        user_btn_layout.addStretch()

        user_info = QLabel("<small>Changes are synced to the private GitHub config repository.</small>")
        user_info.setStyleSheet("color: #666;")
        user_btn_layout.addWidget(user_info)

        user_layout.addLayout(user_btn_layout)
        user_group.setLayout(user_layout)
        layout.addWidget(user_group)

        # File Number Divisions Section
        divisions_group = QGroupBox("File Number Divisions")
        divisions_layout = QVBoxLayout()

        divisions_info = QLabel(
            "<small>Define file number patterns for different divisions. "
            "Each division has a required prefix and total character length.</small>"
        )
        divisions_info.setWordWrap(True)
        divisions_info.setStyleSheet("color: #666; padding: 5px;")
        divisions_layout.addWidget(divisions_info)

        # Divisions table
        self.divisions_table = QTableWidget()
        self.divisions_table.setColumnCount(5)
        self.divisions_table.setHorizontalHeaderLabels(["Division Name", "Prefix", "Length", "Description", "Active"])
        self.divisions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.divisions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.divisions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.divisions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.divisions_table.setMinimumHeight(120)
        self.divisions_table.setAlternatingRowColors(True)
        divisions_layout.addWidget(self.divisions_table)

        # Division management buttons
        div_btn_layout = QHBoxLayout()

        btn_refresh_divisions = QPushButton("Refresh")
        btn_refresh_divisions.clicked.connect(self._refresh_divisions_list)
        div_btn_layout.addWidget(btn_refresh_divisions)

        btn_add_division = QPushButton("Add Division")
        btn_add_division.setStyleSheet(self._get_button_style("primary"))
        btn_add_division.clicked.connect(self._add_division_dialog)
        div_btn_layout.addWidget(btn_add_division)

        btn_edit_division = QPushButton("Edit")
        btn_edit_division.clicked.connect(self._edit_division_dialog)
        div_btn_layout.addWidget(btn_edit_division)

        btn_delete_division = QPushButton("Delete")
        btn_delete_division.setStyleSheet(self._get_button_style("danger"))
        btn_delete_division.clicked.connect(self._delete_division)
        div_btn_layout.addWidget(btn_delete_division)

        div_btn_layout.addStretch()
        divisions_layout.addLayout(div_btn_layout)
        divisions_group.setLayout(divisions_layout)
        layout.addWidget(divisions_group)

        # Billing Rate Group (collapsed by default)
        rate_group = QGroupBox("Billing Rate Settings")
        rate_layout = QFormLayout()

        self.billing_rate_spin = QDoubleSpinBox()
        self.billing_rate_spin.setRange(0, 1000)
        self.billing_rate_spin.setDecimals(2)
        self.billing_rate_spin.setPrefix("$")
        self.billing_rate_spin.setValue(float(self._get_billing_setting('rate_per_file', '0')))
        rate_layout.addRow("Rate per Export:", self.billing_rate_spin)

        rate_info = QLabel("<small>Amount to charge per exported file. Set to 0 to disable billing.</small>")
        rate_info.setWordWrap(True)
        rate_info.setStyleSheet("color: #666; padding: 5px;")
        rate_layout.addRow("", rate_info)

        rate_group.setLayout(rate_layout)
        layout.addWidget(rate_group)

        # Email Configuration Group
        email_group = QGroupBox("Email Configuration")
        email_layout = QFormLayout()

        self.billing_customer_email = QLineEdit()
        self.billing_customer_email.setPlaceholderText("customer@example.com")
        self.billing_customer_email.setText(self._get_billing_setting('customer_email', ''))
        email_layout.addRow("Customer Email:", self.billing_customer_email)

        self.billing_admin_email = QLineEdit()
        self.billing_admin_email.setPlaceholderText("admin@example.com")
        self.billing_admin_email.setText(self._get_billing_setting('admin_email', ''))
        email_layout.addRow("Admin Email:", self.billing_admin_email)

        self.billing_smtp_server = QLineEdit()
        self.billing_smtp_server.setPlaceholderText("smtp.gmail.com")
        self.billing_smtp_server.setText(self._get_billing_setting('smtp_server', ''))
        email_layout.addRow("SMTP Server:", self.billing_smtp_server)

        self.billing_smtp_port = QSpinBox()
        self.billing_smtp_port.setRange(1, 65535)
        self.billing_smtp_port.setValue(int(self._get_billing_setting('smtp_port', '587')))
        email_layout.addRow("SMTP Port:", self.billing_smtp_port)

        self.billing_smtp_user = QLineEdit()
        self.billing_smtp_user.setPlaceholderText("username@gmail.com")
        self.billing_smtp_user.setText(self._get_billing_setting('smtp_user', ''))
        email_layout.addRow("SMTP Username:", self.billing_smtp_user)

        self.billing_smtp_password = QLineEdit()
        self.billing_smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.billing_smtp_password.setText(self._get_billing_setting('smtp_password', ''))
        self.billing_smtp_password.setPlaceholderText("App password (not user password)")
        email_layout.addRow("SMTP Password:", self.billing_smtp_password)

        smtp_note = QLabel("<small><i>Use an app password, not your account password.</i></small>")
        smtp_note.setStyleSheet("color: #888;")
        email_layout.addRow("", smtp_note)

        email_group.setLayout(email_layout)
        layout.addWidget(email_group)

        layout.addStretch()

        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)

        # Load initial data
        QTimer.singleShot(100, self._refresh_user_list)
        QTimer.singleShot(100, self._refresh_divisions_list)

    # =========================================================================
    # USER MANAGEMENT
    # =========================================================================

    def _refresh_user_list(self):
        """Refresh the user table from auth_users.json."""
        self.user_table.setRowCount(0)
        users = self._load_auth_users()

        if not users:
            self.user_table.setRowCount(1)
            item = QTableWidgetItem("No users found. Click 'Add User' to create one.")
            self.user_table.setItem(0, 0, item)
            self.user_table.setSpan(0, 0, 1, 5)
            return

        self.user_table.setRowCount(len(users))

        for row_idx, (email, user_data) in enumerate(users.items()):
            # Email
            email_item = QTableWidgetItem(email)
            self.user_table.setItem(row_idx, 0, email_item)

            # Name
            name = user_data.get('name', '')
            name_item = QTableWidgetItem(name)
            self.user_table.setItem(row_idx, 1, name_item)

            # Role
            role = user_data.get('role', 'user')
            auth_type = user_data.get('auth_type', '')
            role_display = f"{role} (Win)" if auth_type == 'windows' or '\\' in email else role
            role_item = QTableWidgetItem(role_display)
            if role == 'admin':
                role_item.setForeground(QColor('#dc3545'))
            elif role == 'division_admin':
                role_item.setForeground(QColor('#28a745'))
            self.user_table.setItem(row_idx, 2, role_item)

            # Division - look up division names from IDs
            managed_divisions = user_data.get('managed_divisions', [])
            if managed_divisions:
                # Build division ID to name mapping
                divisions = self._get_divisions()
                div_map = {d[0]: f"{d[1]} ({d[2]}*)" for d in divisions}  # id -> "Name (prefix*)"
                div_names = [div_map.get(div_id, str(div_id)) for div_id in managed_divisions]
                div_text = ', '.join(div_names)
            else:
                div_text = ''
            div_item = QTableWidgetItem(div_text)
            self.user_table.setItem(row_idx, 3, div_item)

            # Actions - create action buttons with standard icons (TariffMill style)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            style = self.style()

            # Edit button - use theme icon for pencil/edit
            btn_edit = QPushButton()
            edit_icon = QIcon.fromTheme("document-edit", style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
            btn_edit.setIcon(edit_icon)
            btn_edit.setFixedSize(26, 24)
            btn_edit.setToolTip("Edit user")
            btn_edit.clicked.connect(lambda checked, e=email: self._edit_user_dialog(e))
            actions_layout.addWidget(btn_edit)

            # Reset password button (only for non-Windows users)
            is_windows_user = '\\' in email or user_data.get('auth_type') == 'windows'
            if not is_windows_user:
                btn_reset = QPushButton()
                reset_icon = QIcon.fromTheme("view-refresh", style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
                btn_reset.setIcon(reset_icon)
                btn_reset.setFixedSize(26, 24)
                btn_reset.setToolTip("Reset password")
                btn_reset.clicked.connect(lambda checked, e=email: self._reset_user_password(e))
                actions_layout.addWidget(btn_reset)

            # Suspend/Reactivate button
            is_suspended = user_data.get('suspended', False)
            btn_suspend = QPushButton()
            if is_suspended:
                suspend_icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)  # Play = unsuspend
                btn_suspend.setToolTip("Reactivate user")
            else:
                suspend_icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaPause)  # Pause = suspend
                btn_suspend.setToolTip("Suspend user")
            btn_suspend.setIcon(suspend_icon)
            btn_suspend.setFixedSize(26, 24)
            btn_suspend.clicked.connect(lambda checked, e=email: self._toggle_user_suspended(e))
            actions_layout.addWidget(btn_suspend)

            # Delete button
            btn_delete = QPushButton()
            delete_icon = QIcon.fromTheme("edit-delete", style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            btn_delete.setIcon(delete_icon)
            btn_delete.setFixedSize(26, 24)
            btn_delete.setToolTip("Delete user")
            btn_delete.clicked.connect(lambda checked, e=email: self._delete_user(e))
            actions_layout.addWidget(btn_delete)

            actions_layout.addStretch()

            self.user_table.setCellWidget(row_idx, 4, actions_widget)

            # Gray out suspended users
            if is_suspended:
                for col in range(4):
                    item = self.user_table.item(row_idx, col)
                    if item:
                        item.setForeground(QColor('#999999'))
                        if col == 0:
                            item.setText(f"{email} (suspended)")

    def _load_auth_users(self) -> dict:
        """Load users from local auth_users.json file."""
        try:
            # Check in project root directory (same as TariffMill)
            local_auth_path = Path(__file__).parent.parent.parent / 'auth_users.json'
            if local_auth_path.exists():
                with open(local_auth_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('users', {})

            # Also check in TariffMill_Config repo (shared with TariffMill)
            config_path = Path.home() / 'TariffMill_Config' / 'auth_users.json'
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('users', {})

            # Check TariffMill installation directory
            tariffmill_path = Path(__file__).parent.parent.parent.parent / 'Packaged' / 'auth_users.json'
            if tariffmill_path.exists():
                with open(tariffmill_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('users', {})

            return {}
        except Exception as e:
            logger.warning(f"Failed to load auth users: {e}")
            return {}

    def _save_auth_users(self, users: dict) -> bool:
        """Save users to local auth_users.json file and sync to GitHub."""
        try:
            data = {
                "_comment": "Shared User Authentication Configuration - TariffMill & OCRMill",
                "_instructions": "To add users: Use the Administration panel in either application",
                "users": users
            }

            # Save to local file first
            local_auth_path = Path(__file__).parent.parent.parent / 'auth_users.json'
            with open(local_auth_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

            # Also save to TariffMill_Config repo if it exists
            config_path = Path.home() / 'TariffMill_Config' / 'auth_users.json'
            if config_path.parent.exists():
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)

                # Git commit and push
                self._sync_auth_to_github(config_path)

            return True
        except Exception as e:
            logger.error(f"Failed to save auth users: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save users: {e}")
            return False

    def _sync_auth_to_github(self, config_path: Path):
        """Sync auth_users.json to GitHub repositories."""
        def push_to_repo(repo_dir: Path, repo_name: str):
            """Push auth_users.json to a git repository."""
            try:
                subprocess.run(['git', 'add', 'auth_users.json'], cwd=repo_dir, check=True, capture_output=True)
                subprocess.run(['git', 'commit', '-m', 'Update user credentials from OCRMill'], cwd=repo_dir, check=True, capture_output=True)
                subprocess.run(['git', 'push'], cwd=repo_dir, check=True, capture_output=True)
                logger.info(f"Successfully synced auth_users.json to {repo_name}")
            except subprocess.CalledProcessError as e:
                # Commit might fail if no changes - that's OK
                if e.stderr and b'nothing to commit' not in e.stderr:
                    logger.warning(f"Failed to sync to {repo_name}: {e.stderr.decode() if e.stderr else e}")
            except Exception as e:
                logger.warning(f"Failed to sync to {repo_name}: {e}")

        # Sync to TariffMill_Config repo
        push_to_repo(config_path.parent, "TariffMill_Config")

    def _generate_password_hash(self, password: str) -> Tuple[str, str]:
        """Generate a salted SHA-256 hash for a password."""
        salt = secrets.token_hex(16)
        salted = f"{salt}{password}".encode('utf-8')
        password_hash = hashlib.sha256(salted).hexdigest()
        return password_hash, salt

    def _add_user_dialog(self):
        """Show dialog to add a new user."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add User")
        dialog.setFixedSize(450, 380)

        # Apply stylesheet for proper text visibility
        dialog.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        # User type selection
        user_type_combo = QComboBox()
        user_type_combo.addItems(["Email/Password User", "Windows Domain User"])
        form.addRow("User Type:", user_type_combo)

        # Email/Username input
        email_input = QLineEdit()
        email_input.setPlaceholderText("user@example.com")
        email_label = QLabel("Email:")
        form.addRow(email_label, email_input)

        # Windows domain input
        domain_input = QLineEdit()
        # Get first configured domain as default
        configured_domains = self.config.allowed_domains if self.config else []
        first_domain = configured_domains[0] if configured_domains else ''
        domain_input.setPlaceholderText("MYDOMAIN")
        domain_input.setText(first_domain)
        domain_label = QLabel("Domain:")
        domain_input.setVisible(False)
        domain_label.setVisible(False)
        form.addRow(domain_label, domain_input)

        name_input = QLineEdit()
        name_input.setPlaceholderText("Display Name")
        form.addRow("Name:", name_input)

        role_combo = QComboBox()
        role_combo.addItems(["user", "division_admin", "admin"])
        form.addRow("Role:", role_combo)

        # Divisions selector for division_admin role
        divisions_label = QLabel("Managed Divisions:")
        divisions_list = QListWidget()
        divisions_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        divisions_list.setMaximumHeight(80)
        divisions = self._get_divisions()
        for div_id, name, prefix, length in divisions:
            item = QListWidgetItem(f"{name} ({prefix}*)")
            item.setData(Qt.ItemDataRole.UserRole, div_id)
            divisions_list.addItem(item)
        divisions_label.setVisible(False)
        divisions_list.setVisible(False)
        form.addRow(divisions_label, divisions_list)

        # Show/hide divisions based on role
        def on_role_changed(role_text):
            is_div_admin = role_text == "division_admin"
            divisions_label.setVisible(is_div_admin)
            divisions_list.setVisible(is_div_admin)

        role_combo.currentTextChanged.connect(on_role_changed)

        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input.setPlaceholderText("Password")
        password_label = QLabel("Password:")
        form.addRow(password_label, password_input)

        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_input.setPlaceholderText("Confirm Password")
        confirm_label = QLabel("Confirm:")
        form.addRow(confirm_label, confirm_input)

        # Toggle fields based on user type
        def on_user_type_changed(index):
            is_windows = index == 1
            domain_input.setVisible(is_windows)
            domain_label.setVisible(is_windows)
            password_input.setVisible(not is_windows)
            password_label.setVisible(not is_windows)
            confirm_input.setVisible(not is_windows)
            confirm_label.setVisible(not is_windows)
            if is_windows:
                email_label.setText("Username:")
                email_input.setPlaceholderText("username (without domain)")
            else:
                email_label.setText("Email:")
                email_input.setPlaceholderText("user@example.com")

        user_type_combo.currentIndexChanged.connect(on_user_type_changed)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Add User")
        btn_save.setStyleSheet(self._get_button_style("primary"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        def save_user():
            is_windows_user = user_type_combo.currentIndex() == 1

            if is_windows_user:
                domain = domain_input.text().strip().upper()
                username = email_input.text().strip().lower()
                if not domain or not username:
                    QMessageBox.warning(dialog, "Validation Error", "Domain and username are required.")
                    return
                user_key = f"{domain}\\{username}"
            else:
                email = email_input.text().strip().lower()
                if not email or '@' not in email:
                    QMessageBox.warning(dialog, "Validation Error", "Valid email is required.")
                    return
                password = password_input.text()
                confirm = confirm_input.text()
                if not password or password != confirm:
                    QMessageBox.warning(dialog, "Validation Error", "Passwords must match.")
                    return
                if len(password) < 6:
                    QMessageBox.warning(dialog, "Validation Error", "Password must be at least 6 characters.")
                    return
                user_key = email

            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(dialog, "Validation Error", "Name is required.")
                return

            role = role_combo.currentText()

            # Get managed divisions for division_admin
            managed_divisions = []
            if role == "division_admin":
                for item in divisions_list.selectedItems():
                    managed_divisions.append(item.data(Qt.ItemDataRole.UserRole))

            # Load existing users
            users = self._load_auth_users()

            if user_key in users:
                QMessageBox.warning(dialog, "User Exists", f"User '{user_key}' already exists.")
                return

            # Create user data
            user_data = {
                "name": name,
                "role": role,
                "suspended": False
            }

            if is_windows_user:
                user_data["auth_type"] = "windows"
            else:
                password_hash, salt = self._generate_password_hash(password)
                user_data["password_hash"] = password_hash
                user_data["salt"] = salt

            if managed_divisions:
                user_data["managed_divisions"] = managed_divisions

            users[user_key] = user_data

            if self._save_auth_users(users):
                QMessageBox.information(dialog, "Success", f"User '{name}' added successfully.")
                dialog.accept()
                self._refresh_user_list()

        btn_save.clicked.connect(save_user)
        dialog.exec()

    def _edit_user_dialog(self, email: str):
        """Show dialog to edit a user."""
        users = self._load_auth_users()
        if email not in users:
            QMessageBox.warning(self, "Error", f"User '{email}' not found.")
            return

        user_data = users[email]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit User: {email}")
        dialog.setFixedSize(400, 280)

        # Apply stylesheet for proper text visibility
        dialog.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        # Email (read-only)
        email_label = QLabel(email)
        email_label.setStyleSheet("color: #666;")
        form.addRow("Email:", email_label)

        name_input = QLineEdit()
        name_input.setText(user_data.get('name', ''))
        form.addRow("Name:", name_input)

        role_combo = QComboBox()
        role_combo.addItems(["user", "division_admin", "admin"])
        current_role = user_data.get('role', 'user')
        role_combo.setCurrentText(current_role)
        form.addRow("Role:", role_combo)

        # Divisions selector
        divisions_label = QLabel("Managed Divisions:")
        divisions_list = QListWidget()
        divisions_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        divisions_list.setMaximumHeight(80)
        divisions = self._get_divisions()
        current_divisions = user_data.get('managed_divisions', [])
        for div_id, name, prefix, length in divisions:
            item = QListWidgetItem(f"{name} ({prefix}*)")
            item.setData(Qt.ItemDataRole.UserRole, div_id)
            if div_id in current_divisions:
                item.setSelected(True)
            divisions_list.addItem(item)

        is_div_admin = current_role == "division_admin"
        divisions_label.setVisible(is_div_admin)
        divisions_list.setVisible(is_div_admin)
        form.addRow(divisions_label, divisions_list)

        def on_role_changed(role_text):
            is_div_admin = role_text == "division_admin"
            divisions_label.setVisible(is_div_admin)
            divisions_list.setVisible(is_div_admin)

        role_combo.currentTextChanged.connect(on_role_changed)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet(self._get_button_style("primary"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        def save_changes():
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(dialog, "Validation Error", "Name is required.")
                return

            role = role_combo.currentText()

            managed_divisions = []
            if role == "division_admin":
                for item in divisions_list.selectedItems():
                    managed_divisions.append(item.data(Qt.ItemDataRole.UserRole))

            users[email]["name"] = name
            users[email]["role"] = role
            if managed_divisions:
                users[email]["managed_divisions"] = managed_divisions
            elif "managed_divisions" in users[email]:
                del users[email]["managed_divisions"]

            if self._save_auth_users(users):
                QMessageBox.information(dialog, "Success", "User updated successfully.")
                dialog.accept()
                self._refresh_user_list()

        btn_save.clicked.connect(save_changes)
        dialog.exec()

    def _reset_user_password(self, email: str):
        """Reset a user's password."""
        users = self._load_auth_users()
        if email not in users:
            return

        user_data = users[email]
        if '\\' in email or user_data.get('auth_type') == 'windows':
            QMessageBox.information(self, "Not Applicable", "Windows users don't have passwords to reset.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Reset Password: {email}")
        dialog.setFixedSize(350, 180)

        # Apply stylesheet for proper text visibility
        dialog.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        password_input = QLineEdit()
        password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_input.setPlaceholderText("New Password")
        form.addRow("New Password:", password_input)

        confirm_input = QLineEdit()
        confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_input.setPlaceholderText("Confirm Password")
        form.addRow("Confirm:", confirm_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Reset Password")
        btn_save.setStyleSheet(self._get_button_style("primary"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        def save_password():
            password = password_input.text()
            confirm = confirm_input.text()
            if not password or password != confirm:
                QMessageBox.warning(dialog, "Error", "Passwords must match.")
                return
            if len(password) < 6:
                QMessageBox.warning(dialog, "Error", "Password must be at least 6 characters.")
                return

            password_hash, salt = self._generate_password_hash(password)
            users[email]["password_hash"] = password_hash
            users[email]["salt"] = salt

            if self._save_auth_users(users):
                QMessageBox.information(dialog, "Success", "Password reset successfully.")
                dialog.accept()

        btn_save.clicked.connect(save_password)
        dialog.exec()

    def _toggle_user_suspended(self, email: str):
        """Toggle user suspended status."""
        users = self._load_auth_users()
        if email not in users:
            return

        is_suspended = users[email].get('suspended', False)
        action = "reactivate" if is_suspended else "suspend"

        reply = QMessageBox.question(
            self, f"Confirm {action.title()}",
            f"Are you sure you want to {action} user '{email}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            users[email]['suspended'] = not is_suspended
            if self._save_auth_users(users):
                self._refresh_user_list()

    def _delete_user(self, email: str):
        """Delete a user."""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete user '{email}'?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            users = self._load_auth_users()
            if email in users:
                del users[email]
                if self._save_auth_users(users):
                    self._refresh_user_list()

    # =========================================================================
    # DIVISION MANAGEMENT
    # =========================================================================

    def _get_divisions(self) -> List[Tuple]:
        """Get all divisions from the database."""
        try:
            if self.db:
                import sqlite3
                conn = sqlite3.connect(str(self.config.database_path))
                c = conn.cursor()
                c.execute("""SELECT id, division_name, prefix, total_length
                            FROM file_number_divisions
                            WHERE is_active = 1
                            ORDER BY division_name""")
                result = c.fetchall()
                conn.close()
                return result
        except Exception as e:
            logger.warning(f"Failed to get divisions: {e}")
        return []

    def _refresh_divisions_list(self):
        """Refresh the divisions table."""
        self.divisions_table.setRowCount(0)

        try:
            if not self.db:
                return

            import sqlite3
            conn = sqlite3.connect(str(self.config.database_path))
            c = conn.cursor()
            c.execute("""SELECT id, division_name, prefix, total_length, description, is_active
                        FROM file_number_divisions
                        ORDER BY division_name""")
            divisions = c.fetchall()
            conn.close()

            self.divisions_table.setRowCount(len(divisions))
            for row_idx, (div_id, name, prefix, length, desc, active) in enumerate(divisions):
                self.divisions_table.setItem(row_idx, 0, QTableWidgetItem(str(name or '')))
                self.divisions_table.setItem(row_idx, 1, QTableWidgetItem(str(prefix or '')))
                self.divisions_table.setItem(row_idx, 2, QTableWidgetItem(str(length or '')))
                self.divisions_table.setItem(row_idx, 3, QTableWidgetItem(str(desc or '')))
                self.divisions_table.setItem(row_idx, 4, QTableWidgetItem("Yes" if active else "No"))

                # Store ID in first item
                self.divisions_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, div_id)
        except Exception as e:
            logger.warning(f"Failed to load divisions: {e}")

    def _add_division_dialog(self):
        """Show dialog to add a new division."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Division")
        dialog.setFixedSize(400, 220)

        # Apply stylesheet for proper text visibility
        dialog.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., CHP Houston")
        form.addRow("Division Name:", name_input)

        prefix_input = QLineEdit()
        prefix_input.setPlaceholderText("e.g., 76")
        form.addRow("Prefix:", prefix_input)

        length_spin = QSpinBox()
        length_spin.setRange(1, 20)
        length_spin.setValue(7)
        form.addRow("Total Length:", length_spin)

        desc_input = QLineEdit()
        desc_input.setPlaceholderText("Optional description")
        form.addRow("Description:", desc_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Add Division")
        btn_save.setStyleSheet(self._get_button_style("primary"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        def save_division():
            name = name_input.text().strip()
            prefix = prefix_input.text().strip()
            length = length_spin.value()
            desc = desc_input.text().strip()

            if not name or not prefix:
                QMessageBox.warning(dialog, "Validation Error", "Name and prefix are required.")
                return

            try:
                import sqlite3
                conn = sqlite3.connect(str(self.config.database_path))
                c = conn.cursor()
                c.execute("""INSERT INTO file_number_divisions
                            (division_name, prefix, total_length, description, is_active, created_date)
                            VALUES (?, ?, ?, ?, 1, ?)""",
                         (name, prefix, length, desc, datetime.now().isoformat()))
                conn.commit()
                conn.close()

                QMessageBox.information(dialog, "Success", f"Division '{name}' added successfully.")
                dialog.accept()
                self._refresh_divisions_list()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to add division: {e}")

        btn_save.clicked.connect(save_division)
        dialog.exec()

    def _edit_division_dialog(self):
        """Edit selected division."""
        selected = self.divisions_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a division to edit.")
            return

        row = selected[0].row()
        div_id = self.divisions_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        # Get current values
        name = self.divisions_table.item(row, 0).text()
        prefix = self.divisions_table.item(row, 1).text()
        length = int(self.divisions_table.item(row, 2).text() or 7)
        desc = self.divisions_table.item(row, 3).text()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Division: {name}")
        dialog.setFixedSize(400, 220)

        # Apply stylesheet for proper text visibility
        dialog.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name_input = QLineEdit()
        name_input.setText(name)
        form.addRow("Division Name:", name_input)

        prefix_input = QLineEdit()
        prefix_input.setText(prefix)
        form.addRow("Prefix:", prefix_input)

        length_spin = QSpinBox()
        length_spin.setRange(1, 20)
        length_spin.setValue(length)
        form.addRow("Total Length:", length_spin)

        desc_input = QLineEdit()
        desc_input.setText(desc)
        form.addRow("Description:", desc_input)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet(self._get_button_style("primary"))
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

        def save_changes():
            new_name = name_input.text().strip()
            new_prefix = prefix_input.text().strip()
            new_length = length_spin.value()
            new_desc = desc_input.text().strip()

            if not new_name or not new_prefix:
                QMessageBox.warning(dialog, "Validation Error", "Name and prefix are required.")
                return

            try:
                import sqlite3
                conn = sqlite3.connect(str(self.config.database_path))
                c = conn.cursor()
                c.execute("""UPDATE file_number_divisions
                            SET division_name=?, prefix=?, total_length=?, description=?
                            WHERE id=?""",
                         (new_name, new_prefix, new_length, new_desc, div_id))
                conn.commit()
                conn.close()

                QMessageBox.information(dialog, "Success", "Division updated successfully.")
                dialog.accept()
                self._refresh_divisions_list()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Failed to update division: {e}")

        btn_save.clicked.connect(save_changes)
        dialog.exec()

    def _delete_division(self):
        """Delete selected division."""
        selected = self.divisions_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a division to delete.")
            return

        row = selected[0].row()
        div_id = self.divisions_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name = self.divisions_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete division '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                import sqlite3
                conn = sqlite3.connect(str(self.config.database_path))
                c = conn.cursor()
                c.execute("DELETE FROM file_number_divisions WHERE id=?", (div_id,))
                conn.commit()
                conn.close()
                self._refresh_divisions_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete division: {e}")

    # =========================================================================
    # BILLING SETTINGS
    # =========================================================================

    def _get_billing_setting(self, key: str, default: str = '') -> str:
        """Get a billing setting from the database."""
        try:
            if self.db:
                return self.db.get_app_config(f'billing_{key}') or default
        except:
            pass
        return default

    def _set_billing_setting(self, key: str, value: str):
        """Set a billing setting in the database."""
        try:
            if self.db:
                self.db.set_app_config(f'billing_{key}', value)
        except Exception as e:
            logger.warning(f"Failed to set billing setting {key}: {e}")

    def _save_billing_settings(self):
        """Save all billing settings."""
        self._set_billing_setting('rate_per_file', str(self.billing_rate_spin.value()))
        self._set_billing_setting('customer_email', self.billing_customer_email.text().strip())
        self._set_billing_setting('admin_email', self.billing_admin_email.text().strip())
        self._set_billing_setting('smtp_server', self.billing_smtp_server.text().strip())
        self._set_billing_setting('smtp_port', str(self.billing_smtp_port.value()))
        self._set_billing_setting('smtp_user', self.billing_smtp_user.text().strip())
        self._set_billing_setting('smtp_password', self.billing_smtp_password.text())

        QMessageBox.information(self, "Saved", "Billing settings saved successfully.")

    def _test_billing_email(self):
        """Test email configuration by sending a test email."""
        smtp_server = self.billing_smtp_server.text().strip()
        smtp_port = self.billing_smtp_port.value()
        smtp_user = self.billing_smtp_user.text().strip()
        smtp_password = self.billing_smtp_password.text()
        to_email = self.billing_admin_email.text().strip()

        if not all([smtp_server, smtp_user, smtp_password, to_email]):
            QMessageBox.warning(self, "Missing Settings",
                "Please fill in all SMTP settings and admin email to test.")
            return

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = to_email
            msg['Subject'] = "OCRMill Billing - Test Email"

            body = ("This is a test email from OCRMill billing system.\n\n"
                    "If you received this, your email configuration is working correctly.")
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()

            QMessageBox.information(self, "Success",
                f"Test email sent successfully to {to_email}!")

        except Exception as e:
            QMessageBox.critical(self, "Email Failed",
                f"Failed to send test email:\n{str(e)}")

    def _show_billing_report(self):
        """Show billing report dialog."""
        QMessageBox.information(self, "Billing Report", "Billing report functionality coming soon.")

    # =========================================================================
    # AUDIT LOG TAB
    # =========================================================================

    def _setup_audit_tab(self, tab_widget):
        """Setup the Audit Log tab."""
        layout = QVBoxLayout(tab_widget)

        header = QLabel("<h3>Processing Audit Log</h3>")
        layout.addWidget(header)

        info = QLabel("View all PDF processing attempts, including successful extractions and failures.")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))

        self.audit_event_filter = QComboBox()
        self.audit_event_filter.addItem("All Events", "")
        self.audit_event_filter.addItem("Successful", "SUCCESS")
        self.audit_event_filter.addItem("Failed", "FAILED")
        self.audit_event_filter.addItem("Partial", "PARTIAL")
        filter_layout.addWidget(self.audit_event_filter)

        filter_layout.addWidget(QLabel("Days:"))
        self.audit_days_spin = QSpinBox()
        self.audit_days_spin.setRange(1, 365)
        self.audit_days_spin.setValue(30)
        filter_layout.addWidget(self.audit_days_spin)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_audit_log)
        filter_layout.addWidget(refresh_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Stats row
        stats_layout = QHBoxLayout()
        self.audit_total_label = QLabel("Total: 0")
        self.audit_total_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.audit_total_label)
        self.audit_success_label = QLabel("Successful: 0")
        self.audit_success_label.setStyleSheet("color: green;")
        stats_layout.addWidget(self.audit_success_label)
        self.audit_failed_label = QLabel("Failed: 0")
        self.audit_failed_label.setStyleSheet("color: red;")
        stats_layout.addWidget(self.audit_failed_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Audit table
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(7)
        self.audit_table.setHorizontalHeaderLabels([
            "Date", "Time", "Status", "File Name", "Template", "Items", "User"
        ])
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.audit_table.setAlternatingRowColors(True)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.audit_table)

        self.audit_event_filter.currentIndexChanged.connect(self._refresh_audit_log)
        self.audit_days_spin.valueChanged.connect(self._refresh_audit_log)

        QTimer.singleShot(200, self._refresh_audit_log)

    def _refresh_audit_log(self):
        """Refresh the audit log table."""
        try:
            import sqlite3

            conn = sqlite3.connect(str(self.config.database_path))
            c = conn.cursor()
            days = self.audit_days_spin.value()
            event_type = self.audit_event_filter.currentData()

            query = """SELECT process_date, file_name, template_used, items_extracted,
                              status, user_name
                       FROM processing_history
                       WHERE process_date >= date('now', ?)"""
            params = [f'-{days} days']
            if event_type:
                query += " AND status = ?"
                params.append(event_type)
            query += " ORDER BY process_date DESC, id DESC LIMIT 500"

            c.execute(query, params)
            records = c.fetchall()

            # Get stats
            c.execute("""SELECT COUNT(*),
                        SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END)
                        FROM processing_history WHERE process_date >= date('now', ?)""",
                     [f'-{days} days'])
            stats = c.fetchone()
            conn.close()

            self.audit_total_label.setText(f"Total: {stats[0] or 0}")
            self.audit_success_label.setText(f"Successful: {stats[1] or 0}")
            self.audit_failed_label.setText(f"Failed: {stats[2] or 0}")

            self.audit_table.setRowCount(len(records))
            for row_idx, record in enumerate(records):
                process_date, fname, template, items, status, user = record
                date_str = str(process_date or '')[:10]
                time_str = str(process_date or '')[11:19] if len(str(process_date or '')) > 10 else ''

                self.audit_table.setItem(row_idx, 0, QTableWidgetItem(date_str))
                self.audit_table.setItem(row_idx, 1, QTableWidgetItem(time_str))

                status_item = QTableWidgetItem(str(status or ''))
                if status == 'SUCCESS':
                    status_item.setForeground(QColor('green'))
                elif status == 'FAILED':
                    status_item.setForeground(QColor('red'))
                else:
                    status_item.setForeground(QColor('orange'))
                self.audit_table.setItem(row_idx, 2, status_item)

                self.audit_table.setItem(row_idx, 3, QTableWidgetItem(str(fname or '')[:50]))
                self.audit_table.setItem(row_idx, 4, QTableWidgetItem(str(template or '')))
                self.audit_table.setItem(row_idx, 5, QTableWidgetItem(str(items or 0)))
                self.audit_table.setItem(row_idx, 6, QTableWidgetItem(str(user or '')))
        except Exception as e:
            logger.error(f"Failed to load audit log: {e}")
            self.audit_table.setRowCount(1)
            self.audit_table.setItem(0, 0, QTableWidgetItem("No audit data available"))
            self.audit_table.setSpan(0, 0, 1, 7)

    # =========================================================================
    # SYSTEM INFO TAB
    # =========================================================================

    def _setup_system_tab(self, tab_widget):
        """Setup the System Info tab."""
        layout = QVBoxLayout(tab_widget)

        header = QLabel("<h3>System Information</h3>")
        layout.addWidget(header)

        # Import VERSION
        try:
            from ocrmill_app import VERSION
        except:
            VERSION = "Unknown"

        info_text = f"""
        <table style="font-size: 12px;">
        <tr><td><b>Application:</b></td><td>OCRMill {VERSION}</td></tr>
        <tr><td><b>User:</b></td><td>{getpass.getuser()}</td></tr>
        <tr><td><b>Machine:</b></td><td>{platform.node()}</td></tr>
        <tr><td><b>Platform:</b></td><td>{platform.system()} {platform.release()}</td></tr>
        <tr><td><b>Python:</b></td><td>{platform.python_version()}</td></tr>
        <tr><td><b>Database:</b></td><td>{self.config.database_path if self.config else 'N/A'}</td></tr>
        <tr><td><b>Input Dir:</b></td><td>{self.config.input_folder if self.config else 'N/A'}</td></tr>
        <tr><td><b>Output Dir:</b></td><td>{self.config.output_folder if self.config else 'N/A'}</td></tr>
        </table>
        """
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        layout.addWidget(QLabel("<h4>Database Statistics</h4>"))

        try:
            if self.db:
                stats = self.db.get_statistics()
                parts_count = stats.get('total_parts', 0)

                import sqlite3
                conn = sqlite3.connect(str(self.config.database_path))
                c = conn.cursor()

                try:
                    c.execute("SELECT COUNT(*) FROM processing_history")
                    processing_count = c.fetchone()[0]
                except:
                    processing_count = 0

                conn.close()

                stats_text = f"""
                <table style="font-size: 12px;">
                <tr><td><b>Total Parts:</b></td><td>{parts_count:,}</td></tr>
                <tr><td><b>Processing Records:</b></td><td>{processing_count:,}</td></tr>
                </table>
                """
                stats_label = QLabel(stats_text)
                stats_label.setTextFormat(Qt.TextFormat.RichText)
                layout.addWidget(stats_label)
        except Exception as e:
            layout.addWidget(QLabel(f"Error loading stats: {e}"))

        layout.addStretch()

    # =========================================================================
    # USER STATISTICS TAB
    # =========================================================================

    def _setup_stats_tab(self, tab_widget):
        """Setup the User Statistics tab."""
        layout = QVBoxLayout(tab_widget)

        header = QLabel("<h3>User Statistics</h3>")
        layout.addWidget(header)

        info = QLabel("Processing statistics by user for the selected time period.")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Period:"))

        self.stats_period = QComboBox()
        self.stats_period.addItem("Last 7 days", 7)
        self.stats_period.addItem("Last 30 days", 30)
        self.stats_period.addItem("Last 90 days", 90)
        self.stats_period.addItem("Last year", 365)
        self.stats_period.setCurrentIndex(1)
        filter_layout.addWidget(self.stats_period)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_user_stats)
        filter_layout.addWidget(refresh_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Stats table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(5)
        self.stats_table.setHorizontalHeaderLabels([
            "User", "Files Processed", "Items Extracted", "Success Rate", "Last Activity"
        ])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.stats_table)

        self.stats_period.currentIndexChanged.connect(self._refresh_user_stats)
        QTimer.singleShot(300, self._refresh_user_stats)

    def _refresh_user_stats(self):
        """Refresh user statistics."""
        try:
            import sqlite3

            days = self.stats_period.currentData()

            conn = sqlite3.connect(str(self.config.database_path))
            c = conn.cursor()

            c.execute("""SELECT user_name,
                               COUNT(*) as total,
                               SUM(items_extracted) as items,
                               SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) as success,
                               MAX(process_date) as last_activity
                        FROM processing_history
                        WHERE process_date >= date('now', ?)
                        AND user_name IS NOT NULL AND user_name != ''
                        GROUP BY user_name
                        ORDER BY total DESC""",
                     [f'-{days} days'])
            records = c.fetchall()
            conn.close()

            self.stats_table.setRowCount(len(records))
            for row_idx, (user, total, items, success, last_activity) in enumerate(records):
                self.stats_table.setItem(row_idx, 0, QTableWidgetItem(str(user or '')))
                self.stats_table.setItem(row_idx, 1, QTableWidgetItem(str(total or 0)))
                self.stats_table.setItem(row_idx, 2, QTableWidgetItem(str(items or 0)))

                success_rate = (success / total * 100) if total else 0
                rate_item = QTableWidgetItem(f"{success_rate:.1f}%")
                if success_rate >= 90:
                    rate_item.setForeground(QColor('green'))
                elif success_rate >= 70:
                    rate_item.setForeground(QColor('orange'))
                else:
                    rate_item.setForeground(QColor('red'))
                self.stats_table.setItem(row_idx, 3, rate_item)

                self.stats_table.setItem(row_idx, 4, QTableWidgetItem(str(last_activity or '')[:10]))
        except Exception as e:
            logger.error(f"Failed to load user stats: {e}")
            self.stats_table.setRowCount(1)
            self.stats_table.setItem(0, 0, QTableWidgetItem("No statistics available"))
            self.stats_table.setSpan(0, 0, 1, 5)

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _get_button_style(self, style_type: str = "primary") -> str:
        """Get button stylesheet."""
        if style_type == "primary":
            return """
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1f6dad;
                }
            """
        elif style_type == "success":
            return """
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #219a52;
                }
                QPushButton:pressed {
                    background-color: #1a8044;
                }
            """
        elif style_type == "danger":
            return """
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """
        return ""

    def _get_action_button_style(self, style_type: str = "primary") -> str:
        """Get stylesheet for small action buttons in tables."""
        colors = {
            "primary": ("#3498db", "#2980b9"),
            "success": ("#27ae60", "#219a52"),
            "warning": ("#f39c12", "#e67e22"),
            "danger": ("#e74c3c", "#c0392b"),
            "secondary": ("#95a5a6", "#7f8c8d"),
        }
        bg, hover = colors.get(style_type, colors["primary"])
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                padding: 2px 4px;
                border-radius: 3px;
                font-size: 8pt;
                font-weight: bold;
                min-width: 40px;
                max-width: 45px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {hover};
            }}
        """

    def _get_dialog_style(self) -> str:
        """Get stylesheet for dialog forms to ensure proper text visibility."""
        return """
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QLineEdit {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QListWidget {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QSpinBox {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 5px;
            }
        """
