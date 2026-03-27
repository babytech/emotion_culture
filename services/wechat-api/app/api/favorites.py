from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.feature_flags import is_retention_favorites_enabled
from app.core.user_identity import resolve_user_id
from app.schemas.favorites import (
    FavoriteDeleteResponse,
    FavoriteListResponse,
    FavoriteStatusResponse,
    FavoriteType,
    FavoriteUpsertRequest,
    FavoriteUpsertResponse,
)
from app.services.favorites_service import (
    add_or_update_user_favorite,
    clear_user_favorites,
    get_user_favorite_status,
    list_user_favorites,
    remove_user_favorite,
)


router = APIRouter()


def _ensure_favorites_enabled() -> None:
    if is_retention_favorites_enabled():
        return
    raise HTTPException(
        status_code=503,
        detail="[RETENTION_FAVORITES_DISABLED] 收藏功能未开启，请联系管理员。",
    )


@router.get("/favorites", response_model=FavoriteListResponse)
def list_favorites(
    request: Request,
    favorite_type: Optional[FavoriteType] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> FavoriteListResponse:
    _ensure_favorites_enabled()
    user_id = resolve_user_id(request=request)
    return list_user_favorites(
        user_id=user_id,
        favorite_type=favorite_type,
        limit=limit,
        offset=offset,
    )


@router.get("/favorites/status", response_model=FavoriteStatusResponse)
def favorite_status(
    request: Request,
    favorite_type: FavoriteType = Query(...),
    target_id: str = Query(..., min_length=1, max_length=128),
) -> FavoriteStatusResponse:
    _ensure_favorites_enabled()
    user_id = resolve_user_id(request=request)
    return get_user_favorite_status(user_id=user_id, favorite_type=favorite_type, target_id=target_id)


@router.post("/favorites", response_model=FavoriteUpsertResponse)
def upsert_favorite(payload: FavoriteUpsertRequest, request: Request) -> FavoriteUpsertResponse:
    _ensure_favorites_enabled()
    user_id = resolve_user_id(request=request)
    try:
        return add_or_update_user_favorite(user_id=user_id, payload=payload)
    except ValueError as exc:
        message = str(exc)
        if "[RETENTION_WRITE_DISABLED]" in message:
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.delete("/favorites/{favorite_id}", response_model=FavoriteDeleteResponse)
def delete_favorite(favorite_id: str, request: Request) -> FavoriteDeleteResponse:
    _ensure_favorites_enabled()
    user_id = resolve_user_id(request=request)
    result = remove_user_favorite(user_id=user_id, favorite_id=favorite_id)
    if not result.success:
        raise HTTPException(status_code=404, detail="favorite item not found")
    return result


@router.delete("/favorites", response_model=FavoriteDeleteResponse)
def clear_favorites(
    request: Request,
    favorite_type: Optional[FavoriteType] = Query(default=None),
) -> FavoriteDeleteResponse:
    _ensure_favorites_enabled()
    user_id = resolve_user_id(request=request)
    return clear_user_favorites(user_id=user_id, favorite_type=favorite_type)
