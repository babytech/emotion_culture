from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.feature_flags import is_retention_service_enabled, is_retention_weekly_report_enabled
from app.core.user_identity import resolve_user_id
from app.schemas.retention import CalendarOverviewResponse, WeeklyReportResponse
from app.services.report_service import build_user_weekly_report
from app.services.retention_service import get_user_calendar_overview


router = APIRouter()


@router.get("/retention/calendar", response_model=CalendarOverviewResponse)
def retention_calendar(
    request: Request,
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
) -> CalendarOverviewResponse:
    if not is_retention_service_enabled():
        raise HTTPException(
            status_code=503,
            detail="[RETENTION_SERVICE_DISABLED] 留存功能未开启，请联系管理员。",
        )
    user_id = resolve_user_id(request=request)
    try:
        return get_user_calendar_overview(user_id=user_id, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/retention/weekly-report", response_model=WeeklyReportResponse)
def retention_weekly_report(
    request: Request,
    week_start: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
) -> WeeklyReportResponse:
    if not is_retention_weekly_report_enabled():
        raise HTTPException(
            status_code=503,
            detail="[RETENTION_WEEKLY_REPORT_DISABLED] 周报功能未开启，请联系管理员。",
        )
    user_id = resolve_user_id(request=request)
    try:
        return build_user_weekly_report(user_id=user_id, week_start=week_start)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
