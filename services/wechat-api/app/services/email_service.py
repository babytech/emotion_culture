from typing import Optional

import numpy as np
from PIL import Image

from app.core.email_utils import send_analysis_email
from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.storage_service import cleanup_temp_files, resolve_input_file


def _load_optional_image(path_value: Optional[str]) -> Optional[np.ndarray]:
    if not path_value:
        return None

    with Image.open(path_value) as image:
        return np.array(image.convert("RGB"))


def send_analysis_result_email(payload: SendEmailRequest) -> SendEmailResponse:
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

    cleanup_paths = [
        path
        for path in [user_image.cleanup_path, poet_image.cleanup_path, guochao_image.cleanup_path]
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
        )
        return SendEmailResponse(success=success, message=message)
    finally:
        cleanup_temp_files(cleanup_paths)
