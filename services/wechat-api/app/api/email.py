from fastapi import APIRouter, HTTPException

from app.schemas.email import SendEmailRequest, SendEmailResponse
from app.services.email_service import send_analysis_result_email


router = APIRouter()


@router.post("/send-email", response_model=SendEmailResponse)
def send_email(payload: SendEmailRequest) -> SendEmailResponse:
    try:
        return send_analysis_result_email(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"send email failed: {exc}") from exc
