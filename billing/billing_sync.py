"""
OCRMill Billing Sync Manager

Handles syncing billing records to GitHub repository for centralized tracking.
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from parts_database import PartsDatabase
from billing.billing_manager import BillingManager

logger = logging.getLogger(__name__)

# Default config repository path
DEFAULT_CONFIG_REPO = Path.home() / "OCRMill_Config"


class BillingSyncManager:
    """Manages syncing billing records to a GitHub repository."""

    def __init__(self, db: PartsDatabase, config_repo_path: Optional[Path] = None):
        self.db = db
        self.billing_manager = BillingManager(db)
        self.config_repo_path = config_repo_path or DEFAULT_CONFIG_REPO

    def _run_git_command(self, args: list, cwd: Path = None) -> Tuple[bool, str]:
        """Run a git command and return (success, output)."""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=str(cwd or self.config_repo_path),
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() or result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except FileNotFoundError:
            return False, "Git not found - please install Git"
        except Exception as e:
            return False, str(e)

    def is_repo_configured(self) -> bool:
        """Check if the config repository exists and is valid."""
        if not self.config_repo_path.exists():
            return False

        git_dir = self.config_repo_path / '.git'
        return git_dir.exists() and git_dir.is_dir()

    def get_repo_status(self) -> dict:
        """Get the current status of the config repository."""
        if not self.is_repo_configured():
            return {
                'configured': False,
                'path': str(self.config_repo_path),
                'message': 'Repository not configured'
            }

        # Get current branch
        success, branch = self._run_git_command(['branch', '--show-current'])
        if not success:
            branch = 'unknown'

        # Get remote URL
        success, remote = self._run_git_command(['remote', 'get-url', 'origin'])
        if not success:
            remote = 'No remote configured'

        # Get status
        success, status = self._run_git_command(['status', '--porcelain'])
        has_changes = bool(status.strip()) if success else False

        return {
            'configured': True,
            'path': str(self.config_repo_path),
            'branch': branch,
            'remote': remote,
            'has_uncommitted_changes': has_changes
        }

    def setup_repo(self, remote_url: str = None) -> Tuple[bool, str]:
        """Set up the config repository if it doesn't exist."""
        try:
            if self.is_repo_configured():
                return True, "Repository already configured"

            # Create directory
            self.config_repo_path.mkdir(parents=True, exist_ok=True)

            # Initialize git repo
            success, msg = self._run_git_command(['init'])
            if not success:
                return False, f"Failed to initialize repository: {msg}"

            # Create billing data directory
            billing_dir = self.config_repo_path / 'billing'
            billing_dir.mkdir(exist_ok=True)

            # Create README
            readme_path = self.config_repo_path / 'README.md'
            readme_path.write_text(
                "# OCRMill Configuration\n\n"
                "This repository contains billing and configuration data for OCRMill.\n\n"
                "## Contents\n\n"
                "- `billing/` - Billing records exported from OCRMill\n"
            )

            # Initial commit
            self._run_git_command(['add', '.'])
            self._run_git_command(['commit', '-m', 'Initial OCRMill config repository'])

            # Set up remote if provided
            if remote_url:
                success, msg = self._run_git_command(['remote', 'add', 'origin', remote_url])
                if not success:
                    logger.warning(f"Failed to add remote: {msg}")

            logger.info(f"Config repository initialized at {self.config_repo_path}")
            return True, f"Repository created at {self.config_repo_path}"

        except Exception as e:
            return False, f"Failed to set up repository: {e}"

    def export_billing_data(self, days: int = 90) -> Tuple[bool, str]:
        """Export billing data to the config repository."""
        if not self.is_repo_configured():
            return False, "Repository not configured"

        try:
            billing_dir = self.config_repo_path / 'billing'
            billing_dir.mkdir(exist_ok=True)

            # Get machine ID for unique filename
            machine_id = self.billing_manager.get_machine_id()[:8]

            # Export JSON
            json_data = self.billing_manager.export_to_json(days=days)
            json_filename = f"billing_{machine_id}_{datetime.now().strftime('%Y%m%d')}.json"
            json_path = billing_dir / json_filename

            json_path.write_text(json_data, encoding='utf-8')

            # Also update a latest.json file
            latest_path = billing_dir / f'billing_{machine_id}_latest.json'
            latest_path.write_text(json_data, encoding='utf-8')

            logger.info(f"Billing data exported to {json_path}")
            return True, f"Exported to {json_filename}"

        except Exception as e:
            return False, f"Failed to export billing data: {e}"

    def sync_to_github(self, commit_message: str = None) -> Tuple[bool, str]:
        """Sync billing data to GitHub repository."""
        if not self.is_repo_configured():
            return False, "Repository not configured"

        try:
            # Export latest billing data
            success, msg = self.export_billing_data()
            if not success:
                return False, msg

            # Stage changes
            success, msg = self._run_git_command(['add', '-A'])
            if not success:
                return False, f"Failed to stage changes: {msg}"

            # Check if there are changes to commit
            success, status = self._run_git_command(['status', '--porcelain'])
            if not status.strip():
                return True, "No changes to sync"

            # Commit
            if not commit_message:
                commit_message = f"OCRMill billing sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            success, msg = self._run_git_command(['commit', '-m', commit_message])
            if not success:
                # Check if it's just "nothing to commit"
                if 'nothing to commit' in msg.lower():
                    return True, "No changes to sync"
                return False, f"Failed to commit: {msg}"

            # Push to remote
            success, msg = self._run_git_command(['push', '-u', 'origin', 'HEAD'])
            if not success:
                # Try without -u flag
                success, msg = self._run_git_command(['push'])
                if not success:
                    return False, f"Failed to push: {msg}"

            logger.info("Billing data synced to GitHub successfully")
            return True, "Billing data synced to GitHub"

        except Exception as e:
            return False, f"Sync failed: {e}"

    def pull_latest(self) -> Tuple[bool, str]:
        """Pull latest changes from remote repository."""
        if not self.is_repo_configured():
            return False, "Repository not configured"

        success, msg = self._run_git_command(['pull'])
        if success:
            return True, "Successfully pulled latest changes"
        else:
            return False, f"Failed to pull: {msg}"

    def get_sync_enabled(self) -> bool:
        """Check if billing sync is enabled in settings."""
        enabled = self.db.get_app_config('billing_sync_enabled')
        return enabled == 'true' if enabled else False

    def set_sync_enabled(self, enabled: bool) -> None:
        """Enable or disable billing sync."""
        self.db.set_app_config('billing_sync_enabled', 'true' if enabled else 'false')

    def get_last_sync_time(self) -> Optional[str]:
        """Get the last sync timestamp."""
        return self.db.get_app_config('billing_last_sync')

    def update_last_sync_time(self) -> None:
        """Update the last sync timestamp to now."""
        self.db.set_app_config('billing_last_sync', datetime.now().isoformat())
