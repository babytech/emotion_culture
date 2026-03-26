import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_id
from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.history_service import mark_history_mail_sent
from app.services.media_retention_service import cleanup_expired_media, record_cloud_file_ids
from app.services.email_service import send_analysis_result_email


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/send-email", response_model=SendEmailResponse)
@router.post("/send_email", response_model=SendEmailResponse)
def send_email(payload: SendEmailRequest, request: Request) -> SendEmailResponse:
    try:
        try:
            cleanup_expired_media()
        except Exception as exc:
            logger.warning("media retention cleanup skipped: %s", exc)

        tracked_file_ids = [
            file_id
            for file_id in [
                payload.user_image_file_id,
                payload.poet_image_file_id,
                payload.guochao_image_file_id,
            ]
            if isinstance(file_id, str) and file_id.startswith("cloud://")
        ]
        if tracked_file_ids:
            try:
                record_cloud_file_ids(tracked_file_ids, source="send_email")
            except Exception as exc:
                logger.warning("media retention track skipped: %s", exc)

        result = send_analysis_result_email(payload)
        if result.success and payload.analysis_request_id:
            user_id = resolve_user_id(request=request)
            try:
                mark_history_mail_sent(
                    user_id=user_id,
                    request_id=payload.analysis_request_id,
                )
            except Exception as exc:
                logger.warning("history mail-sent mark skipped: %s", exc)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        return SendEmailResponse(
            request_id=None,
            success=False,
            message=f"邮件发送失败：服务异常 - {exc}",
            error_code="EMAIL_SERVICE_ERROR",
            retryable=True,
        )
