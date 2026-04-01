import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.media_generate import MediaGenerateRequest
from app.services.image_provider_service import generate_stylized_image
from app.services.points_service import deduct_points_for_task, refund_points_transaction
from app.services.quota_service import consume_weekly_quota, release_weekly_quota


logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_TASKS: dict[str, dict[str, Any]] = {}
_TASK_TOKEN_INDEX: dict[str, str] = {}
_EXECUTOR: Optional[ThreadPoolExecutor] = None

_DEFAULT_POLL_AFTER_MS = 2200
_DEFAULT_TASK_TTL_SECONDS = 1800
_DEFAULT_MAX_TASKS = 800
_DEFAULT_WORKERS = 2
_DEFAULT_PROVIDER_MAX_RETRIES = 1
_DEFAULT_PROVIDER_RETRY_BACKOFF_MS = 220
_DEFAULT_WEEKLY_QUOTA = 1
_DEFAULT_POINTS_COST = 1


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
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


def _provider_max_retries() -> int:
    return max(0, _env_int("MEDIA_GEN_PROVIDER_MAX_RETRIES", _DEFAULT_PROVIDER_MAX_RETRIES))


def _provider_retry_backoff_ms() -> int:
    return max(0, _env_int("MEDIA_GEN_PROVIDER_RETRY_BACKOFF_MS", _DEFAULT_PROVIDER_RETRY_BACKOFF_MS))


def _weekly_quota_enabled() -> bool:
    return _env_bool("MEDIA_GEN_ENABLE_WEEKLY_QUOTA", True)


def _points_enabled() -> bool:
    return _env_bool("MEDIA_GEN_ENABLE_POINTS", True)


def _weekly_quota_limit() -> int:
    return max(1, _env_int("MEDIA_GEN_WEEKLY_LIMIT", _DEFAULT_WEEKLY_QUOTA))


def _points_cost() -> int:
    return max(0, _env_int("MEDIA_GEN_POINTS_COST", _DEFAULT_POINTS_COST))


def _consent_required() -> bool:
    return _env_bool("MEDIA_GEN_REQUIRE_CONSENT", True)


def _audit(event: str, **fields: Any) -> None:
    normalized = []
    for key in sorted(fields.keys()):
        value = fields[key]
        if value is None:
            continue
        normalized.append(f"{key}={value}")
    payload = " ".join(normalized)
    logger.info("media-generate audit: event=%s %s", event, payload)


def _error_code_for(exc: Exception) -> str:
    text = str(exc).upper()
    if "CONSENT" in text:
        return "MEDIA_GEN_CONSENT_REQUIRED"
    if "WEEKLY_LIMIT" in text:
        return "MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED"
    if "POINTS_INSUFFICIENT" in text:
        return "MEDIA_GEN_POINTS_INSUFFICIENT"
    if "STATIC_POOL_EMPTY" in text or "POOL_EMPTY" in text:
        return "MEDIA_GEN_POOL_EMPTY"
    if "STYLE" in text:
        return "MEDIA_GEN_STYLE_INVALID"
    if "PROVIDER_DISABLED" in text:
        return "MEDIA_GEN_PROVIDER_DISABLED"
    if isinstance(exc, ValueError):
        return "MEDIA_GEN_BAD_REQUEST"
    return "MEDIA_GEN_INTERNAL_ERROR"


def _retryable_for(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return False
    return True


def _provider_retryable_for(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        text = str(exc).upper()
        if (
            "STYLE_INVALID" in text
            or "PROVIDER_DISABLED" in text
            or "POOL_EMPTY" in text
            or "CONSENT" in text
            or "POINTS_INSUFFICIENT" in text
            or "WEEKLY_LIMIT_EXCEEDED" in text
        ):
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


def _is_cloud_file_id(reference: str) -> bool:
    text = (reference or "").strip().lower()
    return text.startswith("cloud://") or text.startswith("fileid://")


def _run_provider_with_retry(payload: MediaGenerateRequest) -> Any:
    max_attempts = _provider_max_retries() + 1
    backoff_ms = _provider_retry_backoff_ms()
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return generate_stylized_image(
                style=payload.style,
                source_path="",
                source_url=None,
                prompt=(payload.prompt or "").strip() or None,
                emotion_code=(payload.emotion_code or "").strip() or None,
                emotion_label=(payload.emotion_label or "").strip() or None,
                trigger_tags=payload.normalized_trigger_tags(),
            )
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            can_retry = attempt < max_attempts and _provider_retryable_for(exc)
            _audit(
                "provider_attempt",
                attempt=attempt,
                max_attempts=max_attempts,
                retry=can_retry,
                error=str(exc),
            )
            if not can_retry:
                break
            if backoff_ms > 0:
                time.sleep((backoff_ms * attempt) / 1000.0)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("MEDIA_GEN_PROVIDER_FAILED: unexpected empty provider result")


def _reserve_budget_for_task(task: dict[str, Any]) -> None:
    user_id = str(task.get("user_id") or "").strip()
    task_id = str(task.get("task_id") or "").strip()
    if not user_id or not task_id:
        raise ValueError("MEDIA_GEN_BAD_REQUEST: missing task identity")

    if _weekly_quota_enabled():
        quota_result = consume_weekly_quota(user_id=user_id, task_id=task_id, weekly_limit=_weekly_quota_limit())
        task["quota_consumed"] = bool(quota_result.get("consumed"))
        task["quota_week_key"] = str(quota_result.get("week_key") or "")
        _audit(
            "quota_checked",
            user_id=user_id,
            task_id=task_id,
            consumed=task.get("quota_consumed"),
            week_key=task.get("quota_week_key"),
            used=quota_result.get("used"),
            limit=quota_result.get("limit"),
        )
    else:
        task["quota_consumed"] = False
        task["quota_week_key"] = ""

    if _points_enabled():
        points_result = deduct_points_for_task(
            user_id=user_id,
            task_id=task_id,
            points=_points_cost(),
            reason="media_generate",
        )
        task["points_debit_txn_id"] = str(points_result.get("txn_id") or "")
        task["points_charged"] = bool(points_result.get("charged"))
        _audit(
            "points_debited",
            user_id=user_id,
            task_id=task_id,
            txn_id=task.get("points_debit_txn_id"),
            charged=task.get("points_charged"),
            balance=points_result.get("balance"),
            points=points_result.get("points"),
        )
    else:
        task["points_debit_txn_id"] = ""
        task["points_charged"] = False


def _rollback_budget_for_task(task: dict[str, Any], *, reason: str) -> None:
    user_id = str(task.get("user_id") or "").strip()
    task_id = str(task.get("task_id") or "").strip()
    points_txn_id = str(task.get("points_debit_txn_id") or "").strip()
    quota_consumed = bool(task.get("quota_consumed"))
    quota_released = False
    points_refunded = False

    if points_txn_id:
        refund_result = refund_points_transaction(
            user_id=user_id,
            debit_txn_id=points_txn_id,
            reason=reason,
        )
        points_refunded = bool(refund_result.get("refunded"))
        _audit(
            "points_refund",
            user_id=user_id,
            task_id=task_id,
            txn_id=points_txn_id,
            refunded=points_refunded,
            balance=refund_result.get("balance"),
            points=refund_result.get("points"),
            reason=reason,
        )

    if quota_consumed:
        quota_released = bool(release_weekly_quota(user_id=user_id, task_id=task_id))
        _audit(
            "quota_release",
            user_id=user_id,
            task_id=task_id,
            released=quota_released,
            reason=reason,
        )

    task["rollback_applied"] = points_refunded or quota_released


def _run_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task["status"] = "running"
        task["status_message"] = "选图中"
        task["started_at"] = _iso_now_utc()

    try:
        payload = MediaGenerateRequest.model_validate(task.get("payload", {}))
        user_id = str(task.get("user_id") or "anonymous")
        if user_id == "anonymous":
            raise ValueError("MEDIA_GEN_USER_REQUIRED: missing wechat user identity")

        artifact = _run_provider_with_retry(payload=payload)
        reference = str(getattr(artifact, "reference", "") or "").strip()
        if not reference:
            raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: missing media reference")

        result = {
            "generated_image_url": reference,
            "generated_image_file_id": reference if _is_cloud_file_id(reference) else None,
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
            current["status_message"] = "选图完成"
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
            _audit(
                "task_succeeded",
                task_id=task_id,
                user_id=user_id,
                style=payload.style.value,
                provider=artifact.provider,
                identity_type=task.get("identity_type"),
                queue_wait_ms=snapshot.get("queue_wait_ms"),
                run_elapsed_ms=snapshot.get("run_elapsed_ms"),
                total_elapsed_ms=snapshot.get("total_elapsed_ms"),
            )
    except Exception as exc:  # pragma: no cover
        with _LOCK:
            current = _TASKS.get(task_id)
            if not current:
                return
            try:
                _rollback_budget_for_task(current, reason=f"task_failed:{_error_code_for(exc)}")
            except Exception as rollback_exc:  # pragma: no cover
                logger.warning("media-generate rollback failed: task_id=%s detail=%s", task_id, rollback_exc)
            current["status"] = "failed"
            current["status_message"] = "选图失败"
            current["finished_at"] = _iso_now_utc()
            current["retryable"] = _retryable_for(exc)
            current["error_code"] = _error_code_for(exc)
            current["error_detail"] = str(exc)
            current.pop("result", None)
            current.pop("payload", None)
            snapshot = _snapshot(current)
            logger.warning(
                "media-generate failed: task_id=%s queue_wait_ms=%s run_elapsed_ms=%s total_elapsed_ms=%s error_code=%s detail=%s",
                task_id,
                snapshot.get("queue_wait_ms"),
                snapshot.get("run_elapsed_ms"),
                snapshot.get("total_elapsed_ms"),
                current.get("error_code"),
                current.get("error_detail"),
            )


def create_media_generate_task(
    payload: MediaGenerateRequest,
    user_id: str,
    *,
    identity_type: str = "unknown",
) -> dict[str, Any]:
    token = (payload.request_token or "").strip()
    token_key = f"{str(user_id or '').strip()}::{token}" if token else ""
    if _consent_required() and not payload.consent_confirmed:
        raise ValueError("MEDIA_GEN_CONSENT_REQUIRED: user consent must be confirmed before generation")

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
        "identity_type": identity_type,
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
        "quota_consumed": False,
        "quota_week_key": "",
        "points_debit_txn_id": "",
        "points_charged": False,
        "rollback_applied": False,
        "payload": payload.model_dump(mode="python"),
    }

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

    try:
        _reserve_budget_for_task(task)
    except Exception as exc:
        with _LOCK:
            _TASKS.pop(task_id, None)
            if token_key:
                _TASK_TOKEN_INDEX.pop(token_key, None)
        # If points were deducted before failure, return to user.
        try:
            _rollback_budget_for_task(task, reason=f"reserve_failed:{_error_code_for(exc)}")
        except Exception:  # pragma: no cover
            pass
        _audit(
            "task_rejected",
            task_id=task_id,
            user_id=user_id,
            identity_type=identity_type,
            error=str(exc),
        )
        raise

    _executor().submit(_run_task, task_id)
    _audit(
        "task_accepted",
        task_id=task_id,
        user_id=user_id,
        identity_type=identity_type,
        consent_confirmed=payload.consent_confirmed,
        consent_version=(payload.consent_version or "").strip() or None,
        style=payload.style.value,
        token=token or None,
    )
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
