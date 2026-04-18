import json
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.schemas.study_quiz import (
    QuizAnswerSubmission,
    QuizHistoryResponse,
    QuizPaperQuestion,
    QuizPaperResponse,
    QuizQuestionResult,
    QuizQuestionType,
    QuizRecordSummary,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizWrongItem,
    QuizWrongbookResponse,
)
from app.services.history_service import (
    get_quiz_record_detail_by_submit_token,
    get_quiz_record_detail,
    list_quiz_record_summaries,
    list_quiz_wrongbook_entries,
    record_quiz_submission,
)


_COURSE_ENGLISH = "english"
_SUPPORTED_COURSES = {_COURSE_ENGLISH}


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _seed_file_path(course: str) -> Path:
    base_dir = Path(__file__).resolve().parents[1] / "core"
    if course == _COURSE_ENGLISH:
        return base_dir / "study_quiz_english_seed.json"
    raise ValueError("[QUIZ_COURSE_UNSUPPORTED] 当前只支持英语试点。")


def _normalize_course(course: Optional[str]) -> str:
    value = (course or _COURSE_ENGLISH).strip().lower()
    if not value:
        return _COURSE_ENGLISH
    if value not in _SUPPORTED_COURSES:
        raise ValueError("[QUIZ_COURSE_UNSUPPORTED] 当前只支持英语试点。")
    return value


@lru_cache(maxsize=4)
def _load_course_bank(course: str) -> dict[str, Any]:
    path = _seed_file_path(course)
    try:
        with path.open("r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except FileNotFoundError as exc:
        raise ValueError("[QUIZ_BANK_NOT_FOUND] 题库文件不存在。") from exc
    except Exception as exc:
        raise ValueError("[QUIZ_BANK_INVALID] 题库文件无法读取。") from exc

    if not isinstance(payload, dict):
        raise ValueError("[QUIZ_BANK_INVALID] 题库格式错误。")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("[QUIZ_BANK_EMPTY] 题库为空。")
    return payload


def _build_paper_id(course: str, version: str) -> str:
    normalized_version = re.sub(r"[^0-9A-Za-z]+", "", version or "v1")
    return f"paper_{course}_{normalized_version or 'v1'}"


def _to_public_question(raw: dict[str, Any]) -> QuizPaperQuestion:
    question_payload = {
        "question_id": str(raw.get("question_id") or "").strip(),
        "type": str(raw.get("type") or "").strip(),
        "stem": str(raw.get("stem") or "").strip(),
        "options": raw.get("options") if isinstance(raw.get("options"), list) else [],
        "fills": raw.get("fills") if isinstance(raw.get("fills"), list) else [],
        "audio": str(raw.get("audio") or "no").strip() or "no",
        "tags": raw.get("tags") if isinstance(raw.get("tags"), list) else [],
        "difficulty": str(raw.get("difficulty") or "normal").strip() or "normal",
    }
    return QuizPaperQuestion.model_validate(question_payload)


def get_quiz_paper(course: Optional[str] = None) -> QuizPaperResponse:
    normalized_course = _normalize_course(course)
    bank = _load_course_bank(normalized_course)
    version = str(bank.get("version") or "v1")
    questions = [_to_public_question(item) for item in bank.get("questions", []) if isinstance(item, dict)]
    if not questions:
        raise ValueError("[QUIZ_BANK_EMPTY] 题库为空。")

    return QuizPaperResponse(
        paper_id=_build_paper_id(normalized_course, version),
        course=normalized_course,
        title=str(bank.get("title") or "伴学小测"),
        version=version,
        total_questions=len(questions),
        questions=questions,
    )


def _normalize_radio_answer(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    return text[:1] if text else ""


def _normalize_check_answer(value: Any) -> str:
    values: list[str] = []
    if isinstance(value, list):
        for item in value:
            text = re.sub(r"[^A-Z]+", "", str(item).strip().upper())
            if text:
                values.extend(list(text))
    elif value is not None:
        text = re.sub(r"[^A-Z]+", "", str(value).strip().upper())
        if text:
            values.extend(list(text))
    normalized = sorted({letter for letter in values if letter})
    return "".join(normalized)


def _normalize_fill_answer_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    text = str(value or "").strip()
    if not text:
        return []
    return [token.strip() for token in re.split(r"\s+", text) if token.strip()]


def _join_fill_answer(values: list[str]) -> str:
    return " ".join([item for item in values if item]).strip()


def _score_grade(score: int) -> str:
    if score >= 95:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def _answers_map(submissions: list[QuizAnswerSubmission]) -> dict[str, QuizAnswerSubmission]:
    mapping: dict[str, QuizAnswerSubmission] = {}
    for item in submissions:
        question_id = (item.question_id or "").strip()
        if not question_id:
            continue
        mapping[question_id] = item
    return mapping


def submit_quiz_for_user(user_id: str, payload: QuizSubmitRequest) -> QuizSubmitResponse:
    normalized_course = _normalize_course(payload.course)
    bank = _load_course_bank(normalized_course)
    questions = [item for item in bank.get("questions", []) if isinstance(item, dict)]
    if not questions:
        raise ValueError("[QUIZ_BANK_EMPTY] 题库为空。")

    version = str(bank.get("version") or "v1")
    expected_paper_id = _build_paper_id(normalized_course, version)
    input_paper_id = (payload.paper_id or "").strip()
    if input_paper_id and input_paper_id != expected_paper_id:
        raise ValueError("[QUIZ_PAPER_MISMATCH] 试卷版本已更新，请重新开始测验。")

    submit_token = (payload.submit_token or "").strip()[:128]
    if submit_token:
        existing = get_quiz_record_detail_by_submit_token(user_id=user_id, submit_token=submit_token)
        if existing is not None:
            return existing

    answer_by_question_id = _answers_map(payload.answers)
    question_score_full = 100.0 / float(len(questions))
    submitted_at = _iso_now_utc()
    quiz_record_id = f"qzr_{uuid.uuid4().hex[:12]}"

    results: list[QuizQuestionResult] = []
    wrong_items: list[QuizWrongItem] = []
    total_score = 0.0
    answered_questions = 0
    correct_count = 0
    partial_count = 0

    for raw in questions:
        question_id = str(raw.get("question_id") or "").strip()
        question_type = QuizQuestionType(str(raw.get("type") or "").strip())
        stem = str(raw.get("stem") or "").strip()
        right_answer_raw = str(raw.get("answer") or "").strip()

        user_submission = answer_by_question_id.get(question_id)
        user_answer_value = user_submission.answer if user_submission else None
        score = 0.0
        partial = False
        user_answer_text = ""
        right_answer_text = ""

        if question_type == QuizQuestionType.RADIO:
            right_answer = _normalize_radio_answer(right_answer_raw)
            user_answer = _normalize_radio_answer(user_answer_value)
            right_answer_text = right_answer
            user_answer_text = user_answer
            if user_answer:
                answered_questions += 1
            if user_answer and user_answer == right_answer:
                score = question_score_full

        elif question_type == QuizQuestionType.CHECK:
            right_answer = _normalize_check_answer(right_answer_raw)
            user_answer = _normalize_check_answer(user_answer_value)
            right_answer_text = right_answer
            user_answer_text = user_answer
            if user_answer:
                answered_questions += 1
            if user_answer and user_answer == right_answer:
                score = question_score_full

        else:
            right_values = _normalize_fill_answer_list(right_answer_raw)
            user_values = _normalize_fill_answer_list(user_answer_value)
            right_answer_text = _join_fill_answer(right_values)
            user_answer_text = _join_fill_answer(user_values)
            if user_answer_text:
                answered_questions += 1
            if right_values:
                compare_len = len(right_values)
                right_hits = 0
                for idx in range(compare_len):
                    right_value = right_values[idx].strip().lower()
                    user_value = user_values[idx].strip().lower() if idx < len(user_values) else ""
                    if right_value and user_value == right_value:
                        right_hits += 1
                if right_hits > 0:
                    score = question_score_full * (right_hits / float(compare_len))
                    partial = right_hits < compare_len

        score = round(score, 2)
        total_score += score
        is_correct = score >= (question_score_full - 0.001)
        if is_correct:
            correct_count += 1
        elif score > 0:
            partial_count += 1

        result_item = QuizQuestionResult(
            question_id=question_id,
            question_type=question_type,
            stem=stem,
            correct=is_correct,
            partial=partial,
            score=score,
            score_full=round(question_score_full, 2),
            user_answer=user_answer_text,
            right_answer=right_answer_text,
        )
        results.append(result_item)

        if not is_correct:
            wrong_items.append(
                QuizWrongItem(
                    wrong_id=f"wr_{uuid.uuid4().hex[:10]}",
                    question_id=question_id,
                    question_type=question_type,
                    stem=stem,
                    user_answer=user_answer_text or "未作答",
                    right_answer=right_answer_text,
                    score=score,
                    score_full=round(question_score_full, 2),
                )
            )

    score_int = int(round(min(100.0, max(0.0, total_score))))
    grade = _score_grade(score_int)
    wrong_count = len(wrong_items)
    summary = QuizRecordSummary(
        quiz_record_id=quiz_record_id,
        course=normalized_course,
        submitted_at=submitted_at,
        total_questions=len(questions),
        answered_questions=answered_questions,
        score=score_int,
        grade=grade,
        correct_count=correct_count,
        partial_count=partial_count,
        wrong_count=wrong_count,
    )

    record_quiz_submission(
        user_id=user_id,
        summary=summary,
        results=results,
        wrong_items=wrong_items,
        submit_token=submit_token,
    )

    return QuizSubmitResponse(
        quiz_record=summary,
        results=results,
        wrong_items=wrong_items,
        next_action_hint="小测已完成，可去做一次情绪分析，看看今天更适合怎样安排学习节奏。",
    )


def list_quiz_history_for_user(user_id: str, limit: int = 20, offset: int = 0) -> QuizHistoryResponse:
    return list_quiz_record_summaries(user_id=user_id, limit=limit, offset=offset)


def get_quiz_record_for_user(user_id: str, quiz_record_id: str) -> Optional[QuizSubmitResponse]:
    return get_quiz_record_detail(user_id=user_id, quiz_record_id=quiz_record_id)


def list_quiz_wrongbook_for_user(user_id: str, limit: int = 20, offset: int = 0) -> QuizWrongbookResponse:
    return list_quiz_wrongbook_entries(user_id=user_id, limit=limit, offset=offset)
