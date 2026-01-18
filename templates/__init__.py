"""
OCR Invoice Templates Package
Contains template classes for different invoice formats.
Dynamically discovers and loads templates from this directory.

Template Priority: Local templates take priority over shared templates.
Shared templates are used as fallback if a template is not found locally.
"""

import os
import importlib
import importlib.util
import sys
import json
from pathlib import Path

from .base_template import BaseTemplate

# Registry of all available templates (populated dynamically)
TEMPLATE_REGISTRY = {}

# Track template sources (template_name -> 'local' or 'shared')
TEMPLATE_SOURCES = {}

# Files to exclude from template discovery
EXCLUDED_FILES = {'__init__.py', 'base_template.py', 'sample_template.py'}

# Shared templates folder path (loaded from settings)
_shared_templates_folder = None


def set_shared_templates_folder(folder_path: str):
    """Set the shared templates folder path."""
    global _shared_templates_folder
    _shared_templates_folder = folder_path


def get_shared_templates_folder() -> str:
    """Get the shared templates folder path from settings if not already set."""
    global _shared_templates_folder
    if _shared_templates_folder:
        return _shared_templates_folder

    # Try to load from config.json
    try:
        config_path = Path(__file__).parent.parent / "config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                settings = json.load(f)
                _shared_templates_folder = settings.get('shared_templates_folder', '')
    except Exception:
        pass

    return _shared_templates_folder or ''


def _load_template_from_file(file_path: Path, module_name: str) -> bool:
    """
    Load a single template from a file path.
    Returns True if successfully loaded and registered.
    """
    full_module_name = f"templates.{module_name}"

    try:
        # Remove from cache if already loaded (force reload)
        if full_module_name in sys.modules:
            del sys.modules[full_module_name]

        # Load the module fresh
        spec = importlib.util.spec_from_file_location(
            full_module_name,
            file_path
        )
        if spec is None or spec.loader is None:
            return False

        module = importlib.util.module_from_spec(spec)
        sys.modules[full_module_name] = module
        spec.loader.exec_module(module)

        # Find template class (class that inherits from BaseTemplate)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, BaseTemplate) and
                attr is not BaseTemplate):
                # Register the template
                TEMPLATE_REGISTRY[module_name] = attr
                return True

    except Exception as e:
        print(f"Warning: Failed to load template {module_name}: {e}")

    return False


def _discover_templates():
    """
    Dynamically discover and load all template classes.

    Priority order (local templates take precedence):
    1. Local templates folder - these take priority for development
    2. Shared templates folder (if configured) - fallback for templates not found locally

    Templates must:
    - Be .py files in the templates directory
    - Contain a class that inherits from BaseTemplate
    - Not be in EXCLUDED_FILES
    """
    global TEMPLATE_REGISTRY, TEMPLATE_SOURCES
    TEMPLATE_REGISTRY.clear()
    TEMPLATE_SOURCES.clear()

    local_templates_dir = Path(__file__).parent
    shared_folder = get_shared_templates_folder()

    # Track which templates have been loaded (to avoid duplicates)
    loaded_templates = set()

    # FIRST: Load local templates (they take priority)
    for file_path in local_templates_dir.glob('*.py'):
        if file_path.name in EXCLUDED_FILES:
            continue

        if ' ' in file_path.name:
            print(f"Warning: Skipping template '{file_path.name}' - filename contains spaces.")
            continue

        module_name = file_path.stem
        if _load_template_from_file(file_path, module_name):
            loaded_templates.add(module_name)
            TEMPLATE_SOURCES[module_name] = 'local'

    # SECOND: Load shared templates (only if not already loaded locally)
    if shared_folder:
        shared_path = Path(shared_folder)
        if shared_path.exists() and shared_path.is_dir():
            for file_path in shared_path.glob('*.py'):
                if file_path.name in EXCLUDED_FILES:
                    continue

                if ' ' in file_path.name:
                    print(f"Warning: Skipping shared template '{file_path.name}' - filename contains spaces.")
                    continue

                module_name = file_path.stem

                # Skip if already loaded from local folder
                if module_name in loaded_templates:
                    continue

                if _load_template_from_file(file_path, module_name):
                    loaded_templates.add(module_name)
                    TEMPLATE_SOURCES[module_name] = 'shared'
                    print(f"Loaded shared template (fallback): {module_name}")


def sync_templates_to_shared() -> dict:
    """
    Bidirectional sync between local and shared templates.

    - Copies newer templates in either direction based on modification time
    - Templates that only exist in one location are copied to the other

    Returns a dict with sync results:
    - 'to_shared': list of templates copied from local to shared
    - 'to_local': list of templates copied from shared to local
    - 'skipped': list of templates that were already in sync
    - 'errors': list of (template, error) tuples for failed syncs
    """
    import shutil

    results = {'to_shared': [], 'to_local': [], 'skipped': [], 'errors': []}

    shared_folder = get_shared_templates_folder()
    if not shared_folder:
        results['errors'].append(('shared_folder', 'No shared folder configured'))
        return results

    shared_path = Path(shared_folder)
    local_templates_dir = Path(__file__).parent

    # Create shared folder if it doesn't exist
    if not shared_path.exists():
        try:
            shared_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            results['errors'].append(('shared_folder', str(e)))
            return results

    # Get all template files from both locations
    local_files = {f.stem: f for f in local_templates_dir.glob('*.py')
                   if f.name not in EXCLUDED_FILES and ' ' not in f.name}
    shared_files = {f.stem: f for f in shared_path.glob('*.py')
                    if f.name not in EXCLUDED_FILES and ' ' not in f.name}

    all_templates = set(local_files.keys()) | set(shared_files.keys())

    for module_name in all_templates:
        local_file = local_files.get(module_name)
        shared_file = shared_files.get(module_name)

        try:
            if local_file and shared_file:
                # Both exist - sync based on modification time
                local_mtime = local_file.stat().st_mtime
                shared_mtime = shared_file.stat().st_mtime

                if abs(local_mtime - shared_mtime) < 1:  # Within 1 second = same
                    results['skipped'].append(module_name)
                elif local_mtime > shared_mtime:
                    # Local is newer - copy to shared
                    shutil.copy2(local_file, shared_path / local_file.name)
                    results['to_shared'].append(module_name)
                    print(f"Synced to shared: {module_name}")
                else:
                    # Shared is newer - copy to local
                    shutil.copy2(shared_file, local_templates_dir / shared_file.name)
                    results['to_local'].append(module_name)
                    print(f"Synced to local: {module_name}")

            elif local_file and not shared_file:
                # Only in local - copy to shared
                shutil.copy2(local_file, shared_path / local_file.name)
                results['to_shared'].append(module_name)
                print(f"Copied to shared (new): {module_name}")

            elif shared_file and not local_file:
                # Only in shared - copy to local
                shutil.copy2(shared_file, local_templates_dir / shared_file.name)
                results['to_local'].append(module_name)
                print(f"Copied to local (new): {module_name}")

        except Exception as e:
            results['errors'].append((module_name, str(e)))
            print(f"Error syncing template {module_name}: {e}")

    return results


def refresh_templates():
    """
    Re-scan the templates directory and reload all templates.
    Call this to pick up new templates or remove deleted ones.
    """
    _discover_templates()


def get_template(name: str) -> BaseTemplate:
    """Get a template instance by name."""
    if not TEMPLATE_REGISTRY:
        _discover_templates()
    if name in TEMPLATE_REGISTRY:
        return TEMPLATE_REGISTRY[name]()
    raise ValueError(f"Unknown template: {name}")


def get_all_templates() -> dict:
    """Get all available templates."""
    if not TEMPLATE_REGISTRY:
        _discover_templates()
    return {name: cls() for name, cls in TEMPLATE_REGISTRY.items()}


def register_template(name: str, template_class):
    """Register a new template manually."""
    TEMPLATE_REGISTRY[name] = template_class


# Initial discovery on import
_discover_templates()
