"""
QSS Stylesheets for OCRMill PyQt6 Application
Muted cyan theme to match TariffMill branding
"""

# TariffMill-style color palette
THEME = {
    'primary': '#5f9ea0',           # Muted cyan (CadetBlue)
    'primary_dark': '#4a8a8c',      # Darker cyan for hover
    'primary_light': '#7ab8ba',     # Lighter cyan
    'accent': '#6b5b95',            # Purple accent (for logo/branding)
    'accent_light': '#8b7bb5',      # Lighter purple
    'background': '#ffffff',
    'surface': '#f8f9fa',           # Slightly off-white
    'border': '#d0d0d0',
    'border_light': '#e0e0e0',
    'text': '#333333',
    'text_secondary': '#666666',
    'text_muted': '#999999',
    'success': '#5cb85c',
    'warning': '#f0ad4e',
    'error': '#d9534f',
    'header_bg': '#e8f4f4',         # Very light cyan tint
    'selected': '#5f9ea0',
    'hover': '#e8f4f4',
}

# Main application stylesheet
APP_STYLESHEET = f"""
/* Main Window */
QMainWindow {{
    background-color: {THEME['background']};
}}

/* Tab styling - TariffMill style */
QTabWidget::pane {{
    border: 1px solid {THEME['border']};
    background: {THEME['background']};
    border-top: 2px solid {THEME['primary']};
}}

QTabBar::tab {{
    background: {THEME['surface']};
    color: {THEME['text']};
    padding: 8px 20px;
    margin-right: 2px;
    border: 1px solid {THEME['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-family: 'Segoe UI', sans-serif;
    font-size: 9pt;
}}

QTabBar::tab:selected {{
    background: {THEME['primary']};
    color: white;
    font-weight: bold;
}}

QTabBar::tab:hover:!selected {{
    background: {THEME['header_bg']};
}}

/* Primary action buttons - cyan */
QPushButton {{
    padding: 6px 16px;
    border-radius: 3px;
    background-color: {THEME['primary']};
    color: white;
    border: none;
    font-family: 'Segoe UI', sans-serif;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {THEME['primary_dark']};
}}

QPushButton:pressed {{
    background-color: #3d7a7c;
}}

QPushButton:disabled {{
    background-color: #b0b0b0;
    color: #e0e0e0;
}}

/* Secondary/neutral buttons */
QPushButton[secondary="true"], QPushButton#closeButton {{
    background-color: {THEME['surface']};
    color: {THEME['text']};
    border: 1px solid {THEME['border']};
}}

QPushButton[secondary="true"]:hover, QPushButton#closeButton:hover {{
    background-color: #e8e8e8;
}}

/* Group box styling */
QGroupBox {{
    font-weight: bold;
    color: {THEME['text']};
    border: 1px solid {THEME['border']};
    border-radius: 5px;
    margin-top: 1em;
    padding-top: 10px;
    font-family: 'Segoe UI', sans-serif;
    background-color: {THEME['surface']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {THEME['primary']};
}}

/* Status bar */
QStatusBar {{
    background: {THEME['surface']};
    border-top: 1px solid {THEME['border']};
    font-family: 'Segoe UI', sans-serif;
    color: {THEME['text_secondary']};
}}

/* Line edit */
QLineEdit {{
    padding: 6px 8px;
    border: 1px solid {THEME['border']};
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
    background-color: {THEME['background']};
}}

QLineEdit:focus {{
    border: 1px solid {THEME['primary']};
}}

/* Spin box */
QSpinBox {{
    padding: 5px;
    border: 1px solid {THEME['border']};
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
}}

QSpinBox:focus {{
    border: 1px solid {THEME['primary']};
}}

/* Combo box */
QComboBox {{
    padding: 5px 8px;
    border: 1px solid {THEME['border']};
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
    background-color: {THEME['background']};
}}

QComboBox:focus {{
    border: 1px solid {THEME['primary']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    border: 1px solid {THEME['border']};
    selection-background-color: {THEME['primary']};
    selection-color: white;
}}

/* Checkbox */
QCheckBox {{
    font-family: 'Segoe UI', sans-serif;
    spacing: 8px;
    color: {THEME['text']};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
}}

QCheckBox::indicator:unchecked {{
    border: 1px solid {THEME['border']};
    background: {THEME['background']};
}}

QCheckBox::indicator:checked {{
    border: 1px solid {THEME['primary']};
    background: {THEME['primary']};
}}

/* Radio button */
QRadioButton {{
    font-family: 'Segoe UI', sans-serif;
    spacing: 8px;
    color: {THEME['text']};
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}

QRadioButton::indicator:unchecked {{
    border: 1px solid {THEME['border']};
    background: {THEME['background']};
    border-radius: 8px;
}}

QRadioButton::indicator:checked {{
    border: 1px solid {THEME['primary']};
    background: {THEME['primary']};
    border-radius: 8px;
}}

/* Table view - TariffMill style with cyan headers */
QTableView {{
    gridline-color: {THEME['border_light']};
    selection-background-color: {THEME['primary']};
    selection-color: white;
    font-family: 'Segoe UI', sans-serif;
    background-color: {THEME['background']};
    alternate-background-color: {THEME['surface']};
}}

QTableView::item:hover {{
    background-color: {THEME['hover']};
}}

QHeaderView::section {{
    background-color: {THEME['header_bg']};
    color: {THEME['primary']};
    padding: 8px 6px;
    border: none;
    border-right: 1px solid {THEME['border']};
    border-bottom: 1px solid {THEME['border']};
    font-weight: bold;
    font-family: 'Segoe UI', sans-serif;
}}

/* List widget */
QListWidget {{
    border: 1px solid {THEME['border']};
    border-radius: 3px;
    font-family: 'Segoe UI', sans-serif;
    background-color: {THEME['background']};
}}

QListWidget::item:selected {{
    background-color: {THEME['primary']};
    color: white;
}}

QListWidget::item:hover {{
    background-color: {THEME['hover']};
}}

/* Scroll bars */
QScrollBar:vertical {{
    background: {THEME['surface']};
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {THEME['border']};
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background: {THEME['primary_light']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {THEME['surface']};
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {THEME['border']};
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {THEME['primary_light']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Menu bar */
QMenuBar {{
    background-color: {THEME['surface']};
    font-family: 'Segoe UI', sans-serif;
    border-bottom: 1px solid {THEME['border']};
}}

QMenuBar::item {{
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {THEME['hover']};
}}

QMenu {{
    background-color: {THEME['background']};
    border: 1px solid {THEME['border']};
    font-family: 'Segoe UI', sans-serif;
}}

QMenu::item {{
    padding: 6px 40px 6px 20px;
}}

QMenu::item:selected {{
    background-color: {THEME['primary']};
    color: white;
}}

QMenu::separator {{
    height: 1px;
    background: {THEME['border']};
    margin: 4px 8px;
}}

/* Plain text edit (log viewer) */
QPlainTextEdit {{
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    background-color: {THEME['background']};
    border: 1px solid {THEME['border']};
}}

/* Labels */
QLabel {{
    font-family: 'Segoe UI', sans-serif;
    color: {THEME['text']};
}}

/* Branding label for app title */
QLabel#brandingLabel {{
    font-size: 24px;
    font-weight: bold;
    color: {THEME['accent']};
}}

QLabel#brandingLabelAccent {{
    font-size: 24px;
    font-weight: bold;
    color: {THEME['primary']};
}}

/* Progress bar */
QProgressBar {{
    border: 1px solid {THEME['border']};
    border-radius: 3px;
    text-align: center;
    background-color: {THEME['surface']};
}}

QProgressBar::chunk {{
    background-color: {THEME['primary']};
    border-radius: 2px;
}}

/* Tool bar */
QToolBar {{
    background-color: {THEME['surface']};
    border-bottom: 1px solid {THEME['border']};
    spacing: 6px;
    padding: 4px;
}}

QToolButton {{
    background-color: transparent;
    border: none;
    padding: 6px;
    border-radius: 3px;
}}

QToolButton:hover {{
    background-color: {THEME['hover']};
}}

QToolButton:pressed {{
    background-color: {THEME['primary_light']};
}}
"""

# HTS Reference Dialog stylesheet (matches TariffMill theme)
HTS_DIALOG_STYLESHEET = f"""
QDialog#HTSReferenceDialog {{
    background-color: {THEME['background']};
}}

QLabel {{
    color: {THEME['text']};
    font-family: 'Segoe UI', sans-serif;
}}

QLabel#titleLabel {{
    font-size: 18px;
    font-weight: bold;
    color: {THEME['accent']};
}}

QLabel#infoLabel {{
    color: {THEME['text_secondary']};
    font-size: 9pt;
}}

QGroupBox {{
    background-color: {THEME['surface']};
    border: 1px solid {THEME['border']};
    border-radius: 5px;
    color: {THEME['primary']};
    font-weight: bold;
    margin-top: 1em;
    padding-top: 10px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {THEME['primary']};
}}

QLineEdit {{
    background-color: {THEME['background']};
    color: {THEME['text']};
    border: 1px solid {THEME['border']};
    padding: 8px;
    font-size: 11px;
    border-radius: 3px;
}}

QLineEdit:focus {{
    border: 1px solid {THEME['primary']};
}}

QPushButton {{
    background-color: {THEME['primary']};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 3px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {THEME['primary_dark']};
}}

QPushButton:pressed {{
    background-color: #3d7a7c;
}}

QPushButton#closeButton {{
    background-color: {THEME['surface']};
    color: {THEME['text']};
    border: 1px solid {THEME['border']};
}}

QPushButton#closeButton:hover {{
    background-color: #e8e8e8;
}}

QTableView {{
    background-color: {THEME['background']};
    alternate-background-color: {THEME['surface']};
    color: {THEME['text']};
    gridline-color: {THEME['border_light']};
    selection-background-color: {THEME['primary']};
    selection-color: white;
    border: 1px solid {THEME['border']};
    font-family: 'Segoe UI', sans-serif;
}}

QTableView::item {{
    padding: 5px;
}}

QTableView::item:selected {{
    background-color: {THEME['primary']};
    color: white;
}}

QTableView::item:hover {{
    background-color: {THEME['hover']};
}}

QHeaderView::section {{
    background-color: {THEME['header_bg']};
    color: {THEME['primary']};
    padding: 8px;
    border: none;
    border-right: 1px solid {THEME['border']};
    border-bottom: 1px solid {THEME['border']};
    font-weight: bold;
}}

QScrollBar:vertical {{
    background: {THEME['surface']};
    width: 14px;
}}

QScrollBar::handle:vertical {{
    background: {THEME['border']};
    border-radius: 7px;
    margin: 2px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {THEME['primary_light']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {THEME['surface']};
    height: 14px;
}}

QScrollBar::handle:horizontal {{
    background: {THEME['border']};
    border-radius: 7px;
    margin: 2px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {THEME['primary_light']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QCheckBox {{
    color: {THEME['text']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

QCheckBox::indicator:unchecked {{
    border: 1px solid {THEME['border']};
    background: {THEME['background']};
}}

QCheckBox::indicator:checked {{
    border: 1px solid {THEME['primary']};
    background: {THEME['primary']};
}}
"""

# Drop zone styles - using cyan theme
DROP_ZONE_STYLES = {
    'normal': f"""
        QFrame#dropZone {{
            background-color: {THEME['header_bg']};
            border: 2px dashed {THEME['primary']};
            border-radius: 8px;
        }}
        QLabel {{
            color: {THEME['primary_dark']};
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }}
    """,
    'hover': f"""
        QFrame#dropZone {{
            background-color: #d0e8e8;
            border: 2px solid {THEME['primary']};
            border-radius: 8px;
        }}
        QLabel {{
            color: {THEME['primary_dark']};
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
            font-weight: bold;
        }}
    """,
    'warning': f"""
        QFrame#dropZone {{
            background-color: #fff3e0;
            border: 2px dashed {THEME['warning']};
            border-radius: 8px;
        }}
        QLabel {{
            color: #e65100;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }}
    """,
    'disabled': f"""
        QFrame#dropZone {{
            background-color: #f5f5f5;
            border: 2px dashed #bdbdbd;
            border-radius: 8px;
        }}
        QLabel {{
            color: #9e9e9e;
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
        }}
    """
}

# Color constants for programmatic use (export THEME for external use)
COLORS = THEME

# Legacy HTS_COLORS for backwards compatibility
HTS_COLORS = {
    'bg': THEME['background'],
    'fg': THEME['text'],
    'header_bg': THEME['header_bg'],
    'header_fg': THEME['primary'],
    'row_odd': THEME['surface'],
    'row_even': THEME['background'],
    'selected': THEME['primary'],
    'border': THEME['border'],
    'info_bg': THEME['surface'],
    'info_border': THEME['border'],
    'button_bg': THEME['primary'],
    'button_hover': THEME['primary_dark'],
    'search_bg': THEME['background'],
}
