# UI Dialogs for OCRMill
from .settings_dialog import SettingsDialog
from .manufacturers_dialog import ManufacturersDialog, ManufacturerEditDialog
from .hts_reference_dialog import HTSReferenceDialog
from .part_dialogs import PartViewDialog, PartEditDialog
from .login_dialog import LoginDialog
from .license_dialog import LicenseDialog, LicenseExpiredDialog
from .billing_dialog import BillingDialog
from .statistics_dialog import StatisticsDialog

__all__ = [
    'SettingsDialog',
    'ManufacturersDialog',
    'ManufacturerEditDialog',
    'HTSReferenceDialog',
    'PartViewDialog',
    'PartEditDialog',
    'LoginDialog',
    'LicenseDialog',
    'LicenseExpiredDialog',
    'BillingDialog',
    'StatisticsDialog'
]
