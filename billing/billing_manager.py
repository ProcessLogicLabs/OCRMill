"""
OCRMill Billing Manager

Handles billing records tracking, duplicate prevention, and invoice management.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from parts_database import PartsDatabase

logger = logging.getLogger(__name__)


class BillingManager:
    """Manages billing records for OCRMill usage."""

    def __init__(self, db: PartsDatabase):
        self.db = db

    def get_machine_id(self) -> str:
        """Get machine ID from license manager."""
        from licensing.license_manager import LicenseManager
        license_mgr = LicenseManager(self.db)
        return license_mgr.get_machine_id()

    def record_processing(self, file_number: str, file_name: str, line_count: int,
                         total_value: float, hts_codes_used: List[str],
                         user_name: str, processing_time_ms: int) -> Dict:
        """
        Record a billable processing event.

        Returns dict with:
            - success: bool
            - message: str
            - was_duplicate: bool
            - record_id: int (if new record created)
        """
        # Check for duplicate
        if self.db.is_file_already_billed(file_number):
            # Record the duplicate attempt
            self.db.record_duplicate_attempt(
                file_number=file_number,
                user_name=user_name,
                machine_id=self.get_machine_id()
            )

            # Log audit event
            self.db.log_export_event(
                event_type='duplicate_billing_attempt',
                file_number=file_number,
                user_name=user_name,
                machine_id=self.get_machine_id(),
                success=False,
                failure_reason='File already billed'
            )

            logger.warning(f"Duplicate billing attempt for file: {file_number}")
            return {
                'success': False,
                'message': f'File {file_number} has already been billed',
                'was_duplicate': True
            }

        # Convert HTS codes list to string
        hts_codes_str = ','.join(hts_codes_used) if hts_codes_used else ''

        # Record the billing event
        try:
            record_id = self.db.add_billing_record(
                file_number=file_number,
                file_name=file_name,
                line_count=line_count,
                total_value=total_value,
                hts_codes_used=hts_codes_str,
                user_name=user_name,
                machine_id=self.get_machine_id(),
                processing_time_ms=processing_time_ms
            )

            # Log audit event
            self.db.log_export_event(
                event_type='billing_record_created',
                file_number=file_number,
                user_name=user_name,
                machine_id=self.get_machine_id(),
                success=True
            )

            logger.info(f"Billing record created: {file_number} (ID: {record_id})")
            return {
                'success': True,
                'message': f'Billing record created for {file_number}',
                'was_duplicate': False,
                'record_id': record_id
            }

        except Exception as e:
            logger.error(f"Failed to create billing record: {e}")
            self.db.log_export_event(
                event_type='billing_record_failed',
                file_number=file_number,
                user_name=user_name,
                machine_id=self.get_machine_id(),
                success=False,
                failure_reason=str(e)
            )
            return {
                'success': False,
                'message': f'Failed to create billing record: {e}',
                'was_duplicate': False
            }

    def is_already_billed(self, file_number: str) -> bool:
        """Check if a file number has already been billed."""
        return self.db.is_file_already_billed(file_number)

    def get_billing_records(self, start_date: Optional[str] = None,
                           end_date: Optional[str] = None,
                           invoice_month: Optional[str] = None) -> List[Dict]:
        """Get billing records with optional filtering."""
        return self.db.get_billing_records(
            start_date=start_date,
            end_date=end_date,
            invoice_month=invoice_month
        )

    def get_monthly_summary(self, year: int, month: int) -> Dict:
        """Get billing summary for a specific month."""
        summary = self.db.get_monthly_billing_summary(year, month)

        # Get additional stats
        invoice_month = f"{year:04d}-{month:02d}"
        records = self.get_billing_records(invoice_month=invoice_month)

        # Calculate unique HTS codes
        all_hts = set()
        for record in records:
            if record.get('hts_codes_used'):
                for code in record['hts_codes_used'].split(','):
                    if code.strip():
                        all_hts.add(code.strip())

        summary['unique_hts_codes'] = len(all_hts)
        summary['records'] = records

        return summary

    def get_current_month_summary(self) -> Dict:
        """Get billing summary for the current month."""
        now = datetime.now()
        return self.get_monthly_summary(now.year, now.month)

    def mark_invoiced(self, year: int, month: int) -> int:
        """Mark all records for a month as invoiced. Returns count updated."""
        invoice_month = f"{year:04d}-{month:02d}"
        count = self.db.mark_invoiced(invoice_month)
        logger.info(f"Marked {count} records as invoiced for {invoice_month}")
        return count

    def get_uninvoiced_months(self) -> List[str]:
        """Get list of months with uninvoiced records."""
        records = self.db.get_billing_records()
        months = set()
        for record in records:
            if not record.get('invoice_sent'):
                if record.get('invoice_month'):
                    months.add(record['invoice_month'])
        return sorted(list(months))

    def export_to_csv(self, output_path: Path, start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> int:
        """Export billing records to CSV. Returns record count."""
        records = self.get_billing_records(start_date=start_date, end_date=end_date)

        if not records:
            return 0

        fieldnames = [
            'id', 'file_number', 'export_date', 'export_time', 'file_name',
            'line_count', 'total_value', 'hts_codes_used', 'user_name',
            'machine_id', 'processing_time_ms', 'invoice_sent', 'invoice_month'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)

        logger.info(f"Exported {len(records)} billing records to {output_path}")
        return len(records)

    def export_to_json(self, days: int = 90) -> str:
        """Export recent billing data as JSON string."""
        from datetime import timedelta

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        records = self.get_billing_records(start_date=start_date, end_date=end_date)

        export_data = {
            'application': 'OCRMill',
            'export_date': datetime.now().isoformat(),
            'period_start': start_date,
            'period_end': end_date,
            'record_count': len(records),
            'records': records
        }

        return json.dumps(export_data, indent=2, default=str)

    def get_audit_log(self, start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     event_type: Optional[str] = None) -> List[Dict]:
        """Get export audit log with optional filtering."""
        return self.db.get_audit_log(
            start_date=start_date,
            end_date=end_date,
            event_type=event_type
        )

    def get_duplicate_attempts(self, file_number: Optional[str] = None) -> List[Dict]:
        """Get duplicate billing attempts, optionally filtered by file number."""
        query = "SELECT * FROM billing_duplicate_attempts"
        params = []

        if file_number:
            query += " WHERE file_number = ?"
            params.append(file_number)

        query += " ORDER BY attempt_date DESC, attempt_time DESC"

        cursor = self.db.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_all_time_totals(self) -> Dict:
        """Get all-time billing totals."""
        cursor = self.db.conn.execute("""
            SELECT
                COUNT(*) as total_files,
                SUM(line_count) as total_lines,
                SUM(total_value) as total_value,
                COUNT(DISTINCT user_name) as unique_users,
                COUNT(DISTINCT invoice_month) as months_billed,
                MIN(export_date) as first_export,
                MAX(export_date) as last_export
            FROM billing_records
        """)
        row = cursor.fetchone()
        return {
            'total_files': row['total_files'] or 0,
            'total_lines': row['total_lines'] or 0,
            'total_value': row['total_value'] or 0.0,
            'unique_users': row['unique_users'] or 0,
            'months_billed': row['months_billed'] or 0,
            'first_export': row['first_export'],
            'last_export': row['last_export']
        }
