import hashlib
import os
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from app.core.culture import CultureManager
from app.core.emotion import (
    analyze_text_sentiment,
    comfort_text,
    detect_face_emotion,
    guochao_characters,
)
from app.core.speech import analyze_speech_emotion, transcribe_speech_to_text
from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConfidenceLevel,
    EmotionBrief,
    EmotionResult,
    EmotionSources,
    GuochaoResult,
    PoemResult,
    ResultCard,
    SystemFields,
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


class VoiceQualityRejectError(ValueError):
    def __init__(self, code: str, message: str, retry_hint: Optional[str] = None) -> None:
        self.code = code
        self.message = message
        self.retry_hint = retry_hint or "请在安静环境重新录音，若仍失败可改用文字输入。"
        super().__init__(f"{code}: {message}")

    def to_client_message(self) -> str:
        return f"[{self.code}] {self.message} {self.retry_hint}"


class FaceQualityRejectError(ValueError):
    def __init__(self, code: str, message: str, retry_hint: Optional[str] = None) -> None:
        self.code = code
        self.message = message
        self.retry_hint = retry_hint or "请正对镜头、保证光线充足后重新拍摄。"
        super().__init__(f"{code}: {message}")

    def to_client_message(self) -> str:
        return f"[{self.code}] {self.message} {self.retry_hint}"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _normalize_transcript_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return ""
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def _is_unstable_transcript(raw_text: str) -> bool:
    normalized = _normalize_transcript_text(raw_text)
    if not normalized:
        return True

    filler_chars = set("嗯啊呃额哦哈呀啦")
    if set(normalized).issubset(filler_chars):
        return True

    if len(normalized) >= 4 and len(set(normalized)) == 1:
        return True

    return False


def _validate_voice_quality(audio_path: str, speech_transcript: Optional[str]) -> None:
    min_file_size = _env_int("VOICE_MIN_FILE_SIZE_BYTES", 6000)
    min_transcript_chars = _env_int("VOICE_MIN_TRANSCRIPT_CHARS", 2)

    try:
        file_size = os.path.getsize(audio_path)
    except OSError as exc:
        raise VoiceQualityRejectError(
            code="VOICE_FILE_UNREADABLE",
            message="语音文件无法读取，请重新录制。",
        ) from exc

    if file_size < min_file_size:
        raise VoiceQualityRejectError(
            code="VOICE_TOO_SHORT",
            message="语音时长过短或音量过小，请重新录制。",
        )

    if not (speech_transcript or "").strip():
        raise VoiceQualityRejectError(
            code="VOICE_TRANSCRIPT_EMPTY",
            message="语音识别结果为空，可能存在静音或环境杂音过大。",
        )

    normalized = _normalize_transcript_text(speech_transcript or "")
    if len(normalized) < min_transcript_chars:
        raise VoiceQualityRejectError(
            code="VOICE_TEXT_TOO_SHORT",
            message="语音可识别文本过短，请补充完整表达后重录。",
        )

    if _is_unstable_transcript(speech_transcript or ""):
        raise VoiceQualityRejectError(
            code="VOICE_TEXT_UNSTABLE",
            message="语音识别不稳定，建议在更安静环境重新录制。",
        )


def _validate_face_quality(image: np.ndarray) -> None:
    if image is None or image.size == 0:
        raise FaceQualityRejectError(
            code="FACE_IMAGE_INVALID",
            message="图片无效，请重新拍摄。",
        )

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
    )

    if len(faces) == 0:
        raise FaceQualityRejectError(
            code="FACE_NOT_FOUND",
            message="未检测到清晰人脸，请正对镜头重新拍摄。",
        )
    if len(faces) > 1:
        raise FaceQualityRejectError(
            code="FACE_MULTI_FOUND",
            message="检测到多个人脸，请仅保留你本人单人入镜。",
        )

    (x, y, w, h) = faces[0]
    image_area = float(gray.shape[0] * gray.shape[1])
    face_area_ratio = (w * h) / image_area if image_area > 0 else 0.0
    min_face_area_ratio = _env_float("FACE_MIN_AREA_RATIO", 0.06)
    if face_area_ratio < min_face_area_ratio:
        raise FaceQualityRejectError(
            code="FACE_TOO_SMALL",
            message="人脸区域过小，请靠近镜头后重新拍摄。",
        )

    roi = gray[y : y + h, x : x + w]
    if roi.size == 0:
        raise FaceQualityRejectError(
            code="FACE_IMAGE_INVALID",
            message="图片无效，请重新拍摄。",
        )

    min_brightness = _env_float("FACE_MIN_BRIGHTNESS", 55.0)
    brightness = float(np.mean(roi))
    if brightness < min_brightness:
        raise FaceQualityRejectError(
            code="FACE_TOO_DARK",
            message="光线过暗，请在更明亮环境重新拍摄。",
        )

    min_laplacian_var = _env_float("FACE_MIN_LAPLACIAN_VAR", 45.0)
    laplacian_var = float(cv2.Laplacian(roi, cv2.CV_64F).var())
    if laplacian_var < min_laplacian_var:
        raise FaceQualityRejectError(
            code="FACE_TOO_BLUR",
            message="图片模糊，请保持稳定后重新拍摄。",
        )

    eyes = eye_cascade.detectMultiScale(
        roi,
        scaleFactor=1.1,
        minNeighbors=6,
        minSize=(max(12, w // 10), max(12, h // 10)),
    )
    if len(eyes) == 0:
        raise FaceQualityRejectError(
            code="FACE_OCCLUDED",
            message="人脸遮挡较多，请移开遮挡物后重新拍摄。",
        )


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

    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:3]


def _pick_daily_suggestion(primary_emotion: str) -> str:
    return _DAILY_SUGGESTIONS.get(primary_emotion, _DAILY_SUGGESTIONS["neutral"])


def _calc_confidence_level(primary_emotion: str, weights: dict[str, float]) -> ConfidenceLevel:
    primary_score = float(weights.get(primary_emotion, 0.0))
    competitors = sorted(
        (score for emotion_code, score in weights.items() if emotion_code != primary_emotion),
        reverse=True,
    )
    second_score = float(competitors[0]) if competitors else 0.0
    gap = primary_score - second_score

    if primary_score >= 0.75 or gap >= 0.45:
        return ConfidenceLevel.HIGH
    if primary_score >= 0.45 and gap >= 0.2:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _short_hash(value: str, prefix: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_analysis(payload: AnalyzeRequest) -> AnalyzeResponse:
    resolved = resolve_media_paths(payload)
    input_modes = payload.normalized_input_modes()

    try:
        analysis_text = (payload.text or "").strip() or None

        speech_transcript = None
        speech_transcript_provider = None
        speech_emotion = None
        if resolved.audio_path:
            transcription = transcribe_speech_to_text(resolved.audio_path)
            speech_transcript = transcription.text
            speech_transcript_provider = transcription.provider
            _validate_voice_quality(
                audio_path=resolved.audio_path,
                speech_transcript=speech_transcript,
            )
            speech_emotion = analyze_speech_emotion(resolved.audio_path)

        if not analysis_text and speech_transcript:
            analysis_text = speech_transcript

        text_emotion = analyze_text_sentiment(analysis_text) if analysis_text else None
        face_emotion = None
        if resolved.image_path:
            image_np = _load_image_numpy(resolved.image_path)
            _validate_face_quality(image_np)
            face_emotion = detect_face_emotion(image_np)

        chosen_emotion, weights = _select_emotion(
            text_input=analysis_text,
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
        secondary_emotions = _build_secondary_emotions(chosen_emotion, weights)
        trigger_tags = _infer_trigger_tags(analysis_text, chosen_emotion)

        result_card = ResultCard(
            primary_emotion=EmotionBrief(code=chosen_emotion, label=emotion_label),
            secondary_emotions=secondary_emotions,
            emotion_overview=_build_emotion_overview(
                primary_emotion=chosen_emotion,
                primary_label=emotion_label,
                text_emotion=text_emotion,
                face_emotion=face_emotion,
                speech_emotion=speech_emotion,
            ),
            trigger_tags=trigger_tags,
            poem_response=poem_text,
            poem_interpretation=interpretation,
            guochao_comfort=comfort,
            daily_suggestion=_pick_daily_suggestion(chosen_emotion),
        )

        request_id = f"ana_{uuid.uuid4().hex[:12]}"
        poem_id = _short_hash(f"{poet}|{poem_text}", "poem")
        guochao_id = _short_hash(character_name, "gc")

        return AnalyzeResponse(
            request_id=request_id,
            input_modes=input_modes,
            result_card=result_card,
            system_fields=SystemFields(
                request_id=request_id,
                analyzed_at=_iso_now_utc(),
                input_modes=input_modes,
                primary_emotion_code=chosen_emotion,
                secondary_emotion_codes=[item.code for item in secondary_emotions],
                confidence_level=_calc_confidence_level(chosen_emotion, weights),
                trigger_tags=trigger_tags,
                poem_id=poem_id,
                guochao_id=guochao_id,
                mail_sent=False,
                tts_ready=False,
                analysis_text=analysis_text,
                speech_transcript=speech_transcript,
                speech_transcript_provider=speech_transcript_provider,
            ),
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
