"""
Configuration Manager for Invoice Processor
Handles saving/loading settings and template configurations.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List


CONFIG_FILE = Path("config.json")

DEFAULT_CONFIG = {
    "input_folder": "input",
    "output_folder": "output",
    "database_path": "Resources/parts_database.db",
    "poll_interval": 60,
    "auto_start": False,
    "consolidate_multi_invoice": False,  # False = separate CSVs per invoice, True = one CSV per PDF
    "templates": {
        "mmcite_czech": {"enabled": True},
        "mmcite_brazilian": {"enabled": True}
    },
    "window": {
        "width": 800,
        "height": 600,
        "x": None,
        "y": None
    }
}


class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
    
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
        return Path(self.config.get("input_folder", "input"))
    
    @input_folder.setter
    def input_folder(self, value: str):
        self.config["input_folder"] = str(value)
        self.save()
    
    @property
    def output_folder(self) -> Path:
        return Path(self.config.get("output_folder", "output"))
    
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
    def consolidate_multi_invoice(self) -> bool:
        return self.config.get("consolidate_multi_invoice", False)

    @consolidate_multi_invoice.setter
    def consolidate_multi_invoice(self, value: bool):
        self.config["consolidate_multi_invoice"] = value
        self.save()

    @property
    def database_path(self) -> Path:
        return Path(self.config.get("database_path", "parts_database.db"))

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
