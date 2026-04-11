from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.feature_flags import is_today_history_enabled
from app.schemas.today_history import TodayHistoryResponse
from app.services.today_history_service import get_today_history


router = APIRouter()


@router.get("/today-history", response_model=TodayHistoryResponse)
def read_today_history(
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
) -> TodayHistoryResponse:
    if not is_today_history_enabled():
        raise HTTPException(
            status_code=503,
            detail="[TODAY_HISTORY_DISABLED] 历史上的今天功能未开启，请联系管理员。",
        )
    try:
        return get_today_history(date_value=date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
