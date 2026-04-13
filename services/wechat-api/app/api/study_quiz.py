from fastapi import APIRouter, HTTPException, Query, Request

from app.core.user_identity import resolve_user_id
from app.schemas.study_quiz import (
    QuizHistoryResponse,
    QuizPaperResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizWrongbookResponse,
)
from app.services.study_quiz_service import (
    get_quiz_paper,
    get_quiz_record_for_user,
    list_quiz_history_for_user,
    list_quiz_wrongbook_for_user,
    submit_quiz_for_user,
)


router = APIRouter()


@router.get("/study-quiz/paper", response_model=QuizPaperResponse)
def get_study_quiz_paper(
    course: str = Query(default="english"),
) -> QuizPaperResponse:
    try:
        return get_quiz_paper(course=course)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/study-quiz/submit", response_model=QuizSubmitResponse)
def submit_study_quiz(payload: QuizSubmitRequest, request: Request) -> QuizSubmitResponse:
    user_id = resolve_user_id(request=request)
    try:
        return submit_quiz_for_user(user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/study-quiz/history", response_model=QuizHistoryResponse)
def list_study_quiz_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> QuizHistoryResponse:
    user_id = resolve_user_id(request=request)
    return list_quiz_history_for_user(user_id=user_id, limit=limit, offset=offset)


@router.get("/study-quiz/history/{quiz_record_id}", response_model=QuizSubmitResponse)
def get_study_quiz_history_detail(quiz_record_id: str, request: Request) -> QuizSubmitResponse:
    user_id = resolve_user_id(request=request)
    detail = get_quiz_record_for_user(user_id=user_id, quiz_record_id=quiz_record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="quiz history item not found")
    return detail


@router.get("/study-quiz/wrongbook", response_model=QuizWrongbookResponse)
def get_study_quiz_wrongbook(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> QuizWrongbookResponse:
    user_id = resolve_user_id(request=request)
    return list_quiz_wrongbook_for_user(user_id=user_id, limit=limit, offset=offset)
