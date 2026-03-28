import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_id
from app.schemas.analyze import (
    AnalyzeAsyncCreateResponse,
    AnalyzeAsyncStatusResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)
from app.services.analysis_service import FaceQualityRejectError, VoiceQualityRejectError
from app.services.analyze_async_service import (
    create_analyze_task,
    get_analyze_task,
    run_analysis_sync_for_user,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeResponse:
    user_id = resolve_user_id(
        request=request,
        client_user_id=payload.client.user_id if payload.client else None,
    )
    try:
        return run_analysis_sync_for_user(payload=payload, user_id=user_id)
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


@router.post("/analyze/async", response_model=AnalyzeAsyncCreateResponse)
def create_async_analyze(payload: AnalyzeRequest, request: Request) -> AnalyzeAsyncCreateResponse:
    user_id = resolve_user_id(
        request=request,
        client_user_id=payload.client.user_id if payload.client else None,
    )
    task = create_analyze_task(payload=payload, user_id=user_id)
    return AnalyzeAsyncCreateResponse(
        task_id=str(task.get("task_id") or ""),
        status=str(task.get("status") or "queued"),
        accepted_at=str(task.get("accepted_at") or ""),
        poll_after_ms=int(task.get("poll_after_ms") or 1200),
        status_message=str(task.get("status_message") or "") or None,
    )


@router.get("/analyze/async/{task_id}", response_model=AnalyzeAsyncStatusResponse)
def get_async_analyze(task_id: str, request: Request) -> AnalyzeAsyncStatusResponse:
    user_id = resolve_user_id(request=request)
    task = get_analyze_task(task_id=task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="analyze task not found")

    result_payload = task.get("result")
    result = AnalyzeResponse.model_validate(result_payload) if isinstance(result_payload, dict) else None
    return AnalyzeAsyncStatusResponse(
        task_id=str(task.get("task_id") or task_id),
        status=str(task.get("status") or "queued"),
        accepted_at=str(task.get("accepted_at") or ""),
        started_at=str(task.get("started_at") or "") or None,
        finished_at=str(task.get("finished_at") or "") or None,
        poll_after_ms=int(task.get("poll_after_ms") or 1200),
        status_message=str(task.get("status_message") or "") or None,
        retryable=bool(task.get("retryable", False)),
        error_detail=str(task.get("error_detail") or "") or None,
        result=result,
    )
