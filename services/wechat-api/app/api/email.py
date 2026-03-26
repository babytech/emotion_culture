import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_id
from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.history_service import mark_history_mail_sent
from app.services.email_service import send_analysis_result_email


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/send-email", response_model=SendEmailResponse)
@router.post("/send_email", response_model=SendEmailResponse)
def send_email(payload: SendEmailRequest, request: Request) -> SendEmailResponse:
    try:
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
