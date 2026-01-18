# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OCRMill (PyQt6 Version)
Packages the application as a standalone Windows executable
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root directory
project_root = Path(SPECPATH)

a = Analysis(
    ['ocrmill_app.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Configuration and database
        ('config.json', '.'),
        ('parts_database.db', '.'),

        # Template modules
        ('templates', 'templates'),

        # Resources folder
        ('Resources', 'Resources'),

        # UI modules
        ('ui', 'ui'),

        # Core modules
        ('core', 'core'),

        # Licensing module
        ('licensing', 'licensing'),

        # Billing module
        ('billing', 'billing'),

        # Statistics module
        ('statistics', 'statistics'),
    ],
    hiddenimports=[
        # PyQt6
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',

        # PDF processing
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',

        # Data processing
        'pandas',
        'openpyxl',
        'xlsxwriter',
        'sqlite3',

        # Image handling
        'PIL',
        'PIL.Image',

        # Application modules
        'part_description_extractor',
        'parts_database',
        'config_manager',
        'updater',

        # Templates
        'templates',
        'templates.base_template',
        'templates.bill_of_lading',
        'templates.mmcite_czech',
        'templates.mmcite_brazilian',

        # UI modules
        'ui',
        'ui.main_window',
        'ui.tabs',
        'ui.tabs.invoice_tab',
        'ui.tabs.parts_tab',
        'ui.dialogs',
        'ui.dialogs.settings_dialog',
        'ui.dialogs.manufacturers_dialog',
        'ui.dialogs.hts_reference_dialog',
        'ui.dialogs.part_dialogs',
        'ui.widgets',
        'ui.widgets.drop_zone',
        'ui.widgets.log_viewer',

        # Core modules
        'core',
        'core.workers',

        # Resources
        'Resources',
        'Resources.styles',

        # Licensing modules
        'licensing',
        'licensing.license_manager',
        'licensing.auth_manager',

        # Billing modules
        'billing',
        'billing.billing_manager',
        'billing.billing_sync',

        # Statistics modules
        'statistics',
        'statistics.stats_tracker',

        # AI Template Generator
        'ai_template_generator',

        # New dialogs
        'ui.dialogs.license_dialog',
        'ui.dialogs.login_dialog',
        'ui.dialogs.billing_dialog',
        'ui.dialogs.statistics_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'numpy.distutils',
        'pytest',
        'IPython',
        'tkinter',  # No longer needed
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OCRMill',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI app - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Resources/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OCRMill',
)
