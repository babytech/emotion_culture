from fastapi import APIRouter, HTTPException, Query, Request

from app.core.user_identity import resolve_user_id
from app.schemas.history import (
    DeleteHistoryResponse,
    HistoryDetailResponse,
    HistoryListResponse,
    HistoryTimelineResponse,
    HistoryTimelineType,
)
from app.services.history_service import (
    clear_history_summaries,
    delete_history_summary,
    get_history_detail,
    list_history_timeline,
    list_history_summaries,
)


router = APIRouter()


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HistoryListResponse:
    user_id = resolve_user_id(request=request)
    return list_history_summaries(user_id=user_id, limit=limit, offset=offset)


@router.get("/history/timeline", response_model=HistoryTimelineResponse)
def list_history_timeline_items(
    request: Request,
    type: HistoryTimelineType = Query(default=HistoryTimelineType.ALL),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> HistoryTimelineResponse:
    user_id = resolve_user_id(request=request)
    return list_history_timeline(user_id=user_id, timeline_type=type, limit=limit, offset=offset)


@router.get("/history/{history_id}", response_model=HistoryDetailResponse)
def get_history(history_id: str, request: Request) -> HistoryDetailResponse:
    user_id = resolve_user_id(request=request)
    detail = get_history_detail(user_id=user_id, history_id=history_id)
    if not detail:
        raise HTTPException(status_code=404, detail="history item not found")
    return detail


@router.delete("/history/{history_id}", response_model=DeleteHistoryResponse)
def delete_history(history_id: str, request: Request) -> DeleteHistoryResponse:
    user_id = resolve_user_id(request=request)
    deleted = delete_history_summary(user_id=user_id, history_id=history_id)
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="history item not found")
    return DeleteHistoryResponse(
        success=True,
        deleted_count=deleted,
        message="已删除历史记录。",
    )


@router.delete("/history", response_model=DeleteHistoryResponse)
def clear_history(request: Request) -> DeleteHistoryResponse:
    user_id = resolve_user_id(request=request)
    deleted = clear_history_summaries(user_id=user_id)
    return DeleteHistoryResponse(
        success=True,
        deleted_count=deleted,
        message="已清空历史记录。",
    )
