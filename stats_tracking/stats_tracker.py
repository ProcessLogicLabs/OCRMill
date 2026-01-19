"""
OCRMill Statistics Tracker

Tracks usage events and provides processing statistics.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from parts_database import PartsDatabase

logger = logging.getLogger(__name__)


# Event types for tracking
class EventTypes:
    """Standard event types for statistics tracking."""
    PDF_PROCESSED = 'pdf_processed'
    PDF_FAILED = 'pdf_failed'
    ITEMS_EXTRACTED = 'items_extracted'
    TEMPLATE_USED = 'template_used'
    HTS_LOOKUP = 'hts_lookup'
    HTS_MATCH_FOUND = 'hts_match_found'
    HTS_MATCH_FAILED = 'hts_match_failed'
    EXPORT_COMPLETED = 'export_completed'
    EXPORT_FAILED = 'export_failed'
    CBP_EXPORT = 'cbp_export'
    APP_STARTED = 'app_started'
    APP_CLOSED = 'app_closed'
    USER_LOGIN = 'user_login'
    USER_LOGOUT = 'user_logout'
    SETTINGS_CHANGED = 'settings_changed'
    DATABASE_QUERY = 'database_query'


class StatisticsTracker:
    """Tracks usage events and provides processing statistics."""

    def __init__(self, db: PartsDatabase):
        self.db = db

    def track_event(self, event_type: str, event_data: Dict = None,
                   user_name: str = None) -> None:
        """
        Track a usage event.

        Args:
            event_type: Type of event (use EventTypes constants)
            event_data: Optional dictionary with event details
            user_name: Optional user name for the event
        """
        try:
            data_str = json.dumps(event_data) if event_data else '{}'
            self.db.track_event(
                event_type=event_type,
                event_data=data_str,
                user_name=user_name
            )
            logger.debug(f"Tracked event: {event_type}")
        except Exception as e:
            logger.warning(f"Failed to track event {event_type}: {e}")

    def track_pdf_processed(self, file_name: str, page_count: int,
                           items_extracted: int, user_name: str = None) -> None:
        """Track a PDF processing event."""
        self.track_event(
            EventTypes.PDF_PROCESSED,
            {
                'file_name': file_name,
                'page_count': page_count,
                'items_extracted': items_extracted
            },
            user_name
        )

    def track_pdf_failed(self, file_name: str, error: str,
                        user_name: str = None) -> None:
        """Track a failed PDF processing attempt."""
        self.track_event(
            EventTypes.PDF_FAILED,
            {
                'file_name': file_name,
                'error': error
            },
            user_name
        )

    def track_template_used(self, template_name: str, file_name: str,
                           user_name: str = None) -> None:
        """Track template usage."""
        self.track_event(
            EventTypes.TEMPLATE_USED,
            {
                'template_name': template_name,
                'file_name': file_name
            },
            user_name
        )

    def track_hts_lookup(self, part_number: str, found: bool,
                        hts_code: str = None, user_name: str = None) -> None:
        """Track an HTS code lookup."""
        event_type = EventTypes.HTS_MATCH_FOUND if found else EventTypes.HTS_MATCH_FAILED
        self.track_event(
            event_type,
            {
                'part_number': part_number,
                'hts_code': hts_code
            },
            user_name
        )

    def track_export(self, export_type: str, file_count: int, item_count: int,
                    success: bool, user_name: str = None) -> None:
        """Track an export event."""
        event_type = EventTypes.EXPORT_COMPLETED if success else EventTypes.EXPORT_FAILED
        self.track_event(
            event_type,
            {
                'export_type': export_type,
                'file_count': file_count,
                'item_count': item_count
            },
            user_name
        )

    def get_event_counts(self, days: int = 30) -> Dict[str, int]:
        """Get counts by event type for the specified period."""
        return self.db.get_event_counts(days=days)

    def get_usage_statistics(self, event_type: str = None,
                            days: int = 30) -> List[Dict]:
        """Get usage statistics with optional filtering."""
        return self.db.get_usage_statistics(event_type=event_type, days=days)

    def get_processing_stats(self, days: int = 30) -> Dict:
        """Get comprehensive processing statistics for the period."""
        counts = self.get_event_counts(days)

        # Calculate success rate
        pdfs_processed = counts.get(EventTypes.PDF_PROCESSED, 0)
        pdfs_failed = counts.get(EventTypes.PDF_FAILED, 0)
        total_attempts = pdfs_processed + pdfs_failed
        success_rate = (pdfs_processed / total_attempts * 100) if total_attempts > 0 else 0

        # Calculate HTS match rate
        hts_found = counts.get(EventTypes.HTS_MATCH_FOUND, 0)
        hts_failed = counts.get(EventTypes.HTS_MATCH_FAILED, 0)
        total_lookups = hts_found + hts_failed
        hts_match_rate = (hts_found / total_lookups * 100) if total_lookups > 0 else 0

        return {
            'period_days': days,
            'pdfs_processed': pdfs_processed,
            'pdfs_failed': pdfs_failed,
            'total_attempts': total_attempts,
            'success_rate': round(success_rate, 1),
            'exports_completed': counts.get(EventTypes.EXPORT_COMPLETED, 0),
            'exports_failed': counts.get(EventTypes.EXPORT_FAILED, 0),
            'cbp_exports': counts.get(EventTypes.CBP_EXPORT, 0),
            'hts_lookups': total_lookups,
            'hts_matches_found': hts_found,
            'hts_match_rate': round(hts_match_rate, 1),
            'app_starts': counts.get(EventTypes.APP_STARTED, 0),
            'user_logins': counts.get(EventTypes.USER_LOGIN, 0),
        }

    def get_template_usage(self, days: int = 30) -> Dict[str, int]:
        """Get template usage counts for the period."""
        events = self.get_usage_statistics(
            event_type=EventTypes.TEMPLATE_USED,
            days=days
        )

        template_counts = {}
        for event in events:
            try:
                data = json.loads(event.get('event_data', '{}'))
                template = data.get('template_name', 'Unknown')
                template_counts[template] = template_counts.get(template, 0) + 1
            except Exception:
                pass

        return template_counts

    def get_user_statistics(self, days: int = 30) -> Dict[str, Dict]:
        """Get per-user statistics for the period."""
        events = self.get_usage_statistics(days=days)

        user_stats = {}
        for event in events:
            user = event.get('user_name') or 'Unknown'
            if user not in user_stats:
                user_stats[user] = {
                    'event_count': 0,
                    'pdfs_processed': 0,
                    'exports': 0,
                    'last_activity': None
                }

            user_stats[user]['event_count'] += 1

            event_type = event.get('event_type')
            if event_type == EventTypes.PDF_PROCESSED:
                user_stats[user]['pdfs_processed'] += 1
            elif event_type == EventTypes.EXPORT_COMPLETED:
                user_stats[user]['exports'] += 1

            # Track last activity
            timestamp = event.get('timestamp')
            if timestamp:
                if (user_stats[user]['last_activity'] is None or
                    timestamp > user_stats[user]['last_activity']):
                    user_stats[user]['last_activity'] = timestamp

        return user_stats

    def get_daily_activity(self, days: int = 30) -> List[Dict]:
        """Get daily activity counts for the period."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor = self.db.conn.execute("""
            SELECT
                DATE(timestamp) as activity_date,
                COUNT(*) as event_count,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as pdfs_processed,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as exports
            FROM usage_statistics
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY activity_date DESC
        """, (EventTypes.PDF_PROCESSED, EventTypes.EXPORT_COMPLETED, cutoff_date))

        return [dict(row) for row in cursor.fetchall()]

    def get_all_time_totals(self) -> Dict:
        """Get all-time statistics totals."""
        cursor = self.db.conn.execute("""
            SELECT
                COUNT(*) as total_events,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as total_pdfs,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as total_exports,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as total_cbp_exports,
                COUNT(CASE WHEN event_type = ? THEN 1 END) as hts_matches,
                COUNT(DISTINCT user_name) as unique_users,
                MIN(timestamp) as first_event,
                MAX(timestamp) as last_event
            FROM usage_statistics
        """, (EventTypes.PDF_PROCESSED, EventTypes.EXPORT_COMPLETED,
              EventTypes.CBP_EXPORT, EventTypes.HTS_MATCH_FOUND))

        row = cursor.fetchone()
        return {
            'total_events': row['total_events'] or 0,
            'total_pdfs': row['total_pdfs'] or 0,
            'total_exports': row['total_exports'] or 0,
            'total_cbp_exports': row['total_cbp_exports'] or 0,
            'hts_matches': row['hts_matches'] or 0,
            'unique_users': row['unique_users'] or 0,
            'first_event': row['first_event'],
            'last_event': row['last_event'],
            'tracking_since': row['first_event']
        }

    def get_recent_activity(self, limit: int = 20) -> List[Dict]:
        """Get the most recent activity events."""
        cursor = self.db.conn.execute("""
            SELECT event_type, event_data, user_name, timestamp
            FROM usage_statistics
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        events = []
        for row in cursor.fetchall():
            event = dict(row)
            try:
                event['event_data'] = json.loads(event['event_data'])
            except Exception:
                pass
            events.append(event)

        return events

    def cleanup_old_events(self, days_to_keep: int = 365) -> int:
        """Remove events older than specified days. Returns count deleted."""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

        cursor = self.db.conn.execute(
            "DELETE FROM usage_statistics WHERE timestamp < ?",
            (cutoff_date,)
        )
        self.db.conn.commit()

        count = cursor.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} old statistics events")
        return count
