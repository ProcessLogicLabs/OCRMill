"""
Theme Manager for OCRMill
Provides comprehensive theming support with dark/light modes
Adapted from TariffMill theme system
"""

from PyQt6.QtWidgets import QApplication, QStyle
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QSettings


# Available themes
AVAILABLE_THEMES = [
    "Muted Cyan",      # Default - matches OCRMill branding
    "Fusion (Light)",   # Standard light theme
    "Fusion (Dark)",    # Dark mode
    "Ocean",            # Deep blue theme
    "System Default",   # Follow system settings
]


class ThemeManager:
    """Manages application theming with support for light/dark modes."""

    def __init__(self):
        self.current_theme = "Muted Cyan"
        self.settings = QSettings("ProcessLogicLabs", "OCRMill")

    def load_saved_theme(self) -> str:
        """Load the saved theme from settings."""
        return self.settings.value("theme/current", "Muted Cyan")

    def save_theme(self, theme_name: str):
        """Save the current theme to settings."""
        self.settings.setValue("theme/current", theme_name)
        self.settings.sync()

    def apply_theme(self, theme_name: str) -> None:
        """Apply the specified theme to the application."""
        app = QApplication.instance()
        if not app:
            return

        self.current_theme = theme_name
        self.save_theme(theme_name)

        if theme_name == "System Default":
            app.setStyle("Fusion")
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet("")
        elif theme_name == "Fusion (Light)":
            app.setStyle("Fusion")
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet(self._get_light_stylesheet())
        elif theme_name == "Fusion (Dark)":
            app.setStyle("Fusion")
            app.setPalette(self._get_dark_palette())
            app.setStyleSheet(self._get_dark_stylesheet())
        elif theme_name == "Ocean":
            app.setStyle("Fusion")
            app.setPalette(self._get_ocean_palette())
            app.setStyleSheet(self._get_ocean_stylesheet())
        elif theme_name == "Muted Cyan":
            app.setStyle("Fusion")
            app.setPalette(self._get_muted_cyan_palette())
            app.setStyleSheet(self._get_muted_cyan_stylesheet())
        else:
            # Default to Muted Cyan
            app.setStyle("Fusion")
            app.setPalette(self._get_muted_cyan_palette())
            app.setStyleSheet(self._get_muted_cyan_stylesheet())

    def is_dark_theme(self) -> bool:
        """Check if current theme is a dark theme."""
        return self.current_theme in ["Fusion (Dark)", "Ocean"]

    def _get_dark_palette(self) -> QPalette:
        """Create a dark mode palette."""
        palette = QPalette()

        # Dark theme colors
        palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(243, 243, 243))
        palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(243, 243, 243))
        palette.setColor(QPalette.ColorRole.Text, QColor(243, 243, 243))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(243, 243, 243))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(243, 243, 243))
        palette.setColor(QPalette.ColorRole.Light, QColor(70, 70, 70))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(60, 60, 60))
        palette.setColor(QPalette.ColorRole.Mid, QColor(50, 50, 50))
        palette.setColor(QPalette.ColorRole.Dark, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(20, 20, 20))

        return palette

    def _get_ocean_palette(self) -> QPalette:
        """Create an ocean-themed palette with deep blues."""
        palette = QPalette()

        # Ocean theme colors
        palette.setColor(QPalette.ColorRole.Window, QColor(26, 48, 80))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(192, 224, 240))
        palette.setColor(QPalette.ColorRole.Base, QColor(21, 42, 66))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(26, 48, 80))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(30, 58, 85))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(224, 240, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(224, 240, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(58, 106, 154))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(0, 200, 220))
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 168, 204))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(30, 60, 100))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Light, QColor(58, 106, 154))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(42, 80, 112))
        palette.setColor(QPalette.ColorRole.Mid, QColor(58, 106, 154))
        palette.setColor(QPalette.ColorRole.Dark, QColor(18, 36, 56))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(12, 24, 40))

        return palette

    def _get_muted_cyan_palette(self) -> QPalette:
        """Create a muted cyan palette matching OCRMill branding."""
        palette = QPalette()

        # Muted cyan colors based on #5f9ea0 (CadetBlue)
        palette.setColor(QPalette.ColorRole.Window, QColor(248, 250, 250))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(51, 51, 51))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(248, 249, 250))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(51, 51, 51))
        palette.setColor(QPalette.ColorRole.Text, QColor(51, 51, 51))
        palette.setColor(QPalette.ColorRole.Button, QColor(95, 158, 160))  # CadetBlue
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(217, 83, 79))
        palette.setColor(QPalette.ColorRole.Link, QColor(95, 158, 160))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(95, 158, 160))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Light, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Midlight, QColor(232, 244, 244))
        palette.setColor(QPalette.ColorRole.Mid, QColor(95, 158, 160))
        palette.setColor(QPalette.ColorRole.Dark, QColor(74, 138, 140))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(61, 122, 124))

        return palette

    def _get_light_stylesheet(self) -> str:
        """Get stylesheet for light theme."""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                margin-top: 1em;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #333333;
            }
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QDialog {
                background-color: #ffffff;
            }
        """

    def _get_dark_stylesheet(self) -> str:
        """Get stylesheet for dark theme."""
        return """
            QGroupBox {
                font-weight: normal;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d3d3d, stop:1 #2d2d2d);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 2px 8px;
                color: #b0b0b0;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                background: #353535;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #454545, stop:1 #353535);
                color: #a0a0a0;
                padding: 8px 16px;
                border: 1px solid #4a4a4a;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #505050, stop:1 #404040);
                color: #ffffff;
                border-bottom: 2px solid #5f9ea0;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4a4a, stop:1 #3a3a3a);
                color: #d0d0d0;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #353535, stop:1 #2a2a2a);
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 5px 8px;
                selection-background-color: #5f9ea0;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #5f9ea0;
            }
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #353535, stop:1 #2a2a2a);
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QComboBox::drop-down {
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #505050, stop:1 #404040);
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #353535;
                color: #e0e0e0;
                selection-background-color: #5f9ea0;
                border: 1px solid #4a4a4a;
            }
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #353535, stop:1 #2a2a2a);
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #5f9ea0;
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background: #454545;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5f9ea0, stop:1 #4a8a8c);
                color: #ffffff;
                border: 1px solid #6baeaf;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: normal;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6baeaf, stop:1 #5a9a9c);
                border: 1px solid #7ab8ba;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a8a8c, stop:1 #3d7a7c);
            }
            QPushButton:disabled {
                background: #555555;
                color: #888888;
                border: 1px solid #4a4a4a;
            }
            QScrollBar:vertical {
                background: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #505050, stop:1 #5a5a5a);
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5f9ea0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #2d2d2d;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #505050, stop:1 #5a5a5a);
                border-radius: 5px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #5f9ea0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #454545, stop:1 #353535);
                color: #c0c0c0;
                padding: 6px;
                border: none;
                border-right: 1px solid #4a4a4a;
                border-bottom: 2px solid #5f9ea0;
                font-weight: normal;
            }
            QTableWidget, QTableView {
                background-color: #2d2d2d;
                alternate-background-color: #353535;
                gridline-color: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
            QTableWidget::item:selected, QTableView::item:selected {
                background-color: #5f9ea0;
                color: #ffffff;
            }
            QLabel {
                color: #c0c0c0;
            }
            QMenu {
                background-color: #353535;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #5f9ea0;
                color: #ffffff;
            }
            QMenuBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d3d3d, stop:1 #2d2d2d);
                color: #c0c0c0;
            }
            QMenuBar::item:selected {
                background: #505050;
                border-radius: 4px;
            }
            QMessageBox {
                background-color: #2d2d2d;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                min-width: 80px;
            }
            QDialog {
                background-color: #2d2d2d;
            }
            QPlainTextEdit, QTextEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
            }
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #4a4a4a;
                background: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #5f9ea0;
                background: #5f9ea0;
            }
            QRadioButton {
                color: #e0e0e0;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                border: 1px solid #4a4a4a;
                background: #2d2d2d;
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #5f9ea0;
                background: #5f9ea0;
                border-radius: 8px;
            }
            QProgressBar {
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                background-color: #2d2d2d;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #5f9ea0;
                border-radius: 2px;
            }
            QStatusBar {
                background: #2d2d2d;
                border-top: 1px solid #4a4a4a;
                color: #a0a0a0;
            }
            QToolTip {
                background-color: #353535;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                padding: 4px;
            }
            QSplitter::handle {
                background-color: #4a4a4a;
            }
            QSplitter::handle:hover {
                background-color: #5f9ea0;
            }
        """

    def _get_ocean_stylesheet(self) -> str:
        """Get stylesheet for ocean theme."""
        return """
            QGroupBox {
                font-weight: normal;
                border: 1px solid #3a6a9a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #243d5c, stop:1 #1a3050);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 2px 8px;
                color: #7ec8e3;
                background: #1a3050;
                border-radius: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #3a6a9a;
                border-radius: 6px;
                background: #1e3a55;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a4a6a, stop:1 #1e3a55);
                color: #8ac4e0;
                padding: 8px 16px;
                border: 1px solid #3a6a9a;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a6a9a, stop:1 #2a5070);
                color: #ffffff;
                border-bottom: 2px solid #00a8cc;
            }
            QTabBar::tab:hover:!selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #325878, stop:1 #264560);
                color: #c0e0f0;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a3550, stop:1 #152a42);
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
                padding: 5px 8px;
                selection-background-color: #0096b4;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #00a8cc;
            }
            QComboBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a3550, stop:1 #152a42);
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QComboBox::drop-down {
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a6a9a, stop:1 #2a5070);
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a3550;
                color: #e0f0ff;
                selection-background-color: #00a8cc;
                border: 1px solid #3a6a9a;
            }
            QListWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a3550, stop:1 #152a42);
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00b8d4, stop:1 #0096b4);
                color: #ffffff;
            }
            QListWidget::item:hover:!selected {
                background: #2a4a6a;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a7ca5, stop:1 #2a5a80);
                color: #ffffff;
                border: 1px solid #4a8cb5;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: normal;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a8cb5, stop:1 #3a7095);
                border: 1px solid #5a9cc5;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a5a80, stop:1 #1a4a70);
            }
            QPushButton:disabled {
                background: #2a4a6a;
                color: #6090a0;
                border: 1px solid #3a6a9a;
            }
            QScrollBar:vertical {
                background: #1a3050;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3a6a9a, stop:1 #4a7aaa);
                border-radius: 5px;
                min-height: 30px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00a8cc;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #1a3050;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a6a9a, stop:1 #4a7aaa);
                border-radius: 5px;
                min-width: 30px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #00a8cc;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a5070, stop:1 #1e3a55);
                color: #a0d0f0;
                padding: 6px;
                border: none;
                border-right: 1px solid #3a6a9a;
                border-bottom: 2px solid #00a8cc;
                font-weight: normal;
            }
            QTableWidget, QTableView {
                background-color: #152a42;
                alternate-background-color: #1a3050;
                gridline-color: #2a4a6a;
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
            }
            QTableWidget::item:selected, QTableView::item:selected {
                background-color: #1e3c64;
                color: #ffffff;
            }
            QLabel {
                color: #c0e0f0;
            }
            QMenu {
                background-color: #1e3a55;
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0096b4;
            }
            QMenuBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #243d5c, stop:1 #1a3050);
                color: #c0e0f0;
            }
            QMenuBar::item:selected {
                background: #3a6a9a;
                border-radius: 4px;
            }
            QMessageBox {
                background-color: #1a3050;
            }
            QMessageBox QLabel {
                color: #e0f0ff;
            }
            QMessageBox QPushButton {
                min-width: 80px;
            }
            QDialog {
                background-color: #1a3050;
            }
            QPlainTextEdit, QTextEdit {
                background-color: #152a42;
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                border-radius: 4px;
            }
            QCheckBox {
                color: #c0e0f0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #3a6a9a;
                background: #1a3050;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #00a8cc;
                background: #00a8cc;
            }
            QRadioButton {
                color: #c0e0f0;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                border: 1px solid #3a6a9a;
                background: #1a3050;
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #00a8cc;
                background: #00a8cc;
                border-radius: 8px;
            }
            QProgressBar {
                border: 1px solid #3a6a9a;
                border-radius: 3px;
                background-color: #1a3050;
                text-align: center;
                color: #c0e0f0;
            }
            QProgressBar::chunk {
                background-color: #00a8cc;
                border-radius: 2px;
            }
            QStatusBar {
                background: #1a3050;
                border-top: 1px solid #3a6a9a;
                color: #8ac4e0;
            }
            QToolTip {
                background-color: #1e3a55;
                color: #e0f0ff;
                border: 1px solid #3a6a9a;
                padding: 4px;
            }
            QSplitter::handle {
                background-color: #3a6a9a;
            }
            QSplitter::handle:hover {
                background-color: #00a8cc;
            }
        """

    def _get_muted_cyan_stylesheet(self) -> str:
        """Get stylesheet for muted cyan theme (OCRMill default)."""
        return """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                margin-top: 1em;
                padding-top: 10px;
                background-color: #f8f9fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #5f9ea0;
            }
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background: #ffffff;
                border-top: 2px solid #5f9ea0;
            }
            QTabBar::tab {
                background: #f8f9fa;
                color: #333333;
                padding: 8px 20px;
                margin-right: 2px;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #5f9ea0;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #e8f4f4;
            }
            QPushButton {
                padding: 6px 16px;
                border-radius: 3px;
                background-color: #5f9ea0;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a8a8c;
            }
            QPushButton:pressed {
                background-color: #3d7a7c;
            }
            QPushButton:disabled {
                background-color: #b0b0b0;
                color: #e0e0e0;
            }
            QLineEdit {
                padding: 6px 8px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #5f9ea0;
            }
            QComboBox {
                padding: 5px 8px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QComboBox:focus {
                border: 1px solid #5f9ea0;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d0d0;
                selection-background-color: #5f9ea0;
                selection-color: white;
            }
            QTableView, QTableWidget {
                gridline-color: #e0e0e0;
                selection-background-color: #5f9ea0;
                selection-color: white;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
            }
            QTableView::item:hover, QTableWidget::item:hover {
                background-color: #e8f4f4;
            }
            QHeaderView::section {
                background-color: #e8f4f4;
                color: #5f9ea0;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid #d0d0d0;
                border-bottom: 1px solid #d0d0d0;
                font-weight: bold;
            }
            QScrollBar:vertical {
                background: #f8f9fa;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                min-height: 30px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #7ab8ba;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #f8f9fa;
                height: 12px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #d0d0d0;
                min-width: 30px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #7ab8ba;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QMenuBar {
                background-color: #f8f9fa;
                color: #333333;
                border-bottom: 1px solid #d0d0d0;
            }
            QMenuBar::item {
                padding: 6px 12px;
                background-color: transparent;
                color: #333333;
            }
            QMenuBar::item:selected {
                background-color: #e8f4f4;
                color: #333333;
            }
            QMenu {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
            }
            QMenu::item {
                padding: 6px 40px 6px 20px;
                color: #333333;
            }
            QMenu::item:selected {
                background-color: #5f9ea0;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #d0d0d0;
                margin: 4px 8px;
            }
            QStatusBar {
                background: #f8f9fa;
                border-top: 1px solid #d0d0d0;
                color: #666666;
            }
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #333333;
            }
            QDialog {
                background-color: #ffffff;
            }
            QCheckBox {
                color: #333333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #d0d0d0;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #5f9ea0;
                background: #5f9ea0;
            }
            QRadioButton {
                color: #333333;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                border: 1px solid #d0d0d0;
                background: #ffffff;
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #5f9ea0;
                background: #5f9ea0;
                border-radius: 8px;
            }
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                text-align: center;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background-color: #5f9ea0;
                border-radius: 2px;
            }
            QPlainTextEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
            QToolTip {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                padding: 4px;
            }
            QSplitter {
                background-color: transparent;
            }
            QSplitter::handle {
                background-color: #e0e0e0;
            }
            QSplitter::handle:vertical {
                height: 3px;
                margin: 2px 0;
            }
            QSplitter::handle:horizontal {
                width: 3px;
                margin: 0 2px;
            }
            QSplitter::handle:hover {
                background-color: #7ab8ba;
            }
            QSpinBox {
                padding: 5px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
            }
            QSpinBox:focus {
                border: 1px solid #5f9ea0;
            }
        """


# Global theme manager instance
_theme_manager = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
