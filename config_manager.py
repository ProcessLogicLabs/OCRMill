"""
Configuration Manager for Invoice Processor
Handles saving/loading settings and template configurations.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# PyInstaller path handling
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APP_PATH = Path(sys.executable).parent
else:
    # Running as Python script
    APP_PATH = Path(__file__).parent

CONFIG_FILE = APP_PATH / "config.json"

DEFAULT_CONFIG = {
    "input_folder": "input",
    "output_folder": "output",
    "database_path": "Resources/parts_database.db",
    "poll_interval": 60,
    "auto_start": False,
    "consolidate_multi_invoice": False,  # False = separate CSVs per invoice, True = one CSV per PDF
    "auto_cbp_export": False,  # Auto-run CBP export after invoice processing
    "check_updates_on_startup": True,  # Check for updates when application starts
    "cbp_export": {
        "input_folder": "output/Processed",
        "output_folder": "output/CBP_Export"
    },
    "templates": {
        "mmcite_czech": {"enabled": True},
        "mmcite_brazilian": {"enabled": True}
    },
    "window": {
        "width": 800,
        "height": 600,
        "x": None,
        "y": None
    },
    "parts_master_columns": {
        "part_number": True,
        "description": True,
        "hts_code": True,
        "country_origin": True,
        "mid": True,
        "client_code": True,
        "steel_pct": True,
        "aluminum_pct": True,
        "copper_pct": True,
        "wood_pct": True,
        "auto_pct": True,
        "non_steel_pct": True,
        "qty_unit": True,
        "sec301_exclusion_tariff": True,
        "fsc_certified": True,
        "fsc_certificate_code": True,
        "last_updated": True
    }
}


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_configs(DEFAULT_CONFIG, loaded)
            except (json.JSONDecodeError, IOError):
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()
    
    def _merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """Recursively merge loaded config with defaults."""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.input_folder,
            self.output_folder,
            self.output_folder / "Processed",
            self.output_folder / "CBP_Export",
            APP_PATH / "reports",
            self.database_path.parent,  # Resources folder
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save(self):
        """Save current configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any):
        """Set a configuration value."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save()
    
    @property
    def input_folder(self) -> Path:
        folder = self.config.get("input_folder", "input")
        if not Path(folder).is_absolute():
            return APP_PATH / folder
        return Path(folder)
    
    @input_folder.setter
    def input_folder(self, value: str):
        self.config["input_folder"] = str(value)
        self.save()
    
    @property
    def output_folder(self) -> Path:
        folder = self.config.get("output_folder", "output")
        if not Path(folder).is_absolute():
            return APP_PATH / folder
        return Path(folder)
    
    @output_folder.setter
    def output_folder(self, value: str):
        self.config["output_folder"] = str(value)
        self.save()
    
    @property
    def poll_interval(self) -> int:
        return self.config.get("poll_interval", 60)
    
    @poll_interval.setter
    def poll_interval(self, value: int):
        self.config["poll_interval"] = value
        self.save()
    
    @property
    def auto_start(self) -> bool:
        return self.config.get("auto_start", False)

    @auto_start.setter
    def auto_start(self, value: bool):
        self.config["auto_start"] = value
        self.save()

    @property
    def auto_cbp_export(self) -> bool:
        return self.config.get("auto_cbp_export", False)

    @auto_cbp_export.setter
    def auto_cbp_export(self, value: bool):
        self.config["auto_cbp_export"] = value
        self.save()

    @property
    def consolidate_multi_invoice(self) -> bool:
        return self.config.get("consolidate_multi_invoice", False)

    @consolidate_multi_invoice.setter
    def consolidate_multi_invoice(self, value: bool):
        self.config["consolidate_multi_invoice"] = value
        self.save()

    @property
    def check_updates_on_startup(self) -> bool:
        return self.config.get("check_updates_on_startup", True)

    @check_updates_on_startup.setter
    def check_updates_on_startup(self, value: bool):
        self.config["check_updates_on_startup"] = value
        self.save()

    @property
    def database_path(self) -> Path:
        db_path = self.config.get("database_path", "Resources/parts_database.db")
        if not Path(db_path).is_absolute():
            return APP_PATH / db_path
        return Path(db_path)

    @database_path.setter
    def database_path(self, value: str):
        self.config["database_path"] = str(value)
        self.save()

    def get_template_enabled(self, template_name: str) -> bool:
        """Check if a template is enabled."""
        templates = self.config.get("templates", {})
        template_config = templates.get(template_name, {})
        return template_config.get("enabled", True)
    
    def set_template_enabled(self, template_name: str, enabled: bool):
        """Enable or disable a template."""
        if "templates" not in self.config:
            self.config["templates"] = {}
        if template_name not in self.config["templates"]:
            self.config["templates"][template_name] = {}
        self.config["templates"][template_name]["enabled"] = enabled
        self.save()
    
    def get_enabled_templates(self) -> List[str]:
        """Get list of enabled template names."""
        templates = self.config.get("templates", {})
        return [name for name, conf in templates.items() if conf.get("enabled", True)]

    # CBP Export settings
    @property
    def cbp_input_folder(self) -> str:
        """Get CBP export input folder path."""
        folder = self.config.get("cbp_export", {}).get("input_folder", "output/Processed")
        if not Path(folder).is_absolute():
            return str(APP_PATH / folder)
        return folder

    @cbp_input_folder.setter
    def cbp_input_folder(self, value: str):
        """Set CBP export input folder path."""
        if "cbp_export" not in self.config:
            self.config["cbp_export"] = {}
        self.config["cbp_export"]["input_folder"] = str(value)
        self.save()

    @property
    def cbp_output_folder(self) -> str:
        """Get CBP export output folder path."""
        folder = self.config.get("cbp_export", {}).get("output_folder", "output/CBP_Export")
        if not Path(folder).is_absolute():
            return str(APP_PATH / folder)
        return folder

    @cbp_output_folder.setter
    def cbp_output_folder(self, value: str):
        """Set CBP export output folder path."""
        if "cbp_export" not in self.config:
            self.config["cbp_export"] = {}
        self.config["cbp_export"]["output_folder"] = str(value)
        self.save()

    # Parts Master column visibility settings
    def get_column_visible(self, column_name: str) -> bool:
        """Check if a Parts Master column is visible."""
        columns = self.config.get("parts_master_columns", {})
        return columns.get(column_name, True)

    def set_column_visible(self, column_name: str, visible: bool):
        """Set visibility for a Parts Master column."""
        if "parts_master_columns" not in self.config:
            self.config["parts_master_columns"] = {}
        self.config["parts_master_columns"][column_name] = visible
        self.save()

    def get_visible_columns(self) -> List[str]:
        """Get list of visible column names."""
        columns = self.config.get("parts_master_columns", {})
        return [name for name, visible in columns.items() if visible]

    def get_all_column_settings(self) -> Dict[str, bool]:
        """Get all column visibility settings."""
        return self.config.get("parts_master_columns", {}).copy()
