import hashlib
from dataclasses import dataclass
from typing import Optional

from fastapi import Request


_MAX_USER_ID_LEN = 128


def _normalize_candidate(value: Optional[str]) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) <= _MAX_USER_ID_LEN:
        return raw

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"user_{digest}"


@dataclass
class ResolvedUserIdentity:
    user_id: str
    identity_type: str
    openid: Optional[str] = None
    unionid: Optional[str] = None


def resolve_user_identity(request: Request, client_user_id: Optional[str] = None) -> ResolvedUserIdentity:
    raw_unionid = _normalize_candidate(request.headers.get("x-wx-unionid")) or _normalize_candidate(
        request.headers.get("x-unionid")
    )
    raw_openid = _normalize_candidate(request.headers.get("x-wx-openid")) or _normalize_candidate(
        request.headers.get("x-openid")
    )
    raw_user_id = _normalize_candidate(request.headers.get("x-ec-user-id")) or _normalize_candidate(
        request.headers.get("x-user-id")
    )

    if raw_unionid:
        return ResolvedUserIdentity(
            user_id=raw_unionid,
            identity_type="unionid",
            openid=raw_openid,
            unionid=raw_unionid,
        )
    if raw_openid:
        return ResolvedUserIdentity(
            user_id=raw_openid,
            identity_type="openid",
            openid=raw_openid,
            unionid=raw_unionid,
        )
    if raw_user_id:
        return ResolvedUserIdentity(
            user_id=raw_user_id,
            identity_type="header_user_id",
            openid=raw_openid,
            unionid=raw_unionid,
        )

    normalized_client = _normalize_candidate(client_user_id)
    if normalized_client:
        return ResolvedUserIdentity(
            user_id=normalized_client,
            identity_type="client_user_id",
            openid=raw_openid,
            unionid=raw_unionid,
        )

    return ResolvedUserIdentity(
        user_id="anonymous",
        identity_type="anonymous",
        openid=raw_openid,
        unionid=raw_unionid,
    )


def resolve_user_id(request: Request, client_user_id: Optional[str] = None) -> str:
    return resolve_user_identity(request=request, client_user_id=client_user_id).user_id
