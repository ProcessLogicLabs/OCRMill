# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OCRMill
Packages the application as a standalone Windows executable
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root directory
project_root = Path(SPECPATH)

a = Analysis(
    ['invoice_processor_gui.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Configuration and database
        ('config.json', '.'),
        ('parts_database.db', '.'),

        # Template modules
        ('templates', 'templates'),

        # Resources folder (if it contains data files)
        ('Resources', 'Resources'),

        # DerivativeMill submodule (invoice_processor)
        ('DerivativeMill/DerivativeMill', 'DerivativeMill/DerivativeMill'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'pdfplumber',
        'pandas',
        'openpyxl',
        'xlsxwriter',
        'sqlite3',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'part_description_extractor',
        'parts_database',
        'config_manager',
        'templates',
        'templates.bill_of_lading',
        'templates.commercial_invoice',
        'templates.packing_list',
        'DerivativeMill.DerivativeMill.invoice_processor',
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
    console=False,  # Set to False for GUI app (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: 'icon.ico'
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
