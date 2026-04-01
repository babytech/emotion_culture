import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.schemas.media_generate import MediaGenerateStyle


@dataclass
class GeneratedImageArtifact:
    reference: str
    provider: str
    cleanup_path: Optional[str] = None


@dataclass
class StaticPoolItem:
    id: str
    url: str
    style: str
    emotion_tags: list[str]
    intensity: str
    active: bool
    weight: float
    updated_at: str
    source: str


def _env_json_list(name: str) -> list[str]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    result: list[str] = []
    for item in payload:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _env_csv_list(name: str) -> list[str]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return []
    result: list[str] = []
    for item in raw.split(","):
        text = item.strip()
        if text:
            result.append(text)
    return result


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_style(style: object) -> str:
    value = _normalize_text(style).lower()
    return value if value in {"classical", "guochao", "tech", "common"} else ""


def _normalize_tag(tag: object) -> str:
    return _normalize_text(tag).lower()


def _normalize_tags(value: object) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [part.strip() for part in value.replace("，", ",").split(",")]
    else:
        items = []

    normalized: list[str] = []
    for item in items:
        tag = _normalize_tag(item)
        if tag and tag not in normalized:
            normalized.append(tag)
    return normalized


def _normalize_weight(value: object) -> float:
    try:
        parsed = float(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return 1.0


def _normalize_active(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = _normalize_text(value).lower()
    if not text:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return True


def _pool_item_from_url(url: str, *, style: str, source: str, item_id: str = "", updated_at: str = "") -> StaticPoolItem:
    reference = _normalize_text(url)
    return StaticPoolItem(
        id=item_id or reference,
        url=reference,
        style=style,
        emotion_tags=[],
        intensity="",
        active=True,
        weight=1.0,
        updated_at=updated_at,
        source=source,
    )


def _pool_item_from_dict(payload: dict[str, object], *, default_style: str, source: str) -> Optional[StaticPoolItem]:
    url = _normalize_text(payload.get("url") or payload.get("reference"))
    if not url:
        return None
    style = _normalize_style(payload.get("style")) or default_style
    item_id = _normalize_text(payload.get("id")) or url
    return StaticPoolItem(
        id=item_id,
        url=url,
        style=style,
        emotion_tags=_normalize_tags(payload.get("emotion_tags")),
        intensity=_normalize_text(payload.get("intensity")).lower(),
        active=_normalize_active(payload.get("active")),
        weight=_normalize_weight(payload.get("weight")),
        updated_at=_normalize_text(payload.get("updated_at")),
        source=source,
    )


def _env_json_pool_items(name: str, *, default_style: str, source: str) -> list[StaticPoolItem]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    items: list[StaticPoolItem] = []
    for index, item in enumerate(payload):
        if isinstance(item, str):
            reference = item.strip()
            if reference:
                items.append(
                    _pool_item_from_url(
                        reference,
                        style=default_style,
                        source=source,
                        item_id=f"{source}_{index}",
                    )
                )
            continue
        if isinstance(item, dict):
            normalized = _pool_item_from_dict(item, default_style=default_style, source=source)
            if normalized:
                items.append(normalized)
    return items


def _local_assets_by_style(style: MediaGenerateStyle) -> list[str]:
    root = Path(__file__).resolve().parents[1] / "core" / "images"
    if style == MediaGenerateStyle.CLASSICAL:
        subdir = "tangsong"
    elif style == MediaGenerateStyle.GUOCHAO:
        subdir = "guochao"
    else:
        subdir = "tech"
    base = root / subdir
    if not base.exists() or not base.is_dir():
        return []

    refs: list[str] = []
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        refs.append(f"/assets/{subdir}/{path.name}")
    return refs


def _dedupe_pool_items(items: list[StaticPoolItem]) -> list[StaticPoolItem]:
    deduped: list[StaticPoolItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.id or item.url
        if not item.url or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _style_pool_items(style: MediaGenerateStyle) -> list[StaticPoolItem]:
    style_value = style.value
    if style == MediaGenerateStyle.CLASSICAL:
        items = _env_json_pool_items(
            "MEDIA_GEN_STATIC_POOL_CLASSICAL_JSON",
            default_style=style_value,
            source="classical_json",
        )
        items.extend(
            _pool_item_from_url(ref, style=style_value, source="classical_csv", item_id=f"classical_csv_{index}")
            for index, ref in enumerate(_env_csv_list("MEDIA_GEN_STATIC_POOL_CLASSICAL"))
        )
    elif style == MediaGenerateStyle.TECH:
        items = _env_json_pool_items(
            "MEDIA_GEN_STATIC_POOL_TECH_JSON",
            default_style=style_value,
            source="tech_json",
        )
        items.extend(
            _pool_item_from_url(ref, style=style_value, source="tech_csv", item_id=f"tech_csv_{index}")
            for index, ref in enumerate(_env_csv_list("MEDIA_GEN_STATIC_POOL_TECH"))
        )
    else:
        items = _env_json_pool_items(
            "MEDIA_GEN_STATIC_POOL_GUOCHAO_JSON",
            default_style=style_value,
            source="guochao_json",
        )
        items.extend(
            _pool_item_from_url(ref, style=style_value, source="guochao_csv", item_id=f"guochao_csv_{index}")
            for index, ref in enumerate(_env_csv_list("MEDIA_GEN_STATIC_POOL_GUOCHAO"))
        )
    return _dedupe_pool_items(list(items))


def _common_pool_items() -> list[StaticPoolItem]:
    items = _env_json_pool_items(
        "MEDIA_GEN_STATIC_POOL_COMMON_JSON",
        default_style="common",
        source="common_json",
    )
    items.extend(
        _pool_item_from_url(ref, style="common", source="common_csv", item_id=f"common_csv_{index}")
        for index, ref in enumerate(_env_csv_list("MEDIA_GEN_STATIC_POOL_COMMON"))
    )
    return _dedupe_pool_items(list(items))


def _local_default_items(style: MediaGenerateStyle) -> list[StaticPoolItem]:
    return [
        _pool_item_from_url(ref, style=style.value, source="local_assets", item_id=f"local_{index}")
        for index, ref in enumerate(_local_assets_by_style(style))
    ]


def _keyword_variants(*values: str) -> set[str]:
    normalized: set[str] = set()
    for value in values:
        text = _normalize_text(value).lower()
        if not text:
            continue
        normalized.add(text)
        normalized.add(text.replace("情绪", ""))
        normalized.add(text.replace(" ", ""))
    return {item for item in normalized if item}


def _candidate_score(
    item: StaticPoolItem,
    *,
    emotion_code: str,
    emotion_label: str,
    trigger_tags: list[str],
    prompt: Optional[str],
) -> int:
    tags = set(item.emotion_tags)
    if not tags:
        return 0

    score = 0
    emotion_keywords = _keyword_variants(emotion_code, emotion_label)
    for keyword in emotion_keywords:
        if keyword in tags:
            score += 6

    normalized_trigger_tags = [_normalize_tag(tag) for tag in trigger_tags if _normalize_tag(tag)]
    for tag in normalized_trigger_tags:
        if tag in tags:
            score += 3

    prompt_text = _normalize_text(prompt).lower()
    if prompt_text:
        for tag in tags:
            if tag and tag in prompt_text:
                score += 1

    return score


def _pick_index(size: int, *, style: MediaGenerateStyle, prompt: Optional[str], salt: str = "") -> int:
    if size <= 1:
        return 0
    seed = f"{(prompt or '').strip()}|{salt}".strip("|")
    if seed:
        digest = hashlib.sha1(f"{style.value}|{seed}|{time.time_ns()}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % size
    return random.SystemRandom().randrange(size)


def _pick_weighted_item(
    items: list[StaticPoolItem],
    *,
    style: MediaGenerateStyle,
    prompt: Optional[str],
    salt: str = "",
) -> StaticPoolItem:
    if len(items) == 1:
        return items[0]

    weights = [max(item.weight, 0.1) for item in items]
    total_weight = sum(weights)
    if total_weight <= 0:
        return items[_pick_index(len(items), style=style, prompt=prompt, salt=salt)]

    if prompt:
        digest = hashlib.sha1(f"{style.value}|{prompt}|{salt}|{time.time_ns()}".encode("utf-8")).hexdigest()
        cursor = (int(digest[:12], 16) / float(16**12)) * total_weight
    else:
        cursor = random.SystemRandom().random() * total_weight

    running = 0.0
    for item, weight in zip(items, weights):
        running += weight
        if cursor <= running:
            return item
    return items[-1]


def _select_pool_item(
    style: MediaGenerateStyle,
    *,
    prompt: Optional[str],
    emotion_code: str,
    emotion_label: str,
    trigger_tags: list[str],
) -> Optional[StaticPoolItem]:
    style_items = [item for item in _style_pool_items(style) if item.active]
    if style_items:
        scores = [
            _candidate_score(
                item,
                emotion_code=emotion_code,
                emotion_label=emotion_label,
                trigger_tags=trigger_tags,
                prompt=prompt,
            )
            for item in style_items
        ]
        best_score = max(scores)
        if best_score > 0:
            matched = [item for item, score in zip(style_items, scores) if score == best_score]
            return _pick_weighted_item(matched, style=style, prompt=prompt, salt="style_match")
        return _pick_weighted_item(style_items, style=style, prompt=prompt, salt="style_pool")

    common_items = [item for item in _common_pool_items() if item.active]
    if common_items:
        return _pick_weighted_item(common_items, style=style, prompt=prompt, salt="common_pool")

    local_defaults = _local_default_items(style)
    if local_defaults:
        return _pick_weighted_item(local_defaults, style=style, prompt=prompt, salt="local_default")
    return None


def generate_stylized_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    source_url: Optional[str] = None,
    prompt: Optional[str] = None,
    emotion_code: Optional[str] = None,
    emotion_label: Optional[str] = None,
    trigger_tags: Optional[list[str]] = None,
) -> GeneratedImageArtifact:
    _ = (source_path, source_url)
    provider = (os.getenv("MEDIA_GEN_PROVIDER", "local_mock") or "").strip().lower()
    if provider not in {"local_mock", "mock", "local", "static_pool", "static"}:
        raise ValueError(
            "MEDIA_GEN_PROVIDER_DISABLED: third-party dynamic image providers are removed; "
            "please use MEDIA_GEN_PROVIDER=local_mock"
        )

    selected = _select_pool_item(
        style,
        prompt=prompt,
        emotion_code=_normalize_text(emotion_code).lower(),
        emotion_label=_normalize_text(emotion_label).lower(),
        trigger_tags=trigger_tags or [],
    )
    if not selected:
        raise ValueError("MEDIA_GEN_STATIC_POOL_EMPTY: no static assets configured for selected style")

    return GeneratedImageArtifact(reference=selected.url, provider="static_pool", cleanup_path=None)
