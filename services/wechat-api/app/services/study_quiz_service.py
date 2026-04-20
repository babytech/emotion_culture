import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.schemas.study_quiz import (
    QuizAnswerSubmission,
    QuizBankIngestQuestion,
    QuizBankIngestResponse,
    QuizHistoryResponse,
    QuizPaperQuestion,
    QuizPointsReward,
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
from app.services.points_service import credit_points_for_action


_COURSE_CHINESE = "chinese"
_COURSE_ENGLISH = "english"
_COURSE_MATH = "math"
_COURSE_PHYSICS = "physics"
_COURSE_CHEMISTRY = "chemistry"
_COURSE_HISTORY = "history"
_COURSE_GEOGRAPHY = "geography"
_SUPPORTED_COURSES = {
    _COURSE_CHINESE,
    _COURSE_ENGLISH,
    _COURSE_MATH,
    _COURSE_PHYSICS,
    _COURSE_CHEMISTRY,
    _COURSE_HISTORY,
    _COURSE_GEOGRAPHY,
}
_COURSE_DISPLAY_NAME = {
    _COURSE_CHINESE: "语文",
    _COURSE_ENGLISH: "英语",
    _COURSE_MATH: "数学",
    _COURSE_PHYSICS: "物理",
    _COURSE_CHEMISTRY: "化学",
    _COURSE_HISTORY: "历史",
    _COURSE_GEOGRAPHY: "地理",
}
_COURSE_ALIASES = {
    "zh": _COURSE_CHINESE,
    "cn": _COURSE_CHINESE,
    "chinese": _COURSE_CHINESE,
    "语文": _COURSE_CHINESE,
    "english": _COURSE_ENGLISH,
    "en": _COURSE_ENGLISH,
    "英语": _COURSE_ENGLISH,
    "math": _COURSE_MATH,
    "mathematics": _COURSE_MATH,
    "数学": _COURSE_MATH,
    "physics": _COURSE_PHYSICS,
    "物理": _COURSE_PHYSICS,
    "chemistry": _COURSE_CHEMISTRY,
    "化学": _COURSE_CHEMISTRY,
    "history": _COURSE_HISTORY,
    "历史": _COURSE_HISTORY,
    "geography": _COURSE_GEOGRAPHY,
    "地理": _COURSE_GEOGRAPHY,
}
_BANK_STORE_LOCK = threading.RLock()
_DEFAULT_BANK_STORE_PATH = "/tmp/emotion_culture/study_quiz_bank_store.json"


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _seed_file_path(course: str) -> Path:
    base_dir = Path(__file__).resolve().parents[1] / "core"
    # Stage2 multi-subject rollout: before each subject has its own seed, fall back
    # to the validated english seed to keep all subject paths available.
    if course in _SUPPORTED_COURSES:
        return base_dir / "study_quiz_english_seed.json"
    raise ValueError("[QUIZ_COURSE_UNSUPPORTED] 当前仅支持语文/英语/数学/物理/化学/历史/地理。")


def _normalize_course(course: Optional[str]) -> str:
    value = (course or _COURSE_ENGLISH).strip().lower()
    if not value:
        return _COURSE_ENGLISH
    normalized = _COURSE_ALIASES.get(value)
    if normalized in _SUPPORTED_COURSES:
        return normalized
    raise ValueError("[QUIZ_COURSE_UNSUPPORTED] 当前仅支持语文/英语/数学/物理/化学/历史/地理。")


def _bank_store_path() -> Path:
    raw = (os.getenv("STUDY_QUIZ_BANK_STORE_PATH", _DEFAULT_BANK_STORE_PATH) or "").strip()
    path = Path(raw).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_bank_store() -> dict[str, Any]:
    path = _bank_store_path()
    if not path.exists():
        return {"version": 1, "courses": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "courses": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "courses": {}}
    courses = payload.get("courses")
    if not isinstance(courses, dict):
        payload["courses"] = {}
    return payload


def _save_bank_store(payload: dict[str, Any]) -> None:
    path = _bank_store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _quiz_points_enabled() -> bool:
    return _env_bool("STUDY_QUIZ_ENABLE_POINTS", True)


def _quiz_points_by_score(score: int) -> int:
    value = max(0, min(100, int(score or 0)))
    if value >= 95:
        return 8
    if value >= 85:
        return 6
    if value >= 75:
        return 4
    if value >= 60:
        return 2
    return 1


def _load_override_bank(course: str) -> Optional[dict[str, Any]]:
    with _BANK_STORE_LOCK:
        payload = _load_bank_store()
        courses = payload.get("courses", {})
        if not isinstance(courses, dict):
            return None
        bank = courses.get(course)
        return bank if isinstance(bank, dict) else None


def _normalize_bank_question(raw: dict[str, Any], index: int) -> dict[str, Any]:
    question_id = str(raw.get("question_id") or f"{index + 1}").strip()
    question_type = str(raw.get("type") or "").strip().lower()
    if question_type not in {"radio", "check", "fill"}:
        raise ValueError(f"[QUIZ_BANK_INVALID] 第 {index + 1} 题 type 非法，仅支持 radio/check/fill。")
    stem = str(raw.get("stem") or "").strip()
    if not stem:
        raise ValueError(f"[QUIZ_BANK_INVALID] 第 {index + 1} 题 stem 不能为空。")
    answer = str(raw.get("answer") or "").strip()
    if not answer:
        raise ValueError(f"[QUIZ_BANK_INVALID] 第 {index + 1} 题 answer 不能为空。")
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    fills = raw.get("fills") if isinstance(raw.get("fills"), list) else []
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    return {
        "question_id": question_id,
        "type": question_type,
        "stem": stem,
        "options": options,
        "fills": fills,
        "audio": str(raw.get("audio") or "no").strip() or "no",
        "tags": [str(item).strip() for item in tags if str(item).strip()],
        "difficulty": str(raw.get("difficulty") or "normal").strip() or "normal",
        "answer": answer,
    }


@lru_cache(maxsize=4)
def _load_course_bank(course: str) -> dict[str, Any]:
    override_bank = _load_override_bank(course)
    if isinstance(override_bank, dict):
        questions = override_bank.get("questions")
        if isinstance(questions, list) and questions:
            return override_bank

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

    normalized_payload = dict(payload)
    normalized_payload["course"] = course
    display_name = _COURSE_DISPLAY_NAME.get(course) or "课程"
    raw_title = str(normalized_payload.get("title") or "").strip()
    if not raw_title:
        normalized_payload["title"] = f"{display_name}伴学小测"
    elif course != _COURSE_ENGLISH and ("英语" in raw_title or raw_title.lower().startswith("english")):
        normalized_payload["title"] = f"{display_name}伴学小测"
    return normalized_payload


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
    display_name = _COURSE_DISPLAY_NAME.get(normalized_course) or "课程"
    default_title = f"{display_name}伴学小测"

    return QuizPaperResponse(
        paper_id=_build_paper_id(normalized_course, version),
        course=normalized_course,
        title=str(bank.get("title") or default_title),
        version=version,
        total_questions=len(questions),
        questions=questions,
    )


def upsert_quiz_bank(
    *,
    course: str,
    title: str,
    version: Optional[str],
    questions: list[dict[str, Any]],
    source_type: str = "manual",
) -> QuizBankIngestResponse:
    normalized_course = _normalize_course(course)
    default_title = f"{_COURSE_DISPLAY_NAME.get(normalized_course) or '课程'}伴学小测"
    cleaned_questions: list[dict[str, Any]] = []
    for index, raw in enumerate(questions):
        if not isinstance(raw, dict):
            raise ValueError(f"[QUIZ_BANK_INVALID] 第 {index + 1} 题结构非法。")
        cleaned_questions.append(_normalize_bank_question(raw, index))

    if not cleaned_questions:
        raise ValueError("[QUIZ_BANK_EMPTY] 导入后题库为空。")

    payload = {
        "course": normalized_course,
        "title": (title or default_title).strip() or default_title,
        "version": (version or _iso_now_utc().replace(":", "").replace("-", "")).strip(),
        "questions": cleaned_questions,
        "updated_at": _iso_now_utc(),
        "source_type": (source_type or "manual").strip() or "manual",
    }

    with _BANK_STORE_LOCK:
        store = _load_bank_store()
        courses = store.setdefault("courses", {})
        courses[normalized_course] = payload
        _save_bank_store(store)
    _load_course_bank.cache_clear()

    excel_rows = export_quiz_bank_excel_rows(course=normalized_course)
    return QuizBankIngestResponse(
        course=normalized_course,
        title=str(payload.get("title") or "伴学小测"),
        version=str(payload.get("version") or "v1"),
        source_type=str(payload.get("source_type") or "manual"),
        persisted=True,
        total_questions=len(cleaned_questions),
        questions=[
            QuizBankIngestQuestion.model_validate(item)
            for item in cleaned_questions
        ],
        excel_rows=excel_rows,
    )


def export_quiz_bank_excel_rows(course: Optional[str] = None) -> list[list[str]]:
    normalized_course = _normalize_course(course)
    bank = _load_course_bank(normalized_course)
    questions = [item for item in bank.get("questions", []) if isinstance(item, dict)]
    rows: list[list[str]] = [
        ["question_id", "type", "stem", "options", "fills", "answer", "difficulty", "tags", "audio"]
    ]
    for item in questions:
        options = item.get("options") if isinstance(item.get("options"), list) else []
        fills = item.get("fills") if isinstance(item.get("fills"), list) else []
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        option_text = " | ".join(
            [
                f"{str(opt.get('item') or '').strip()}:{str(opt.get('content') or '').strip()}"
                for opt in options
                if isinstance(opt, dict)
            ]
        )
        fill_text = " | ".join(
            [
                f"{str(fill.get('item') or '').strip()}:{str(fill.get('content') or '').strip()}"
                for fill in fills
                if isinstance(fill, dict)
            ]
        )
        tag_text = ",".join([str(tag).strip() for tag in tags if str(tag).strip()])
        rows.append(
            [
                str(item.get("question_id") or "").strip(),
                str(item.get("type") or "").strip(),
                str(item.get("stem") or "").strip(),
                option_text,
                fill_text,
                str(item.get("answer") or "").strip(),
                str(item.get("difficulty") or "normal").strip() or "normal",
                tag_text,
                str(item.get("audio") or "no").strip() or "no",
            ]
        )
    return rows


def export_quiz_bank_excel_tsv(course: Optional[str] = None) -> str:
    rows = export_quiz_bank_excel_rows(course=course)
    escaped_rows: list[str] = []
    for row in rows:
        cells = [str(cell or "").replace("\t", " ").replace("\n", " ") for cell in row]
        escaped_rows.append("\t".join(cells))
    return "\n".join(escaped_rows)


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


def _award_points_for_quiz_submit(
    user_id: str,
    *,
    quiz_record_id: str,
    score: int,
) -> Optional[QuizPointsReward]:
    if not _quiz_points_enabled():
        return None

    points = _quiz_points_by_score(score)
    action_key = f"quiz_submit:{quiz_record_id}"
    result = credit_points_for_action(
        user_id=user_id,
        action_key=action_key,
        points=points,
        reason="study_quiz_submit",
    )
    return QuizPointsReward(
        awarded=bool(result.get("awarded")),
        points=int(result.get("points") or points),
        balance=int(result.get("balance")) if result.get("balance") is not None else None,
        reason="study_quiz_submit",
        action_key=action_key,
    )


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
        is_answered = False

        if question_type == QuizQuestionType.RADIO:
            right_answer = _normalize_radio_answer(right_answer_raw)
            user_answer = _normalize_radio_answer(user_answer_value)
            right_answer_text = right_answer
            user_answer_text = user_answer
            if user_answer:
                is_answered = True
                answered_questions += 1
            if user_answer and user_answer == right_answer:
                score = question_score_full

        elif question_type == QuizQuestionType.CHECK:
            right_answer = _normalize_check_answer(right_answer_raw)
            user_answer = _normalize_check_answer(user_answer_value)
            right_answer_text = right_answer
            user_answer_text = user_answer
            if user_answer:
                is_answered = True
                answered_questions += 1
            if user_answer and user_answer == right_answer:
                score = question_score_full

        else:
            right_values = _normalize_fill_answer_list(right_answer_raw)
            user_values = _normalize_fill_answer_list(user_answer_value)
            right_answer_text = _join_fill_answer(right_values)
            user_answer_text = _join_fill_answer(user_values)
            if user_answer_text:
                is_answered = True
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

        # 未作答不写入错题本，避免用户“先看分数再补做”时污染错题记录。
        if not is_correct and is_answered:
            wrong_items.append(
                QuizWrongItem(
                    wrong_id=f"wr_{uuid.uuid4().hex[:10]}",
                    question_id=question_id,
                    question_type=question_type,
                    stem=stem,
                    user_answer=user_answer_text,
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

    points_reward = _award_points_for_quiz_submit(
        user_id=user_id,
        quiz_record_id=quiz_record_id,
        score=score_int,
    )

    record_quiz_submission(
        user_id=user_id,
        summary=summary,
        results=results,
        wrong_items=wrong_items,
        submit_token=submit_token,
        points_reward=points_reward,
    )

    return QuizSubmitResponse(
        quiz_record=summary,
        results=results,
        wrong_items=wrong_items,
        next_action_hint="小测已完成，可去做一次情绪分析，看看今天更适合怎样安排学习节奏。",
        points_reward=points_reward,
    )


def list_quiz_history_for_user(user_id: str, limit: int = 20, offset: int = 0) -> QuizHistoryResponse:
    return list_quiz_record_summaries(user_id=user_id, limit=limit, offset=offset)


def get_quiz_record_for_user(user_id: str, quiz_record_id: str) -> Optional[QuizSubmitResponse]:
    return get_quiz_record_detail(user_id=user_id, quiz_record_id=quiz_record_id)


def list_quiz_wrongbook_for_user(user_id: str, limit: int = 20, offset: int = 0) -> QuizWrongbookResponse:
    return list_quiz_wrongbook_entries(user_id=user_id, limit=limit, offset=offset)
