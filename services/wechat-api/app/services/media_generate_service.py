import hashlib
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from app.schemas.media_generate import MediaGenerateRequest, MediaGenerateStyle
from app.services.image_provider_service import generate_stylized_image
from app.services.points_service import deduct_points_for_task, refund_points_transaction
from app.services.quota_service import consume_weekly_quota, release_weekly_quota
from app.services.storage_service import cleanup_temp_files, resolve_input_file


logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_TASKS: dict[str, dict[str, Any]] = {}
_TASK_TOKEN_INDEX: dict[str, str] = {}
_EXECUTOR: Optional[ThreadPoolExecutor] = None

_DEFAULT_POLL_AFTER_MS = 2200
_DEFAULT_TASK_TTL_SECONDS = 1800
_DEFAULT_MAX_TASKS = 800
_DEFAULT_WORKERS = 2
_DEFAULT_WEEKLY_LIMIT = 1
_DEFAULT_POINTS_PER_TASK = 1

_GENERATED_DIR = Path(
    (os.getenv("MEDIA_GEN_OUTPUT_DIR", "/tmp/emotion_culture/generated_media") or "").strip()
).expanduser()


def ensure_generated_media_dir() -> Path:
    _GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return _GENERATED_DIR


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
    return _env_int("MEDIA_GEN_POLL_AFTER_MS", _DEFAULT_POLL_AFTER_MS)


def _task_ttl_seconds() -> int:
    return _env_int("MEDIA_GEN_TASK_TTL_SECONDS", _DEFAULT_TASK_TTL_SECONDS)


def _task_max_items() -> int:
    return _env_int("MEDIA_GEN_TASK_MAX_ITEMS", _DEFAULT_MAX_TASKS)


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=_env_int("MEDIA_GEN_WORKERS", _DEFAULT_WORKERS))
    return _EXECUTOR


def _weekly_limit() -> int:
    return _env_int("MEDIA_GEN_WEEKLY_LIMIT", _DEFAULT_WEEKLY_LIMIT)


def _points_per_task() -> int:
    return _env_int("MEDIA_GEN_POINTS_PER_TASK", _DEFAULT_POINTS_PER_TASK)


def _error_code_for(exc: Exception) -> str:
    text = str(exc).upper()
    if "CONSENT" in text:
        return "MEDIA_GEN_CONSENT_REQUIRED"
    if "STYLE" in text:
        return "MEDIA_GEN_STYLE_INVALID"
    if "SOURCE_IMAGE" in text or "SELFIE" in text:
        return "MEDIA_GEN_SOURCE_INVALID"
    if isinstance(exc, NotImplementedError):
        return "MEDIA_GEN_PROVIDER_NOT_READY"
    if isinstance(exc, ValueError):
        return "MEDIA_GEN_BAD_REQUEST"
    return "MEDIA_GEN_INTERNAL_ERROR"


def _retryable_for(exc: Exception) -> bool:
    if isinstance(exc, (ValueError, NotImplementedError)):
        return False
    return True


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


def _snapshot(task: dict[str, Any]) -> dict[str, Any]:
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

    snapshot = {
        "task_id": task.get("task_id"),
        "status": status,
        "accepted_at": accepted_at,
        "started_at": started_at or None,
        "finished_at": finished_at or None,
        "poll_after_ms": task.get("poll_after_ms", _poll_after_ms()),
        "status_message": task.get("status_message") or "",
        "retryable": bool(task.get("retryable", False)),
        "error_code": task.get("error_code"),
        "error_detail": task.get("error_detail"),
        "queue_wait_ms": queue_wait_ms,
        "run_elapsed_ms": run_elapsed_ms,
        "total_elapsed_ms": total_elapsed_ms,
    }
    if task.get("status") == "succeeded" and isinstance(task.get("result"), dict):
        snapshot["result"] = task["result"]
    return snapshot


def _build_output_name(*, user_id: str, style: MediaGenerateStyle, task_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(f"{user_id}|{style.value}|{task_id}".encode("utf-8")).hexdigest()[:10]
    return f"{stamp}_{style.value}_{digest}.jpg"


def _stage_generated_image(source_path: str, *, user_id: str, style: MediaGenerateStyle, task_id: str) -> str:
    output_dir = ensure_generated_media_dir()
    output_name = _build_output_name(user_id=user_id, style=style, task_id=task_id)
    output_path = output_dir / output_name

    with Image.open(source_path) as image:
        image.convert("RGB").save(
            output_path,
            format="JPEG",
            quality=max(55, min(92, _env_int("MEDIA_GEN_OUTPUT_QUALITY", 84))),
            optimize=True,
            progressive=True,
        )
    return f"/generated-media/{output_name}"


def _run_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["status"] = "running"
        task["status_message"] = "生图中"
        task["started_at"] = _iso_now_utc()

    cleanup_paths: list[str] = []
    try:
        payload = MediaGenerateRequest.model_validate(task.get("payload", {}))
        user_id = str(task.get("user_id") or "anonymous")
        if user_id == "anonymous":
            raise ValueError("MEDIA_GEN_USER_REQUIRED: missing wechat user identity")
        if not payload.consent_confirmed:
            raise ValueError("MEDIA_GEN_CONSENT_REQUIRED: user consent is required before generation")

        resolved_source = resolve_input_file(
            local_path=payload.resolved_source_image_local_path(),
            file_url=payload.resolved_source_image_url(),
            file_id=payload.resolved_source_image_file_id(),
            field_name="source_image_path/source_image_url/source_image_file_id",
            prefer_file_id=False,
        )
        if not resolved_source.path:
            raise ValueError("MEDIA_GEN_SOURCE_INVALID: source selfie image is required")
        if resolved_source.cleanup_path:
            cleanup_paths.append(resolved_source.cleanup_path)

        artifact = generate_stylized_image(
            style=payload.style,
            source_path=resolved_source.path,
            source_url=payload.resolved_source_image_url(),
            prompt=(payload.prompt or "").strip() or None,
        )
        if artifact.cleanup_path:
            cleanup_paths.append(artifact.cleanup_path)

        generated_url = _stage_generated_image(
            artifact.path,
            user_id=user_id,
            style=payload.style,
            task_id=task_id,
        )

        result = {
            "generated_image_url": generated_url,
            "generated_image_file_id": generated_url,
            "provider": artifact.provider,
            "style": payload.style.value,
            "generated_at": _iso_now_utc(),
            "prompt": (payload.prompt or "").strip() or None,
            "analysis_request_id": (payload.analysis_request_id or "").strip() or None,
        }

        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "succeeded"
            current["status_message"] = "生图完成"
            current["finished_at"] = _iso_now_utc()
            current["retryable"] = False
            current["error_code"] = None
            current["error_detail"] = None
            current["result"] = result
            current.pop("payload", None)
            snapshot = _snapshot(current)
            logger.info(
                "media-generate succeeded: task_id=%s user_id=%s queue_wait_ms=%s run_elapsed_ms=%s total_elapsed_ms=%s",
                task_id,
                user_id,
                snapshot.get("queue_wait_ms"),
                snapshot.get("run_elapsed_ms"),
                snapshot.get("total_elapsed_ms"),
            )
    except Exception as exc:  # pragma: no cover
        refunded = False
        quota_released = False
        with _LOCK:
            current = _TASKS.get(task_id)
            points_txn_id = str(current.get("points_txn_id") or "").strip() if isinstance(current, dict) else ""
            quota_consumed = bool(current.get("quota_consumed")) if isinstance(current, dict) else False
            current_user_id = str(current.get("user_id") or "").strip() if isinstance(current, dict) else ""
        if points_txn_id and current_user_id:
            try:
                refunded = bool(
                    refund_points_transaction(
                        current_user_id,
                        points_txn_id,
                        reason="media_generate_failed",
                    ).get("refunded", False)
                )
            except Exception:
                refunded = False
        if quota_consumed and current_user_id:
            try:
                quota_released = release_weekly_quota(current_user_id, task_id)
            except Exception:
                quota_released = False

        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            current["status"] = "failed"
            current["status_message"] = "生图失败"
            current["finished_at"] = _iso_now_utc()
            current["retryable"] = _retryable_for(exc)
            current["error_code"] = _error_code_for(exc)
            current["error_detail"] = str(exc)
            current.pop("result", None)
            current.pop("payload", None)
            snapshot = _snapshot(current)
            logger.warning(
                "media-generate failed: task_id=%s queue_wait_ms=%s run_elapsed_ms=%s total_elapsed_ms=%s error_code=%s refunded=%s quota_released=%s detail=%s",
                task_id,
                snapshot.get("queue_wait_ms"),
                snapshot.get("run_elapsed_ms"),
                snapshot.get("total_elapsed_ms"),
                current.get("error_code"),
                refunded,
                quota_released,
                current.get("error_detail"),
            )
    finally:
        cleanup_temp_files(cleanup_paths)


def create_media_generate_task(payload: MediaGenerateRequest, user_id: str) -> dict[str, Any]:
    if not payload.consent_confirmed:
        raise ValueError("MEDIA_GEN_CONSENT_REQUIRED: user consent is required before generation")
    if not (
        payload.resolved_source_image_local_path()
        or payload.resolved_source_image_url()
        or payload.resolved_source_image_file_id()
    ):
        raise ValueError("MEDIA_GEN_SOURCE_INVALID: source selfie image is required")

    token = (payload.request_token or "").strip()
    token_key = f"{str(user_id or '').strip()}::{token}" if token else ""

    with _LOCK:
        _cleanup_finished_tasks_locked(time.time())
        if token_key:
            existing_task_id = _TASK_TOKEN_INDEX.get(token_key)
            if existing_task_id:
                existing = _TASKS.get(existing_task_id)
                if existing:
                    return _snapshot(existing)

    task_id = f"mgt_{uuid.uuid4().hex[:12]}"
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "task_token_key": token_key or None,
        "status": "queued",
        "status_message": "排队中",
        "accepted_at": _iso_now_utc(),
        "started_at": None,
        "finished_at": None,
        "poll_after_ms": _poll_after_ms(),
        "retryable": False,
        "error_code": None,
        "error_detail": None,
        "payload": payload.model_dump(mode="python"),
    }

    try:
        quota_info = consume_weekly_quota(
            user_id=user_id,
            task_id=task_id,
            weekly_limit=_weekly_limit(),
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    quota_consumed = bool(quota_info.get("consumed", False))

    try:
        points_info = deduct_points_for_task(
            user_id=user_id,
            task_id=task_id,
            points=_points_per_task(),
            reason="media_generate_create",
        )
    except ValueError as exc:
        if quota_consumed:
            release_weekly_quota(user_id, task_id)
        raise ValueError(str(exc)) from exc

    task["quota_consumed"] = quota_consumed
    task["points_charged"] = bool(points_info.get("charged", False))
    task["points_txn_id"] = points_info.get("txn_id")
    task["points_cost"] = int(points_info.get("points", 0) or 0)
    task["points_balance_after_charge"] = int(points_info.get("balance", 0) or 0)

    with _LOCK:
        if token_key:
            existing_task_id = _TASK_TOKEN_INDEX.get(token_key)
            if existing_task_id:
                existing = _TASKS.get(existing_task_id)
                if existing:
                    return _snapshot(existing)
        _TASKS[task_id] = task
        if token_key:
            _TASK_TOKEN_INDEX[token_key] = task_id

    _executor().submit(_run_task, task_id)
    return _snapshot(task)


def get_media_generate_task(task_id: str, user_id: str) -> Optional[dict[str, Any]]:
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
        return _snapshot(task)
