import hashlib
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


def resolve_user_id(request: Request, client_user_id: Optional[str] = None) -> str:
    header_candidates = [
        request.headers.get("x-wx-openid"),
        request.headers.get("x-openid"),
        request.headers.get("x-ec-user-id"),
        request.headers.get("x-user-id"),
    ]
    for candidate in header_candidates:
        normalized = _normalize_candidate(candidate)
        if normalized:
            return normalized

    normalized_client = _normalize_candidate(client_user_id)
    if normalized_client:
        return normalized_client

    return "anonymous"
