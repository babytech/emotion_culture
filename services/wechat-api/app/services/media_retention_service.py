import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.services.storage_service import delete_cloud_file_ids


logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_DEFAULT_STORE_PATH = "/tmp/emotion_culture/media_retention_store.json"
_DEFAULT_RETENTION_HOURS = 24
_DEFAULT_MAX_ITEMS = 5000


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
    raw = os.getenv("MEDIA_RETENTION_STORE_PATH", _DEFAULT_STORE_PATH).strip() or _DEFAULT_STORE_PATH
    return Path(raw).expanduser()


def _retention_hours() -> int:
    return _env_int("MEDIA_RETENTION_HOURS", _DEFAULT_RETENTION_HOURS)


def _max_items() -> int:
    return _env_int("MEDIA_RETENTION_MAX_ITEMS", _DEFAULT_MAX_ITEMS)


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


def _normalize_cloud_file_id(file_id: str) -> Optional[str]:
    value = (file_id or "").strip()
    if not value or not value.startswith("cloud://"):
        return None
    return value


def _default_store() -> dict:
    return {"version": 1, "items": []}


def _load_store() -> dict:
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
    items = payload.get("items")
    if not isinstance(items, list):
        payload["items"] = []
    return payload


def _save_store(payload: dict) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def _dedupe_items(items: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        file_id = _normalize_cloud_file_id(str(item.get("file_id") or ""))
        if not file_id:
            continue

        tracked_at = str(item.get("tracked_at") or "").strip()
        tracked_parsed = _parse_iso_datetime(tracked_at)
        if tracked_parsed is None:
            tracked_at = _iso_now_utc()
            tracked_parsed = _parse_iso_datetime(tracked_at)

        source = str(item.get("source") or "").strip()
        existing = deduped.get(file_id)
        if not existing:
            deduped[file_id] = {
                "file_id": file_id,
                "tracked_at": tracked_at,
                "source": source,
                "_tracked_parsed": tracked_parsed,
            }
            continue

        existing_parsed = existing.get("_tracked_parsed")
        if (
            isinstance(existing_parsed, datetime)
            and isinstance(tracked_parsed, datetime)
            and tracked_parsed < existing_parsed
        ):
            existing["tracked_at"] = tracked_at
            existing["_tracked_parsed"] = tracked_parsed
        if source and not existing.get("source"):
            existing["source"] = source

    normalized = list(deduped.values())
    normalized.sort(key=lambda item: item.get("_tracked_parsed") or datetime.now(timezone.utc))
    for item in normalized:
        item.pop("_tracked_parsed", None)
    return normalized


def _normalize_store(payload: dict) -> tuple[list[dict], bool]:
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        payload["items"] = []
        return [], True

    normalized = _dedupe_items(raw_items)
    changed = normalized != raw_items
    payload["items"] = normalized
    return normalized, changed


def record_cloud_file_ids(file_ids: Iterable[str], source: str = "") -> int:
    normalized_ids: list[str] = []
    for file_id in file_ids:
        normalized = _normalize_cloud_file_id(file_id)
        if normalized and normalized not in normalized_ids:
            normalized_ids.append(normalized)

    if not normalized_ids:
        return 0

    with _LOCK:
        payload = _load_store()
        items, changed = _normalize_store(payload)
        existing_ids = {item.get("file_id") for item in items}

        now_iso = _iso_now_utc()
        added = 0
        for file_id in normalized_ids:
            if file_id in existing_ids:
                continue
            items.append(
                {
                    "file_id": file_id,
                    "tracked_at": now_iso,
                    "source": (source or "").strip(),
                }
            )
            existing_ids.add(file_id)
            added += 1

        items.sort(key=lambda item: _parse_iso_datetime(item.get("tracked_at", "")) or datetime.now(timezone.utc))
        max_items = _max_items()
        if len(items) > max_items:
            items[:] = items[-max_items:]
            changed = True

        if added > 0 or changed:
            payload["items"] = items
            _save_store(payload)
        return added


def cleanup_expired_media() -> dict[str, int]:
    with _LOCK:
        payload = _load_store()
        items, changed = _normalize_store(payload)
        if not items:
            if changed:
                _save_store(payload)
            return {"tracked": 0, "expired": 0, "deleted": 0, "failed": 0}

        cutoff = datetime.now(timezone.utc) - timedelta(hours=_retention_hours())
        expired_ids: list[str] = []
        for item in items:
            tracked_at = _parse_iso_datetime(item.get("tracked_at", ""))
            if tracked_at and tracked_at <= cutoff:
                file_id = item.get("file_id")
                if isinstance(file_id, str) and file_id not in expired_ids:
                    expired_ids.append(file_id)

        deleted_ids: list[str] = []
        failed_ids: list[str] = []
        if expired_ids:
            try:
                outcome = delete_cloud_file_ids(expired_ids)
                deleted_ids = list(dict.fromkeys(outcome.get("deleted_ids", [])))
                failed_ids = list(dict.fromkeys(outcome.get("failed_ids", [])))
            except Exception as exc:
                logger.warning("cleanup expired media failed: %s", exc)
                failed_ids = expired_ids

        deleted_set = set(deleted_ids)
        if deleted_set:
            items = [item for item in items if item.get("file_id") not in deleted_set]
            changed = True

        if changed:
            payload["items"] = items
            _save_store(payload)

        return {
            "tracked": len(items),
            "expired": len(expired_ids),
            "deleted": len(deleted_ids),
            "failed": len(failed_ids),
        }
