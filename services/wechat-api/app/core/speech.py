"""
语音处理模块 - 语音转文字（主链路）+ 语音情绪（辅助信号）
"""

import base64
import json
import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Optional

import librosa
import numpy as np
import requests

from app.core.feature_flags import is_asr_service_enabled

logger = logging.getLogger(__name__)


@dataclass
class SpeechTranscription:
    text: Optional[str]
    provider: Optional[str] = None
    status: str = "unavailable"
    error: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _env_json_dict(name: str) -> dict[str, Any]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("%s is not valid JSON object, ignored", name)
        return {}

    if not isinstance(payload, dict):
        logger.warning("%s must be a JSON object, ignored", name)
        return {}
    return payload


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


def _stringify_header_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _split_object_path(path: str) -> list[Any]:
    parts: list[Any] = []
    token = ""
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            if token:
                parts.append(token)
                token = ""
            index += 1
            continue
        if char == "[":
            if token:
                parts.append(token)
                token = ""
            closing = path.find("]", index + 1)
            if closing < 0:
                return []
            key = path[index + 1 : closing].strip()
            if key.isdigit():
                parts.append(int(key))
            elif key:
                parts.append(key)
            index = closing + 1
            continue
        token += char
        index += 1
    if token:
        parts.append(token)
    return parts


def _lookup_path(payload: Any, path: str) -> Any:
    current: Any = payload
    for part in _split_object_path(path):
        if isinstance(part, int):
            if not isinstance(current, list) or part < 0 or part >= len(current):
                return None
            current = current[part]
            continue
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _extract_first_text(payload: Any, depth: int = 0) -> Optional[str]:
    if depth > 5:
        return None

    if isinstance(payload, str):
        text = payload.strip()
        return text or None

    if isinstance(payload, list):
        for item in payload[:6]:
            text = _extract_first_text(item, depth + 1)
            if text:
                return text
        return None

    if not isinstance(payload, dict):
        return None

    preferred_keys = (
        "text",
        "transcript",
        "result",
        "sentence",
        "recognized_text",
        "utterance",
        "content",
    )
    for key in preferred_keys:
        if key in payload:
            text = _extract_first_text(payload.get(key), depth + 1)
            if text:
                return text

    for value in payload.values():
        text = _extract_first_text(value, depth + 1)
        if text:
            return text
    return None


def _normalize_transcript(payload: object) -> Optional[str]:
    default_paths = [
        "text",
        "transcript",
        "result",
        "sentence",
        "recognized_text",
        "data.text",
        "data.transcript",
        "data.result",
        "result.text",
        "output.text",
    ]
    response_paths = _env_csv("SPEECH_STT_RESPONSE_PATHS", default_paths)
    for path in response_paths:
        value = _lookup_path(payload, path)
        text = _extract_first_text(value)
        if text:
            return text
    return _extract_first_text(payload)


def _build_stt_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in _env_json_dict("SPEECH_STT_HEADERS_JSON").items():
        if not isinstance(key, str):
            continue
        headers[key] = _stringify_header_value(value)

    token = os.getenv("SPEECH_STT_TOKEN", "").strip()
    if token:
        auth_header = os.getenv("SPEECH_STT_AUTH_HEADER", "Authorization").strip() or "Authorization"
        auth_scheme = os.getenv("SPEECH_STT_AUTH_SCHEME", "Bearer").strip()
        if auth_header not in headers:
            headers[auth_header] = f"{auth_scheme} {token}".strip() if auth_scheme else token
    return headers


def _resolve_audio_mime_type(audio_path: str) -> str:
    override = os.getenv("SPEECH_STT_FILE_MIME", "").strip()
    if override:
        return override
    guessed, _ = mimetypes.guess_type(audio_path)
    return guessed or "audio/mpeg"


def _parse_stt_response(response: requests.Response) -> object:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "json" in content_type:
        return response.json()
    try:
        return response.json()
    except ValueError:
        return response.text


def _transcribe_by_http_endpoint(audio_path: str) -> Optional[str]:
    endpoint = os.getenv("SPEECH_STT_ENDPOINT", "").strip()
    if not endpoint:
        return None

    timeout_sec = _env_int("SPEECH_STT_TIMEOUT_SEC", 18)
    method = (os.getenv("SPEECH_STT_HTTP_METHOD", "POST").strip() or "POST").upper()
    mode = (os.getenv("SPEECH_STT_HTTP_MODE", "multipart").strip() or "multipart").lower()
    headers = _build_stt_headers()
    query = _env_json_dict("SPEECH_STT_QUERY_JSON")
    form = _env_json_dict("SPEECH_STT_FORM_JSON")

    request_kwargs: dict[str, Any] = {
        "method": method,
        "url": endpoint,
        "headers": headers,
        "params": query,
        "timeout": timeout_sec,
    }

    if mode == "multipart":
        file_field = os.getenv("SPEECH_STT_FILE_FIELD", "audio").strip() or "audio"
        mime_type = _resolve_audio_mime_type(audio_path)
        with open(audio_path, "rb") as audio_file:
            request_kwargs["files"] = {
                file_field: (os.path.basename(audio_path), audio_file, mime_type),
            }
            request_kwargs["data"] = form
            response = requests.request(**request_kwargs)
    elif mode == "raw":
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        raw_headers = dict(headers)
        if "Content-Type" not in raw_headers:
            raw_headers["Content-Type"] = (
                os.getenv("SPEECH_STT_RAW_CONTENT_TYPE", "").strip() or _resolve_audio_mime_type(audio_path)
            )
        request_kwargs["headers"] = raw_headers
        request_kwargs["data"] = audio_bytes
        response = requests.request(**request_kwargs)
    elif mode == "json_base64":
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        payload_json = _env_json_dict("SPEECH_STT_JSON_TEMPLATE")
        audio_field = os.getenv("SPEECH_STT_JSON_AUDIO_FIELD", "audio_base64").strip() or "audio_base64"
        filename_field = os.getenv("SPEECH_STT_JSON_FILENAME_FIELD", "filename").strip()
        payload_json[audio_field] = base64.b64encode(audio_bytes).decode("ascii")
        if filename_field and filename_field not in payload_json:
            payload_json[filename_field] = os.path.basename(audio_path)

        json_headers = dict(headers)
        if "Content-Type" not in json_headers:
            json_headers["Content-Type"] = "application/json"
        request_kwargs["headers"] = json_headers
        request_kwargs["json"] = payload_json
        response = requests.request(**request_kwargs)
    else:
        raise ValueError(f"unsupported SPEECH_STT_HTTP_MODE: {mode}")

    if response.status_code >= 400:
        preview = (response.text or "").strip().replace("\n", " ")
        if len(preview) > 240:
            preview = f"{preview[:240]}..."
        raise requests.HTTPError(
            f"stt endpoint returned HTTP {response.status_code}: {preview}",
            response=response,
        )

    payload = _parse_stt_response(response)
    return _normalize_transcript(payload)


def transcribe_speech_to_text(audio_path: str) -> SpeechTranscription:
    """
    语音转文字主链路。

    provider strategy:
    - mock:    SPEECH_STT_PROVIDER=mock, return SPEECH_STT_MOCK_TEXT (for local validation)
    - http:    SPEECH_STT_PROVIDER=http, call SPEECH_STT_ENDPOINT
    - auto:    if SPEECH_STT_ENDPOINT is set, use http; otherwise no transcript
    - unset:   no transcript (compatible fallback)
    - SPEECH_ASR_SERVICE=off: disable transcript request regardless of provider/endpoint

    HTTP adapter:
    - SPEECH_STT_HTTP_MODE=multipart|raw|json_base64
    - request/response keys can be adjusted by env vars without code changes
    """
    if not audio_path or not os.path.exists(audio_path):
        logger.warning("音频文件不存在，无法转写: %s", audio_path)
        return SpeechTranscription(
            text=None,
            provider=None,
            status="audio_missing",
            error="audio file not found",
        )

    provider = os.getenv("SPEECH_STT_PROVIDER", "auto").strip().lower() or "auto"
    asr_enabled = is_asr_service_enabled()

    if not asr_enabled:
        return SpeechTranscription(
            text=None,
            provider=None,
            status="service_disabled",
            error="SPEECH_ASR_SERVICE=off",
        )

    try:
        if provider == "mock":
            text = os.getenv("SPEECH_STT_MOCK_TEXT", "").strip()
            return SpeechTranscription(
                text=text or None,
                provider="mock",
                status="ok" if text else "empty",
                error=None,
            )

        if provider == "http":
            if not os.getenv("SPEECH_STT_ENDPOINT", "").strip():
                return SpeechTranscription(
                    text=None,
                    provider="http",
                    status="provider_unconfigured",
                    error="SPEECH_STT_ENDPOINT is empty",
                )
            text = _transcribe_by_http_endpoint(audio_path)
            return SpeechTranscription(
                text=text,
                provider="http",
                status="ok" if text else "empty",
                error=None,
            )

        if provider == "auto":
            if os.getenv("SPEECH_STT_ENDPOINT", "").strip():
                text = _transcribe_by_http_endpoint(audio_path)
                return SpeechTranscription(
                    text=text,
                    provider="http",
                    status="ok" if text else "empty",
                    error=None,
                )
            return SpeechTranscription(
                text=None,
                provider=None,
                status="provider_unconfigured",
                error="SPEECH_STT_ENDPOINT is empty",
            )

        logger.warning("未知 SPEECH_STT_PROVIDER=%s，已跳过转写", provider)
        return SpeechTranscription(
            text=None,
            provider=provider,
            status="provider_invalid",
            error=f"unsupported provider: {provider}",
        )
    except requests.RequestException as exc:
        logger.warning("语音转写请求失败: %s", exc)
        return SpeechTranscription(
            text=None,
            provider=provider,
            status="request_failed",
            error=str(exc),
        )
    except Exception as exc:
        logger.error("语音转写异常: %s", exc)
        return SpeechTranscription(
            text=None,
            provider=provider,
            status="runtime_error",
            error=str(exc),
        )


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
