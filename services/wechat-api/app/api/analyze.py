import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_id
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import (
    FaceQualityRejectError,
    VoiceQualityRejectError,
    run_analysis,
)
from app.services.history_service import record_analysis_summary


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    try:
        response = run_analysis(payload)
        user_id = resolve_user_id(
            request=request,
            client_user_id=payload.client.user_id if payload.client else None,
        )
        try:
            record_analysis_summary(user_id=user_id, response=response)
        except Exception as exc:
            logger.warning("history summary save skipped: %s", exc)
        return response
    except FaceQualityRejectError as exc:
        raise HTTPException(status_code=400, detail=exc.to_client_message()) from exc
    except VoiceQualityRejectError as exc:
        raise HTTPException(status_code=400, detail=exc.to_client_message()) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analysis failed: {exc}") from exc
