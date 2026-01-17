"""
QSS Stylesheets for OCRMill PyQt6 Application
"""

# Main application stylesheet
APP_STYLESHEET = """
/* Tab styling */
QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background: white;
}

QTabBar::tab {
    background: #d0d0d0;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 9pt;
}

QTabBar::tab:selected {
    background: white;
    border-bottom: none;
}

QTabBar::tab:hover:!selected {
    background: #e8e8e8;
}

/* Button styling */
QPushButton {
    padding: 6px 14px;
    border-radius: 3px;
    background-color: #e0e0e0;
    border: 1px solid #c0c0c0;
    font-family: 'Segoe UI', sans-serif;
}

QPushButton:hover {
    background-color: #d0d0d0;
}

QPushButton:pressed {
    background-color: #c0c0c0;
}

QPushButton:disabled {
    background-color: #f0f0f0;
    color: #a0a0a0;
}

/* Group box styling */
QGroupBox {
    font-weight: bold;
    border: 1px solid #c0c0c0;
    border-radius: 5px;
    margin-top: 1em;
    padding-top: 10px;
    font-family: 'Segoe UI', sans-serif;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

/* Status bar */
QStatusBar {
    background: #f0f0f0;
    border-top: 1px solid #c0c0c0;
    font-family: 'Segoe UI', sans-serif;
}

/* Line edit */
QLineEdit {
    padding: 5px;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
}

QLineEdit:focus {
    border: 1px solid #0078d4;
}

/* Spin box */
QSpinBox {
    padding: 5px;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
}

/* Checkbox */
QCheckBox {
    font-family: 'Segoe UI', sans-serif;
    spacing: 8px;
}

/* Table view */
QTableView {
    gridline-color: #e0e0e0;
    selection-background-color: #0078d4;
    selection-color: white;
    font-family: 'Segoe UI', sans-serif;
}

QTableView::item:hover {
    background-color: #e8f4fc;
}

QHeaderView::section {
    background-color: #f0f0f0;
    padding: 6px;
    border: none;
    border-right: 1px solid #c0c0c0;
    border-bottom: 1px solid #c0c0c0;
    font-weight: bold;
    font-family: 'Segoe UI', sans-serif;
}

/* List widget */
QListWidget {
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: white;
}

QListWidget::item:hover {
    background-color: #e8f4fc;
}

/* Scroll bars */
QScrollBar:vertical {
    background: #f0f0f0;
    width: 14px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #c0c0c0;
    min-height: 30px;
    border-radius: 7px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #f0f0f0;
    height: 14px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #c0c0c0;
    min-width: 30px;
    border-radius: 7px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #a0a0a0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Menu bar */
QMenuBar {
    background-color: #f0f0f0;
    font-family: 'Segoe UI', sans-serif;
}

QMenuBar::item:selected {
    background-color: #e0e0e0;
}

QMenu {
    background-color: white;
    border: 1px solid #c0c0c0;
    font-family: 'Segoe UI', sans-serif;
}

QMenu::item {
    padding: 6px 40px 6px 20px;
}

QMenu::item:selected {
    background-color: #0078d4;
    color: white;
}

QMenu::separator {
    height: 1px;
    background: #c0c0c0;
    margin: 4px 8px;
}

/* Plain text edit (log viewer) */
QPlainTextEdit {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    background-color: white;
    border: 1px solid #c0c0c0;
}

/* Labels */
QLabel {
    font-family: 'Segoe UI', sans-serif;
}
"""

# HTS Reference Dialog stylesheet (matches app theme)
HTS_DIALOG_STYLESHEET = """
QDialog#HTSReferenceDialog {
    background-color: #ffffff;
}

QLabel {
    color: #333333;
    font-family: 'Segoe UI', sans-serif;
}

QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
    color: #0078d4;
}

QLabel#infoLabel {
    color: #666666;
    font-size: 9pt;
}

QGroupBox {
    background-color: #f8f8f8;
    border: 1px solid #c0c0c0;
    border-radius: 5px;
    color: #0078d4;
    font-weight: bold;
    margin-top: 1em;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #0078d4;
}

QLineEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #c0c0c0;
    padding: 8px;
    font-size: 11px;
    border-radius: 3px;
}

QLineEdit:focus {
    border: 1px solid #0078d4;
}

QPushButton {
    background-color: #0078d4;
    color: #ffffff;
    border: none;
    padding: 8px 16px;
    border-radius: 3px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #106ebe;
}

QPushButton:pressed {
    background-color: #005a9e;
}

QPushButton#closeButton {
    background-color: #e0e0e0;
    color: #333333;
}

QPushButton#closeButton:hover {
    background-color: #d0d0d0;
}

QTableView {
    background-color: #ffffff;
    alternate-background-color: #f5f5f5;
    color: #333333;
    gridline-color: #e0e0e0;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
    border: 1px solid #c0c0c0;
    font-family: 'Segoe UI', sans-serif;
}

QTableView::item {
    padding: 5px;
}

QTableView::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTableView::item:hover {
    background-color: #e8f4fc;
}

QHeaderView::section {
    background-color: #f0f0f0;
    color: #333333;
    padding: 8px;
    border: none;
    border-right: 1px solid #c0c0c0;
    border-bottom: 1px solid #c0c0c0;
    font-weight: bold;
}

QScrollBar:vertical {
    background: #f0f0f0;
    width: 14px;
}

QScrollBar::handle:vertical {
    background: #c0c0c0;
    border-radius: 7px;
    margin: 2px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #f0f0f0;
    height: 14px;
}

QScrollBar::handle:horizontal {
    background: #c0c0c0;
    border-radius: 7px;
    margin: 2px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #a0a0a0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QCheckBox {
    color: #333333;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QCheckBox::indicator:unchecked {
    border: 1px solid #c0c0c0;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    border: 1px solid #0078d4;
    background: #0078d4;
}
"""

# Drop zone styles
DROP_ZONE_STYLES = {
    'normal': """
        QFrame#dropZone {
            background-color: #e8f4e8;
            border: 2px dashed #4caf50;
            border-radius: 8px;
        }
        QLabel {
            color: #2e7d32;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }
    """,
    'hover': """
        QFrame#dropZone {
            background-color: #c8e6c9;
            border: 2px solid #4caf50;
            border-radius: 8px;
        }
        QLabel {
            color: #1b5e20;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }
    """,
    'warning': """
        QFrame#dropZone {
            background-color: #fff3e0;
            border: 2px dashed #ff9800;
            border-radius: 8px;
        }
        QLabel {
            color: #e65100;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }
    """,
    'disabled': """
        QFrame#dropZone {
            background-color: #f5f5f5;
            border: 2px dashed #bdbdbd;
            border-radius: 8px;
        }
        QLabel {
            color: #9e9e9e;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }
    """
}

# Color constants for programmatic use
COLORS = {
    'primary': '#0078d4',
    'success': '#4caf50',
    'warning': '#ff9800',
    'error': '#f44336',
    'text': '#333333',
    'text_light': '#666666',
    'background': '#ffffff',
    'border': '#c0c0c0',
}

HTS_COLORS = {
    'bg': '#ffffff',
    'fg': '#333333',
    'header_bg': '#f0f0f0',
    'header_fg': '#333333',
    'row_odd': '#f5f5f5',
    'row_even': '#ffffff',
    'selected': '#0078d4',
    'border': '#c0c0c0',
    'info_bg': '#f8f8f8',
    'info_border': '#c0c0c0',
    'button_bg': '#0078d4',
    'button_hover': '#106ebe',
    'search_bg': '#ffffff',
}
