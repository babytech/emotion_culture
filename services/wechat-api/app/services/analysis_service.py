import random
import uuid
import os
from typing import Optional

import numpy as np
from PIL import Image

from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    EmotionResult,
    EmotionSources,
    GuochaoResult,
    PoemResult,
)
from app.core.culture import CultureManager
from app.core.emotion import (
    comfort_text,
    detect_face_emotion,
    guochao_characters,
    analyze_text_sentiment,
)
from app.core.speech import analyze_speech_emotion
from app.services.storage_service import cleanup_temp_files, resolve_media_paths


_culture_manager = CultureManager()
_emotions = ("happy", "sad", "angry", "surprise", "neutral", "fear")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _load_image_numpy(image_path: str) -> np.ndarray:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        max_edge = _env_int("ANALYZE_IMAGE_MAX_EDGE", 896)
        width, height = rgb.size
        longest = max(width, height)
        if longest > max_edge:
            scale = max_edge / float(longest)
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resampling = getattr(getattr(Image, "Resampling", Image), "BILINEAR", Image.BILINEAR)
            rgb = rgb.resize(new_size, resampling)
        return np.array(rgb)


def _select_emotion(
    text_input: Optional[str],
    text_emotion: Optional[str],
    face_emotion: Optional[str],
    speech_emotion: Optional[str],
) -> tuple[str, dict[str, float]]:
    weights = {key: 0.0 for key in _emotions}

    if text_input and text_emotion:
        weights[text_emotion] += 0.5
        if face_emotion == text_emotion:
            weights[text_emotion] += 0.2
        if speech_emotion == text_emotion:
            weights[text_emotion] += 0.2
    else:
        if face_emotion:
            weights[face_emotion] += 0.4
        if speech_emotion:
            weights[speech_emotion] += 0.4

    if face_emotion and face_emotion != text_emotion:
        weights[face_emotion] += 0.2
    if speech_emotion and speech_emotion != text_emotion:
        weights[speech_emotion] += 0.2

    if all(value == 0.0 for value in weights.values()):
        return "neutral", weights

    best = max(weights.items(), key=lambda item: item[1])[0]
    return best, weights


def _pick_guochao_name(emotion: str) -> str:
    choices = guochao_characters.get(emotion, guochao_characters["neutral"])
    return random.choice(choices)


def run_analysis(payload: AnalyzeRequest) -> AnalyzeResponse:
    resolved = resolve_media_paths(payload)
    input_modes = payload.normalized_input_modes()
    try:
        text_emotion = analyze_text_sentiment(payload.text) if payload.text else None
        face_emotion = None
        if resolved.image_path:
            face_emotion = detect_face_emotion(_load_image_numpy(resolved.image_path))

        speech_emotion = None
        if resolved.audio_path:
            speech_emotion = analyze_speech_emotion(resolved.audio_path)

        chosen_emotion, weights = _select_emotion(
            text_input=payload.text,
            text_emotion=text_emotion,
            face_emotion=face_emotion,
            speech_emotion=speech_emotion,
        )

        poet, poem_text = _culture_manager.get_poem_for_emotion(chosen_emotion)
        interpretation = _culture_manager.get_rich_poem_interpretation(
            poet=poet,
            poem_text=poem_text,
            emotion=chosen_emotion,
        )

        character_name = _pick_guochao_name(chosen_emotion)
        comfort = comfort_text.get(chosen_emotion, comfort_text["neutral"])
        emotion_label = _culture_manager.translate_emotion(chosen_emotion)

        return AnalyzeResponse(
            request_id=f"ana_{uuid.uuid4().hex[:12]}",
            input_modes=input_modes,
            emotion=EmotionResult(
                code=chosen_emotion,
                label=emotion_label,
                sources=EmotionSources(
                    text=text_emotion,
                    face=face_emotion,
                    speech=speech_emotion,
                ),
                weights=weights,
            ),
            poem=PoemResult(
                poet=poet,
                text=poem_text,
                interpretation=interpretation,
            ),
            poet_image_url=f"/assets/tangsong/{poet}.png",
            guochao=GuochaoResult(
                name=character_name,
                comfort=comfort,
            ),
            guochao_image_url=f"/assets/guochao/{character_name}.png",
        )
    finally:
        cleanup_temp_files(resolved.cleanup_paths)
