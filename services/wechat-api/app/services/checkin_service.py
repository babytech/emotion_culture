import json
import os
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.schemas.checkin import CheckinDayItem, CheckinSignResponse, CheckinStatusResponse
from app.services.points_service import credit_points_for_action, get_points_balance


_LOCK = threading.RLock()
_DEFAULT_STORE_PATH = "/tmp/emotion_culture/checkin_store.json"
_DEFAULT_APP_TIMEZONE = "Asia/Shanghai"
_DEFAULT_DAILY_POINTS = 2
_DEFAULT_CYCLE_LENGTH = 12


def _store_path() -> Path:
    raw = (os.getenv("CHECKIN_STORE_PATH", _DEFAULT_STORE_PATH) or "").strip() or _DEFAULT_STORE_PATH
    path = Path(raw).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _app_timezone() -> ZoneInfo:
    raw = (os.getenv("APP_TIMEZONE", _DEFAULT_APP_TIMEZONE) or "").strip() or _DEFAULT_APP_TIMEZONE
    try:
        return ZoneInfo(raw)
    except Exception:
        return ZoneInfo(_DEFAULT_APP_TIMEZONE)


def _today_local() -> date:
    return datetime.now(_app_timezone()).date()


def _daily_points() -> int:
    raw = (os.getenv("CHECKIN_DAILY_POINTS", str(_DEFAULT_DAILY_POINTS)) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_DAILY_POINTS
    return max(0, value)


def _cycle_length() -> int:
    raw = (os.getenv("CHECKIN_CYCLE_LENGTH", str(_DEFAULT_CYCLE_LENGTH)) or "").strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_CYCLE_LENGTH
    return max(1, value)


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_store() -> dict[str, Any]:
    return {"version": 1, "users": {}}


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _default_store()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_store()
    if not isinstance(payload, dict):
        return _default_store()
    if not isinstance(payload.get("users"), dict):
        payload["users"] = {}
    return payload


def _save_store(payload: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def _normalize_user_id(user_id: str) -> str:
    value = (user_id or "").strip()
    return value or "anonymous"


def _ensure_user_bucket(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    users = payload.setdefault("users", {})
    bucket = users.get(user_id)
    if not isinstance(bucket, dict):
        bucket = {}
        users[user_id] = bucket
    if not isinstance(bucket.get("current_streak"), int):
        bucket["current_streak"] = 0
    if not isinstance(bucket.get("total_signed_days"), int):
        bucket["total_signed_days"] = 0
    if not isinstance(bucket.get("last_signed_day"), str):
        bucket["last_signed_day"] = ""
    if not isinstance(bucket.get("updated_at"), str):
        bucket["updated_at"] = ""
    return bucket


def _parse_iso_day(raw: str) -> date | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _compute_cycle_position(streak: int, cycle_length: int) -> int:
    if streak <= 0:
        return 0
    return ((streak - 1) % cycle_length) + 1


def _build_days(*, cycle_length: int, cycle_position: int, signed_today: bool, streak: int, daily_points: int) -> list[CheckinDayItem]:
    active = cycle_position if cycle_position > 0 else 1
    items: list[CheckinDayItem] = []
    for index in range(1, cycle_length + 1):
        if streak <= 0 and index == 1:
            state = "current"
        elif index < active:
            state = "done"
        elif index == active:
            state = "done" if signed_today else "current"
        else:
            state = "pending"
        items.append(
            CheckinDayItem(
                day_index=index,
                label=f"第{index}天",
                points=daily_points,
                state=state,
            )
        )
    return items


def _build_status_from_bucket(user_id: str, bucket: dict[str, Any]) -> CheckinStatusResponse:
    today = _today_local()
    today_text = today.isoformat()
    last_signed_day = str(bucket.get("last_signed_day") or "").strip()
    signed_today = last_signed_day == today_text
    streak = max(0, int(bucket.get("current_streak") or 0))
    total_signed_days = max(0, int(bucket.get("total_signed_days") or 0))
    cycle_length = _cycle_length()
    daily_points = _daily_points()
    cycle_position = _compute_cycle_position(streak, cycle_length)
    points_balance = get_points_balance(user_id)

    message = (
        "今天已经签到，请明日再来吧～"
        if signed_today
        else f"今日签到可获得 +{daily_points} 积分"
    )

    return CheckinStatusResponse(
        today=today_text,
        signed_today=signed_today,
        current_streak=streak,
        total_signed_days=total_signed_days,
        daily_points=daily_points,
        points_balance=points_balance,
        cycle_length=cycle_length,
        cycle_position=cycle_position,
        last_signed_day=last_signed_day or None,
        message=message,
        days=_build_days(
            cycle_length=cycle_length,
            cycle_position=cycle_position,
            signed_today=signed_today,
            streak=streak,
            daily_points=daily_points,
        ),
    )


def get_checkin_status(user_id: str) -> CheckinStatusResponse:
    normalized_user = _normalize_user_id(user_id)
    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        _save_store(payload)
    return _build_status_from_bucket(normalized_user, bucket)


def sign_in_today(user_id: str) -> CheckinSignResponse:
    normalized_user = _normalize_user_id(user_id)
    today = _today_local()
    today_text = today.isoformat()
    daily_points = _daily_points()
    awarded_points = 0
    just_signed = False

    with _LOCK:
        payload = _load_store()
        bucket = _ensure_user_bucket(payload, normalized_user)
        last_signed_day = str(bucket.get("last_signed_day") or "").strip()
        last_signed_date = _parse_iso_day(last_signed_day)

        if last_signed_day == today_text:
            status = _build_status_from_bucket(normalized_user, bucket)
            return CheckinSignResponse(
                just_signed=False,
                awarded_points=0,
                status=status,
            )

        just_signed = True
        if last_signed_date and today - last_signed_date == timedelta(days=1):
            next_streak = max(0, int(bucket.get("current_streak") or 0)) + 1
        else:
            next_streak = 1

        bucket["current_streak"] = next_streak
        bucket["total_signed_days"] = max(0, int(bucket.get("total_signed_days") or 0)) + 1
        bucket["last_signed_day"] = today_text
        bucket["updated_at"] = _iso_now_utc()
        _save_store(payload)

    credit = credit_points_for_action(
        normalized_user,
        action_key=f"daily_checkin:{today_text}",
        points=daily_points,
        reason="daily_checkin",
    )
    if credit.get("awarded"):
        awarded_points = int(credit.get("points") or 0)

    status = get_checkin_status(normalized_user)
    return CheckinSignResponse(
        just_signed=just_signed,
        awarded_points=awarded_points,
        status=status,
    )
