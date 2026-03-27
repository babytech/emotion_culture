from typing import Optional

from app.schemas.retention import CalendarOverviewResponse
from app.services.history_service import get_calendar_overview


_ALLOWED_INPUT_MODES = {"text", "voice", "selfie", "pc_camera"}


def _safe_text(value: object, max_len: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _sanitize_input_modes(values: list[str]) -> list[str]:
    sanitized: list[str] = []
    for item in values:
        text = _safe_text(item, 24)
        if text and text in _ALLOWED_INPUT_MODES and text not in sanitized:
            sanitized.append(text)
    return sanitized


def get_user_calendar_overview(user_id: str, month: Optional[str] = None) -> CalendarOverviewResponse:
    overview = get_calendar_overview(user_id=user_id, month=month)

    sanitized_items = [
        item.model_copy(
            update={
                "analyzed_at": None,
                "input_modes": _sanitize_input_modes(item.input_modes),
                "analyses_count": max(0, int(item.analyses_count)),
            },
        )
        for item in overview.items
    ]
    return overview.model_copy(update={"items": sanitized_items})
