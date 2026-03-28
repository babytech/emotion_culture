import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import (
    FaceQualityRejectError,
    VoiceQualityRejectError,
    run_analysis,
)
from app.services.history_service import record_analysis_summary
from app.services.media_retention_service import cleanup_expired_media, record_cloud_file_ids


logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_TASKS: dict[str, dict[str, Any]] = {}
_EXECUTOR: Optional[ThreadPoolExecutor] = None

_DEFAULT_POLL_AFTER_MS = 1200
_DEFAULT_TASK_TTL_SECONDS = 1800
_DEFAULT_MAX_TASKS = 1000
_DEFAULT_WORKERS = 4


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


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


def _poll_after_ms() -> int:
    return _env_int("ANALYZE_ASYNC_POLL_AFTER_MS", _DEFAULT_POLL_AFTER_MS)


def _task_ttl_seconds() -> int:
    return _env_int("ANALYZE_ASYNC_TASK_TTL_SECONDS", _DEFAULT_TASK_TTL_SECONDS)


def _task_max_items() -> int:
    return _env_int("ANALYZE_ASYNC_TASK_MAX_ITEMS", _DEFAULT_MAX_TASKS)


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=_env_int("ANALYZE_ASYNC_WORKERS", _DEFAULT_WORKERS))
    return _EXECUTOR


def _track_media_ids(payload: AnalyzeRequest) -> None:
    image_file_id = payload.resolved_image_file_id()
    audio_file_id = payload.resolved_audio_file_id()
    tracked_file_ids = [
        file_id
        for file_id in [image_file_id, audio_file_id]
        if isinstance(file_id, str) and file_id.startswith("cloud://")
    ]
    if not tracked_file_ids:
        return
    try:
        record_cloud_file_ids(tracked_file_ids, source="analyze")
    except Exception as exc:  # pragma: no cover
        logger.warning("media retention track skipped: %s", exc)


def run_analysis_sync_for_user(payload: AnalyzeRequest, user_id: str) -> AnalyzeResponse:
    try:
        cleanup_expired_media()
    except Exception as exc:  # pragma: no cover
        logger.warning("media retention cleanup skipped: %s", exc)

    _track_media_ids(payload)
    response = run_analysis(payload)
    try:
        record_analysis_summary(user_id=user_id, response=response)
    except Exception as exc:  # pragma: no cover
        logger.warning("history summary save skipped: %s", exc)
    return response


def _classify_failure(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, (FaceQualityRejectError, VoiceQualityRejectError)):
        return exc.to_client_message(), False
    if isinstance(exc, NotImplementedError):
        return str(exc), False
    if isinstance(exc, ValueError):
        return str(exc), False
    return f"analysis failed: {exc}", True


def _cleanup_finished_tasks_locked(now_ts: float) -> None:
    ttl_seconds = _task_ttl_seconds()
    removable: list[str] = []
    for task_id, task in _TASKS.items():
        if task.get("status") in {"queued", "running"}:
            continue
        finished_at = _parse_iso_datetime(str(task.get("finished_at") or ""))
        if not finished_at:
            continue
        if now_ts - finished_at.timestamp() > ttl_seconds:
            removable.append(task_id)
    for task_id in removable:
        _TASKS.pop(task_id, None)

    max_items = _task_max_items()
    if len(_TASKS) <= max_items:
        return

    def _accepted_sort_key(item: tuple[str, dict[str, Any]]) -> float:
        accepted = _parse_iso_datetime(str(item[1].get("accepted_at") or ""))
        return accepted.timestamp() if accepted else 0.0

    for task_id, _task in sorted(_TASKS.items(), key=_accepted_sort_key)[: max(0, len(_TASKS) - max_items)]:
        if _TASKS.get(task_id, {}).get("status") in {"queued", "running"}:
            continue
        _TASKS.pop(task_id, None)


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    snapshot = {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "accepted_at": task.get("accepted_at"),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
        "poll_after_ms": task.get("poll_after_ms", _poll_after_ms()),
        "retryable": bool(task.get("retryable", False)),
        "error_detail": task.get("error_detail"),
        "status_message": task.get("status_message") or "",
    }
    if task.get("status") == "succeeded" and isinstance(task.get("result"), dict):
        snapshot["result"] = task["result"]
    return snapshot


def _run_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["status"] = "running"
        task["status_message"] = "分析中"
        task["started_at"] = _iso_now_utc()

    try:
        payload = AnalyzeRequest.model_validate(task.get("payload", {}))
        user_id = str(task.get("user_id") or "anonymous")
        response = run_analysis_sync_for_user(payload=payload, user_id=user_id)
        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "succeeded"
            current["status_message"] = "分析完成"
            current["finished_at"] = _iso_now_utc()
            current["retryable"] = False
            current["result"] = response.model_dump(mode="json")
            current["error_detail"] = None
            current.pop("payload", None)
    except Exception as exc:  # pragma: no cover
        detail, retryable = _classify_failure(exc)
        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "failed"
            current["status_message"] = "分析失败"
            current["finished_at"] = _iso_now_utc()
            current["retryable"] = retryable
            current["error_detail"] = detail
            current.pop("result", None)
            current.pop("payload", None)


def create_analyze_task(payload: AnalyzeRequest, user_id: str) -> dict[str, Any]:
    task_id = f"atk_{uuid.uuid4().hex[:12]}"
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "status": "queued",
        "status_message": "排队中",
        "accepted_at": _iso_now_utc(),
        "started_at": None,
        "finished_at": None,
        "poll_after_ms": _poll_after_ms(),
        "retryable": False,
        "error_detail": None,
        "payload": payload.model_dump(mode="python"),
    }
    with _LOCK:
        _cleanup_finished_tasks_locked(time.time())
        _TASKS[task_id] = task

    _executor().submit(_run_task, task_id)
    return _task_snapshot(task)


def get_analyze_task(task_id: str, user_id: str) -> Optional[dict[str, Any]]:
    normalized_task_id = (task_id or "").strip()
    if not normalized_task_id:
        return None
    with _LOCK:
        _cleanup_finished_tasks_locked(time.time())
        task = _TASKS.get(normalized_task_id)
        if not task:
            return None
        if str(task.get("user_id") or "") != str(user_id or ""):
            return None
        return _task_snapshot(task)
