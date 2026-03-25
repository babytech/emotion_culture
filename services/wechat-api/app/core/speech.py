"""
语音处理模块 - 语音转文字（主链路）+ 语音情绪（辅助信号）
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import librosa
import numpy as np
import requests


logger = logging.getLogger(__name__)


@dataclass
class SpeechTranscription:
    text: Optional[str]
    provider: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _normalize_transcript(payload: object) -> Optional[str]:
    if isinstance(payload, str):
        text = payload.strip()
        return text or None

    if not isinstance(payload, dict):
        return None

    # Common response keys from different ASR gateways.
    candidates: list[Optional[str]] = [
        payload.get("text"),
        payload.get("transcript"),
        payload.get("result"),
        payload.get("sentence"),
        payload.get("recognized_text"),
    ]

    # Nested layout fallback: {data: {text: ...}}
    data_obj = payload.get("data")
    if isinstance(data_obj, dict):
        candidates.extend(
            [
                data_obj.get("text"),
                data_obj.get("transcript"),
                data_obj.get("result"),
            ]
        )

    for item in candidates:
        if isinstance(item, str):
            text = item.strip()
            if text:
                return text

    return None


def _transcribe_by_http_endpoint(audio_path: str) -> Optional[str]:
    endpoint = os.getenv("SPEECH_STT_ENDPOINT", "").strip()
    if not endpoint:
        return None

    timeout_sec = _env_int("SPEECH_STT_TIMEOUT_SEC", 18)
    token = os.getenv("SPEECH_STT_TOKEN", "").strip()

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            endpoint,
            headers=headers,
            files={"audio": (os.path.basename(audio_path), audio_file, "audio/mpeg")},
            timeout=timeout_sec,
        )

    response.raise_for_status()
    payload = response.json()
    return _normalize_transcript(payload)


def transcribe_speech_to_text(audio_path: str) -> SpeechTranscription:
    """
    语音转文字主链路。

    provider strategy:
    - mock:    SPEECH_STT_PROVIDER=mock, return SPEECH_STT_MOCK_TEXT (for local validation)
    - http:    SPEECH_STT_PROVIDER=http, call SPEECH_STT_ENDPOINT
    - auto:    if SPEECH_STT_ENDPOINT is set, use http; otherwise no transcript
    - unset:   no transcript (compatible fallback)
    """
    if not audio_path or not os.path.exists(audio_path):
        logger.warning("音频文件不存在，无法转写: %s", audio_path)
        return SpeechTranscription(text=None, provider=None)

    provider = os.getenv("SPEECH_STT_PROVIDER", "auto").strip().lower() or "auto"

    try:
        if provider == "mock":
            text = os.getenv("SPEECH_STT_MOCK_TEXT", "").strip()
            return SpeechTranscription(text=text or None, provider="mock")

        if provider == "http":
            text = _transcribe_by_http_endpoint(audio_path)
            return SpeechTranscription(text=text, provider="http")

        if provider == "auto":
            if os.getenv("SPEECH_STT_ENDPOINT", "").strip():
                text = _transcribe_by_http_endpoint(audio_path)
                return SpeechTranscription(text=text, provider="http")
            return SpeechTranscription(text=None, provider=None)

        logger.warning("未知 SPEECH_STT_PROVIDER=%s，已跳过转写", provider)
        return SpeechTranscription(text=None, provider=None)
    except requests.RequestException as exc:
        logger.warning("语音转写请求失败: %s", exc)
        return SpeechTranscription(text=None, provider=provider)
    except Exception as exc:
        logger.error("语音转写异常: %s", exc)
        return SpeechTranscription(text=None, provider=provider)


def extract_audio_features(audio_path):
    """
    从音频文件中提取基本特征

    参数:
        audio_path: 音频文件路径

    返回:
        提取的特征字典
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)

        energy = np.sum(y**2) / len(y)

        f0, voiced_flag, _voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        pitch_mean = 0.0
        if voiced_flag.any():
            valid_pitches = f0[voiced_flag]
            if len(valid_pitches) > 0:
                pitch_mean = np.mean(valid_pitches)

        zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(y))
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfccs, axis=1)
        duration = librosa.get_duration(y=y, sr=sr)

        features = {
            "energy": float(energy),
            "pitch_mean": float(pitch_mean),
            "zero_crossing_rate": float(zero_crossing_rate),
            "mfcc_mean": mfcc_mean.tolist(),
            "duration": float(duration),
        }

        return features

    except Exception as exc:
        logger.error("提取音频特征时出错: %s", exc)
        return None


def analyze_speech_emotion(audio_path):
    """
    分析语音情绪（辅助信号）

    参数:
        audio_path: 音频文件路径

    返回:
        检测到的情绪标签: happy, sad, angry, surprise, neutral, fear
    """
    if not audio_path or not os.path.exists(audio_path):
        logger.warning("音频文件不存在: %s", audio_path)
        return None

    try:
        features = extract_audio_features(audio_path)
        if not features:
            return None

        energy = features["energy"]
        pitch_mean = features["pitch_mean"]
        zero_crossing_rate = features["zero_crossing_rate"]

        if energy > 0.05 and pitch_mean > 200 and zero_crossing_rate > 0.1:
            if pitch_mean > 300:
                return "surprise"
            return "happy"

        if energy > 0.05 and 150 < pitch_mean < 250 and zero_crossing_rate > 0.08:
            return "angry"

        if energy < 0.02 and pitch_mean < 200:
            return "sad"

        if energy < 0.03 and 150 < pitch_mean < 250 and zero_crossing_rate < 0.06:
            return "fear"

        return "neutral"
    except Exception as exc:
        logger.error("分析语音情绪时出错: %s", exc)
        return "neutral"
