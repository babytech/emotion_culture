import os
import tempfile
import base64
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from hashlib import sha1
from typing import Any, Optional
from urllib.parse import urlencode

import numpy as np
import requests
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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_json(name: str) -> dict[str, Any]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be a valid JSON object string") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be a JSON object")
    return payload


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
            np.clip(gray * 0.20, 0, 255),  # red
            np.clip(gray * 0.80, 0, 255),  # green
            np.clip(gray * 1.28 + 18.0, 0, 255),  # blue
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
    warm[:, :, 0] = np.clip(arr[:, :, 0] * 1.22 + 14.0, 0, 255)  # red
    warm[:, :, 1] = np.clip(arr[:, :, 1] * 0.92 + 6.0, 0, 255)  # green
    warm[:, :, 2] = np.clip(arr[:, :, 2] * 0.74, 0, 255)  # blue
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


def _extract_response_value(payload: dict, path_expr: str) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    paths = [item.strip() for item in (path_expr or "").split(",") if item.strip()]
    if not paths:
        paths = ["result.url", "data.url", "url"]

    for path in paths:
        node = _extract_response_path(payload, path)
        if isinstance(node, str) and node.strip():
            return node.strip()
    return None


def _extract_response_path(payload: dict[str, Any], path_expr: str) -> Any:
    if not isinstance(payload, dict):
        return None
    paths = [item.strip() for item in (path_expr or "").split(",") if item.strip()]
    for path in paths:
        node: Any = payload
        ok = True
        for key in path.split("."):
            if isinstance(node, dict):
                if key not in node:
                    ok = False
                    break
                node = node[key]
                continue
            if isinstance(node, list):
                try:
                    index = int(key)
                except ValueError:
                    ok = False
                    break
                if index < 0 or index >= len(node):
                    ok = False
                    break
                node = node[index]
                continue
            ok = False
            break
        if ok:
            return node
    return None


def _set_path_value(payload: dict[str, Any], path_expr: str, value: Any) -> None:
    if not path_expr:
        return
    segments = [segment.strip() for segment in path_expr.split(".") if segment.strip()]
    if not segments:
        return

    node: Any = payload
    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1
        next_segment = segments[index + 1] if not is_last else None

        if isinstance(node, dict):
            if is_last:
                node[segment] = value
                return
            if segment not in node or node[segment] is None:
                node[segment] = [] if (next_segment and next_segment.isdigit()) else {}
            node = node[segment]
            continue

        if isinstance(node, list):
            try:
                list_index = int(segment)
            except ValueError as exc:
                raise ValueError(f"invalid list index in path: {path_expr}") from exc
            if list_index < 0:
                raise ValueError(f"list index must be >= 0 in path: {path_expr}")
            while len(node) <= list_index:
                node.append(None)
            if is_last:
                node[list_index] = value
                return
            if node[list_index] is None:
                node[list_index] = [] if (next_segment and next_segment.isdigit()) else {}
            node = node[list_index]
            continue

        raise ValueError(f"cannot set nested path on non-container value: {path_expr}")


def _download_temp_image(url: str) -> str:
    timeout = _env_int("MEDIA_GEN_HTTP_TIMEOUT_SEC", 25)
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="media_gen_http_")
    with open(tmp.name, "wb") as file_obj:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)
    return tmp.name


def _request_json(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    json_body: Optional[dict[str, Any]],
    timeout: int,
) -> dict[str, Any]:
    req_method = (method or "POST").strip().upper()
    if req_method in {"GET", "DELETE"}:
        resp = requests.request(
            req_method,
            url,
            headers=headers,
            params=json_body or None,
            timeout=timeout,
        )
    else:
        resp = requests.request(
            req_method,
            url,
            headers=headers,
            json=json_body or {},
            timeout=timeout,
        )
    resp.raise_for_status()
    if not resp.content:
        return {}
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: provider response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: provider response is not JSON object")
    provider_code = payload.get("code")
    code_text = str(provider_code).strip() if provider_code is not None else ""
    if code_text and code_text not in {"0", "200"}:
        msg = str(payload.get("msg") or payload.get("message") or "").strip()
        raise ValueError(f"MEDIA_GEN_PROVIDER_FAILED: code={code_text}, msg={msg}")
    return payload


def _generate_http_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    prompt: Optional[str] = None,
) -> GeneratedImageArtifact:
    endpoint = (os.getenv("MEDIA_GEN_HTTP_ENDPOINT", "") or "").strip()
    if not endpoint:
        raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_HTTP_ENDPOINT is required")

    mode = (os.getenv("MEDIA_GEN_HTTP_MODE", "multipart") or "").strip().lower()
    style_field = (os.getenv("MEDIA_GEN_HTTP_STYLE_FIELD", "style") or "").strip() or "style"
    prompt_field = (os.getenv("MEDIA_GEN_HTTP_PROMPT_FIELD", "prompt") or "").strip() or "prompt"
    file_field = (os.getenv("MEDIA_GEN_HTTP_FILE_FIELD", "image") or "").strip() or "image"
    response_path = (os.getenv("MEDIA_GEN_HTTP_RESPONSE_PATH", "result.url,data.url,url") or "").strip()
    timeout = _env_int("MEDIA_GEN_HTTP_TIMEOUT_SEC", 25)

    headers: dict[str, str] = {}
    auth_token = (os.getenv("MEDIA_GEN_HTTP_AUTH_TOKEN", "") or "").strip()
    auth_header = (os.getenv("MEDIA_GEN_HTTP_AUTH_HEADER", "Authorization") or "").strip() or "Authorization"
    if auth_token:
        headers[auth_header] = auth_token

    if mode == "multipart":
        data = {
            style_field: style.value,
            prompt_field: (prompt or "").strip(),
        }
        with open(source_path, "rb") as image_file:
            files = {
                file_field: (
                    os.path.basename(source_path),
                    image_file,
                    "image/jpeg",
                )
            }
            resp = requests.post(
                endpoint,
                headers=headers,
                data=data,
                files=files,
                timeout=timeout,
            )
    else:
        with open(source_path, "rb") as image_file:
            binary = image_file.read()
        payload = {
            style_field: style.value,
            prompt_field: (prompt or "").strip(),
            file_field: binary.hex(),
            "image_encoding": "hex",
        }
        headers.setdefault("Content-Type", "application/json")
        resp = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    resp.raise_for_status()
    body = resp.json() if resp.content else {}
    image_url = _extract_response_value(body, response_path)
    if not image_url:
        raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: missing image url in provider response")
    downloaded_path = _download_temp_image(image_url)
    return GeneratedImageArtifact(path=downloaded_path, provider="http_gateway", cleanup_path=downloaded_path)


def _liblib_make_sign(*, secret_key: str, uri: str, timestamp_ms: str, signature_nonce: str) -> str:
    content = "&".join((uri, timestamp_ms, signature_nonce))
    digest = hmac.new(secret_key.encode("utf-8"), content.encode("utf-8"), sha1).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _join_url(base_url: str, uri: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    route = (uri or "").strip()
    if not base:
        raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_BASE_URL is required")
    if not route:
        raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_CREATE_URI is required")
    if not route.startswith("/"):
        route = f"/{route}"
    return f"{base}{route}"


def _build_liblib_signed_url(base_url: str, uri: str) -> str:
    access_key = (os.getenv("MEDIA_GEN_LIBLIB_ACCESS_KEY", "") or "").strip()
    secret_key = (os.getenv("MEDIA_GEN_LIBLIB_SECRET_KEY", "") or "").strip()
    if not access_key or not secret_key:
        raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_ACCESS_KEY/SECRET_KEY are required")

    signature_param = (os.getenv("MEDIA_GEN_LIBLIB_SIGNATURE_PARAM", "Signature") or "").strip() or "Signature"
    nonce_param = (os.getenv("MEDIA_GEN_LIBLIB_NONCE_PARAM", "SignatureNonce") or "").strip() or "SignatureNonce"
    ts_param = (os.getenv("MEDIA_GEN_LIBLIB_TIMESTAMP_PARAM", "Timestamp") or "").strip() or "Timestamp"
    ak_param = (os.getenv("MEDIA_GEN_LIBLIB_ACCESS_KEY_PARAM", "AccessKey") or "").strip() or "AccessKey"

    now_ms = str(int(time.time() * 1000))
    nonce_with_dash = _env_bool("MEDIA_GEN_LIBLIB_NONCE_WITH_DASH", False)
    signature_nonce = str(uuid.uuid4()) if nonce_with_dash else uuid.uuid4().hex
    sign = _liblib_make_sign(
        secret_key=secret_key,
        uri=uri if uri.startswith("/") else f"/{uri}",
        timestamp_ms=now_ms,
        signature_nonce=signature_nonce,
    )
    query = {
        ak_param: access_key,
        ts_param: now_ms,
        nonce_param: signature_nonce,
        signature_param: sign,
    }

    extra_query = _env_json("MEDIA_GEN_LIBLIB_QUERY_JSON")
    for key, value in extra_query.items():
        if value is None:
            continue
        query[str(key)] = str(value)
    return f"{_join_url(base_url, uri)}?{urlencode(query)}"


def _build_liblib_create_payload(
    *,
    style: MediaGenerateStyle,
    source_path: str,
    source_url: Optional[str],
    prompt: Optional[str],
) -> dict[str, Any]:
    payload = _env_json("MEDIA_GEN_LIBLIB_CREATE_JSON_TEMPLATE")
    raw_style_field = os.getenv("MEDIA_GEN_LIBLIB_STYLE_FIELD")
    raw_prompt_field = os.getenv("MEDIA_GEN_LIBLIB_PROMPT_FIELD")
    raw_image_field = os.getenv("MEDIA_GEN_LIBLIB_IMAGE_FIELD")
    style_field = "style" if raw_style_field is None else raw_style_field.strip()
    prompt_field = "prompt" if raw_prompt_field is None else raw_prompt_field.strip()
    image_field = "image" if raw_image_field is None else raw_image_field.strip()
    image_mode = (os.getenv("MEDIA_GEN_LIBLIB_IMAGE_MODE", "base64") or "").strip().lower()

    if style_field:
        _set_path_value(payload, style_field, style.value)
    if prompt_field:
        _set_path_value(payload, prompt_field, (prompt or "").strip())

    if image_mode == "url":
        value = (source_url or "").strip()
        if not value:
            raise ValueError("MEDIA_GEN_PROVIDER_BAD_REQUEST: source image url is required for image_mode=url")
        if not image_field:
            raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_IMAGE_FIELD is required when image_mode=url")
        _set_path_value(payload, image_field, value)
    elif image_mode == "hex":
        if not image_field:
            raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_IMAGE_FIELD is required when image_mode=hex")
        with open(source_path, "rb") as image_file:
            _set_path_value(payload, image_field, image_file.read().hex())
        encoding_field = (os.getenv("MEDIA_GEN_LIBLIB_IMAGE_ENCODING_FIELD", "image_encoding") or "").strip()
        if encoding_field:
            _set_path_value(payload, encoding_field, "hex")
    elif image_mode == "base64":
        if not image_field:
            raise ValueError("MEDIA_GEN_PROVIDER_CONFIG_INVALID: MEDIA_GEN_LIBLIB_IMAGE_FIELD is required when image_mode=base64")
        with open(source_path, "rb") as image_file:
            _set_path_value(payload, image_field, base64.b64encode(image_file.read()).decode("ascii"))
        encoding_field = (os.getenv("MEDIA_GEN_LIBLIB_IMAGE_ENCODING_FIELD", "image_encoding") or "").strip()
        if encoding_field:
            _set_path_value(payload, encoding_field, "base64")
    elif image_mode == "none":
        pass
    else:
        raise ValueError(f"MEDIA_GEN_PROVIDER_CONFIG_INVALID: unsupported MEDIA_GEN_LIBLIB_IMAGE_MODE={image_mode}")
    return payload


def _status_value_in(value: Any, values_expr: str) -> bool:
    expected = {item.strip().lower() for item in (values_expr or "").split(",") if item.strip()}
    if not expected:
        return False
    text = str(value).strip().lower()
    return text in expected


def _generate_liblib_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    source_url: Optional[str] = None,
    prompt: Optional[str] = None,
) -> GeneratedImageArtifact:
    base_url = (os.getenv("MEDIA_GEN_LIBLIB_BASE_URL", "https://openapi.liblibai.cloud") or "").strip()
    create_uri = (os.getenv("MEDIA_GEN_LIBLIB_CREATE_URI", "/api/genImg") or "").strip()
    create_method = (os.getenv("MEDIA_GEN_LIBLIB_CREATE_METHOD", "POST") or "").strip().upper()
    timeout = _env_int("MEDIA_GEN_HTTP_TIMEOUT_SEC", 25)
    response_path = (
        os.getenv(
            "MEDIA_GEN_LIBLIB_RESPONSE_PATH",
            "data.images.0.imageUrl,data.image_url,data.imageUrl,data.url,result.url,url",
        )
        or ""
    ).strip()

    headers = {"Content-Type": "application/json"}
    extra_headers = _env_json("MEDIA_GEN_LIBLIB_HEADERS_JSON")
    for key, value in extra_headers.items():
        if value is None:
            continue
        headers[str(key)] = str(value)

    create_payload = _build_liblib_create_payload(
        style=style,
        source_path=source_path,
        source_url=source_url,
        prompt=prompt,
    )
    create_url = _build_liblib_signed_url(base_url, create_uri)
    create_resp = _request_json(
        url=create_url,
        method=create_method,
        headers=headers,
        json_body=create_payload,
        timeout=timeout,
    )
    image_url = _extract_response_value(create_resp, response_path)
    if image_url:
        downloaded_path = _download_temp_image(image_url)
        return GeneratedImageArtifact(path=downloaded_path, provider="liblib", cleanup_path=downloaded_path)

    status_uri = (os.getenv("MEDIA_GEN_LIBLIB_STATUS_URI", "") or "").strip()
    if not status_uri:
        raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: missing image url in liblib create response")

    task_id_path = (
        os.getenv("MEDIA_GEN_LIBLIB_TASK_ID_PATH", "data.generateUuid,generateUuid,data.task_id,task_id,data.id,id")
        or ""
    ).strip()
    task_id = _extract_response_path(create_resp, task_id_path)
    task_id_text = str(task_id).strip() if task_id is not None else ""
    if not task_id_text:
        raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: missing task id in liblib create response")

    status_method = (os.getenv("MEDIA_GEN_LIBLIB_STATUS_METHOD", "POST") or "").strip().upper()
    status_task_field = (os.getenv("MEDIA_GEN_LIBLIB_STATUS_TASK_FIELD", "generateUuid") or "").strip() or "generateUuid"
    status_state_path = (
        os.getenv("MEDIA_GEN_LIBLIB_STATUS_STATE_PATH", "data.generateStatus,generateStatus,data.status,status,data.state,state")
        or ""
    ).strip()
    done_values = (os.getenv("MEDIA_GEN_LIBLIB_STATUS_DONE_VALUES", "5,SUCCESS,SUCCEEDED,DONE,FINISHED,2,ok") or "").strip()
    failed_values = (os.getenv("MEDIA_GEN_LIBLIB_STATUS_FAILED_VALUES", "6,7,FAILED,FAIL,ERROR,-1") or "").strip()
    poll_interval_ms = _env_int("MEDIA_GEN_LIBLIB_POLL_INTERVAL_MS", 1500)
    poll_attempts = _env_int("MEDIA_GEN_LIBLIB_POLL_ATTEMPTS", 25)
    status_template = _env_json("MEDIA_GEN_LIBLIB_STATUS_JSON_TEMPLATE")

    for _ in range(max(1, poll_attempts)):
        status_payload = dict(status_template)
        status_payload[status_task_field] = task_id_text
        status_url = _build_liblib_signed_url(base_url, status_uri)
        status_resp = _request_json(
            url=status_url,
            method=status_method,
            headers=headers,
            json_body=status_payload,
            timeout=timeout,
        )
        status_image_url = _extract_response_value(status_resp, response_path)
        if status_image_url:
            downloaded_path = _download_temp_image(status_image_url)
            return GeneratedImageArtifact(path=downloaded_path, provider="liblib", cleanup_path=downloaded_path)

        state_value = _extract_response_path(status_resp, status_state_path)
        if _status_value_in(state_value, failed_values):
            raise ValueError(f"MEDIA_GEN_PROVIDER_FAILED: liblib task failed ({state_value})")
        if _status_value_in(state_value, done_values):
            raise ValueError("MEDIA_GEN_PROVIDER_BAD_RESPONSE: liblib task finished but image url is missing")
        time.sleep(max(200, poll_interval_ms) / 1000.0)

    raise ValueError("MEDIA_GEN_PROVIDER_TIMEOUT: liblib task polling timed out")


def generate_stylized_image(
    style: MediaGenerateStyle,
    source_path: str,
    *,
    source_url: Optional[str] = None,
    prompt: Optional[str] = None,
) -> GeneratedImageArtifact:
    provider = (os.getenv("MEDIA_GEN_PROVIDER", "local_mock") or "").strip().lower()
    if provider in {"local_mock", "mock", "local"}:
        return _generate_local_mock_image(style=style, source_path=source_path)

    if provider in {"http", "liblib", "liblib_http"}:
        return _generate_http_image(
            style=style,
            source_path=source_path,
            prompt=prompt,
        )
    if provider in {"liblib_signed", "liblib_openapi"}:
        return _generate_liblib_image(
            style=style,
            source_path=source_path,
            source_url=source_url,
            prompt=prompt,
        )

    raise ValueError(f"unsupported MEDIA_GEN_PROVIDER: {provider}")
