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


def _style_pool_refs(style: MediaGenerateStyle) -> list[str]:
    if style == MediaGenerateStyle.CLASSICAL:
        refs = _env_json_list("MEDIA_GEN_STATIC_POOL_CLASSICAL_JSON")
        refs.extend(_env_csv_list("MEDIA_GEN_STATIC_POOL_CLASSICAL"))
    elif style == MediaGenerateStyle.TECH:
        refs = _env_json_list("MEDIA_GEN_STATIC_POOL_TECH_JSON")
        refs.extend(_env_csv_list("MEDIA_GEN_STATIC_POOL_TECH"))
    else:
        refs = _env_json_list("MEDIA_GEN_STATIC_POOL_GUOCHAO_JSON")
        refs.extend(_env_csv_list("MEDIA_GEN_STATIC_POOL_GUOCHAO"))

    dedup: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        dedup.append(ref)

    if dedup:
        return dedup
    return _local_assets_by_style(style)


def _pick_index(size: int, *, style: MediaGenerateStyle, prompt: Optional[str]) -> int:
    if size <= 1:
        return 0
    seed = (prompt or "").strip()
    if seed:
        digest = hashlib.sha1(f"{style.value}|{seed}|{time.time_ns()}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % size
    return random.SystemRandom().randrange(size)


def generate_stylized_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    source_url: Optional[str] = None,
    prompt: Optional[str] = None,
) -> GeneratedImageArtifact:
    _ = (source_path, source_url)
    provider = (os.getenv("MEDIA_GEN_PROVIDER", "local_mock") or "").strip().lower()
    if provider not in {"local_mock", "mock", "local", "static_pool", "static"}:
        raise ValueError(
            "MEDIA_GEN_PROVIDER_DISABLED: third-party dynamic image providers are removed; "
            "please use MEDIA_GEN_PROVIDER=local_mock"
        )

    refs = _style_pool_refs(style)
    if not refs:
        raise ValueError("MEDIA_GEN_STATIC_POOL_EMPTY: no static assets configured for selected style")

    index = _pick_index(len(refs), style=style, prompt=prompt)
    reference = refs[index]
    return GeneratedImageArtifact(reference=reference, provider="static_pool", cleanup_path=None)
