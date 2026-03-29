import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOCK = threading.RLock()


def _store_path() -> Path:
    raw = (os.getenv("MEDIA_QUOTA_STORE_PATH", "/tmp/emotion_culture/media_quota_store.json") or "").strip()
    candidate = Path(raw).expanduser()
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def _week_key(now: datetime | None = None) -> str:
    anchor = now or datetime.now(timezone.utc)
    iso = anchor.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"version": 1, "users": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "users": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "users": {}}
    if not isinstance(payload.get("users"), dict):
        payload["users"] = {}
    return payload


def _save_store(payload: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def _ensure_user_bucket(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    users = payload.setdefault("users", {})
    bucket = users.get(user_id)
    if not isinstance(bucket, dict):
        bucket = {}
        users[user_id] = bucket
    weeks = bucket.get("weeks")
    if not isinstance(weeks, dict):
        weeks = {}
        bucket["weeks"] = weeks
    return bucket


def consume_weekly_quota(user_id: str, task_id: str, *, weekly_limit: int) -> dict[str, Any]:
    normalized_user = (user_id or "").strip()
    normalized_task = (task_id or "").strip()
    if not normalized_user or not normalized_task:
        raise ValueError("MEDIA_GEN_QUOTA_INVALID: missing user_id or task_id")

    limit = max(1, int(weekly_limit or 1))
    week = _week_key()

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        weeks = bucket["weeks"]
        raw = weeks.get(week)
        if not isinstance(raw, list):
            raw = []
            weeks[week] = raw
        task_ids = [str(item).strip() for item in raw if str(item).strip()]
        if normalized_task in task_ids:
            return {"allowed": True, "consumed": False, "week_key": week, "used": len(task_ids), "limit": limit}
        if len(task_ids) >= limit:
            raise ValueError(f"MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED: week={week}, limit={limit}")
        task_ids.append(normalized_task)
        weeks[week] = task_ids
        _save_store(payload)
        return {"allowed": True, "consumed": True, "week_key": week, "used": len(task_ids), "limit": limit}


def release_weekly_quota(user_id: str, task_id: str) -> bool:
    normalized_user = (user_id or "").strip()
    normalized_task = (task_id or "").strip()
    if not normalized_user or not normalized_task:
        return False

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        weeks = bucket.get("weeks", {})
        changed = False
        for week_key, raw in list(weeks.items()):
            if not isinstance(raw, list):
                continue
            task_ids = [str(item).strip() for item in raw if str(item).strip()]
            if normalized_task not in task_ids:
                continue
            task_ids = [item for item in task_ids if item != normalized_task]
            if task_ids:
                weeks[week_key] = task_ids
            else:
                weeks.pop(week_key, None)
            changed = True
        if changed:
            _save_store(payload)
        return changed
