import uuid
from typing import Optional

import numpy as np
from PIL import Image

from app.core.email_utils import send_analysis_email
from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.storage_service import cleanup_temp_files, resolve_input_file


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

    user_image = resolve_input_file(
        local_path=payload.user_image_path,
        file_url=payload.user_image_url,
        file_id=payload.user_image_file_id,
        field_name="user_image_path/user_image_url/user_image_file_id",
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
    )

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
        user_photo_np = _load_optional_image(user_image.path)
        poet_image_np = _load_optional_image(poet_image.path)
        guochao_image_np = _load_optional_image(guochao_image.path)

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
    finally:
        cleanup_temp_files(cleanup_paths)
