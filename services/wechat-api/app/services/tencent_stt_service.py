import base64
import hashlib
import hmac
import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value
    except ValueError:
        return default


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name, "").strip()
    return raw if raw else default


def _sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _tc3_sign(
    *,
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    version: str,
    payload: str,
    timestamp: int,
) -> str:
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\n"
    signed_headers = "content-type;host"
    canonical_request = (
        "POST\n"
        "/\n"
        "\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{_sha256_hex(payload)}"
    )
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = (
        "TC3-HMAC-SHA256\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{_sha256_hex(canonical_request)}"
    )

    secret_date = _hmac_sha256(f"TC3{secret_key}".encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return (
        "TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )


def _guess_voice_format(filename: str, content_type: str) -> str:
    ext = os.path.splitext((filename or "").strip())[1].lower().lstrip(".")
    supported = {"wav", "mp3", "silk", "opus", "pcm", "m4a", "speex"}
    if ext:
        return ext if ext in supported else "mp3"

    mime = (content_type or "").strip().lower()
    if mime:
        guessed_ext = mimetypes.guess_extension(mime) or ""
        guessed = guessed_ext.lstrip(".")
        if guessed:
            return guessed if guessed in supported else "mp3"
    return "mp3"


@dataclass
class TencentSentenceResult:
    text: str
    request_id: Optional[str]
    audio_duration_ms: Optional[int]
    raw_response: dict


def recognize_sentence(audio_bytes: bytes, *, filename: str = "", content_type: str = "") -> TencentSentenceResult:
    secret_id = _env_str("TENCENT_SECRET_ID")
    secret_key = _env_str("TENCENT_SECRET_KEY")
    if not secret_id or not secret_key:
        raise ValueError("missing TENCENT_SECRET_ID/TENCENT_SECRET_KEY")

    if not audio_bytes:
        raise ValueError("empty audio bytes")
    if len(audio_bytes) > _env_int("TENCENT_ASR_MAX_AUDIO_BYTES", 3 * 1024 * 1024):
        raise ValueError("audio file is too large for Tencent SentenceRecognition (max 3MB)")

    host = _env_str("TENCENT_ASR_ENDPOINT", "asr.tencentcloudapi.com")
    service = _env_str("TENCENT_ASR_SERVICE", "asr")
    action = _env_str("TENCENT_ASR_ACTION", "SentenceRecognition")
    version = _env_str("TENCENT_ASR_VERSION", "2019-06-14")
    region = _env_str("TENCENT_ASR_REGION", "ap-guangzhou")

    payload = {
        "SubServiceType": _env_int("TENCENT_ASR_SUB_SERVICE_TYPE", 2),
        "ProjectId": _env_int("TENCENT_ASR_PROJECT_ID", 0),
        "EngSerViceType": _env_str("TENCENT_ASR_ENGINE_MODEL_TYPE", "16k_zh"),
        "SourceType": 1,
        "VoiceFormat": _env_str("TENCENT_ASR_VOICE_FORMAT", "") or _guess_voice_format(filename, content_type),
        "Data": base64.b64encode(audio_bytes).decode("ascii"),
        "DataLen": len(audio_bytes),
    }

    word_info = _env_int("TENCENT_ASR_WORD_INFO", 0)
    if word_info in (0, 1, 2):
        payload["WordInfo"] = word_info

    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    authorization = _tc3_sign(
        secret_id=secret_id,
        secret_key=secret_key,
        service=service,
        host=host,
        action=action,
        version=version,
        payload=payload_json,
        timestamp=timestamp,
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
    }
    if region:
        headers["X-TC-Region"] = region

    timeout_sec = _env_int("TENCENT_ASR_TIMEOUT_SEC", 20)
    url = f"https://{host}/"
    response = requests.post(url, headers=headers, data=payload_json.encode("utf-8"), timeout=timeout_sec)
    response.raise_for_status()

    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("invalid Tencent ASR response payload")
    resp = body.get("Response")
    if not isinstance(resp, dict):
        raise RuntimeError("missing Response object in Tencent ASR payload")

    error_obj = resp.get("Error")
    if isinstance(error_obj, dict):
        code = str(error_obj.get("Code") or "TencentASRError")
        message = str(error_obj.get("Message") or "unknown error")
        raise RuntimeError(f"{code}: {message}")

    text = str(resp.get("Result") or "").strip()
    request_id = str(resp.get("RequestId") or "").strip() or None
    duration = resp.get("AudioDuration")
    duration_ms = int(duration) if isinstance(duration, int) else None
    return TencentSentenceResult(
        text=text,
        request_id=request_id,
        audio_duration_ms=duration_ms,
        raw_response=body,
    )
