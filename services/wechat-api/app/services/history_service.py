import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.schemas.analyze import AnalyzeResponse, EmotionBrief
from app.schemas.history import (
    HistoryDetailResponse,
    HistoryEmotionBrief,
    HistoryInternalFields,
    HistoryListResponse,
    HistorySummary,
)
from app.schemas.settings import UserSettingsResponse


_STORE_LOCK = threading.RLock()
_DEFAULT_STORE_PATH = "/tmp/emotion_culture/history_store.json"
_DEFAULT_RETENTION_DAYS = 180
_DEFAULT_USER_MAX_ITEMS = 500


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _store_path() -> Path:
    raw = os.getenv("HISTORY_STORE_PATH", _DEFAULT_STORE_PATH).strip() or _DEFAULT_STORE_PATH
    return Path(raw).expanduser()


def _retention_days() -> int:
    return _env_int("HISTORY_RETENTION_DAYS", _DEFAULT_RETENTION_DAYS)


def _max_user_items() -> int:
    return _env_int("HISTORY_USER_MAX_ITEMS", _DEFAULT_USER_MAX_ITEMS)


def _default_store() -> dict[str, Any]:
    return {"version": 1, "users": {}}


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso_datetime(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _default_store()

    try:
        with path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except Exception:
        return _default_store()

    if not isinstance(payload, dict):
        return _default_store()

    users = payload.get("users")
    if not isinstance(users, dict):
        payload["users"] = {}
    return payload


def _save_store(payload: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def _normalize_user_id(user_id: str) -> str:
    normalized = (user_id or "").strip()
    return normalized if normalized else "anonymous"


def _default_settings_dict() -> dict[str, Any]:
    return {
        "save_history": True,
        "updated_at": None,
    }


def _ensure_user_bucket(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    users = payload.setdefault("users", {})
    bucket = users.get(user_id)
    if not isinstance(bucket, dict):
        bucket = {}
        users[user_id] = bucket

    settings = bucket.get("settings")
    if not isinstance(settings, dict):
        settings = _default_settings_dict()
        bucket["settings"] = settings
    else:
        if "save_history" not in settings:
            settings["save_history"] = True
        if "updated_at" not in settings:
            settings["updated_at"] = None

    history = bucket.get("history")
    if not isinstance(history, list):
        bucket["history"] = []

    return bucket


def _history_sort_key(entry: dict[str, Any]) -> datetime:
    summary = entry.get("summary", {})
    analyzed_at = summary.get("analyzed_at") if isinstance(summary, dict) else ""
    parsed = _parse_iso_datetime(analyzed_at or "")
    return parsed or datetime.fromtimestamp(0, timezone.utc)


def _cleanup_user_history(bucket: dict[str, Any]) -> bool:
    history = bucket.get("history", [])
    if not isinstance(history, list):
        bucket["history"] = []
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(days=_retention_days())
    cleaned: list[dict[str, Any]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        summary = entry.get("summary", {})
        analyzed_at = summary.get("analyzed_at") if isinstance(summary, dict) else ""
        parsed = _parse_iso_datetime(analyzed_at or "")
        if parsed and parsed < cutoff:
            continue
        cleaned.append(entry)

    cleaned.sort(key=_history_sort_key, reverse=True)
    max_items = _max_user_items()
    if len(cleaned) > max_items:
        cleaned = cleaned[:max_items]

    if cleaned != history:
        bucket["history"] = cleaned
        return True
    return False


def _to_history_brief(item: EmotionBrief) -> HistoryEmotionBrief:
    code = (item.code or "").strip()
    label = (item.label or "").strip() or code or "未识别"
    return HistoryEmotionBrief(code=code, label=label)


def _truncate_text(value: str, max_len: int = 160) -> str:
    text = (value or "").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len].rstrip()}..."


def _build_summary(response: AnalyzeResponse, history_id: str) -> HistorySummary:
    result_card = response.result_card
    guochao_name = (response.guochao.name or "").strip() if response.guochao else ""

    return HistorySummary(
        history_id=history_id,
        request_id=response.request_id,
        analyzed_at=response.system_fields.analyzed_at,
        input_modes=response.input_modes,
        primary_emotion=_to_history_brief(result_card.primary_emotion),
        secondary_emotions=[_to_history_brief(item) for item in result_card.secondary_emotions],
        emotion_overview_summary=_truncate_text(result_card.emotion_overview, max_len=180),
        trigger_tags=list(result_card.trigger_tags),
        poem_response_summary=_truncate_text(result_card.poem_response, max_len=120),
        guochao_name=guochao_name or "国潮伙伴",
        daily_suggestion_summary=_truncate_text(result_card.daily_suggestion, max_len=120),
        mail_sent=bool(response.system_fields.mail_sent),
    )


def _build_internal_fields(response: AnalyzeResponse) -> HistoryInternalFields:
    system_fields = response.system_fields
    return HistoryInternalFields(
        request_id=system_fields.request_id,
        analyzed_at=system_fields.analyzed_at,
        input_modes=system_fields.input_modes,
        primary_emotion_code=system_fields.primary_emotion_code,
        secondary_emotion_codes=system_fields.secondary_emotion_codes,
        confidence_level=system_fields.confidence_level,
        trigger_tags=system_fields.trigger_tags,
        poem_id=system_fields.poem_id,
        guochao_id=system_fields.guochao_id,
        mail_sent=bool(system_fields.mail_sent),
        tts_ready=bool(system_fields.tts_ready),
    )


def _get_settings_response(settings: dict[str, Any]) -> UserSettingsResponse:
    return UserSettingsResponse(
        save_history=bool(settings.get("save_history", True)),
        history_retention_days=_retention_days(),
        updated_at=settings.get("updated_at"),
    )


def record_analysis_summary(user_id: str, response: AnalyzeResponse) -> Optional[HistorySummary]:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)

        settings = bucket.get("settings", _default_settings_dict())
        if not bool(settings.get("save_history", True)):
            if changed:
                _save_store(payload)
            return None

        history = bucket.get("history", [])
        request_id = response.request_id
        history_id: Optional[str] = None

        for index, entry in enumerate(history):
            summary = entry.get("summary", {})
            if isinstance(summary, dict) and summary.get("request_id") == request_id:
                existing_history_id = (summary.get("history_id") or "").strip()
                history_id = existing_history_id or f"his_{uuid.uuid4().hex[:12]}"
                history.pop(index)
                break

        if not history_id:
            history_id = f"his_{uuid.uuid4().hex[:12]}"

        summary = _build_summary(response, history_id=history_id)
        internal_fields = _build_internal_fields(response)

        history.insert(
            0,
            {
                "summary": summary.model_dump(mode="json"),
                "result_card": response.result_card.model_dump(mode="json"),
                "internal_fields": internal_fields.model_dump(mode="json"),
            },
        )
        _cleanup_user_history(bucket)
        _save_store(payload)
        return summary


def list_history_summaries(user_id: str, limit: int = 20, offset: int = 0) -> HistoryListResponse:
    normalized_user_id = _normalize_user_id(user_id)
    safe_limit = max(1, min(int(limit or 20), 100))
    safe_offset = max(0, int(offset or 0))

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        history = bucket.get("history", [])
        total = len(history)
        sliced = history[safe_offset : safe_offset + safe_limit]

        items: list[HistorySummary] = []
        for entry in sliced:
            summary = entry.get("summary", {})
            if not isinstance(summary, dict):
                continue
            try:
                items.append(HistorySummary.model_validate(summary))
            except Exception:
                continue

        if changed:
            _save_store(payload)
        return HistoryListResponse(items=items, total=total)


def get_history_detail(user_id: str, history_id: str) -> Optional[HistoryDetailResponse]:
    normalized_user_id = _normalize_user_id(user_id)
    target_id = (history_id or "").strip()
    if not target_id:
        return None

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)

        history = bucket.get("history", [])
        result: Optional[HistoryDetailResponse] = None
        for entry in history:
            summary_payload = entry.get("summary", {})
            if not isinstance(summary_payload, dict):
                continue
            if summary_payload.get("history_id") != target_id:
                continue

            try:
                result = HistoryDetailResponse(
                    summary=HistorySummary.model_validate(summary_payload),
                    result_card=entry.get("result_card", {}),
                    internal_fields=entry.get("internal_fields", {}),
                )
            except Exception:
                result = None
            break

        if changed:
            _save_store(payload)
        return result


def mark_history_mail_sent(user_id: str, request_id: str) -> bool:
    normalized_user_id = _normalize_user_id(user_id)
    target_request_id = (request_id or "").strip()
    if not target_request_id:
        return False

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        history = bucket.get("history", [])
        changed = False

        for entry in history:
            summary = entry.get("summary", {})
            if not isinstance(summary, dict):
                continue
            if summary.get("request_id") != target_request_id:
                continue
            if not summary.get("mail_sent"):
                summary["mail_sent"] = True
                changed = True

            internal_fields = entry.get("internal_fields", {})
            if isinstance(internal_fields, dict) and not internal_fields.get("mail_sent"):
                internal_fields["mail_sent"] = True
                changed = True

        if changed:
            _save_store(payload)
        return changed


def delete_history_summary(user_id: str, history_id: str) -> int:
    normalized_user_id = _normalize_user_id(user_id)
    target_id = (history_id or "").strip()
    if not target_id:
        return 0

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        history = bucket.get("history", [])
        before = len(history)
        history[:] = [
            entry
            for entry in history
            if not (
                isinstance(entry, dict)
                and isinstance(entry.get("summary"), dict)
                and entry["summary"].get("history_id") == target_id
            )
        ]
        deleted = before - len(history)
        if deleted > 0:
            _save_store(payload)
        return deleted


def clear_history_summaries(user_id: str) -> int:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        history = bucket.get("history", [])
        deleted = len(history)
        if deleted > 0:
            bucket["history"] = []
            _save_store(payload)
        return deleted


def get_user_settings(user_id: str) -> UserSettingsResponse:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        settings = bucket.get("settings", _default_settings_dict())
        return _get_settings_response(settings)


def update_user_save_history(user_id: str, save_history: bool) -> UserSettingsResponse:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        settings = bucket.get("settings", _default_settings_dict())
        settings["save_history"] = bool(save_history)
        settings["updated_at"] = _iso_now_utc()
        bucket["settings"] = settings
        _save_store(payload)
        return _get_settings_response(settings)
