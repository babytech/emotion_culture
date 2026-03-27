from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.user_identity import resolve_user_id
from app.schemas.favorites import FavoriteType
from app.schemas.retention import (
    RetentionDeleteResponse,
    RetentionWriteSettingsResponse,
    RetentionWriteSettingsUpdateRequest,
)
from app.services.favorites_service import clear_user_favorites
from app.services.history_service import (
    clear_weekly_report_snapshots,
    delete_weekly_report_snapshot,
    get_user_settings,
    update_user_save_history,
)


router = APIRouter()


def _map_write_settings(write_enabled: bool, updated_at: Optional[str]) -> RetentionWriteSettingsResponse:
    return RetentionWriteSettingsResponse(
        write_enabled=bool(write_enabled),
        updated_at=updated_at,
    )


@router.get("/retention/write-settings", response_model=RetentionWriteSettingsResponse)
def get_retention_write_settings(request: Request) -> RetentionWriteSettingsResponse:
    user_id = resolve_user_id(request=request)
    settings = get_user_settings(user_id=user_id)
    return _map_write_settings(write_enabled=settings.save_history, updated_at=settings.updated_at)


@router.put("/retention/write-settings", response_model=RetentionWriteSettingsResponse)
def update_retention_write_settings(
    payload: RetentionWriteSettingsUpdateRequest,
    request: Request,
) -> RetentionWriteSettingsResponse:
    user_id = resolve_user_id(request=request)
    settings = update_user_save_history(user_id=user_id, save_history=payload.write_enabled)
    return _map_write_settings(write_enabled=settings.save_history, updated_at=settings.updated_at)


@router.delete("/retention/weekly-report", response_model=RetentionDeleteResponse)
def delete_retention_weekly_report(
    request: Request,
    week_start: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
) -> RetentionDeleteResponse:
    user_id = resolve_user_id(request=request)
    try:
        deleted = delete_weekly_report_snapshot(user_id=user_id, week_start=week_start)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RetentionDeleteResponse(
        success=True,
        deleted_count=deleted,
        message="已删除周报快照。" if deleted > 0 else "未找到可删除的周报快照。",
    )


@router.delete("/retention/weekly-reports", response_model=RetentionDeleteResponse)
def clear_retention_weekly_reports(request: Request) -> RetentionDeleteResponse:
    user_id = resolve_user_id(request=request)
    deleted = clear_weekly_report_snapshots(user_id=user_id)
    return RetentionDeleteResponse(
        success=True,
        deleted_count=deleted,
        message="已清空周报快照。" if deleted > 0 else "周报快照已为空。",
    )


@router.delete("/retention/favorites", response_model=RetentionDeleteResponse)
def clear_retention_favorites(
    request: Request,
    favorite_type: Optional[FavoriteType] = Query(default=None),
) -> RetentionDeleteResponse:
    user_id = resolve_user_id(request=request)
    result = clear_user_favorites(user_id=user_id, favorite_type=favorite_type)
    return RetentionDeleteResponse(
        success=bool(result.success),
        deleted_count=int(result.deleted_count or 0),
        message=result.message,
    )
