import os
import tempfile
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from app.schemas.media_generate import MediaGenerateStyle


@dataclass
class GeneratedImageArtifact:
    path: str
    provider: str
    cleanup_path: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _fit_image(path: str, max_edge: int) -> Image.Image:
    with Image.open(path) as raw:
        image = raw.convert("RGB")
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image
    scale = float(max_edge) / float(longest)
    resized = (max(1, int(width * scale)), max(1, int(height * scale)))
    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BILINEAR)
    return image.resize(resized, resampling)


def _style_tech(image: Image.Image) -> Image.Image:
    arr = np.array(image).astype(np.float32)
    gray = arr.mean(axis=2, keepdims=True)
    tech = np.concatenate(
        [
            np.clip(gray * 0.20, 0, 255),
            np.clip(gray * 0.80, 0, 255),
            np.clip(gray * 1.28 + 18.0, 0, 255),
        ],
        axis=2,
    ).astype(np.uint8)
    stylized = Image.fromarray(tech, mode="RGB")
    stylized = ImageEnhance.Contrast(stylized).enhance(1.22)
    draw = ImageDraw.Draw(stylized)
    width, height = stylized.size
    for y in range(0, height, 7):
        draw.line((0, y, width, y), fill=(20, 96, 122), width=1)
    return stylized


def _style_guochao(image: Image.Image) -> Image.Image:
    arr = np.array(image).astype(np.float32)
    warm = np.zeros_like(arr)
    warm[:, :, 0] = np.clip(arr[:, :, 0] * 1.22 + 14.0, 0, 255)
    warm[:, :, 1] = np.clip(arr[:, :, 1] * 0.92 + 6.0, 0, 255)
    warm[:, :, 2] = np.clip(arr[:, :, 2] * 0.74, 0, 255)
    stylized = Image.fromarray(warm.astype(np.uint8), mode="RGB")
    stylized = ImageEnhance.Contrast(stylized).enhance(1.08)
    draw = ImageDraw.Draw(stylized)
    width, height = stylized.size
    border = max(8, min(width, height) // 48)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(163, 44, 38), width=border)
    inset = border * 2
    draw.rectangle((inset, inset, width - inset - 1, height - inset - 1), outline=(215, 176, 106), width=2)
    return stylized


def _generate_local_mock_image(style: MediaGenerateStyle, source_path: str) -> GeneratedImageArtifact:
    max_edge = _env_int("MEDIA_GEN_MOCK_MAX_EDGE", 1024)
    image = _fit_image(source_path, max_edge=max(320, min(2048, max_edge)))
    if style == MediaGenerateStyle.TECH:
        output = _style_tech(image)
    else:
        output = _style_guochao(image)

    quality = max(55, min(92, _env_int("MEDIA_GEN_MOCK_QUALITY", 82)))
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix=f"media_gen_{style.value}_")
    output.save(
        tmp.name,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return GeneratedImageArtifact(path=tmp.name, provider="local_mock", cleanup_path=tmp.name)


def generate_stylized_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    source_url: Optional[str] = None,
    prompt: Optional[str] = None,
) -> GeneratedImageArtifact:
    _ = (source_url, prompt)
    provider = (os.getenv("MEDIA_GEN_PROVIDER", "local_mock") or "").strip().lower()
    if provider in {"local_mock", "mock", "local", "static_pool", "static"}:
        return _generate_local_mock_image(style=style, source_path=source_path)

    raise ValueError(
        "MEDIA_GEN_PROVIDER_DISABLED: third-party dynamic image providers are removed; "
        "please use MEDIA_GEN_PROVIDER=local_mock"
    )
