import os


def env_bool_like(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    if raw in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def is_asr_service_enabled() -> bool:
    return env_bool_like("SPEECH_ASR_SERVICE", True)


def is_retention_service_enabled() -> bool:
    return env_bool_like("RETENTION_SERVICE_ENABLED", True)


def is_retention_weekly_report_enabled() -> bool:
    if not is_retention_service_enabled():
        return False
    return env_bool_like("RETENTION_WEEKLY_REPORT_ENABLED", True)


def is_retention_favorites_enabled() -> bool:
    if not is_retention_service_enabled():
        return False
    return env_bool_like("RETENTION_FAVORITES_ENABLED", True)
