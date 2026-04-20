import os

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.user_identity import resolve_user_id
from app.schemas.study_quiz import (
    QuizBankIngestResponse,
    QuizHistoryResponse,
    QuizPaperResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizWrongbookResponse,
)
from app.services.study_quiz_ingest_service import ingest_quiz_bank_file
from app.services.study_quiz_service import (
    export_quiz_bank_excel_tsv,
    get_quiz_paper,
    get_quiz_record_for_user,
    list_quiz_history_for_user,
    list_quiz_wrongbook_for_user,
    submit_quiz_for_user,
)


router = APIRouter()


def _verify_quiz_admin_token(request: Request) -> None:
    expected = (os.getenv("STUDY_QUIZ_ADMIN_TOKEN", "") or "").strip()
    if not expected:
        return
    actual = (
        request.headers.get("x-admin-token")
        or request.headers.get("X-Admin-Token")
        or ""
    ).strip()
    if actual != expected:
        raise HTTPException(status_code=403, detail="[QUIZ_ADMIN_FORBIDDEN] 缺少或无效的管理密钥。")


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


@router.post("/study-quiz/bank/ingest", response_model=QuizBankIngestResponse)
async def ingest_study_quiz_bank(
    request: Request,
    file: UploadFile = File(...),
    course: str = Form(default="english"),
    title: str = Form(default="伴学小测"),
    version: str = Form(default=""),
) -> QuizBankIngestResponse:
    _verify_quiz_admin_token(request)
    filename = (file.filename or "quiz_upload").strip() or "quiz_upload"
    content_type = (file.content_type or "").strip() or "application/octet-stream"
    try:
        payload = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="[QUIZ_INGEST_INVALID] 文件读取失败。") from exc

    if not payload:
        raise HTTPException(status_code=400, detail="[QUIZ_INGEST_INVALID] 上传文件为空。")

    try:
        return ingest_quiz_bank_file(
            course=course,
            title=title,
            version=version or None,
            filename=filename,
            content_type=content_type,
            file_bytes=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/study-quiz/bank/export", response_class=PlainTextResponse)
def export_study_quiz_bank_sheet(
    request: Request,
    course: str = Query(default="english"),
) -> PlainTextResponse:
    _verify_quiz_admin_token(request)
    try:
        tsv_text = export_quiz_bank_excel_tsv(course=course)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"study_quiz_{course or 'course'}.xls"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return PlainTextResponse(
        content=tsv_text,
        headers=headers,
        media_type="application/vnd.ms-excel; charset=utf-8",
    )
