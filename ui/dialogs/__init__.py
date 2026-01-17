# UI Dialogs for OCRMill
from .settings_dialog import SettingsDialog
from .manufacturers_dialog import ManufacturersDialog, ManufacturerEditDialog
from .hts_reference_dialog import HTSReferenceDialog
from .part_dialogs import PartViewDialog, PartEditDialog

__all__ = [
    'SettingsDialog',
    'ManufacturersDialog',
    'ManufacturerEditDialog',
    'HTSReferenceDialog',
    'PartViewDialog',
    'PartEditDialog'
]
