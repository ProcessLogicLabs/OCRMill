"""
Statistics Dialog for OCRMill.

Displays usage statistics and processing metrics.
"""

import sys
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QTabWidget, QWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from parts_database import PartsDatabase
from statistics.stats_tracker import StatisticsTracker, EventTypes


class StatisticsDialog(QDialog):
    """Dialog for viewing usage statistics."""

    def __init__(self, db: PartsDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.stats_tracker = StatisticsTracker(db)

        self.setWindowTitle("OCRMill - Statistics")
        self.setMinimumSize(700, 550)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Period selector
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Time Period:"))

        self.period_combo = QComboBox()
        self.period_combo.addItem("Last 7 Days", 7)
        self.period_combo.addItem("Last 30 Days", 30)
        self.period_combo.addItem("Last 90 Days", 90)
        self.period_combo.addItem("Last Year", 365)
        self.period_combo.setCurrentIndex(1)  # Default to 30 days
        self.period_combo.currentIndexChanged.connect(self._load_data)
        period_layout.addWidget(self.period_combo)

        period_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_data)
        period_layout.addWidget(refresh_btn)

        layout.addLayout(period_layout)

        # Tabs
        tabs = QTabWidget()

        # Overview Tab
        overview_tab = self._create_overview_tab()
        tabs.addTab(overview_tab, "Overview")

        # Processing Tab
        processing_tab = self._create_processing_tab()
        tabs.addTab(processing_tab, "Processing")

        # Activity Tab
        activity_tab = self._create_activity_tab()
        tabs.addTab(activity_tab, "Recent Activity")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _create_overview_tab(self) -> QWidget:
        """Create the overview tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # All-Time Totals
        alltime_group = QGroupBox("All-Time Totals")
        alltime_layout = QFormLayout(alltime_group)

        self.total_pdfs_label = QLabel("-")
        self.total_pdfs_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        alltime_layout.addRow("PDFs Processed:", self.total_pdfs_label)

        self.total_exports_label = QLabel("-")
        self.total_exports_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        alltime_layout.addRow("Exports Completed:", self.total_exports_label)

        self.total_cbp_label = QLabel("-")
        alltime_layout.addRow("CBP Exports:", self.total_cbp_label)

        self.hts_matches_label = QLabel("-")
        alltime_layout.addRow("HTS Matches Found:", self.hts_matches_label)

        self.unique_users_label = QLabel("-")
        alltime_layout.addRow("Unique Users:", self.unique_users_label)

        self.tracking_since_label = QLabel("-")
        alltime_layout.addRow("Tracking Since:", self.tracking_since_label)

        layout.addWidget(alltime_group)

        # Period Statistics
        period_group = QGroupBox("Period Statistics")
        period_layout = QFormLayout(period_group)

        self.period_pdfs_label = QLabel("-")
        period_layout.addRow("PDFs Processed:", self.period_pdfs_label)

        self.period_failed_label = QLabel("-")
        period_layout.addRow("PDFs Failed:", self.period_failed_label)

        self.success_rate_label = QLabel("-")
        period_layout.addRow("Success Rate:", self.success_rate_label)

        self.period_exports_label = QLabel("-")
        period_layout.addRow("Exports:", self.period_exports_label)

        self.hts_rate_label = QLabel("-")
        period_layout.addRow("HTS Match Rate:", self.hts_rate_label)

        self.app_starts_label = QLabel("-")
        period_layout.addRow("App Starts:", self.app_starts_label)

        layout.addWidget(period_group)

        layout.addStretch()
        return widget

    def _create_processing_tab(self) -> QWidget:
        """Create the processing statistics tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Template Usage
        template_group = QGroupBox("Template Usage")
        template_layout = QVBoxLayout(template_group)

        self.template_table = QTableWidget()
        self.template_table.setColumnCount(2)
        self.template_table.setHorizontalHeaderLabels(["Template", "Times Used"])
        self.template_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.template_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.template_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.template_table.setMaximumHeight(150)

        template_layout.addWidget(self.template_table)
        layout.addWidget(template_group)

        # User Statistics
        user_group = QGroupBox("User Activity")
        user_layout = QVBoxLayout(user_group)

        self.user_table = QTableWidget()
        self.user_table.setColumnCount(4)
        self.user_table.setHorizontalHeaderLabels([
            "User", "PDFs", "Exports", "Last Activity"
        ])
        self.user_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.user_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.user_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        user_layout.addWidget(self.user_table)
        layout.addWidget(user_group)

        return widget

    def _create_activity_tab(self) -> QWidget:
        """Create the recent activity tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Recent Activity Table
        activity_group = QGroupBox("Recent Activity (Last 20 Events)")
        activity_layout = QVBoxLayout(activity_group)

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels([
            "Time", "Event", "User", "Details"
        ])
        self.activity_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.activity_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.activity_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.activity_table.setAlternatingRowColors(True)

        activity_layout.addWidget(self.activity_table)
        layout.addWidget(activity_group)

        return widget

    def _load_data(self):
        """Load all statistics data."""
        days = self.period_combo.currentData()

        # All-time totals
        totals = self.stats_tracker.get_all_time_totals()
        self.total_pdfs_label.setText(f"{totals['total_pdfs']:,}")
        self.total_exports_label.setText(f"{totals['total_exports']:,}")
        self.total_cbp_label.setText(f"{totals['total_cbp_exports']:,}")
        self.hts_matches_label.setText(f"{totals['hts_matches']:,}")
        self.unique_users_label.setText(str(totals['unique_users']))

        if totals['tracking_since']:
            tracking_since = totals['tracking_since'][:10]
            self.tracking_since_label.setText(tracking_since)
        else:
            self.tracking_since_label.setText("No data yet")

        # Period statistics
        stats = self.stats_tracker.get_processing_stats(days=days)
        self.period_pdfs_label.setText(str(stats['pdfs_processed']))
        self.period_failed_label.setText(str(stats['pdfs_failed']))
        self.success_rate_label.setText(f"{stats['success_rate']}%")
        self.period_exports_label.setText(str(stats['exports_completed']))
        self.hts_rate_label.setText(f"{stats['hts_match_rate']}%")
        self.app_starts_label.setText(str(stats['app_starts']))

        # Template usage
        template_usage = self.stats_tracker.get_template_usage(days=days)
        self.template_table.setRowCount(len(template_usage))
        for row, (template, count) in enumerate(sorted(
            template_usage.items(), key=lambda x: x[1], reverse=True
        )):
            self.template_table.setItem(row, 0, QTableWidgetItem(template))
            self.template_table.setItem(row, 1, QTableWidgetItem(str(count)))

        # User statistics
        user_stats = self.stats_tracker.get_user_statistics(days=days)
        self.user_table.setRowCount(len(user_stats))
        for row, (user, data) in enumerate(sorted(
            user_stats.items(), key=lambda x: x[1]['event_count'], reverse=True
        )):
            self.user_table.setItem(row, 0, QTableWidgetItem(user))
            self.user_table.setItem(row, 1, QTableWidgetItem(str(data['pdfs_processed'])))
            self.user_table.setItem(row, 2, QTableWidgetItem(str(data['exports'])))
            last_activity = data.get('last_activity', '')
            if last_activity:
                last_activity = last_activity[:19].replace('T', ' ')
            self.user_table.setItem(row, 3, QTableWidgetItem(last_activity))

        # Recent activity
        self._load_recent_activity()

    def _load_recent_activity(self):
        """Load recent activity events."""
        events = self.stats_tracker.get_recent_activity(limit=20)
        self.activity_table.setRowCount(len(events))

        event_labels = {
            EventTypes.PDF_PROCESSED: "PDF Processed",
            EventTypes.PDF_FAILED: "PDF Failed",
            EventTypes.ITEMS_EXTRACTED: "Items Extracted",
            EventTypes.TEMPLATE_USED: "Template Used",
            EventTypes.HTS_MATCH_FOUND: "HTS Match Found",
            EventTypes.HTS_MATCH_FAILED: "HTS Lookup Failed",
            EventTypes.EXPORT_COMPLETED: "Export Completed",
            EventTypes.EXPORT_FAILED: "Export Failed",
            EventTypes.CBP_EXPORT: "CBP Export",
            EventTypes.APP_STARTED: "App Started",
            EventTypes.APP_CLOSED: "App Closed",
            EventTypes.USER_LOGIN: "User Login",
            EventTypes.USER_LOGOUT: "User Logout",
            EventTypes.SETTINGS_CHANGED: "Settings Changed",
        }

        for row, event in enumerate(events):
            # Time
            timestamp = event.get('timestamp', '')
            if timestamp:
                timestamp = timestamp[:19].replace('T', ' ')
            self.activity_table.setItem(row, 0, QTableWidgetItem(timestamp))

            # Event type
            event_type = event.get('event_type', '')
            event_label = event_labels.get(event_type, event_type)
            self.activity_table.setItem(row, 1, QTableWidgetItem(event_label))

            # User
            user = event.get('user_name', '')
            self.activity_table.setItem(row, 2, QTableWidgetItem(user or '-'))

            # Details
            details = ""
            event_data = event.get('event_data', {})
            if isinstance(event_data, dict):
                if 'file_name' in event_data:
                    details = event_data['file_name']
                elif 'template_name' in event_data:
                    details = event_data['template_name']
                elif 'part_number' in event_data:
                    details = event_data['part_number']
                elif 'error' in event_data:
                    details = event_data['error'][:50]

            self.activity_table.setItem(row, 3, QTableWidgetItem(details))

    def _format_event_type(self, event_type: str) -> str:
        """Format event type for display."""
        return event_type.replace('_', ' ').title()
