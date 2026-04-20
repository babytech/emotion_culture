import base64
import csv
import io
import json
import os
import re
from typing import Any, Optional

import requests

from app.schemas.study_quiz import QuizBankIngestResponse
from app.services.study_quiz_service import upsert_quiz_bank


_QUESTION_START_PATTERN = re.compile(r"^\s*(\d{1,3})[\.、\)]\s*(.+?)\s*$")
_OPTION_PATTERN = re.compile(r"^\s*([A-F])[\.、\)]\s*(.+?)\s*$", re.IGNORECASE)
_ANSWER_PATTERN = re.compile(r"^\s*(答案|answer)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE)
_FILL_SPLIT_PATTERN = re.compile(r"[|｜/]")


def _safe_text(value: Any, max_len: int = 5000) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _file_suffix(filename: str) -> str:
    name = _safe_text(filename, 200).lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _normalize_source_type(filename: str, content_type: str) -> str:
    suffix = _file_suffix(filename)
    normalized_type = _safe_text(content_type, 120).lower()
    if suffix in {"jpg", "jpeg", "png"}:
        return "image"
    if suffix == "pdf":
        return "pdf"
    if suffix in {"json"}:
        return "json"
    if suffix in {"csv", "xls", "xlsx"}:
        return "sheet"
    if "image/" in normalized_type:
        return "image"
    if "pdf" in normalized_type:
        return "pdf"
    if "json" in normalized_type:
        return "json"
    return "sheet"


def _ocr_endpoint() -> str:
    return _safe_text(os.getenv("STUDY_QUIZ_OCR_HTTP_ENDPOINT", ""), 400)


def _ocr_timeout_sec() -> float:
    raw = (os.getenv("STUDY_QUIZ_OCR_HTTP_TIMEOUT_SEC", "20") or "").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 20.0


def _ocr_headers() -> dict[str, str]:
    raw = (os.getenv("STUDY_QUIZ_OCR_HTTP_HEADERS_JSON", "") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    headers: dict[str, str] = {}
    for key, value in payload.items():
        key_text = _safe_text(key, 64)
        value_text = _safe_text(value, 400)
        if key_text and value_text:
            headers[key_text] = value_text
    return headers


def _ocr_payload_template() -> dict[str, Any]:
    raw = (os.getenv("STUDY_QUIZ_OCR_HTTP_PAYLOAD_JSON", "") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _decode_to_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312"):
        try:
            return file_bytes.decode(encoding)
        except Exception:
            continue
    return ""


def _parse_option_pairs(raw: str) -> list[dict[str, str]]:
    text = _safe_text(raw, 4000)
    if not text:
        return []
    segments = [item.strip() for item in text.split("|")]
    options: list[dict[str, str]] = []
    for seg in segments:
        if not seg:
            continue
        if ":" in seg:
            key, value = seg.split(":", 1)
        elif "：" in seg:
            key, value = seg.split("：", 1)
        else:
            continue
        item = _safe_text(key, 8).upper()
        content = _safe_text(value, 500)
        if item and content:
            options.append({"item": item[:1], "content": content})
    return options


def _parse_fill_pairs(raw: str) -> list[dict[str, str]]:
    text = _safe_text(raw, 4000)
    if not text:
        return []
    segments = [item.strip() for item in text.split("|")]
    rows: list[dict[str, str]] = []
    for idx, seg in enumerate(segments):
        if not seg:
            continue
        label = chr(ord("A") + idx)
        if ":" in seg:
            key, value = seg.split(":", 1)
            if _safe_text(key, 8):
                label = _safe_text(key, 8).upper()[:1]
            content = _safe_text(value, 500)
        elif "：" in seg:
            key, value = seg.split("：", 1)
            if _safe_text(key, 8):
                label = _safe_text(key, 8).upper()[:1]
            content = _safe_text(value, 500)
        else:
            content = _safe_text(seg, 500)
        if content:
            rows.append({"item": label, "content": content})
    return rows


def _normalize_sheet_rows(text: str) -> list[dict[str, Any]]:
    cleaned = _safe_text(text, 200000)
    if not cleaned:
        return []
    stream = io.StringIO(cleaned)
    reader = csv.DictReader(stream)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(reader):
        if not isinstance(row, dict):
            continue
        question_id = _safe_text(row.get("question_id"), 64) or str(idx + 1)
        question_type = _safe_text(row.get("type"), 32).lower() or "radio"
        stem = _safe_text(row.get("stem"), 1000)
        answer = _safe_text(row.get("answer"), 200)
        if not stem or not answer:
            continue
        tags_raw = _safe_text(row.get("tags"), 500)
        tags = [item.strip() for item in tags_raw.split(",") if item.strip()]
        rows.append(
            {
                "question_id": question_id,
                "type": question_type,
                "stem": stem,
                "options": _parse_option_pairs(_safe_text(row.get("options"), 2000)),
                "fills": _parse_fill_pairs(_safe_text(row.get("fills"), 2000)),
                "answer": answer,
                "difficulty": _safe_text(row.get("difficulty"), 32) or "normal",
                "audio": _safe_text(row.get("audio"), 16) or "no",
                "tags": tags,
            }
        )
    return rows


def _question_type_by_answer(answer: str, option_count: int) -> str:
    normalized = _safe_text(answer, 200).upper()
    if not normalized:
        return "radio"
    letters = re.sub(r"[^A-F]", "", normalized)
    if letters and len(letters) >= 2 and ("," in normalized or "/" in normalized or " " in normalized):
        return "check"
    if letters and len(letters) == 1 and option_count >= 2:
        return "radio"
    return "fill"


def _parse_questions_from_text(text: str) -> list[dict[str, Any]]:
    lines = [_safe_text(line, 3000) for line in (_safe_text(text, 300000) or "").splitlines()]
    blocks: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    stem_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current, stem_lines
        if not current:
            stem_lines = []
            return
        stem = " ".join([item for item in stem_lines if item]).strip()
        answer = _safe_text(current.get("answer"), 400)
        if stem and answer:
            options = current.get("options") if isinstance(current.get("options"), list) else []
            q_type = _question_type_by_answer(answer, len(options))
            fills: list[dict[str, str]] = []
            if q_type == "fill":
                parts = [item.strip() for item in _FILL_SPLIT_PATTERN.split(answer) if item.strip()]
                if not parts:
                    parts = [answer]
                fills = [{"item": chr(ord("A") + idx), "content": part} for idx, part in enumerate(parts[:6])]
            blocks.append(
                {
                    "question_id": str(current.get("question_id") or len(blocks) + 1),
                    "type": q_type,
                    "stem": stem,
                    "options": options if q_type in {"radio", "check"} else [],
                    "fills": fills if q_type == "fill" else [],
                    "answer": answer,
                    "audio": "no",
                    "tags": [],
                    "difficulty": "normal",
                }
            )
        current = None
        stem_lines = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        question_start = _QUESTION_START_PATTERN.match(line)
        if question_start:
            flush_current()
            current = {
                "question_id": question_start.group(1),
                "options": [],
                "answer": "",
            }
            stem_lines = [question_start.group(2).strip()]
            continue

        if current is None:
            continue

        answer_match = _ANSWER_PATTERN.match(line)
        if answer_match:
            current["answer"] = answer_match.group(2).strip()
            continue

        option_match = _OPTION_PATTERN.match(line)
        if option_match:
            current.setdefault("options", []).append(
                {
                    "item": option_match.group(1).upper(),
                    "content": option_match.group(2).strip(),
                }
            )
            continue

        stem_lines.append(line)

    flush_current()
    return blocks


def _extract_questions_from_ocr_response(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        questions = payload.get("questions")
        if isinstance(questions, list):
            return [item for item in questions if isinstance(item, dict)]
        candidate_text = (
            _safe_text(payload.get("text"), 300000)
            or _safe_text(payload.get("content"), 300000)
            or _safe_text(payload.get("result"), 300000)
        )
        if candidate_text:
            return _parse_questions_from_text(candidate_text)
        return []
    if isinstance(payload, str):
        return _parse_questions_from_text(payload)
    return []


def _call_ocr_http(
    *,
    course: str,
    title: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> list[dict[str, Any]]:
    endpoint = _ocr_endpoint()
    if not endpoint:
        raise ValueError("[QUIZ_OCR_UNCONFIGURED] 未配置 STUDY_QUIZ_OCR_HTTP_ENDPOINT，无法识别图片/PDF。")

    payload = _ocr_payload_template()
    payload.update(
        {
            "course": course,
            "title": title,
            "filename": filename,
            "content_type": content_type,
            "file_base64": base64.b64encode(file_bytes).decode("utf-8"),
            "return_format": "quiz_questions_json",
        }
    )
    headers = _ocr_headers()
    if "content-type" not in {key.lower() for key in headers.keys()}:
        headers["content-type"] = "application/json"
    response = requests.post(endpoint, json=payload, headers=headers, timeout=_ocr_timeout_sec())
    if response.status_code < 200 or response.status_code >= 300:
        preview = _safe_text(response.text, 240)
        raise ValueError(f"[QUIZ_OCR_FAILED] OCR 服务返回 {response.status_code}: {preview}")

    try:
        data = response.json()
    except Exception:
        data = _safe_text(response.text, 300000)

    questions = _extract_questions_from_ocr_response(data)
    if not questions:
        raise ValueError("[QUIZ_OCR_EMPTY] OCR 未提取到有效题目，请检查原卷清晰度或模板。")
    return questions


def ingest_quiz_bank_file(
    *,
    course: str,
    title: str,
    version: Optional[str],
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> QuizBankIngestResponse:
    source_type = _normalize_source_type(filename=filename, content_type=content_type)
    questions: list[dict[str, Any]] = []

    if source_type == "json":
        text = _decode_to_text(file_bytes)
        if not text:
            raise ValueError("[QUIZ_INGEST_INVALID] JSON 文件解码失败。")
        try:
            payload = json.loads(text)
        except Exception as exc:
            raise ValueError("[QUIZ_INGEST_INVALID] JSON 解析失败。") from exc
        if isinstance(payload, dict):
            raw_questions = payload.get("questions")
            if isinstance(raw_questions, list):
                questions = [item for item in raw_questions if isinstance(item, dict)]
                if not title:
                    title = _safe_text(payload.get("title"), 80) or title
                if not version:
                    version = _safe_text(payload.get("version"), 48) or version
        elif isinstance(payload, list):
            questions = [item for item in payload if isinstance(item, dict)]
        if not questions:
            raise ValueError("[QUIZ_INGEST_INVALID] JSON 中未找到 questions。")
    elif source_type == "sheet":
        text = _decode_to_text(file_bytes)
        if not text:
            raise ValueError(
                "[QUIZ_INGEST_INVALID] 表格无法读取。请导出为 UTF-8 CSV 后再导入，或使用 OCR 识别图片/PDF。"
            )
        questions = _normalize_sheet_rows(text)
        if not questions:
            raise ValueError("[QUIZ_INGEST_INVALID] 表格中没有可用题目。")
    else:
        questions = _call_ocr_http(
            course=course,
            title=title,
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
        )

    return upsert_quiz_bank(
        course=course,
        title=title,
        version=version,
        questions=questions,
        source_type=source_type,
    )
