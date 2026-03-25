import os
import random
import uuid
from typing import Optional

import numpy as np
from PIL import Image

from app.core.culture import CultureManager
from app.core.emotion import (
    analyze_text_sentiment,
    comfort_text,
    detect_face_emotion,
    guochao_characters,
)
from app.core.speech import analyze_speech_emotion
from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    EmotionBrief,
    EmotionResult,
    EmotionSources,
    GuochaoResult,
    PoemResult,
    ResultCard,
)
from app.services.storage_service import cleanup_temp_files, resolve_media_paths


_culture_manager = CultureManager()
_emotions = ("happy", "sad", "angry", "surprise", "neutral", "fear")

_TRIGGER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "学业压力": ("考试", "成绩", "作业", "学习", "上课", "老师", "升学"),
    "人际关系": ("同学", "朋友", "家人", "父母", "关系", "吵架", "冲突"),
    "自我期待": ("目标", "计划", "未来", "担心", "焦虑", "压力", "比较"),
    "身体状态": ("失眠", "疲惫", "头痛", "不舒服", "生病", "累", "困"),
    "环境变化": ("转学", "搬家", "新环境", "变化", "陌生", "适应"),
}

_DEFAULT_TRIGGER_TAGS: dict[str, list[str]] = {
    "happy": ["积极体验", "关系支持"],
    "sad": ["情绪低落", "压力积累"],
    "angry": ["冲突压力", "期待落差"],
    "surprise": ["突发变化", "信息冲击"],
    "neutral": ["日常波动", "状态平稳"],
    "fear": ["未知担忧", "安全感不足"],
}

_DAILY_SUGGESTIONS: dict[str, str] = {
    "happy": "记录今天让你开心的一个瞬间，并把这份积极感受分享给一个信任的人。",
    "sad": "给自己 10 分钟安静时间，做 3 次深呼吸，再写下一个可马上完成的小目标。",
    "angry": "先暂停 1 分钟离开冲突现场，缓和呼吸后再表达你的真实需求。",
    "surprise": "把这次意外感受写成一句话，分清“事实”和“想法”，再决定下一步。",
    "neutral": "保持当前节奏，今晚固定一个放松时段，巩固这份平稳状态。",
    "fear": "把担心拆成“可控制/不可控制”两部分，先执行一件可控制的小行动。",
}

_EMOTION_OVERVIEW_SUFFIX: dict[str, str] = {
    "happy": "你当前的情绪更偏积极，可以把这股能量用于推进今天最重要的一件事。",
    "sad": "你当前有明显低落信号，先稳住状态，再逐步处理具体问题会更有效。",
    "angry": "你当前有较强激活情绪，先降低生理唤醒水平，再沟通会更清晰。",
    "surprise": "你当前受到变化刺激，先确认信息，再决定行动能减少误判。",
    "neutral": "你当前整体平稳，是适合整理思路和做结构化决策的状态。",
    "fear": "你当前有担忧信号，拆解问题并按优先级行动能明显提升安全感。",
}


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


def _build_secondary_emotions(primary_emotion: str, weights: dict[str, float]) -> list[EmotionBrief]:
    ranked = sorted(
        (
            (emotion_code, score)
            for emotion_code, score in weights.items()
            if emotion_code != primary_emotion and score > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    secondary: list[EmotionBrief] = []
    for emotion_code, _ in ranked[:2]:
        secondary.append(
            EmotionBrief(
                code=emotion_code,
                label=_culture_manager.translate_emotion(emotion_code),
            )
        )

    return secondary


def _build_emotion_overview(
    primary_emotion: str,
    primary_label: str,
    text_emotion: Optional[str],
    face_emotion: Optional[str],
    speech_emotion: Optional[str],
) -> str:
    source_labels: list[str] = []
    if text_emotion:
        source_labels.append("文本")
    if face_emotion:
        source_labels.append("图像")
    if speech_emotion:
        source_labels.append("语音")

    source_text = "、".join(source_labels) if source_labels else "当前输入"
    suffix = _EMOTION_OVERVIEW_SUFFIX.get(primary_emotion, _EMOTION_OVERVIEW_SUFFIX["neutral"])
    return f"综合{source_text}信号，当前以“{primary_label}”为主。{suffix}"


def _infer_trigger_tags(text: Optional[str], primary_emotion: str) -> list[str]:
    tags: list[str] = []
    normalized_text = (text or "").strip().lower()

    if normalized_text:
        for tag, keywords in _TRIGGER_KEYWORDS.items():
            if any(keyword in normalized_text for keyword in keywords):
                tags.append(tag)

    if not tags:
        tags.extend(_DEFAULT_TRIGGER_TAGS.get(primary_emotion, _DEFAULT_TRIGGER_TAGS["neutral"]))

    # 去重并限制数量
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:3]


def _pick_daily_suggestion(primary_emotion: str) -> str:
    return _DAILY_SUGGESTIONS.get(primary_emotion, _DAILY_SUGGESTIONS["neutral"])


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

        result_card = ResultCard(
            primary_emotion=EmotionBrief(code=chosen_emotion, label=emotion_label),
            secondary_emotions=_build_secondary_emotions(chosen_emotion, weights),
            emotion_overview=_build_emotion_overview(
                primary_emotion=chosen_emotion,
                primary_label=emotion_label,
                text_emotion=text_emotion,
                face_emotion=face_emotion,
                speech_emotion=speech_emotion,
            ),
            trigger_tags=_infer_trigger_tags(payload.text, chosen_emotion),
            poem_response=poem_text,
            poem_interpretation=interpretation,
            guochao_comfort=comfort,
            daily_suggestion=_pick_daily_suggestion(chosen_emotion),
        )

        return AnalyzeResponse(
            request_id=f"ana_{uuid.uuid4().hex[:12]}",
            input_modes=input_modes,
            result_card=result_card,
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
