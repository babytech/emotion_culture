from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_identity
from app.schemas.auth import BindWechatPhoneRequest, BindWechatPhoneResponse
from app.services.wechat_auth_service import exchange_wechat_phone_code


router = APIRouter()


@router.post("/auth/wechat-phone", response_model=BindWechatPhoneResponse)
def bind_wechat_phone(payload: BindWechatPhoneRequest, request: Request) -> BindWechatPhoneResponse:
    identity = resolve_user_identity(request=request)
    if identity.identity_type == "anonymous":
        raise HTTPException(status_code=401, detail="WECHAT_IDENTITY_REQUIRED: 请在微信小程序内重试")

    try:
        phone_info = exchange_wechat_phone_code(payload.code)
    except ValueError as exc:
        message = str(exc)
        if "missing required env var" in message or "failed to get access token" in message or "ssl verify failed" in message:
            raise HTTPException(status_code=503, detail="微信手机号服务暂不可用，请稍后重试") from exc
        raise HTTPException(status_code=400, detail=message or "微信绑定号码失败，请稍后重试") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="微信手机号服务暂不可用，请稍后重试") from exc

    return BindWechatPhoneResponse(
        identity_type=identity.identity_type,
        openid_present=bool(identity.openid),
        unionid_present=bool(identity.unionid),
        phone_bound=True,
        masked_phone_number=phone_info["masked_phone_number"],
        phone_tail=phone_info["phone_tail"],
        country_code=phone_info["country_code"],
    )
