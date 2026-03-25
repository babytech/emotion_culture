from fastapi import APIRouter, HTTPException

from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.email_service import send_analysis_result_email


router = APIRouter()


@router.post("/send-email", response_model=SendEmailResponse)
@router.post("/send_email", response_model=SendEmailResponse)
def send_email(payload: SendEmailRequest) -> SendEmailResponse:
    try:
        return send_analysis_result_email(payload)
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
