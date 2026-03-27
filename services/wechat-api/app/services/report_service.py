from typing import Optional

from app.schemas.retention import WeeklyReportResponse
from app.services.history_service import get_weekly_report


def _safe_text(value: object, max_len: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _sanitize_tag(tag: str) -> str:
    return _safe_text(tag, 32)


def _sanitize_suggestion(text: str) -> str:
    return _safe_text(text, 180)


def _sanitize_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        text = _sanitize_tag(tag)
        if text:
            cleaned.append(text)
    return cleaned


def build_user_weekly_report(user_id: str, week_start: Optional[str] = None) -> WeeklyReportResponse:
    report = get_weekly_report(user_id=user_id, week_start=week_start)

    dominant_emotions = [
        item.model_copy(
            update={
                "code": _safe_text(item.code, 24),
                "label": _safe_text(item.label, 24),
                "days": max(0, int(item.days)),
            },
        )
        for item in report.dominant_emotions
    ]
    top_trigger_tags = [
        item.model_copy(
            update={
                "tag": _sanitize_tag(item.tag),
                "count": max(0, int(item.count)),
            },
        )
        for item in report.top_trigger_tags
    ]
    daily_digests = [
        item.model_copy(
            update={
                "trigger_tags": _sanitize_tags(item.trigger_tags),
                "suggestion_summary": _sanitize_suggestion(item.suggestion_summary or "")
                if item.suggestion_summary
                else None,
                "analyzed_at": None,
            },
        )
        for item in report.daily_digests
    ]
    suggestion_highlights = [
        _sanitize_suggestion(item)
        for item in report.suggestion_highlights
        if _sanitize_suggestion(item)
    ]
    return report.model_copy(
        update={
            "dominant_emotions": dominant_emotions,
            "top_trigger_tags": top_trigger_tags,
            "daily_digests": daily_digests,
            "suggestion_highlights": suggestion_highlights,
            "insight": _safe_text(report.insight, 220),
        },
    )
