from datetime import date, datetime, timedelta, timezone
from typing import Any


def default_retention_dict() -> dict[str, Any]:
    return {
        "checkins": {},
        "weekly_reports": {},
        "favorites": [],
    }


def parse_iso_day(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _sanitize_weekly_reports(
    weekly_reports: Any,
    max_items: int,
) -> tuple[dict[str, dict[str, Any]], bool]:
    if not isinstance(weekly_reports, dict):
        return {}, True

    changed = False
    cleaned_reports: dict[str, dict[str, Any]] = {}
    for week_key, report in weekly_reports.items():
        if not isinstance(week_key, str) or not isinstance(report, dict):
            changed = True
            continue
        cleaned_reports[week_key] = report

    if len(cleaned_reports) > max_items:
        sorted_items = sorted(
            cleaned_reports.items(),
            key=lambda pair: str(pair[1].get("generated_at") or ""),
            reverse=True,
        )
        cleaned_reports = dict(sorted_items[:max_items])
        changed = True

    if cleaned_reports != weekly_reports:
        changed = True
    return cleaned_reports, changed


def _sanitize_favorites(
    favorites: Any,
    max_items: int,
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(favorites, list):
        return [], True

    changed = False
    cleaned_favorites: list[dict[str, Any]] = []
    for item in favorites:
        if not isinstance(item, dict):
            changed = True
            continue
        favorite_id = (item.get("favorite_id") or "").strip()
        favorite_type = (item.get("favorite_type") or "").strip()
        target_id = (item.get("target_id") or "").strip()
        title = (item.get("title") or "").strip()
        if not (favorite_id and favorite_type and target_id and title):
            changed = True
            continue
        cleaned_favorites.append(item)

    if len(cleaned_favorites) > max_items:
        cleaned_favorites.sort(
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )
        cleaned_favorites = cleaned_favorites[:max_items]
        changed = True

    if cleaned_favorites != favorites:
        changed = True
    return cleaned_favorites, changed


def cleanup_retention_bucket(
    bucket: dict[str, Any],
    retention_days: int,
    weekly_report_cache_max_items: int,
    favorites_max_items: int,
) -> bool:
    retention = bucket.get("retention")
    if not isinstance(retention, dict):
        bucket["retention"] = default_retention_dict()
        return True

    changed = False
    cutoff_day = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date()

    checkins = retention.get("checkins")
    if not isinstance(checkins, dict):
        checkins = {}
        retention["checkins"] = checkins
        changed = True

    cleaned_checkins: dict[str, dict[str, Any]] = {}
    for day_key, payload in checkins.items():
        parsed_day = parse_iso_day(day_key)
        if not parsed_day or parsed_day < cutoff_day:
            changed = True
            continue
        if not isinstance(payload, dict):
            changed = True
            continue
        cleaned_checkins[day_key] = payload
    if cleaned_checkins != checkins:
        retention["checkins"] = cleaned_checkins
        changed = True

    cleaned_reports, report_changed = _sanitize_weekly_reports(
        retention.get("weekly_reports"),
        max_items=weekly_report_cache_max_items,
    )
    if report_changed:
        retention["weekly_reports"] = cleaned_reports
        changed = True

    cleaned_favorites, favorite_changed = _sanitize_favorites(
        retention.get("favorites"),
        max_items=favorites_max_items,
    )
    if favorite_changed:
        retention["favorites"] = cleaned_favorites
        changed = True

    return changed
