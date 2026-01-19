"""
Billing Dialog for OCRMill.

Displays billing records and provides export functionality.
"""

import sys
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QFileDialog, QMessageBox, QTabWidget,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase
from billing.billing_manager import BillingManager
from billing.billing_sync import BillingSyncManager
from core.theme_manager import get_theme_manager


class BillingDialog(QDialog):
    """Dialog for viewing billing records and statistics."""

    def __init__(self, db: PartsDatabase, parent=None, is_admin: bool = False):
        super().__init__(parent)
        self.db = db
        self.billing_manager = BillingManager(db)
        self.sync_manager = BillingSyncManager(db)
        self.is_admin = is_admin
        self.theme_manager = get_theme_manager()

        self.setWindowTitle("OCRMill - Billing Records")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._setup_ui()
        self._apply_styling()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Tabs
        tabs = QTabWidget()

        # Summary Tab
        summary_tab = self._create_summary_tab()
        tabs.addTab(summary_tab, "Summary")

        # Records Tab
        records_tab = self._create_records_tab()
        tabs.addTab(records_tab, "Records")

        # Sync Tab (admin only)
        if self.is_admin:
            sync_tab = self._create_sync_tab()
            tabs.addTab(sync_tab, "GitHub Sync")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _create_summary_tab(self) -> QWidget:
        """Create the summary tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Current Month Summary
        month_group = QGroupBox("Current Month")
        month_layout = QFormLayout(month_group)

        now = datetime.now()
        self.month_label = QLabel(f"{now.strftime('%B %Y')}")
        self.month_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        month_layout.addRow("Period:", self.month_label)

        self.files_label = QLabel("-")
        month_layout.addRow("Files Processed:", self.files_label)

        self.lines_label = QLabel("-")
        month_layout.addRow("Total Lines:", self.lines_label)

        self.value_label = QLabel("-")
        month_layout.addRow("Total Value:", self.value_label)

        self.users_label = QLabel("-")
        month_layout.addRow("Unique Users:", self.users_label)

        layout.addWidget(month_group)

        # All-Time Summary
        alltime_group = QGroupBox("All-Time Totals")
        alltime_layout = QFormLayout(alltime_group)

        self.total_files_label = QLabel("-")
        alltime_layout.addRow("Total Files:", self.total_files_label)

        self.total_lines_label = QLabel("-")
        alltime_layout.addRow("Total Lines:", self.total_lines_label)

        self.total_value_label = QLabel("-")
        alltime_layout.addRow("Total Value:", self.total_value_label)

        self.total_users_label = QLabel("-")
        alltime_layout.addRow("Unique Users:", self.total_users_label)

        self.first_export_label = QLabel("-")
        alltime_layout.addRow("First Export:", self.first_export_label)

        self.last_export_label = QLabel("-")
        alltime_layout.addRow("Last Export:", self.last_export_label)

        layout.addWidget(alltime_group)

        # Uninvoiced Months
        uninvoiced_group = QGroupBox("Uninvoiced Periods")
        uninvoiced_layout = QVBoxLayout(uninvoiced_group)

        self.uninvoiced_label = QLabel("-")
        self.uninvoiced_label.setWordWrap(True)
        uninvoiced_layout.addWidget(self.uninvoiced_label)

        if self.is_admin:
            mark_btn = QPushButton("Mark Selected Month as Invoiced")
            mark_btn.clicked.connect(self._mark_invoiced)
            uninvoiced_layout.addWidget(mark_btn)

        layout.addWidget(uninvoiced_group)

        layout.addStretch()
        return widget

    def _create_records_tab(self) -> QWidget:
        """Create the records tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Filter controls
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        self.month_combo.addItem("All Records", None)
        # Add last 12 months
        now = datetime.now()
        for i in range(12):
            month = now.month - i
            year = now.year
            if month <= 0:
                month += 12
                year -= 1
            month_str = f"{year:04d}-{month:02d}"
            self.month_combo.addItem(f"{datetime(year, month, 1).strftime('%B %Y')}", month_str)
        self.month_combo.currentIndexChanged.connect(self._filter_records)
        filter_layout.addWidget(self.month_combo)

        filter_layout.addStretch()

        export_btn = QPushButton("Export to CSV")
        export_btn.clicked.connect(self._export_csv)
        filter_layout.addWidget(export_btn)

        layout.addLayout(filter_layout)

        # Records table
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(8)
        self.records_table.setHorizontalHeaderLabels([
            "Date", "Time", "File Number", "File Name",
            "Lines", "Value", "User", "Invoiced"
        ])
        self.records_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.records_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.records_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.records_table.setAlternatingRowColors(True)

        layout.addWidget(self.records_table)

        return widget

    def _create_sync_tab(self) -> QWidget:
        """Create the GitHub sync tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Sync Status
        status_group = QGroupBox("Sync Status")
        status_layout = QFormLayout(status_group)

        repo_status = self.sync_manager.get_repo_status()

        self.repo_path_label = QLabel(repo_status.get('path', '-'))
        self.repo_path_label.setWordWrap(True)
        status_layout.addRow("Repository:", self.repo_path_label)

        if repo_status.get('configured'):
            self.repo_status_label = QLabel("Configured")
            self.repo_status_label.setStyleSheet("color: #27ae60;")
        else:
            self.repo_status_label = QLabel("Not Configured")
            self.repo_status_label.setStyleSheet("color: #e74c3c;")
        status_layout.addRow("Status:", self.repo_status_label)

        if repo_status.get('remote'):
            self.remote_label = QLabel(repo_status['remote'])
        else:
            self.remote_label = QLabel("-")
        self.remote_label.setWordWrap(True)
        status_layout.addRow("Remote:", self.remote_label)

        last_sync = self.sync_manager.get_last_sync_time()
        self.last_sync_label = QLabel(last_sync[:19].replace('T', ' ') if last_sync else "Never")
        status_layout.addRow("Last Sync:", self.last_sync_label)

        layout.addWidget(status_group)

        # Sync Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        sync_btn = QPushButton("Sync Billing Data to GitHub")
        sync_btn.clicked.connect(self._sync_to_github)
        actions_layout.addWidget(sync_btn)

        pull_btn = QPushButton("Pull Latest from GitHub")
        pull_btn.clicked.connect(self._pull_from_github)
        actions_layout.addWidget(pull_btn)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setWordWrap(True)
        actions_layout.addWidget(self.sync_status_label)

        layout.addWidget(actions_group)

        layout.addStretch()
        return widget

    def _load_data(self):
        """Load billing data."""
        # Current month summary
        summary = self.billing_manager.get_current_month_summary()
        self.files_label.setText(str(summary['total_files']))
        self.lines_label.setText(f"{summary['total_lines']:,}")
        self.value_label.setText(f"${summary['total_value']:,.2f}")
        self.users_label.setText(str(summary['unique_users']))

        # All-time totals
        totals = self.billing_manager.get_all_time_totals()
        self.total_files_label.setText(f"{totals['total_files']:,}")
        self.total_lines_label.setText(f"{totals['total_lines']:,}")
        self.total_value_label.setText(f"${totals['total_value']:,.2f}")
        self.total_users_label.setText(str(totals['unique_users']))
        self.first_export_label.setText(totals['first_export'] or "-")
        self.last_export_label.setText(totals['last_export'] or "-")

        # Uninvoiced months
        uninvoiced = self.billing_manager.get_uninvoiced_months()
        if uninvoiced:
            self.uninvoiced_label.setText(", ".join(uninvoiced))
        else:
            self.uninvoiced_label.setText("No uninvoiced periods")

        # Load records table
        self._filter_records()

    def _filter_records(self):
        """Filter and reload records table."""
        month = self.month_combo.currentData()
        records = self.billing_manager.get_billing_records(invoice_month=month)

        self.records_table.setRowCount(len(records))

        for row, record in enumerate(records):
            self.records_table.setItem(row, 0,
                QTableWidgetItem(record.get('export_date', '')))
            self.records_table.setItem(row, 1,
                QTableWidgetItem(record.get('export_time', '')))
            self.records_table.setItem(row, 2,
                QTableWidgetItem(record.get('file_number', '')))
            self.records_table.setItem(row, 3,
                QTableWidgetItem(record.get('file_name', '')))
            self.records_table.setItem(row, 4,
                QTableWidgetItem(str(record.get('line_count', 0))))
            self.records_table.setItem(row, 5,
                QTableWidgetItem(f"${record.get('total_value', 0):,.2f}"))
            self.records_table.setItem(row, 6,
                QTableWidgetItem(record.get('user_name', '')))
            self.records_table.setItem(row, 7,
                QTableWidgetItem("Yes" if record.get('invoice_sent') else "No"))

    def _export_csv(self):
        """Export records to CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Billing Records",
            f"billing_records_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            month = self.month_combo.currentData()
            if month:
                # Get date range for the month
                year, mon = month.split('-')
                start_date = f"{year}-{mon}-01"
                if int(mon) == 12:
                    end_date = f"{int(year)+1}-01-01"
                else:
                    end_date = f"{year}-{int(mon)+1:02d}-01"
                count = self.billing_manager.export_to_csv(
                    Path(file_path), start_date=start_date, end_date=end_date
                )
            else:
                count = self.billing_manager.export_to_csv(Path(file_path))

            QMessageBox.information(
                self, "Export Complete",
                f"Exported {count} records to:\n{file_path}"
            )

    def _mark_invoiced(self):
        """Mark a month as invoiced."""
        uninvoiced = self.billing_manager.get_uninvoiced_months()
        if not uninvoiced:
            QMessageBox.information(
                self, "No Uninvoiced Periods",
                "There are no uninvoiced periods to mark."
            )
            return

        # For simplicity, mark the oldest uninvoiced month
        month = uninvoiced[0]
        reply = QMessageBox.question(
            self, "Mark as Invoiced",
            f"Mark all records for {month} as invoiced?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            year, mon = month.split('-')
            count = self.billing_manager.mark_invoiced(int(year), int(mon))
            QMessageBox.information(
                self, "Marked as Invoiced",
                f"Marked {count} records for {month} as invoiced."
            )
            self._load_data()

    def _sync_to_github(self):
        """Sync billing data to GitHub."""
        self.sync_status_label.setText("Syncing...")
        self.sync_status_label.setStyleSheet("color: #3498db;")

        success, message = self.sync_manager.sync_to_github()

        if success:
            self.sync_status_label.setText(message)
            self.sync_status_label.setStyleSheet("color: #27ae60;")
            self.sync_manager.update_last_sync_time()
            self.last_sync_label.setText(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            self.sync_status_label.setText(message)
            self.sync_status_label.setStyleSheet("color: #e74c3c;")

    def _pull_from_github(self):
        """Pull latest from GitHub."""
        self.sync_status_label.setText("Pulling...")
        self.sync_status_label.setStyleSheet("color: #3498db;")

        success, message = self.sync_manager.pull_latest()

        if success:
            self.sync_status_label.setText(message)
            self.sync_status_label.setStyleSheet("color: #27ae60;")
        else:
            self.sync_status_label.setText(message)
            self.sync_status_label.setStyleSheet("color: #e74c3c;")

    def _apply_styling(self):
        """Apply theme-aware styling."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2d2d2d;
                }
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #2d2d2d;
                }
                QTabBar::tab {
                    background-color: #252526;
                    color: #cccccc;
                    padding: 10px 20px;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #094771;
                    color: white;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #2a2d2e;
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
                QComboBox {
                    padding: 6px;
                    border: 1px solid #3c3c3c;
                    border-radius: 3px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                }
                QTableWidget {
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    alternate-background-color: #2d2d2d;
                }
                QTableWidget::item:selected {
                    background-color: #094771;
                }
                QHeaderView::section {
                    background-color: #2d2d2d;
                    color: #cccccc;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #3c3c3c;
                    border-bottom: 1px solid #3c3c3c;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f5f5f5;
                }
                QTabWidget::pane {
                    border: 1px solid #d0d0d0;
                    background-color: white;
                }
                QTabBar::tab {
                    background-color: #f0f0f0;
                    color: #333333;
                    padding: 10px 20px;
                    border: 1px solid #d0d0d0;
                    border-bottom: none;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #5f9ea0;
                    color: white;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #e0e8e8;
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
                QComboBox {
                    padding: 6px;
                    border: 1px solid #d0d0d0;
                    border-radius: 3px;
                    background-color: white;
                }
                QTableWidget {
                    background-color: white;
                    border: 1px solid #d0d0d0;
                    alternate-background-color: #f8f9fa;
                }
                QTableWidget::item:selected {
                    background-color: #5f9ea0;
                    color: white;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    color: #333;
                    padding: 8px;
                    border: none;
                    border-right: 1px solid #d0d0d0;
                    border-bottom: 1px solid #d0d0d0;
                }
            """)
