from app.services.storage_service import WECHAT_API_BASE, _env_int, _get_access_token, _http_request


def _mask_phone_number(phone_number: str) -> str:
    value = (phone_number or "").strip()
    if len(value) < 7:
        return value
    return f"{value[:3]}****{value[-4:]}"


def exchange_wechat_phone_code(code: str) -> dict[str, str]:
    normalized_code = (code or "").strip()
    if not normalized_code:
        raise ValueError("手机号授权已失效，请重新点击“微信绑定号码”")

    access_token = _get_access_token()
    response = _http_request(
        "POST",
        f"{WECHAT_API_BASE}/wxa/business/getuserphonenumber",
        params={"access_token": access_token},
        json={"code": normalized_code},
        timeout=_env_int("WECHAT_PHONE_BIND_TIMEOUT_SEC", 8),
    )
    response.raise_for_status()
    payload = response.json()

    errcode = int(payload.get("errcode", 0) or 0)
    if errcode != 0:
        if errcode in {40029, 40163}:
            raise ValueError("手机号授权已失效，请重新点击“微信绑定号码”")
        raise ValueError("微信绑定号码失败，请稍后重试")

    phone_info = payload.get("phone_info")
    if not isinstance(phone_info, dict):
        raise ValueError("微信绑定号码失败，请稍后重试")

    phone_number = str(phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber") or "").strip()
    if not phone_number:
        raise ValueError("微信绑定号码失败，请稍后重试")

    country_code = str(phone_info.get("countryCode") or "").strip() or "86"
    phone_tail = phone_number[-4:] if len(phone_number) >= 4 else phone_number
    return {
        "masked_phone_number": _mask_phone_number(phone_number),
        "phone_tail": phone_tail,
        "country_code": country_code,
    }
