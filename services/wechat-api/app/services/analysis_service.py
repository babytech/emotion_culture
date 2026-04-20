import hashlib
import logging
import os
import random
import re
import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

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
from app.services.history_service import get_recent_analysis_content_ids
from app.services.storage_service import cleanup_temp_files, resolve_media_paths


logger = logging.getLogger(__name__)
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
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


def _validate_voice_quality(
    audio_path: str,
    speech_transcript: Optional[str],
    *,
    speech_transcript_status: Optional[str] = None,
    speech_transcript_error: Optional[str] = None,
) -> None:
    min_file_size = _env_int("VOICE_MIN_FILE_SIZE_BYTES", 6000)
    min_transcript_chars = _env_int("VOICE_MIN_TRANSCRIPT_CHARS", 2)
    require_transcript = _env_bool("VOICE_REQUIRE_TRANSCRIPT", False)

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
        if require_transcript:
            status = (speech_transcript_status or "unknown").strip() or "unknown"
            base_message = (
                f"语音识别结果为空（VOICE_REQUIRE_TRANSCRIPT=1，ASR状态={status}），"
                "当前请求要求必须拿到转写文本。"
            )
            if status == "provider_unconfigured":
                raise VoiceQualityRejectError(
                    code="VOICE_TRANSCRIPT_EMPTY",
                    message=(
                        f"{base_message} 当前未配置 STT 转写端点（SPEECH_STT_ENDPOINT 为空）。"
                    ),
                    retry_hint="请联系管理员开启 ASR 转写，或将 VOICE_REQUIRE_TRANSCRIPT 调整为 0。",
                )
            if status == "service_disabled":
                raise VoiceQualityRejectError(
                    code="VOICE_TRANSCRIPT_EMPTY",
                    message=f"{base_message} 管理员已关闭 ASR 转写服务（SPEECH_ASR_SERVICE=off）。",
                    retry_hint="如需强制转写，请联系管理员开启 ASR 服务或将 VOICE_REQUIRE_TRANSCRIPT 调整为 0。",
                )
            if status in {"request_failed", "runtime_error"}:
                details = (speech_transcript_error or "").strip()
                detail_text = f" 详细原因：{details}" if details else ""
                raise VoiceQualityRejectError(
                    code="VOICE_TRANSCRIPT_EMPTY",
                    message=f"{base_message}{detail_text}",
                    retry_hint="请稍后重试；若持续失败请检查 STT 网关可用性，或改用文字输入。",
                )
            raise VoiceQualityRejectError(
                code="VOICE_TRANSCRIPT_EMPTY",
                message=f"{base_message} 可能存在静音、杂音过大或语音内容过短。",
            )
        return

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


def _box_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def _dedupe_overlapped_faces(
    faces: list[tuple[int, int, int, int]],
    iou_threshold: float,
) -> list[tuple[int, int, int, int]]:
    kept: list[tuple[int, int, int, int]] = []
    for box in sorted(faces, key=lambda item: item[2] * item[3], reverse=True):
        if all(_box_iou(box, existing) < iou_threshold for existing in kept):
            kept.append(box)
    return kept


def _detect_eye_count(
    eye_cascade: cv2.CascadeClassifier,
    gray: np.ndarray,
    face_box: tuple[int, int, int, int],
) -> int:
    x, y, w, h = face_box
    roi = gray[y : y + h, x : x + w]
    if roi.size == 0:
        return 0
    eyes = eye_cascade.detectMultiScale(
        roi,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(max(10, w // 12), max(10, h // 12)),
    )
    return int(len(eyes))


def _validate_face_quality(image: np.ndarray) -> None:
    if image is None or image.size == 0:
        raise FaceQualityRejectError(
            code="FACE_IMAGE_INVALID",
            message="图片无效，请重新拍摄。",
        )

    gray_raw = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray_blurred = cv2.GaussianBlur(gray_raw, (3, 3), 0)
    gray = cv2.equalizeHist(gray_blurred)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_clahe = clahe.apply(gray_blurred)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    face_alt_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml")
    face_alt2_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
    face_profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    image_area = float(gray.shape[0] * gray.shape[1])
    min_candidate_ratio = _env_float("FACE_MIN_CANDIDATE_AREA_RATIO", 0.01)
    image_height, image_width = gray.shape[:2]

    def _append_candidate_faces(
        candidates: list[tuple[int, int, int, int]],
        detected_faces: np.ndarray | list[tuple[int, int, int, int]],
    ) -> None:
        if detected_faces is None:
            return
        for (x, y, w, h) in detected_faces:
            x = int(x)
            y = int(y)
            w = int(w)
            h = int(h)
            if w <= 0 or h <= 0:
                continue
            if x >= image_width or y >= image_height:
                continue
            if x < 0:
                w += x
                x = 0
            if y < 0:
                h += y
                y = 0
            if w <= 0 or h <= 0:
                continue
            if x + w > image_width:
                w = image_width - x
            if y + h > image_height:
                h = image_height - y
            if w <= 0 or h <= 0:
                continue
            area_ratio = (w * h) / image_area if image_area > 0 else 0.0
            if area_ratio >= min_candidate_ratio:
                candidates.append((x, y, w, h))

    detection_sources = [gray, gray_clahe, gray_raw]
    candidate_faces: list[tuple[int, int, int, int]] = []
    for detection_gray in detection_sources:
        _append_candidate_faces(
            candidate_faces,
            face_cascade.detectMultiScale(
                detection_gray,
                scaleFactor=1.1,
                minNeighbors=6,
                minSize=(40, 40),
            ),
        )
        _append_candidate_faces(
            candidate_faces,
            face_cascade.detectMultiScale(
                detection_gray,
                scaleFactor=1.08,
                minNeighbors=4,
                minSize=(30, 30),
            ),
        )
        _append_candidate_faces(
            candidate_faces,
            face_cascade.detectMultiScale(
                detection_gray,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(24, 24),
            ),
        )
        _append_candidate_faces(
            candidate_faces,
            face_alt_cascade.detectMultiScale(
                detection_gray,
                scaleFactor=1.08,
                minNeighbors=4,
                minSize=(30, 30),
            ),
        )
        _append_candidate_faces(
            candidate_faces,
            face_alt2_cascade.detectMultiScale(
                detection_gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            ),
        )

        profile_faces = face_profile_cascade.detectMultiScale(
            detection_gray,
            scaleFactor=1.08,
            minNeighbors=3,
            minSize=(24, 24),
        )
        _append_candidate_faces(candidate_faces, profile_faces)

        flipped_gray = cv2.flip(detection_gray, 1)
        profile_faces_flipped = face_profile_cascade.detectMultiScale(
            flipped_gray,
            scaleFactor=1.08,
            minNeighbors=3,
            minSize=(24, 24),
        )
        mapped_flipped_faces: list[tuple[int, int, int, int]] = []
        for (fx, fy, fw, fh) in profile_faces_flipped:
            mapped_flipped_faces.append(
                (int(image_width - (int(fx) + int(fw))), int(fy), int(fw), int(fh))
            )
        _append_candidate_faces(candidate_faces, mapped_flipped_faces)

    dedupe_iou = _env_float("FACE_DEDUPE_IOU_THRESHOLD", 0.3)
    faces = _dedupe_overlapped_faces(candidate_faces, dedupe_iou)

    if len(faces) == 0:
        raise FaceQualityRejectError(
            code="FACE_NOT_FOUND",
            message="没有人像出现，请保证自拍时露脸拍照。",
        )

    min_presence_eye_count = _env_int("FACE_MIN_PRESENCE_EYE_COUNT", 1)
    high_area_presence_ratio = _env_float("FACE_HIGH_AREA_PRESENCE_RATIO", 0.08)

    valid_faces: list[tuple[int, int, int, int]] = []
    face_eye_count: dict[tuple[int, int, int, int], int] = {}
    face_area_ratio_map: dict[tuple[int, int, int, int], float] = {}
    for box in faces:
        x, y, w, h = box
        area_ratio = (w * h) / image_area if image_area > 0 else 0.0
        eye_count = _detect_eye_count(eye_cascade, gray, box)
        face_area_ratio_map[box] = area_ratio
        face_eye_count[box] = eye_count
        # 眼睛特征满足，或人脸区域本身足够大，才当做人像候选，过滤背景误检。
        if eye_count >= min_presence_eye_count or area_ratio >= high_area_presence_ratio:
            valid_faces.append(box)

    if len(valid_faces) == 0:
        raise FaceQualityRejectError(
            code="FACE_NOT_FOUND",
            message="没有人像出现，请保证自拍时露脸拍照。",
        )

    valid_faces = sorted(valid_faces, key=lambda item: item[2] * item[3], reverse=True)
    (x, y, w, h) = valid_faces[0]
    face_area_ratio = face_area_ratio_map.get((x, y, w, h), 0.0)
    min_face_area_ratio = _env_float("FACE_MIN_AREA_RATIO", 0.022)
    if face_area_ratio < min_face_area_ratio:
        if face_eye_count.get((x, y, w, h), 0) <= 0:
            raise FaceQualityRejectError(
                code="FACE_NOT_FOUND",
                message="没有人像出现，请保证自拍时露脸拍照。",
            )
        raise FaceQualityRejectError(
            code="FACE_TOO_SMALL",
            message="人脸区域过小，请靠近镜头后重新拍摄。",
        )

    primary_area = float(w * h)
    multi_min_ratio = _env_float("FACE_MULTI_MIN_RATIO", 0.8)
    min_secondary_area_ratio = min_face_area_ratio * _env_float(
        "FACE_MULTI_SECONDARY_ABS_RATIO_FACTOR", 0.75
    )
    significant_secondary = [
        box
        for box in valid_faces[1:]
        if (
            primary_area > 0
            and ((box[2] * box[3]) / primary_area) >= multi_min_ratio
            and face_area_ratio_map.get(box, 0.0) >= min_secondary_area_ratio
            and face_eye_count.get(box, 0) >= min_presence_eye_count
        )
    ]
    if significant_secondary:
        raise FaceQualityRejectError(
            code="FACE_MULTI_FOUND",
            message="检测到多个人像，请仅保留你本人单人入镜。",
        )

    roi = gray[y : y + h, x : x + w]
    if roi.size == 0:
        raise FaceQualityRejectError(
            code="FACE_IMAGE_INVALID",
            message="图片无效，请重新拍摄。",
        )

    min_brightness = _env_float("FACE_MIN_BRIGHTNESS", 50.0)
    brightness = float(np.mean(roi))
    if brightness < min_brightness:
        raise FaceQualityRejectError(
            code="FACE_TOO_DARK",
            message="光线过暗，请在更明亮环境重新拍摄。",
        )

    min_laplacian_var = _env_float("FACE_MIN_LAPLACIAN_VAR", 24.0)
    if face_area_ratio >= _env_float("FACE_LARGE_FACE_AREA_RATIO", 0.10):
        min_laplacian_var = min(
            min_laplacian_var,
            _env_float("FACE_LARGE_FACE_MIN_LAPLACIAN_VAR", 14.0),
        )
    laplacian_var = float(cv2.Laplacian(roi, cv2.CV_64F).var())
    if laplacian_var < min_laplacian_var:
        raise FaceQualityRejectError(
            code="FACE_TOO_BLUR",
            message="图片模糊，请保持稳定后重新拍摄。",
        )


def _load_image_numpy(image_path: str) -> np.ndarray:
    with Image.open(image_path) as image:
        # Normalize EXIF orientation first. Some mobile photos are stored in rotated
        # orientation metadata; without this, face detection may run on a sideways image.
        normalized = ImageOps.exif_transpose(image)
        rgb = normalized.convert("RGB")
        max_edge = _env_int("ANALYZE_IMAGE_MAX_EDGE", 1280)
        width, height = rgb.size
        longest = max(width, height)
        if longest > max_edge:
            scale = max_edge / float(longest)
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
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
        text_length = len((text_input or "").strip())
        text_weight = 0.55 if text_length >= 12 else 0.45
        if text_length >= 40:
            text_weight = 0.62
        weights[text_emotion] += text_weight
        if face_emotion == text_emotion:
            weights[text_emotion] += 0.18
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


def _poem_entry_id(poet: str, poem_text: str) -> str:
    return _short_hash(f"{poet}|{poem_text}", "poem")


def _guochao_entry_id(name: str) -> str:
    return _short_hash(name, "gc")


def _pick_poem_for_emotion(
    emotion: str,
    recent_poem_ids: Optional[list[str]] = None,
) -> tuple[str, str, str]:
    fallback_emotion = emotion if emotion in _culture_manager.poems_data else "neutral"
    pool = _culture_manager.poems_data.get(fallback_emotion, []) or _culture_manager.poems_data.get("neutral", [])
    if not pool:
        poet = "佚名"
        poem_text = "暂无适合的诗词"
        return poet, poem_text, _poem_entry_id(poet, poem_text)

    recent_set = {item for item in (recent_poem_ids or []) if item}
    available: list[dict[str, str]] = []
    for raw in pool:
        if not isinstance(raw, dict):
            continue
        poet = str(raw.get("poet") or "佚名").strip() or "佚名"
        poem_text = str(raw.get("text") or "").strip() or "暂无诗词"
        if _poem_entry_id(poet, poem_text) in recent_set:
            continue
        available.append({"poet": poet, "text": poem_text})

    candidate_pool = available or [
        {
            "poet": str(item.get("poet") or "佚名").strip() or "佚名",
            "text": str(item.get("text") or "").strip() or "暂无诗词",
        }
        for item in pool
        if isinstance(item, dict)
    ]
    if not candidate_pool:
        poet = "佚名"
        poem_text = "暂无适合的诗词"
        return poet, poem_text, _poem_entry_id(poet, poem_text)

    chosen = random.choice(candidate_pool)
    poet = str(chosen.get("poet") or "佚名").strip() or "佚名"
    poem_text = str(chosen.get("text") or "").strip() or "暂无诗词"
    return poet, poem_text, _poem_entry_id(poet, poem_text)


def _pick_guochao_name(
    emotion: str,
    recent_guochao_ids: Optional[list[str]] = None,
) -> tuple[str, str]:
    choices = guochao_characters.get(emotion, guochao_characters["neutral"])
    normalized_choices = [str(item).strip() for item in choices if str(item).strip()]
    if not normalized_choices:
        normalized_choices = [str(item).strip() for item in guochao_characters.get("neutral", []) if str(item).strip()]
    if not normalized_choices:
        normalized_choices = ["国潮伙伴"]

    recent_set = {item for item in (recent_guochao_ids or []) if item}
    available = [name for name in normalized_choices if _guochao_entry_id(name) not in recent_set]
    picked = random.choice(available or normalized_choices)
    return picked, _guochao_entry_id(picked)


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


def _elapsed_ms(start_ts: float) -> int:
    return max(0, int((perf_counter() - start_ts) * 1000))


ProgressCallback = Optional[Callable[[str, Optional[str]], None]]


def _emit_progress(progress_callback: ProgressCallback, stage: str, message: Optional[str] = None) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(stage, message)
    except Exception as exc:  # pragma: no cover
        logger.debug("analysis progress callback skipped: stage=%s detail=%s", stage, exc)


def run_analysis(
    payload: AnalyzeRequest,
    progress_callback: ProgressCallback = None,
    user_id: Optional[str] = None,
) -> AnalyzeResponse:
    total_started = perf_counter()
    resolve_started = perf_counter()
    resolved = resolve_media_paths(payload)
    processing_metrics_ms: dict[str, int] = {"resolve_media_ms": _elapsed_ms(resolve_started)}
    input_modes = payload.normalized_input_modes()
    _emit_progress(progress_callback, "media_resolved", "分析中：已完成输入校验，正在拆解多模态信号...")

    try:
        analysis_text = (payload.text or "").strip() or None
        request_id = f"ana_{uuid.uuid4().hex[:12]}"

        speech_transcript = None
        speech_transcript_provider = None
        speech_transcript_status = None
        speech_transcript_error = None
        speech_emotion = None
        if resolved.audio_path:
            _emit_progress(progress_callback, "asr_processing", "分析中：正在识别语音内容...")
            stt_started = perf_counter()
            transcription = transcribe_speech_to_text(resolved.audio_path)
            processing_metrics_ms["asr_transcribe_ms"] = _elapsed_ms(stt_started)
            speech_transcript = transcription.text
            speech_transcript_provider = transcription.provider
            speech_transcript_status = transcription.status
            speech_transcript_error = transcription.error

            voice_quality_started = perf_counter()
            try:
                _validate_voice_quality(
                    audio_path=resolved.audio_path,
                    speech_transcript=speech_transcript,
                    speech_transcript_status=speech_transcript_status,
                    speech_transcript_error=speech_transcript_error,
                )
                processing_metrics_ms["voice_quality_check_ms"] = _elapsed_ms(voice_quality_started)

                speech_emotion_started = perf_counter()
                speech_emotion = analyze_speech_emotion(resolved.audio_path)
                processing_metrics_ms["voice_emotion_ms"] = _elapsed_ms(speech_emotion_started)
                _emit_progress(progress_callback, "asr_done", "分析中：语音信号处理完成，正在理解文本内容...")
            except VoiceQualityRejectError as exc:
                processing_metrics_ms["voice_quality_check_ms"] = _elapsed_ms(voice_quality_started)
                # 文本已存在时，语音信号降级为可选输入，避免整单失败。
                if analysis_text:
                    logger.warning(
                        "voice quality rejected but request has text, fallback to text-only: code=%s provider=%s",
                        exc.code,
                        speech_transcript_provider,
                    )
                    speech_transcript = None
                    speech_transcript_provider = None
                    speech_transcript_status = f"rejected:{exc.code}"
                    speech_transcript_error = exc.message
                    speech_emotion = None
                else:
                    raise

        if not analysis_text and speech_transcript:
            analysis_text = speech_transcript

        _emit_progress(progress_callback, "text_processing", "分析中：正在理解文本情绪...")
        text_started = perf_counter()
        text_emotion = analyze_text_sentiment(analysis_text) if analysis_text else None
        processing_metrics_ms["text_emotion_ms"] = _elapsed_ms(text_started)
        _emit_progress(progress_callback, "text_done", "分析中：文本信号已完成，正在检查自拍信号...")

        face_emotion = None
        if resolved.image_path:
            _emit_progress(progress_callback, "face_processing", "分析中：正在识别自拍表情...")
            face_started = perf_counter()
            image_np = _load_image_numpy(resolved.image_path)
            _validate_face_quality(image_np)
            face_emotion = detect_face_emotion(image_np)
            processing_metrics_ms["face_emotion_ms"] = _elapsed_ms(face_started)
            _emit_progress(progress_callback, "face_done", "分析中：自拍信号已完成，正在融合结果...")

        _emit_progress(progress_callback, "fusion_processing", "分析中：正在融合多模态信号...")
        fusion_started = perf_counter()
        chosen_emotion, weights = _select_emotion(
            text_input=analysis_text,
            text_emotion=text_emotion,
            face_emotion=face_emotion,
            speech_emotion=speech_emotion,
        )

        recent_poem_ids: list[str] = []
        recent_guochao_ids: list[str] = []
        normalized_user_id = (user_id or "").strip()
        if normalized_user_id:
            recent_limit = _env_int("ANALYZE_RECENT_AVOID_WINDOW", 8)
            try:
                recent_payload = get_recent_analysis_content_ids(
                    user_id=normalized_user_id,
                    limit=recent_limit,
                )
                recent_poem_ids = list(recent_payload.get("poem_ids") or [])
                recent_guochao_ids = list(recent_payload.get("guochao_ids") or [])
            except Exception as exc:  # pragma: no cover
                logger.debug("recent analysis ids unavailable: %s", exc)

        poet, poem_text, poem_id = _pick_poem_for_emotion(
            chosen_emotion,
            recent_poem_ids=recent_poem_ids,
        )
        interpretation = _culture_manager.get_rich_poem_interpretation(
            poet=poet,
            poem_text=poem_text,
            emotion=chosen_emotion,
        )

        character_name, guochao_id = _pick_guochao_name(
            chosen_emotion,
            recent_guochao_ids=recent_guochao_ids,
        )
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
        processing_metrics_ms["fusion_render_ms"] = _elapsed_ms(fusion_started)
        _emit_progress(progress_callback, "fusion_done", "分析中：结果已生成，正在整理展示内容...")

        processing_metrics_ms["total_ms"] = _elapsed_ms(total_started)
        _emit_progress(progress_callback, "result_ready", "分析中：结果已生成，正在落库并准备打开结果页...")

        logger.info(
            "analysis completed: request_id=%s input_modes=%s transcript_status=%s metrics_ms=%s",
            request_id,
            [mode.value for mode in input_modes],
            speech_transcript_status,
            processing_metrics_ms,
        )

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
                speech_transcript_status=speech_transcript_status,
                speech_transcript_error=speech_transcript_error,
                processing_metrics_ms=processing_metrics_ms,
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
    except Exception as exc:
        processing_metrics_ms["total_ms"] = _elapsed_ms(total_started)
        logger.warning(
            "analysis failed: input_modes=%s metrics_ms=%s error=%s",
            [mode.value for mode in input_modes],
            processing_metrics_ms,
            exc,
        )
        raise
    finally:
        cleanup_temp_files(resolved.cleanup_paths)
