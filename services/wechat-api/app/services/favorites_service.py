from typing import Optional

from app.schemas.favorites import (
    FavoriteDeleteResponse,
    FavoriteListResponse,
    FavoriteStatusResponse,
    FavoriteType,
    FavoriteUpsertRequest,
    FavoriteUpsertResponse,
)
from app.services.history_service import (
    clear_favorites,
    delete_favorite,
    get_favorite_status,
    list_favorites,
    upsert_favorite,
)


def list_user_favorites(
    user_id: str,
    favorite_type: Optional[FavoriteType] = None,
    limit: int = 20,
    offset: int = 0,
) -> FavoriteListResponse:
    return list_favorites(user_id=user_id, favorite_type=favorite_type, limit=limit, offset=offset)


def get_user_favorite_status(
    user_id: str,
    favorite_type: FavoriteType,
    target_id: str,
) -> FavoriteStatusResponse:
    return get_favorite_status(user_id=user_id, favorite_type=favorite_type, target_id=target_id)


def add_or_update_user_favorite(user_id: str, payload: FavoriteUpsertRequest) -> FavoriteUpsertResponse:
    return upsert_favorite(user_id=user_id, payload_input=payload)


def remove_user_favorite(user_id: str, favorite_id: str) -> FavoriteDeleteResponse:
    return delete_favorite(user_id=user_id, favorite_id=favorite_id)


def clear_user_favorites(
    user_id: str,
    favorite_type: Optional[FavoriteType] = None,
) -> FavoriteDeleteResponse:
    return clear_favorites(user_id=user_id, favorite_type=favorite_type)
