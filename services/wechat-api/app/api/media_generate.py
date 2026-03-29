from fastapi import APIRouter, HTTPException, Request

from app.core.user_identity import resolve_user_id
from app.schemas.media_generate import (
    MediaGenerateCreateResponse,
    MediaGenerateRequest,
    MediaGenerateResult,
    MediaGenerateStatusResponse,
)
from app.services.media_generate_service import (
    create_media_generate_task,
    get_media_generate_task,
)


router = APIRouter()


@router.post("/media-generate", response_model=MediaGenerateCreateResponse)
@router.post("/media_generate", response_model=MediaGenerateCreateResponse)
def create_media_generate(payload: MediaGenerateRequest, request: Request) -> MediaGenerateCreateResponse:
    user_id = resolve_user_id(
        request=request,
        client_user_id=payload.client.user_id if payload.client else None,
    )
    if user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="MEDIA_GEN_USER_REQUIRED: please call with x-wx-openid identity",
        )

    try:
        task = create_media_generate_task(payload=payload, user_id=user_id)
    except ValueError as exc:
        detail = str(exc)
        if "MEDIA_GEN_WEEKLY_LIMIT_EXCEEDED" in detail:
            raise HTTPException(status_code=429, detail=detail) from exc
        if "MEDIA_GEN_POINTS_INSUFFICIENT" in detail:
            raise HTTPException(status_code=402, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return MediaGenerateCreateResponse(
        task_id=str(task.get("task_id") or ""),
        status=str(task.get("status") or "queued"),
        accepted_at=str(task.get("accepted_at") or ""),
        poll_after_ms=int(task.get("poll_after_ms") or 2200),
        status_message=str(task.get("status_message") or "") or None,
    )


@router.get("/media-generate/{task_id}", response_model=MediaGenerateStatusResponse)
@router.get("/media_generate/{task_id}", response_model=MediaGenerateStatusResponse)
def get_media_generate(task_id: str, request: Request) -> MediaGenerateStatusResponse:
    user_id = resolve_user_id(request=request)
    if user_id == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="MEDIA_GEN_USER_REQUIRED: please call with x-wx-openid identity",
        )

    task = get_media_generate_task(task_id=task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="media generate task not found")

    result_payload = task.get("result")
    result = MediaGenerateResult.model_validate(result_payload) if isinstance(result_payload, dict) else None
    return MediaGenerateStatusResponse(
        task_id=str(task.get("task_id") or task_id),
        status=str(task.get("status") or "queued"),
        accepted_at=str(task.get("accepted_at") or ""),
        started_at=str(task.get("started_at") or "") or None,
        finished_at=str(task.get("finished_at") or "") or None,
        poll_after_ms=int(task.get("poll_after_ms") or 2200),
        status_message=str(task.get("status_message") or "") or None,
        retryable=bool(task.get("retryable", False)),
        error_code=str(task.get("error_code") or "") or None,
        error_detail=str(task.get("error_detail") or "") or None,
        queue_wait_ms=int(task.get("queue_wait_ms")) if task.get("queue_wait_ms") is not None else None,
        run_elapsed_ms=int(task.get("run_elapsed_ms")) if task.get("run_elapsed_ms") is not None else None,
        total_elapsed_ms=int(task.get("total_elapsed_ms")) if task.get("total_elapsed_ms") is not None else None,
        result=result,
    )
