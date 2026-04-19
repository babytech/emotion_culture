import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional

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
_TASK_TOKEN_INDEX: dict[str, str] = {}
_EXECUTOR: Optional[ThreadPoolExecutor] = None

_DEFAULT_POLL_AFTER_MS = 2500
_DEFAULT_TASK_TTL_SECONDS = 1800
_DEFAULT_MAX_TASKS = 1000
_DEFAULT_WORKERS = 4

_RUNNING_STAGE_PROGRESS: dict[str, tuple[int, int, int]] = {
    "running_bootstrap": (24, 34, 5000),
    "media_resolved": (32, 44, 6000),
    "asr_processing": (44, 58, 14000),
    "asr_done": (56, 64, 2800),
    "text_processing": (60, 72, 7000),
    "text_done": (70, 78, 2800),
    "face_processing": (74, 86, 10000),
    "face_done": (84, 90, 2800),
    "fusion_processing": (88, 95, 5500),
    "fusion_done": (94, 97, 3200),
    "result_ready": (97, 99, 4200),
}


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


def _duration_ms(start_raw: str, end_raw: Optional[str] = None) -> Optional[int]:
    start_at = _parse_iso_datetime(start_raw)
    if not start_at:
        return None
    end_at = _parse_iso_datetime(end_raw or "") or datetime.now(timezone.utc)
    duration = int((end_at - start_at).total_seconds() * 1000)
    return max(0, duration)


def _poll_after_ms() -> int:
    return _env_int("ANALYZE_ASYNC_POLL_AFTER_MS", _DEFAULT_POLL_AFTER_MS)


def _task_ttl_seconds() -> int:
    return _env_int("ANALYZE_ASYNC_TASK_TTL_SECONDS", _DEFAULT_TASK_TTL_SECONDS)


def _task_max_items() -> int:
    return _env_int("ANALYZE_ASYNC_TASK_MAX_ITEMS", _DEFAULT_MAX_TASKS)


def _dynamic_poll_after_ms(status: str, queue_wait_ms: Optional[int], run_elapsed_ms: Optional[int]) -> int:
    base = _poll_after_ms()
    if status == "queued":
        if queue_wait_ms is not None and queue_wait_ms >= 25000:
            return max(base, 3200)
        if queue_wait_ms is not None and queue_wait_ms >= 8000:
            return max(base, 2800)
        return base
    if status == "running":
        if run_elapsed_ms is not None and run_elapsed_ms >= 45000:
            return max(base, 3200)
        if run_elapsed_ms is not None and run_elapsed_ms >= 15000:
            return max(base, 2800)
    return base


def _dynamic_status_message(
    task: dict[str, Any],
    *,
    status: str,
    queue_wait_ms: Optional[int],
    run_elapsed_ms: Optional[int],
) -> str:
    stored = str(task.get("status_message") or "").strip()
    if status == "queued":
        if queue_wait_ms is not None and queue_wait_ms >= 25000:
            return "排队中：云端较忙，任务已保留，可稍后回来继续查询。"
        if queue_wait_ms is not None and queue_wait_ms >= 8000:
            return "排队中：请求已接收，云端正在排队处理。"
        return stored or "排队中：已收到请求，正在进入云端队列。"

    if status == "running":
        if stored:
            if run_elapsed_ms is not None and run_elapsed_ms >= 45000:
                return f"{stored}（耗时较长，可稍后回来继续查询）"
            return stored
        if run_elapsed_ms is not None and run_elapsed_ms >= 45000:
            return "分析中：自拍或录音仍在云端处理，可保持当前页，也可稍后回来继续查询。"
        if run_elapsed_ms is not None and run_elapsed_ms >= 15000:
            return "分析中：云端正在整理文字、自拍和语音，请再稍等一下。"
        return "分析中：正在生成情绪结果。"

    if status == "succeeded":
        return "分析完成"
    if status == "failed":
        return stored or "分析失败"
    return stored or "分析中"


def _normalize_progress_percent(value: Any, default: int = 0) -> int:
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(100, numeric))


def _build_progress_snapshot(
    task: dict[str, Any],
    *,
    status: str,
    queue_wait_ms: Optional[int],
    run_elapsed_ms: Optional[int],
) -> tuple[int, str]:
    previous = _normalize_progress_percent(task.get("progress_percent"), 0)
    stage = str(task.get("progress_stage") or "").strip()

    if status == "succeeded":
        return 100, "succeeded"

    if status == "failed":
        return max(1, min(99, previous or 99)), "failed"

    if status == "queued":
        waited_ms = max(0, int(queue_wait_ms or 0))
        # Queue stage uses real wait time and tops out below running stage.
        dynamic = min(22, 4 + waited_ms // 1200)
        return max(previous, dynamic), "queued"

    if status == "running":
        current_stage = stage or "running_bootstrap"
        min_progress, max_progress, ramp_ms = _RUNNING_STAGE_PROGRESS.get(
            current_stage,
            _RUNNING_STAGE_PROGRESS["running_bootstrap"],
        )
        stage_started_at = str(task.get("progress_stage_started_at") or task.get("started_at") or "")
        stage_elapsed_ms = _duration_ms(stage_started_at) or 0
        ramp_total = max(1000, int(ramp_ms))
        ramp_ratio = min(1.0, max(0.0, float(stage_elapsed_ms) / float(ramp_total)))
        dynamic = min_progress + int((max_progress - min_progress) * ramp_ratio)
        computed = max(previous, dynamic)
        if run_elapsed_ms is not None and run_elapsed_ms >= 1000:
            computed = max(computed, min_progress)
        return min(99, computed), current_stage

    return max(previous, 1 if status else 0), stage or status or ""


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


def run_analysis_sync_for_user(
    payload: AnalyzeRequest,
    user_id: str,
    progress_callback: Optional[Callable[[str, Optional[str]], None]] = None,
) -> AnalyzeResponse:
    try:
        cleanup_expired_media()
    except Exception as exc:  # pragma: no cover
        logger.warning("media retention cleanup skipped: %s", exc)

    _track_media_ids(payload)
    response = run_analysis(payload, progress_callback=progress_callback)
    try:
        record_analysis_summary(user_id=user_id, response=response)
    except Exception as exc:  # pragma: no cover
        logger.warning("history summary save skipped: %s", exc)
    if progress_callback:
        try:
            progress_callback("result_ready", "分析中：结果已保存，正在准备打开结果页...")
        except Exception as exc:  # pragma: no cover
            logger.debug("analysis progress callback skipped on save: %s", exc)
    return response


def _classify_failure(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, (FaceQualityRejectError, VoiceQualityRejectError)):
        return exc.to_client_message(), False
    if isinstance(exc, TimeoutError):
        return "[ANALYZE_TIMEOUT] 云端处理超时，请稍后重试。", True
    if isinstance(exc, NotImplementedError):
        return str(exc), False
    if isinstance(exc, ValueError):
        return str(exc), False

    message = str(exc or "").strip()
    lowered = message.lower()
    transient_signals = (
        "timeout",
        "timed out",
        "network",
        "connection reset",
        "econnreset",
        "econnaborted",
        "502",
        "503",
        "504",
        "temporarily unavailable",
    )
    if any(signal in lowered for signal in transient_signals):
        return f"[ANALYZE_UPSTREAM_TRANSIENT] {message or '网络波动，请稍后重试。'}", True

    return f"analysis failed: {exc}", True


def _build_failed_status_message(detail: str, retryable: bool) -> str:
    normalized = (detail or "").strip()
    lowered = normalized.lower()
    if "[ANALYZE_TIMEOUT]" in normalized or "timeout" in lowered:
        return "分析超时：云端处理较慢，可稍后重试。"
    if retryable:
        return "分析失败：网络波动，可稍后重试。"
    return "分析失败"


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
        task = _TASKS.pop(task_id, None)
        token_key = str(task.get("task_token_key") or "").strip() if isinstance(task, dict) else ""
        if token_key:
            _TASK_TOKEN_INDEX.pop(token_key, None)

    max_items = _task_max_items()
    if len(_TASKS) <= max_items:
        return

    def _accepted_sort_key(item: tuple[str, dict[str, Any]]) -> float:
        accepted = _parse_iso_datetime(str(item[1].get("accepted_at") or ""))
        return accepted.timestamp() if accepted else 0.0

    for task_id, _task in sorted(_TASKS.items(), key=_accepted_sort_key)[: max(0, len(_TASKS) - max_items)]:
        if _TASKS.get(task_id, {}).get("status") in {"queued", "running"}:
            continue
        removed = _TASKS.pop(task_id, None)
        token_key = str(removed.get("task_token_key") or "").strip() if isinstance(removed, dict) else ""
        if token_key:
            _TASK_TOKEN_INDEX.pop(token_key, None)


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    accepted_at = str(task.get("accepted_at") or "")
    started_at = str(task.get("started_at") or "")
    finished_at = str(task.get("finished_at") or "")
    status = str(task.get("status") or "")

    queue_wait_ms = None
    if started_at:
        queue_wait_ms = _duration_ms(accepted_at, started_at)
    elif status == "queued":
        queue_wait_ms = _duration_ms(accepted_at)

    run_elapsed_ms = _duration_ms(started_at, finished_at if finished_at else None) if started_at else None
    total_elapsed_ms = _duration_ms(accepted_at, finished_at if finished_at else None)
    status_message = _dynamic_status_message(
        task,
        status=status,
        queue_wait_ms=queue_wait_ms,
        run_elapsed_ms=run_elapsed_ms,
    )
    poll_after_ms = _dynamic_poll_after_ms(status, queue_wait_ms, run_elapsed_ms)
    progress_percent, progress_stage = _build_progress_snapshot(
        task,
        status=status,
        queue_wait_ms=queue_wait_ms,
        run_elapsed_ms=run_elapsed_ms,
    )
    task["progress_percent"] = progress_percent
    task["progress_stage"] = progress_stage

    snapshot = {
        "task_id": task.get("task_id"),
        "status": status,
        "accepted_at": accepted_at,
        "started_at": started_at or None,
        "finished_at": finished_at or None,
        "poll_after_ms": poll_after_ms,
        "retryable": bool(task.get("retryable", False)),
        "error_detail": task.get("error_detail"),
        "status_message": status_message,
        "queue_wait_ms": queue_wait_ms,
        "run_elapsed_ms": run_elapsed_ms,
        "total_elapsed_ms": total_elapsed_ms,
        "progress_percent": progress_percent,
        "progress_stage": progress_stage,
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
        task["started_at"] = _iso_now_utc()
        task["status_message"] = "分析中：任务已开始，正在准备处理内容..."
        task["progress_stage"] = "running_bootstrap"
        task["progress_stage_started_at"] = task["started_at"]
        task["progress_percent"] = max(_normalize_progress_percent(task.get("progress_percent"), 0), 24)

    try:
        def _on_progress(stage: str, message: Optional[str] = None) -> None:
            normalized_stage = str(stage or "").strip()
            if not normalized_stage:
                return
            with _LOCK:
                current = _TASKS.get(task_id)
                if not current or str(current.get("status") or "") != "running":
                    return
                if normalized_stage != str(current.get("progress_stage") or ""):
                    current["progress_stage"] = normalized_stage
                    current["progress_stage_started_at"] = _iso_now_utc()
                if message:
                    current["status_message"] = str(message).strip()

        payload = AnalyzeRequest.model_validate(task.get("payload", {}))
        user_id = str(task.get("user_id") or "anonymous")
        response = run_analysis_sync_for_user(payload=payload, user_id=user_id, progress_callback=_on_progress)
        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "succeeded"
            current["status_message"] = "分析完成"
            current["finished_at"] = _iso_now_utc()
            current["progress_stage"] = "succeeded"
            current["progress_stage_started_at"] = current["finished_at"]
            current["progress_percent"] = 100
            current["retryable"] = False
            current["result"] = response.model_dump(mode="json")
            current["error_detail"] = None
            current.pop("payload", None)
            snapshot = _task_snapshot(current)
            logger.info(
                "async analyze succeeded: task_id=%s user_id=%s queue_wait_ms=%s run_elapsed_ms=%s total_elapsed_ms=%s",
                task_id,
                user_id,
                snapshot.get("queue_wait_ms"),
                snapshot.get("run_elapsed_ms"),
                snapshot.get("total_elapsed_ms"),
            )
    except Exception as exc:  # pragma: no cover
        detail, retryable = _classify_failure(exc)
        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "failed"
            current["status_message"] = _build_failed_status_message(detail, retryable)
            current["finished_at"] = _iso_now_utc()
            current["progress_stage"] = "failed"
            current["progress_stage_started_at"] = current["finished_at"]
            current["progress_percent"] = max(
                _normalize_progress_percent(current.get("progress_percent"), 0),
                1,
            )
            current["retryable"] = retryable
            current["error_detail"] = detail
            current.pop("result", None)
            current.pop("payload", None)
            snapshot = _task_snapshot(current)
            logger.warning(
                "async analyze failed: task_id=%s queue_wait_ms=%s run_elapsed_ms=%s total_elapsed_ms=%s detail=%s",
                task_id,
                snapshot.get("queue_wait_ms"),
                snapshot.get("run_elapsed_ms"),
                snapshot.get("total_elapsed_ms"),
                detail,
            )


def create_analyze_task(payload: AnalyzeRequest, user_id: str) -> dict[str, Any]:
    token = (payload.request_token or "").strip()
    token_key = f"{str(user_id or '').strip()}::{token}" if token else ""

    with _LOCK:
        _cleanup_finished_tasks_locked(time.time())
        if token_key:
            existing_task_id = _TASK_TOKEN_INDEX.get(token_key)
            if existing_task_id:
                existing_task = _TASKS.get(existing_task_id)
                if existing_task:
                    return _task_snapshot(existing_task)

    task_id = f"atk_{uuid.uuid4().hex[:12]}"
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "task_token_key": token_key or None,
        "status": "queued",
        "status_message": "排队中",
        "accepted_at": _iso_now_utc(),
        "started_at": None,
        "finished_at": None,
        "progress_stage": "queued",
        "progress_stage_started_at": None,
        "progress_percent": 4,
        "poll_after_ms": _poll_after_ms(),
        "retryable": False,
        "error_detail": None,
        "payload": payload.model_dump(mode="python"),
    }
    with _LOCK:
        if token_key:
            existing_task_id = _TASK_TOKEN_INDEX.get(token_key)
            if existing_task_id:
                existing_task = _TASKS.get(existing_task_id)
                if existing_task:
                    return _task_snapshot(existing_task)
        _TASKS[task_id] = task
        if token_key:
            _TASK_TOKEN_INDEX[token_key] = task_id

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
