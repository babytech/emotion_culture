import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from app.schemas.today_history import TodayHistoryEntry, TodayHistoryResponse


_LOCK = threading.RLock()
_SEED_PATH = Path(__file__).resolve().parents[1] / "core" / "today_history_seed.json"
_DEFAULT_CACHE_PATH = "/tmp/emotion_culture/today_history_cache.json"
_DEFAULT_SENSITIVE_KEYWORDS = (
    "屠杀",
    "恐袭",
    "恐怖袭击",
    "政变",
    "种族灭绝",
    "核泄漏",
    "爆炸袭击",
    "大屠杀",
    "刺杀",
)
_DEFAULT_EMOTION_HINTS = (
    "愿你",
    "你可以",
    "不妨",
    "提醒我们",
    "也许",
    "值得",
    "感受",
    "心情",
    "情绪",
    "治愈",
    "安慰",
)
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？!?；;\n]+")


def _safe_text(value: object, max_len: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _store_path() -> Path:
    raw = (os.getenv("TODAY_HISTORY_CACHE_PATH", _DEFAULT_CACHE_PATH) or "").strip()
    candidate = Path(raw).expanduser()
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _seed_payload() -> dict[str, Any]:
    if not _SEED_PATH.exists():
        return {}
    try:
        payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_cache() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"version": 1, "entries": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "entries": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "entries": {}}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def _save_cache(payload: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def _cache_ttl_seconds() -> int:
    raw = (os.getenv("TODAY_HISTORY_CACHE_TTL_SEC", str(14 * 24 * 60 * 60)) or "").strip()
    try:
        return max(300, int(raw))
    except ValueError:
        return 14 * 24 * 60 * 60


def _provider_name() -> str:
    raw = (os.getenv("TODAY_HISTORY_PROVIDER", "auto") or "").strip().lower()
    return raw or "auto"


def _http_endpoint() -> str:
    return _safe_text(os.getenv("TODAY_HISTORY_HTTP_ENDPOINT", ""), 400)


def _http_method() -> str:
    raw = (os.getenv("TODAY_HISTORY_HTTP_METHOD", "POST") or "").strip().upper()
    return raw if raw in {"GET", "POST"} else "POST"


def _http_timeout_sec() -> float:
    raw = (os.getenv("TODAY_HISTORY_HTTP_TIMEOUT_SEC", "12") or "").strip()
    try:
        return max(3.0, float(raw))
    except ValueError:
        return 12.0


def _http_headers() -> dict[str, str]:
    raw = (os.getenv("TODAY_HISTORY_HTTP_HEADERS_JSON", "") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    headers: dict[str, str] = {}
    for key, value in payload.items():
        key_text = _safe_text(key, 64)
        value_text = _safe_text(value, 400)
        if key_text and value_text:
            headers[key_text] = value_text
    return headers


def _http_payload_json() -> dict[str, Any]:
    raw = (os.getenv("TODAY_HISTORY_HTTP_PAYLOAD_JSON", "") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now_utc() -> str:
    return _now_utc().isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso_datetime(raw: object) -> Optional[datetime]:
    text = _safe_text(raw, 64)
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _resolve_target_date(date_value: Optional[str]) -> datetime:
    text = _safe_text(date_value, 32)
    if not text:
        return datetime.now()
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc


def _month_day(date_value: datetime) -> str:
    return date_value.strftime("%m-%d")


def _date_key(date_value: datetime) -> str:
    return date_value.strftime("%Y-%m-%d")


def _cache_bucket_key(provider: str, date_key: str) -> str:
    return f"{provider}:{date_key}"


def _read_cache_entry(provider: str, date_key: str, *, allow_stale: bool = False) -> Optional[dict[str, Any]]:
    ttl = timedelta(seconds=_cache_ttl_seconds())
    now = _now_utc()
    with _LOCK:
        payload = _load_cache()
        entries = payload.get("entries") or {}
        bucket = entries.get(_cache_bucket_key(provider, date_key))
        if not isinstance(bucket, dict):
            return None
        cached_at = _parse_iso_datetime(bucket.get("cached_at"))
        if not cached_at:
            return None
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        if not allow_stale and now - cached_at > ttl:
            return None
        entry = bucket.get("entry")
        return entry if isinstance(entry, dict) else None


def _write_cache_entry(provider: str, date_key: str, entry: dict[str, Any]) -> None:
    with _LOCK:
        payload = _load_cache()
        entries = payload.setdefault("entries", {})
        entries[_cache_bucket_key(provider, date_key)] = {
            "cached_at": _iso_now_utc(),
            "entry": entry,
        }
        _save_cache(payload)


def _sensitive_keywords() -> tuple[str, ...]:
    raw = (os.getenv("TODAY_HISTORY_SENSITIVE_KEYWORDS", "") or "").strip()
    if not raw:
        return _DEFAULT_SENSITIVE_KEYWORDS
    parts = [item.strip() for item in raw.split(",")]
    custom = tuple(item for item in parts if item)
    return custom or _DEFAULT_SENSITIVE_KEYWORDS


def _emotion_hints() -> tuple[str, ...]:
    raw = (os.getenv("TODAY_HISTORY_EMOTION_HINTS", "") or "").strip()
    if not raw:
        return _DEFAULT_EMOTION_HINTS
    parts = [item.strip() for item in raw.split(",")]
    custom = tuple(item for item in parts if item)
    return custom or _DEFAULT_EMOTION_HINTS


def _is_sensitive(entry: TodayHistoryEntry) -> bool:
    haystack = " ".join(
        filter(
            None,
            [
                entry.headline.lower(),
                entry.summary.lower(),
                (entry.optional_note or "").lower(),
            ],
        )
    )
    return any(keyword.lower() in haystack for keyword in _sensitive_keywords())


def _looks_like_emotion_sentence(text: str) -> bool:
    normalized = _safe_text(text, 200)
    if not normalized:
        return False
    haystack = normalized.lower()
    return any(hint.lower() in haystack for hint in _emotion_hints())


def _split_sentences(text: str) -> list[str]:
    normalized = _safe_text(text, 400)
    if not normalized:
        return []
    return [item.strip() for item in _SENTENCE_SPLIT_PATTERN.split(normalized) if item and item.strip()]


def _layer_fact_and_note(raw_summary: str) -> tuple[str, Optional[str]]:
    sentences = _split_sentences(raw_summary)
    if not sentences:
        return "", None
    factual: list[str] = []
    emotion_like: list[str] = []
    for sentence in sentences:
        if _looks_like_emotion_sentence(sentence):
            emotion_like.append(sentence)
        else:
            factual.append(sentence)
    if not factual:
        factual.append(sentences[0])
        emotion_like = sentences[1:]
    summary = _safe_text("；".join(factual), 140)
    note = _safe_text("；".join(emotion_like), 60) or None
    return summary, note


def _coalesce_text(raw: dict[str, Any], keys: tuple[str, ...], max_len: int) -> str:
    for key in keys:
        value = raw.get(key)
        text = _safe_text(value, max_len)
        if text:
            return text
    return ""


def _parse_json_from_text(raw_text: str) -> Optional[Any]:
    text = _safe_text(raw_text, 5000)
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*([\s\S]+?)```", text)
    candidates.extend(fenced)
    for item in candidates:
        candidate = item.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _walk_candidates(raw: Any, output: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 5:
        return
    if isinstance(raw, dict):
        output.append(raw)
        for key in ("data", "result", "entry", "item", "event", "payload"):
            value = raw.get(key)
            if isinstance(value, (dict, list, str)):
                _walk_candidates(value, output, depth + 1)
        for key in ("items", "events", "results", "records", "candidates", "list"):
            value = raw.get(key)
            if isinstance(value, list):
                for element in value[:8]:
                    _walk_candidates(element, output, depth + 1)
        choices = raw.get("choices")
        if isinstance(choices, list):
            for choice in choices[:3]:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                if isinstance(message, dict):
                    _walk_candidates(message.get("content"), output, depth + 1)
                _walk_candidates(choice.get("text"), output, depth + 1)
        return
    if isinstance(raw, list):
        for item in raw[:8]:
            _walk_candidates(item, output, depth + 1)
        return
    if isinstance(raw, str):
        parsed = _parse_json_from_text(raw)
        if parsed is not None:
            _walk_candidates(parsed, output, depth + 1)


def _normalize_entry(
    raw: dict[str, Any],
    *,
    month_day: str,
    source_label: str,
) -> Optional[TodayHistoryEntry]:
    if not isinstance(raw, dict):
        return None
    headline = _coalesce_text(raw, ("headline", "title", "event_title"), 48)
    raw_summary = _coalesce_text(
        raw,
        (
            "fact_summary",
            "factual_summary",
            "summary",
            "description",
            "history_summary",
            "event_summary",
        ),
        320,
    )
    summary, derived_note = _layer_fact_and_note(raw_summary)
    optional_note = _coalesce_text(
        raw,
        ("optional_note", "note", "emotion_note", "companion_note", "reflection"),
        60,
    ) or derived_note
    event_year = _coalesce_text(raw, ("event_year", "year"), 24) or None
    final_source = _safe_text(raw.get("source_label") or source_label, 24) or source_label
    if not headline or not summary:
        return None
    return TodayHistoryEntry(
        month_day=month_day,
        event_year=event_year,
        headline=headline,
        summary=summary,
        optional_note=optional_note,
        source_label=final_source,
    )


def _seed_entry(month_day: str) -> Optional[TodayHistoryEntry]:
    payload = _seed_payload()
    raw = payload.get(month_day)
    if not isinstance(raw, dict):
        return None
    return _normalize_entry(raw, month_day=month_day, source_label="历史资料")


def _fetch_http_entry(date_key: str, month_day: str) -> Optional[TodayHistoryEntry]:
    endpoint = _http_endpoint()
    if not endpoint:
        return None

    payload = {
        "date": date_key,
        "month_day": month_day,
        "locale": "zh-CN",
        "max_items": 3,
    }
    payload.update(_http_payload_json())
    headers = _http_headers()
    method = _http_method()
    timeout = _http_timeout_sec()

    try:
        if method == "GET":
            response = requests.get(endpoint, params=payload, headers=headers, timeout=timeout)
        else:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        try:
            raw: Any = response.json()
        except Exception:
            raw = response.text
    except Exception:
        return None

    candidates: list[dict[str, Any]] = []
    _walk_candidates(raw, candidates)

    for candidate in candidates:
        entry = _normalize_entry(candidate, month_day=month_day, source_label="AI 检索")
        if entry:
            return entry
    return None


def _build_response(
    *,
    date_key: str,
    month_day: str,
    status: str,
    status_message: str,
    available: bool,
    entry: Optional[TodayHistoryEntry] = None,
    cache_hit: bool = False,
) -> TodayHistoryResponse:
    return TodayHistoryResponse(
        date=date_key,
        month_day=month_day,
        available=available,
        collapsed_default=True,
        status=status,
        status_message=status_message,
        cache_hit=cache_hit,
        entry=entry,
    )


def get_today_history(date_value: Optional[str] = None) -> TodayHistoryResponse:
    target_date = _resolve_target_date(date_value)
    date_key = _date_key(target_date)
    month_day = _month_day(target_date)
    provider = _provider_name()

    cache_provider = "today_history"
    cached = _read_cache_entry(cache_provider, date_key)
    if cached:
        entry = _normalize_entry(cached, month_day=month_day, source_label="缓存结果")
        if entry and not _is_sensitive(entry):
            return _build_response(
                date_key=date_key,
                month_day=month_day,
                status="ok",
                status_message="已整理",
                available=True,
                entry=entry,
                cache_hit=True,
            )

    entry: Optional[TodayHistoryEntry] = None
    if provider in {"auto", "http"}:
        entry = _fetch_http_entry(date_key, month_day)
    if not entry and provider in {"auto", "seed", "mock"}:
        entry = _seed_entry(month_day)

    if entry and _is_sensitive(entry):
        return _build_response(
            date_key=date_key,
            month_day=month_day,
            status="filtered",
            status_message="今日历史内容已自动收起",
            available=False,
        )

    if entry:
        _write_cache_entry(
            cache_provider,
            date_key,
            {
                "month_day": entry.month_day,
                "event_year": entry.event_year,
                "headline": entry.headline,
                "summary": entry.summary,
                "optional_note": entry.optional_note,
                "source_label": entry.source_label,
            },
        )
        return _build_response(
            date_key=date_key,
            month_day=month_day,
            status="ok",
            status_message="可展开查看",
            available=True,
            entry=entry,
            cache_hit=False,
        )

    stale = _read_cache_entry(cache_provider, date_key, allow_stale=True)
    if stale:
        stale_entry = _normalize_entry(stale, month_day=month_day, source_label="缓存结果")
        if stale_entry and not _is_sensitive(stale_entry):
            return _build_response(
                date_key=date_key,
                month_day=month_day,
                status="degraded",
                status_message="当前展示缓存内容",
                available=True,
                entry=stale_entry,
                cache_hit=True,
            )

    return _build_response(
        date_key=date_key,
        month_day=month_day,
        status="empty",
        status_message="今日历史内容整理中",
        available=False,
    )
