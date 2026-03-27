from typing import Optional

from app.schemas.retention import CalendarOverviewResponse
from app.services.history_service import get_calendar_overview


def get_user_calendar_overview(user_id: str, month: Optional[str] = None) -> CalendarOverviewResponse:
    return get_calendar_overview(user_id=user_id, month=month)
