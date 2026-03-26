from fastapi import APIRouter, Request

from app.core.user_identity import resolve_user_id
from app.schemas.settings import UpdateUserSettingsRequest, UserSettingsResponse
from app.services.history_service import get_user_settings, update_user_save_history


router = APIRouter()


@router.get("/settings", response_model=UserSettingsResponse)
def read_settings(request: Request) -> UserSettingsResponse:
    user_id = resolve_user_id(request=request)
    return get_user_settings(user_id=user_id)


@router.put("/settings", response_model=UserSettingsResponse)
def update_settings(payload: UpdateUserSettingsRequest, request: Request) -> UserSettingsResponse:
    user_id = resolve_user_id(request=request)
    return update_user_save_history(user_id=user_id, save_history=payload.save_history)
