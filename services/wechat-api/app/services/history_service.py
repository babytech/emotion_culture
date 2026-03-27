import calendar
import json
import os
import threading
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.feature_flags import is_retention_service_enabled
from app.schemas.analyze import AnalyzeResponse, EmotionBrief
from app.schemas.favorites import (
    FavoriteDeleteResponse,
    FavoriteItem,
    FavoriteListResponse,
    FavoriteStatusResponse,
    FavoriteType,
    FavoriteUpsertRequest,
    FavoriteUpsertResponse,
)
from app.schemas.history import (
    HistoryDetailResponse,
    HistoryEmotionBrief,
    HistoryInternalFields,
    HistoryListResponse,
    HistorySummary,
)
from app.schemas.retention import (
    CalendarDaySummary,
    CalendarOverviewResponse,
    WeeklyDailyDigest,
    WeeklyEmotionStat,
    WeeklyReportResponse,
    WeeklyTriggerStat,
)
from app.schemas.settings import UserSettingsResponse
from app.services.retention_cleanup_service import (
    cleanup_retention_bucket,
    default_retention_dict as build_default_retention_dict,
    parse_iso_day as parse_retention_iso_day,
)


_STORE_LOCK = threading.RLock()
_DEFAULT_STORE_PATH = "/tmp/emotion_culture/history_store.json"
_DEFAULT_RETENTION_DAYS = 180
_DEFAULT_USER_MAX_ITEMS = 500
_DEFAULT_WEEKLY_REPORT_CACHE_MAX_ITEMS = 32
_DEFAULT_FAVORITES_MAX_ITEMS = 500


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


def _weekly_report_cache_max_items() -> int:
    return _env_int(
        "WEEKLY_REPORT_CACHE_MAX_ITEMS",
        _DEFAULT_WEEKLY_REPORT_CACHE_MAX_ITEMS,
    )


def _favorites_max_items() -> int:
    return _env_int("FAVORITES_MAX_ITEMS", _DEFAULT_FAVORITES_MAX_ITEMS)


def _default_store() -> dict[str, Any]:
    return {"version": 2, "users": {}}


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

    version = payload.get("version")
    if not isinstance(version, int) or version <= 0:
        payload["version"] = 2

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


def _default_retention_dict() -> dict[str, Any]:
    return build_default_retention_dict()


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

    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        retention = _default_retention_dict()
        bucket["retention"] = retention
    else:
        checkins = retention.get("checkins")
        if not isinstance(checkins, dict):
            retention["checkins"] = {}

        weekly_reports = retention.get("weekly_reports")
        if not isinstance(weekly_reports, dict):
            retention["weekly_reports"] = {}

        favorites = retention.get("favorites")
        if not isinstance(favorites, list):
            retention["favorites"] = []

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


def _to_iso_day(value: datetime) -> str:
    return value.date().isoformat()


def _parse_iso_day(raw: str) -> Optional[date]:
    return parse_retention_iso_day(raw)


def _normalize_input_modes(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        if item is None:
            continue
        if hasattr(item, "value"):
            value = str(item.value).strip()
        else:
            value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _cleanup_retention_data(bucket: dict[str, Any]) -> bool:
    return cleanup_retention_bucket(
        bucket=bucket,
        retention_days=_retention_days(),
        weekly_report_cache_max_items=_weekly_report_cache_max_items(),
        favorites_max_items=_favorites_max_items(),
    )


def _upsert_daily_checkin(bucket: dict[str, Any], response: AnalyzeResponse) -> None:
    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        retention = _default_retention_dict()
        bucket["retention"] = retention

    checkins = retention.get("checkins")
    if not isinstance(checkins, dict):
        checkins = {}
        retention["checkins"] = checkins

    analyzed_at = _parse_iso_datetime(response.system_fields.analyzed_at) or datetime.now(timezone.utc)
    day_key = _to_iso_day(analyzed_at)
    existing = checkins.get(day_key) if isinstance(checkins.get(day_key), dict) else {}

    prev_request_id = (existing.get("request_id") or "").strip() if isinstance(existing, dict) else ""
    analyses_count = int(existing.get("analyses_count", 0)) if isinstance(existing, dict) else 0
    if response.request_id and response.request_id != prev_request_id:
        analyses_count += 1
    elif analyses_count <= 0:
        analyses_count = 1

    checkins[day_key] = {
        "day": day_key,
        "request_id": response.request_id,
        "analyzed_at": response.system_fields.analyzed_at,
        "primary_emotion_code": response.result_card.primary_emotion.code,
        "primary_emotion_label": response.result_card.primary_emotion.label,
        "input_modes": _normalize_input_modes(response.input_modes),
        "analyses_count": analyses_count,
        "updated_at": _iso_now_utc(),
    }


def _sorted_checkin_dates(bucket: dict[str, Any]) -> list[date]:
    retention = bucket.get("retention", {})
    checkins = retention.get("checkins", {}) if isinstance(retention, dict) else {}
    if not isinstance(checkins, dict):
        return []

    parsed_dates: list[date] = []
    for day_key in checkins.keys():
        parsed = _parse_iso_day(day_key)
        if parsed:
            parsed_dates.append(parsed)
    parsed_dates.sort()
    return parsed_dates


def _calculate_longest_streak(checkin_dates: list[date]) -> int:
    if not checkin_dates:
        return 0

    longest = 1
    current = 1
    for index in range(1, len(checkin_dates)):
        if checkin_dates[index] - checkin_dates[index - 1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        elif checkin_dates[index] != checkin_dates[index - 1]:
            current = 1
    return longest


def _calculate_current_streak(checkin_dates: list[date], today: date) -> int:
    if not checkin_dates:
        return 0

    day_set = set(checkin_dates)
    streak = 0
    cursor = today
    while cursor in day_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _week_start_from_day(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _week_key(week_start: date) -> str:
    return week_start.isoformat()


def _history_entries_with_summary(bucket: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], datetime]]:
    history = bucket.get("history", [])
    if not isinstance(history, list):
        return []

    rows: list[tuple[dict[str, Any], dict[str, Any], datetime]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        summary = entry.get("summary")
        if not isinstance(summary, dict):
            continue
        analyzed_at_raw = (summary.get("analyzed_at") or "").strip()
        analyzed_at = _parse_iso_datetime(analyzed_at_raw)
        if not analyzed_at:
            continue
        rows.append((entry, summary, analyzed_at))
    return rows


def _rebuild_daily_checkins_from_history(bucket: dict[str, Any]) -> None:
    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        retention = _default_retention_dict()
        bucket["retention"] = retention

    by_day: dict[str, dict[str, Any]] = {}
    for _entry, summary, analyzed_at in sorted(
        _history_entries_with_summary(bucket),
        key=lambda row: row[2],
    ):
        day_key = analyzed_at.date().isoformat()
        primary_emotion = summary.get("primary_emotion", {})
        current = by_day.get(day_key)
        next_count = int(current.get("analyses_count", 0)) + 1 if isinstance(current, dict) else 1

        by_day[day_key] = {
            "day": day_key,
            "request_id": summary.get("request_id"),
            "analyzed_at": summary.get("analyzed_at"),
            "primary_emotion_code": (primary_emotion.get("code") or "").strip(),
            "primary_emotion_label": (primary_emotion.get("label") or "").strip(),
            "input_modes": _normalize_input_modes(summary.get("input_modes")),
            "analyses_count": next_count,
            "updated_at": _iso_now_utc(),
        }

    retention["checkins"] = by_day


def _invalidate_weekly_report_cache(bucket: dict[str, Any]) -> None:
    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        return
    weekly_reports = retention.get("weekly_reports")
    if isinstance(weekly_reports, dict):
        weekly_reports.clear()


def _normalize_short_text(value: Optional[str], max_len: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _favorites_list(bucket: dict[str, Any]) -> list[dict[str, Any]]:
    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        retention = _default_retention_dict()
        bucket["retention"] = retention

    favorites = retention.get("favorites")
    if not isinstance(favorites, list):
        favorites = []
        retention["favorites"] = favorites
    return favorites

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


def _is_retention_write_enabled(settings: dict[str, Any]) -> bool:
    return bool(settings.get("save_history", True))


def record_analysis_summary(user_id: str, response: AnalyzeResponse) -> Optional[HistorySummary]:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        settings = bucket.get("settings", _default_settings_dict())
        if not _is_retention_write_enabled(settings):
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
        if is_retention_service_enabled():
            _upsert_daily_checkin(bucket, response)
            _invalidate_weekly_report_cache(bucket)
        _cleanup_user_history(bucket)
        _cleanup_retention_data(bucket)
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
        if _cleanup_retention_data(bucket):
            changed = True
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
        if _cleanup_retention_data(bucket):
            changed = True

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
            _rebuild_daily_checkins_from_history(bucket)
            _invalidate_weekly_report_cache(bucket)
            _cleanup_retention_data(bucket)
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
            _rebuild_daily_checkins_from_history(bucket)
            _invalidate_weekly_report_cache(bucket)
            _cleanup_retention_data(bucket)
            _save_store(payload)
        return deleted


def delete_weekly_report_snapshot(user_id: str, week_start: Optional[str] = None) -> int:
    normalized_user_id = _normalize_user_id(user_id)
    week_key = _week_key(_parse_week_start(week_start))

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        retention = bucket.get("retention")
        if not isinstance(retention, dict):
            retention = _default_retention_dict()
            bucket["retention"] = retention
            changed = True
        weekly_reports = retention.get("weekly_reports")
        if not isinstance(weekly_reports, dict):
            weekly_reports = {}
            retention["weekly_reports"] = weekly_reports
            changed = True

        deleted = 1 if week_key in weekly_reports else 0
        weekly_reports.pop(week_key, None)
        if deleted > 0:
            changed = True

        if changed:
            _save_store(payload)
        return deleted


def clear_weekly_report_snapshots(user_id: str) -> int:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        retention = bucket.get("retention")
        if not isinstance(retention, dict):
            retention = _default_retention_dict()
            bucket["retention"] = retention
            changed = True
        weekly_reports = retention.get("weekly_reports")
        if not isinstance(weekly_reports, dict):
            weekly_reports = {}
            retention["weekly_reports"] = weekly_reports
            changed = True

        deleted = len(weekly_reports)
        if deleted > 0:
            weekly_reports.clear()
            changed = True

        if changed:
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


def _parse_month(month: Optional[str]) -> date:
    raw = (month or "").strip()
    if not raw:
        return datetime.now(timezone.utc).date().replace(day=1)
    try:
        parsed = datetime.strptime(raw, "%Y-%m").date()
    except ValueError:
        raise ValueError("month must be in YYYY-MM format")
    return parsed.replace(day=1)


def _parse_week_start(week_start: Optional[str]) -> date:
    raw = (week_start or "").strip()
    if raw:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("week_start must be in YYYY-MM-DD format")
        return _week_start_from_day(parsed)
    return _week_start_from_day(datetime.now(timezone.utc).date())


def get_calendar_overview(user_id: str, month: Optional[str] = None) -> CalendarOverviewResponse:
    normalized_user_id = _normalize_user_id(user_id)
    month_start = _parse_month(month)
    _, day_count = calendar.monthrange(month_start.year, month_start.month)
    month_end = month_start.replace(day=day_count)
    today = datetime.now(timezone.utc).date()

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        retention = bucket.get("retention", {})
        checkins = retention.get("checkins", {}) if isinstance(retention, dict) else {}
        if not isinstance(checkins, dict):
            checkins = {}

        items: list[CalendarDaySummary] = []
        checked_days = 0
        for day in range(1, day_count + 1):
            current_day = month_start.replace(day=day)
            payload_item = checkins.get(current_day.isoformat(), {})
            if not isinstance(payload_item, dict):
                payload_item = {}

            has_checkin = bool(payload_item)
            if has_checkin:
                checked_days += 1

            code = (payload_item.get("primary_emotion_code") or "").strip()
            label = (payload_item.get("primary_emotion_label") or "").strip()

            items.append(
                CalendarDaySummary(
                    date=current_day,
                    has_checkin=has_checkin,
                    analyzed_at=(payload_item.get("analyzed_at") or None),
                    primary_emotion=HistoryEmotionBrief(code=code, label=label)
                    if code or label
                    else None,
                    analyses_count=int(payload_item.get("analyses_count", 0)) if has_checkin else 0,
                    input_modes=_normalize_input_modes(payload_item.get("input_modes")),
                ),
            )

        checkin_dates = _sorted_checkin_dates(bucket)
        response = CalendarOverviewResponse(
            month=month_start.strftime("%Y-%m"),
            month_start=month_start,
            month_end=month_end,
            total_days=day_count,
            checked_days=checked_days,
            checked_today=today in set(checkin_dates),
            current_streak=_calculate_current_streak(checkin_dates, today=today),
            longest_streak=_calculate_longest_streak(checkin_dates),
            items=items,
        )

        if changed:
            _save_store(payload)
        return response


def _build_weekly_insight(
    total_checkin_days: int,
    dominant_emotions: list[WeeklyEmotionStat],
    trigger_stats: list[WeeklyTriggerStat],
) -> str:
    if total_checkin_days <= 0:
        return "本周还没有情绪记录，先完成一次记录开启周报。"

    top_emotion = dominant_emotions[0].label if dominant_emotions else "情绪状态"
    top_tag = trigger_stats[0].tag if trigger_stats else ""
    if top_tag:
        return f"本周你有 {total_checkin_days} 天完成记录，主情绪偏向「{top_emotion}」，高频触发因素是「{top_tag}」。"
    return f"本周你有 {total_checkin_days} 天完成记录，主情绪偏向「{top_emotion}」，建议继续保持稳定记录。"


def get_weekly_report(user_id: str, week_start: Optional[str] = None) -> WeeklyReportResponse:
    normalized_user_id = _normalize_user_id(user_id)
    start = _parse_week_start(week_start)
    end = start + timedelta(days=6)
    week_key = _week_key(start)
    today = datetime.now(timezone.utc).date()

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True
        settings = bucket.get("settings", _default_settings_dict())
        retention_write_enabled = _is_retention_write_enabled(settings)

        retention = bucket.get("retention", {})
        if isinstance(retention, dict):
            weekly_cache = retention.get("weekly_reports")
            if isinstance(weekly_cache, dict):
                cached = weekly_cache.get(week_key)
                if isinstance(cached, dict):
                    try:
                        report = WeeklyReportResponse.model_validate(cached)
                        report.source = "cache"
                        if changed:
                            _save_store(payload)
                        return report
                    except Exception:
                        weekly_cache.pop(week_key, None)
                        changed = True

        history_rows = _history_entries_with_summary(bucket)
        weekly_rows = [row for row in history_rows if start <= row[2].date() <= end]
        weekly_rows.sort(key=lambda row: row[2])

        latest_by_day: dict[str, tuple[dict[str, Any], dict[str, Any], datetime]] = {}
        for row in weekly_rows:
            day_key = row[2].date().isoformat()
            previous = latest_by_day.get(day_key)
            if not previous or row[2] >= previous[2]:
                latest_by_day[day_key] = row

        emotion_counter: Counter[tuple[str, str]] = Counter()
        trigger_counter: Counter[str] = Counter()
        suggestion_counter: Counter[str] = Counter()

        for _entry, summary, _analyzed_at in weekly_rows:
            primary = summary.get("primary_emotion", {})
            code = (primary.get("code") or "").strip()
            label = (primary.get("label") or "").strip() or code or "未识别"
            emotion_counter[(code, label)] += 1

            tags = summary.get("trigger_tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    text = str(tag).strip()
                    if text:
                        trigger_counter[text] += 1

            suggestion = (summary.get("daily_suggestion_summary") or "").strip()
            if suggestion:
                suggestion_counter[suggestion] += 1

        dominant_emotions = [
            WeeklyEmotionStat(code=code, label=label, days=count)
            for (code, label), count in emotion_counter.most_common(3)
        ]
        top_trigger_tags = [
            WeeklyTriggerStat(tag=tag, count=count)
            for tag, count in trigger_counter.most_common(5)
        ]
        suggestion_highlights = [item for item, _count in suggestion_counter.most_common(3)]

        daily_digests: list[WeeklyDailyDigest] = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            row = latest_by_day.get(day.isoformat())
            if not row:
                daily_digests.append(WeeklyDailyDigest(date=day, has_checkin=False))
                continue

            _entry, summary, analyzed_at = row
            primary = summary.get("primary_emotion", {})
            code = (primary.get("code") or "").strip()
            label = (primary.get("label") or "").strip() or code or "未识别"
            tags = summary.get("trigger_tags", [])
            if not isinstance(tags, list):
                tags = []
            daily_digests.append(
                WeeklyDailyDigest(
                    date=day,
                    has_checkin=True,
                    primary_emotion=HistoryEmotionBrief(code=code, label=label),
                    trigger_tags=[str(tag).strip() for tag in tags if str(tag).strip()],
                    suggestion_summary=(summary.get("daily_suggestion_summary") or "").strip() or None,
                    analyzed_at=analyzed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                ),
            )

        checkin_dates = _sorted_checkin_dates(bucket)
        report = WeeklyReportResponse(
            week_start=start,
            week_end=end,
            generated_at=_iso_now_utc(),
            total_checkin_days=len(latest_by_day),
            checked_today=today in set(checkin_dates),
            current_streak=_calculate_current_streak(checkin_dates, today=today),
            dominant_emotions=dominant_emotions,
            top_trigger_tags=top_trigger_tags,
            suggestion_highlights=suggestion_highlights,
            daily_digests=daily_digests,
            insight=_build_weekly_insight(
                total_checkin_days=len(latest_by_day),
                dominant_emotions=dominant_emotions,
                trigger_stats=top_trigger_tags,
            ),
        )

        if retention_write_enabled and isinstance(retention, dict):
            weekly_cache = retention.get("weekly_reports")
            if not isinstance(weekly_cache, dict):
                weekly_cache = {}
                retention["weekly_reports"] = weekly_cache
            weekly_cache[week_key] = report.model_dump(mode="json")
            if _cleanup_retention_data(bucket):
                changed = True
            changed = True

        if changed:
            _save_store(payload)
        return report


def _to_favorite_item(payload: dict[str, Any]) -> FavoriteItem:
    return FavoriteItem.model_validate(payload)


def list_favorites(
    user_id: str,
    favorite_type: Optional[FavoriteType] = None,
    limit: int = 20,
    offset: int = 0,
) -> FavoriteListResponse:
    normalized_user_id = _normalize_user_id(user_id)
    safe_limit = max(1, min(int(limit or 20), 100))
    safe_offset = max(0, int(offset or 0))

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        favorites = _favorites_list(bucket)
        favorite_type_value = favorite_type.value if favorite_type else None
        filtered = [
            item
            for item in favorites
            if not favorite_type_value or (item.get("favorite_type") == favorite_type_value)
        ]
        filtered.sort(
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )

        total = len(filtered)
        sliced = filtered[safe_offset : safe_offset + safe_limit]
        items: list[FavoriteItem] = []
        for row in sliced:
            try:
                items.append(_to_favorite_item(row))
            except Exception:
                continue

        if changed:
            _save_store(payload)
        return FavoriteListResponse(items=items, total=total)


def get_favorite_status(user_id: str, favorite_type: FavoriteType, target_id: str) -> FavoriteStatusResponse:
    normalized_user_id = _normalize_user_id(user_id)
    normalized_target_id = (target_id or "").strip()
    if not normalized_target_id:
        return FavoriteStatusResponse(is_favorited=False, item=None)

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True

        favorites = _favorites_list(bucket)
        found: Optional[FavoriteItem] = None
        for row in favorites:
            if not isinstance(row, dict):
                continue
            if row.get("favorite_type") != favorite_type.value:
                continue
            if (row.get("target_id") or "").strip() != normalized_target_id:
                continue
            try:
                found = _to_favorite_item(row)
            except Exception:
                found = None
            break

        if changed:
            _save_store(payload)
        return FavoriteStatusResponse(is_favorited=bool(found), item=found)


def upsert_favorite(user_id: str, payload_input: FavoriteUpsertRequest) -> FavoriteUpsertResponse:
    normalized_user_id = _normalize_user_id(user_id)
    now = _iso_now_utc()
    favorite_type = payload_input.favorite_type.value
    target_id = payload_input.target_id.strip()

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        changed = _cleanup_user_history(bucket)
        if _cleanup_retention_data(bucket):
            changed = True
        settings = bucket.get("settings", _default_settings_dict())
        if not _is_retention_write_enabled(settings):
            if changed:
                _save_store(payload)
            raise ValueError("[RETENTION_WRITE_DISABLED] 留存写入已关闭，暂不支持新增收藏。")

        favorites = _favorites_list(bucket)
        created = True
        favorite_row: Optional[dict[str, Any]] = None
        for row in favorites:
            if not isinstance(row, dict):
                continue
            if row.get("favorite_type") != favorite_type:
                continue
            if (row.get("target_id") or "").strip() != target_id:
                continue
            favorite_row = row
            created = False
            break

        if not favorite_row:
            favorite_row = {
                "favorite_id": f"fav_{uuid.uuid4().hex[:12]}",
                "favorite_type": favorite_type,
                "target_id": target_id,
                "created_at": now,
            }
            favorites.append(favorite_row)

        favorite_row["title"] = payload_input.title.strip()
        favorite_row["subtitle"] = _normalize_short_text(payload_input.subtitle, 200)
        favorite_row["content_summary"] = _normalize_short_text(payload_input.content_summary, 800)
        favorite_row["request_id"] = _normalize_short_text(payload_input.request_id, 128)
        favorite_row["metadata"] = payload_input.metadata if isinstance(payload_input.metadata, dict) else {}
        favorite_row["updated_at"] = now
        if "created_at" not in favorite_row or not favorite_row.get("created_at"):
            favorite_row["created_at"] = now

        favorites.sort(
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )
        if len(favorites) > _favorites_max_items():
            del favorites[_favorites_max_items() :]

        changed = True
        if _cleanup_retention_data(bucket):
            changed = True
        if changed:
            _save_store(payload)

        item = _to_favorite_item(favorite_row)
        return FavoriteUpsertResponse(
            success=True,
            created=created,
            item=item,
            message="已加入收藏。" if created else "已更新收藏。",
        )


def delete_favorite(user_id: str, favorite_id: str) -> FavoriteDeleteResponse:
    normalized_user_id = _normalize_user_id(user_id)
    target_id = (favorite_id or "").strip()
    if not target_id:
        return FavoriteDeleteResponse(success=False, deleted_count=0, message="favorite_id is required")

    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        favorites = _favorites_list(bucket)
        before = len(favorites)
        favorites[:] = [
            row
            for row in favorites
            if not (isinstance(row, dict) and (row.get("favorite_id") or "").strip() == target_id)
        ]
        deleted = before - len(favorites)
        if deleted > 0:
            _save_store(payload)
            return FavoriteDeleteResponse(success=True, deleted_count=deleted, message="已取消收藏。")
        return FavoriteDeleteResponse(success=False, deleted_count=0, message="收藏项不存在。")


def clear_favorites(
    user_id: str,
    favorite_type: Optional[FavoriteType] = None,
) -> FavoriteDeleteResponse:
    normalized_user_id = _normalize_user_id(user_id)
    with _STORE_LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user_id)
        favorites = _favorites_list(bucket)
        before = len(favorites)

        if favorite_type is None:
            favorites[:] = []
        else:
            type_value = favorite_type.value
            favorites[:] = [
                row
                for row in favorites
                if not (isinstance(row, dict) and row.get("favorite_type") == type_value)
            ]

        deleted = before - len(favorites)
        if deleted > 0:
            _save_store(payload)
        return FavoriteDeleteResponse(
            success=True,
            deleted_count=deleted,
            message="已清空收藏。" if favorite_type is None else "已清空该类型收藏。",
        )
