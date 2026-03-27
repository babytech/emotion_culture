from typing import Optional

from app.schemas.retention import WeeklyReportResponse
from app.services.history_service import get_weekly_report


def build_user_weekly_report(user_id: str, week_start: Optional[str] = None) -> WeeklyReportResponse:
    return get_weekly_report(user_id=user_id, week_start=week_start)
