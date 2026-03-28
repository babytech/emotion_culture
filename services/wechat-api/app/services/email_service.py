import logging
import time
import uuid
from typing import Optional

import numpy as np
from PIL import Image

from app.core.email_utils import send_analysis_email
from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.storage_service import cleanup_temp_files, resolve_input_file

logger = logging.getLogger(__name__)


def _classify_email_failure(message: str) -> tuple[str, bool]:
    normalized = (message or "").lower()

    if "configuration missing" in normalized or "配置" in normalized:
        return "EMAIL_CONFIG_INVALID", False
    if "认证" in normalized or "authentication" in normalized:
        return "EMAIL_AUTH_FAILED", False
    if "无法连接" in normalized or "断开连接" in normalized or "timeout" in normalized:
        return "EMAIL_NETWORK_ERROR", True
    if "unknown error" in normalized or "未知错误" in normalized:
        return "EMAIL_UNKNOWN_ERROR", True

    return "EMAIL_SEND_FAILED", True


def _load_optional_image(path_value: Optional[str]) -> Optional[np.ndarray]:
    if not path_value:
        return None

    with Image.open(path_value) as image:
        return np.array(image.convert("RGB"))


def send_analysis_result_email(payload: SendEmailRequest) -> SendEmailResponse:
    request_id = f"mail_{uuid.uuid4().hex[:12]}"
    total_started = time.perf_counter()

    user_media_resolve_started = time.perf_counter()
    user_image = resolve_input_file(
        local_path=payload.user_image_path,
        file_url=payload.user_image_url,
        file_id=payload.user_image_file_id,
        field_name="user_image_path/user_image_url/user_image_file_id",
        prefer_file_id=False,
    )
    poet_image = resolve_input_file(
        local_path=payload.poet_image_path,
        file_url=None,
        file_id=payload.poet_image_file_id,
        field_name="poet_image_path/poet_image_file_id",
    )
    guochao_image = resolve_input_file(
        local_path=payload.guochao_image_path,
        file_url=None,
        file_id=payload.guochao_image_file_id,
        field_name="guochao_image_path/guochao_image_file_id",
    )
    user_audio = resolve_input_file(
        local_path=payload.user_audio_path,
        file_url=payload.user_audio_url,
        file_id=payload.user_audio_file_id,
        field_name="user_audio_path/user_audio_url/user_audio_file_id",
        prefer_file_id=False,
    )
    user_media_resolve_ms = round((time.perf_counter() - user_media_resolve_started) * 1000, 1)

    cleanup_paths = [
        path
        for path in [
            user_image.cleanup_path,
            poet_image.cleanup_path,
            guochao_image.cleanup_path,
            user_audio.cleanup_path,
        ]
        if path
    ]

    try:
        decode_started = time.perf_counter()
        user_photo_np = _load_optional_image(user_image.path)
        poet_image_np = _load_optional_image(poet_image.path)
        guochao_image_np = _load_optional_image(guochao_image.path)
        decode_ms = round((time.perf_counter() - decode_started) * 1000, 1)

        send_started = time.perf_counter()
        success, message = send_analysis_email(
            to_email=payload.to_email,
            thoughts=payload.thoughts or "",
            user_photo_np=user_photo_np,
            poet_image_np=poet_image_np,
            poem=payload.poem_text or "",
            guochao_image_np=guochao_image_np,
            comfort=payload.comfort_text or "",
            user_audio_path=user_audio.path,
        )
        send_ms = round((time.perf_counter() - send_started) * 1000, 1)
        total_ms = round((time.perf_counter() - total_started) * 1000, 1)
        logger.info(
            "send-email completed: request_id=%s success=%s total_ms=%s media_resolve_ms=%s decode_ms=%s smtp_ms=%s",
            request_id,
            success,
            total_ms,
            user_media_resolve_ms,
            decode_ms,
            send_ms,
        )
        if success:
            return SendEmailResponse(
                request_id=request_id,
                success=True,
                message=message,
                error_code=None,
                retryable=False,
            )

        error_code, retryable = _classify_email_failure(message)
        return SendEmailResponse(
            request_id=request_id,
            success=False,
            message=message,
            error_code=error_code,
            retryable=retryable,
        )
    except Exception:
        total_ms = round((time.perf_counter() - total_started) * 1000, 1)
        logger.exception("send-email failed: request_id=%s total_ms=%s", request_id, total_ms)
        raise
    finally:
        cleanup_temp_files(cleanup_paths)
