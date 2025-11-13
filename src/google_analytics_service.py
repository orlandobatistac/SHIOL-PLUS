"""
Google Analytics 4 Data API Integration
Fetches real-time and historical analytics data from GA4
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunRealtimeReportRequest,
    RunReportRequest
)
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GoogleAnalyticsService:
    """Service to fetch analytics data from Google Analytics 4"""
    
    def __init__(self):
        self.property_id = os.getenv("GA4_PROPERTY_ID")
        self.credentials_path = os.getenv("GA4_CREDENTIALS_PATH", "config/ga4-credentials.json")
        self.client = None
        
        if self.property_id and os.path.exists(self.credentials_path):
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
                self.client = BetaAnalyticsDataClient(credentials=credentials)
                logger.info("Google Analytics 4 client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GA4 client: {e}")
                self.client = None
        else:
            logger.warning("GA4_PROPERTY_ID or credentials file not found. Analytics disabled.")
    
    def is_enabled(self) -> bool:
        """Check if GA4 integration is enabled"""
        return self.client is not None
    
    def get_realtime_stats(self) -> Dict[str, Any]:
        """
        Get real-time analytics (last 30 minutes)
        Returns: active users, pageviews, events
        """
        if not self.is_enabled():
            return self._get_fallback_stats()
        
        try:
            request = RunRealtimeReportRequest(
                property=f"properties/{self.property_id}",
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="screenPageViews"),
                ],
            )
            
            response = self.client.run_realtime_report(request)
            
            if response.row_count > 0:
                row = response.rows[0]
                return {
                    "active_users": int(row.metric_values[0].value),
                    "pageviews_30min": int(row.metric_values[1].value),
                }
            
            return {"active_users": 0, "pageviews_30min": 0}
            
        except Exception as e:
            logger.error(f"Error fetching realtime stats: {e}")
            return {"active_users": 0, "pageviews_30min": 0}
    
    def get_traffic_stats(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Get traffic statistics for the last N days
        
        Args:
            days_back: Number of days to look back (default 7)
            
        Returns:
            Dictionary with traffic metrics
        """
        if not self.is_enabled():
            return self._get_fallback_stats()
        
        try:
            # Date range
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                metrics=[
                    Metric(name="totalUsers"),           # Unique visitors
                    Metric(name="sessions"),             # Total sessions
                    Metric(name="screenPageViews"),      # Total pageviews
                    Metric(name="averageSessionDuration"), # Avg session duration (seconds)
                    Metric(name="screenPageViewsPerSession"), # Pages per session
                    Metric(name="newUsers"),             # New visitors
                ],
            )
            
            response = self.client.run_report(request)
            
            if response.row_count > 0:
                row = response.rows[0]
                
                return {
                    "unique_visitors": int(float(row.metric_values[0].value)),
                    "total_sessions": int(float(row.metric_values[1].value)),
                    "total_pageviews": int(float(row.metric_values[2].value)),
                    "avg_session_duration_sec": int(float(row.metric_values[3].value)),
                    "pages_per_session": round(float(row.metric_values[4].value), 1),
                    "new_visitors": int(float(row.metric_values[5].value)),
                    "period_days": days_back,
                }
            
            return self._get_fallback_stats()
            
        except Exception as e:
            logger.error(f"Error fetching traffic stats: {e}")
            return self._get_fallback_stats()
    
    def get_daily_breakdown(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Get daily traffic breakdown for charts
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of daily stats with date, sessions, and unique visitors
        """
        if not self.is_enabled():
            return {"daily_stats": []}
        
        try:
            start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                ],
                order_bys=[{"dimension": {"dimension_name": "date"}}]
            )
            
            response = self.client.run_report(request)
            
            daily_stats = []
            for row in response.rows:
                date_str = row.dimension_values[0].value  # Format: YYYYMMDD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                daily_stats.append({
                    "date": formatted_date,
                    "sessions": int(float(row.metric_values[0].value)),
                    "unique_visitors": int(float(row.metric_values[1].value)),
                })
            
            return {"daily_stats": daily_stats}
            
        except Exception as e:
            logger.error(f"Error fetching daily breakdown: {e}")
            return {"daily_stats": []}
    
    def get_device_breakdown(self) -> Dict[str, Any]:
        """Get traffic breakdown by device type (mobile, desktop, tablet)"""
        if not self.is_enabled():
            return {"devices": {}}
        
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
                dimensions=[Dimension(name="deviceCategory")],
                metrics=[Metric(name="sessions")],
            )
            
            response = self.client.run_report(request)
            
            devices = {}
            for row in response.rows:
                device = row.dimension_values[0].value
                sessions = int(float(row.metric_values[0].value))
                devices[device.lower()] = sessions
            
            return {"devices": devices}
            
        except Exception as e:
            logger.error(f"Error fetching device breakdown: {e}")
            return {"devices": {}}
    
    def _get_fallback_stats(self) -> Dict[str, Any]:
        """Return default stats when GA4 is not available"""
        return {
            "unique_visitors": 0,
            "total_sessions": 0,
            "total_pageviews": 0,
            "avg_session_duration_sec": 0,
            "pages_per_session": 0.0,
            "new_visitors": 0,
            "period_days": 7,
        }


# Singleton instance
_ga_service = None

def get_ga_service() -> GoogleAnalyticsService:
    """Get or create GoogleAnalyticsService singleton"""
    global _ga_service
    if _ga_service is None:
        _ga_service = GoogleAnalyticsService()
    return _ga_service
