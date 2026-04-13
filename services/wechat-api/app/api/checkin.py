from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_identity
from app.schemas.checkin import CheckinSignResponse, CheckinStatusResponse
from app.services.checkin_service import get_checkin_status, sign_in_today


router = APIRouter()


def _resolve_required_user_id(request: Request) -> str:
    identity = resolve_user_identity(request=request)
    if identity.user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="CHECKIN_USER_REQUIRED: please call with x-wx-openid or x-wx-unionid identity",
        )
    return identity.user_id


@router.get("/checkin/status", response_model=CheckinStatusResponse)
def checkin_status(request: Request) -> CheckinStatusResponse:
    user_id = _resolve_required_user_id(request)
    return get_checkin_status(user_id=user_id)


@router.post("/checkin/sign", response_model=CheckinSignResponse)
def checkin_sign(request: Request) -> CheckinSignResponse:
    user_id = _resolve_required_user_id(request)
    return sign_in_today(user_id=user_id)
