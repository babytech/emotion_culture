from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query, Request

from app.core.feature_flags import (
    is_retention_service_enabled,
    is_retention_weekly_report_enabled,
    is_today_history_enabled,
)
from app.core.user_identity import resolve_user_identity
from app.schemas.dashboard import DashboardOverviewResponse, DashboardSectionResult
from app.services.checkin_service import get_checkin_status
from app.services.favorites_service import list_user_favorites
from app.services.history_service import list_history_summaries
from app.services.report_service import build_user_weekly_report
from app.services.retention_service import get_user_calendar_overview
from app.services.today_history_service import get_today_history


router = APIRouter()


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _to_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            payload = value.model_dump(mode="json")
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
    return {}


def _fulfilled(value: Any) -> DashboardSectionResult:
    return DashboardSectionResult(status="fulfilled", value=_to_payload(value), reason=None)


def _rejected(reason: str) -> DashboardSectionResult:
    return DashboardSectionResult(status="rejected", value=None, reason=(reason or "unknown error").strip())


@router.get("/dashboard/overview", response_model=DashboardOverviewResponse)
def read_dashboard_overview(
    request: Request,
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    history_limit: int = Query(default=5, ge=1, le=20),
    favorites_limit: int = Query(default=2, ge=1, le=20),
) -> DashboardOverviewResponse:
    identity = resolve_user_identity(request=request)
    user_id = identity.user_id

    calendar_result = _rejected("not executed")
    weekly_report_result = _rejected("not executed")
    history_result = _rejected("not executed")
    favorites_result = _rejected("not executed")
    today_history_result = _rejected("not executed")
    checkin_result = _rejected("not executed")

    if is_retention_service_enabled():
        try:
            calendar_result = _fulfilled(get_user_calendar_overview(user_id=user_id, month=month))
        except Exception as exc:
            calendar_result = _rejected(str(exc))
    else:
        calendar_result = _rejected("[RETENTION_SERVICE_DISABLED] 留存功能未开启。")

    if is_retention_weekly_report_enabled():
        try:
            weekly_report_result = _fulfilled(build_user_weekly_report(user_id=user_id, week_start=None))
        except Exception as exc:
            weekly_report_result = _rejected(str(exc))
    else:
        weekly_report_result = _rejected("[RETENTION_WEEKLY_REPORT_DISABLED] 周报功能未开启。")

    try:
        history_result = _fulfilled(list_history_summaries(user_id=user_id, limit=history_limit, offset=0))
    except Exception as exc:
        history_result = _rejected(str(exc))

    try:
        favorites_result = _fulfilled(
            list_user_favorites(user_id=user_id, favorite_type=None, limit=favorites_limit, offset=0)
        )
    except Exception as exc:
        favorites_result = _rejected(str(exc))

    if is_today_history_enabled():
        try:
            today_history_result = _fulfilled(get_today_history(date_value=date))
        except Exception as exc:
            today_history_result = _rejected(str(exc))
    else:
        today_history_result = _rejected("[TODAY_HISTORY_DISABLED] 历史上的今天功能未开启。")

    if user_id == "anonymous":
        checkin_result = _rejected("CHECKIN_USER_REQUIRED: please call with x-wx-openid or x-wx-unionid identity")
    else:
        try:
            checkin_result = _fulfilled(get_checkin_status(user_id=user_id))
        except Exception as exc:
            checkin_result = _rejected(str(exc))

    return DashboardOverviewResponse(
        generated_at=_iso_now_utc(),
        month=(month or "").strip(),
        date=(date or "").strip(),
        calendar=calendar_result,
        weekly_report=weekly_report_result,
        history=history_result,
        favorites=favorites_result,
        today_history=today_history_result,
        checkin=checkin_result,
    )
