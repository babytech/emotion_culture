import os
import tempfile
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from app.schemas.analyze import AnalyzeRequest


API_ROOT = Path(__file__).resolve().parents[2]
CORE_IMAGES_DIR = Path(__file__).resolve().parents[1] / "core" / "images"
WECHAT_API_BASE = "https://api.weixin.qq.com"
logger = logging.getLogger(__name__)

_TOKEN_CACHE: dict[str, Optional[object]] = {"token": None, "expires_at": None}
_HTTP_TRUST_ENV_HINT: Optional[bool] = None


@dataclass
class ResolvedMediaPaths:
    image_path: Optional[str]
    audio_path: Optional[str]
    cleanup_paths: list[str] = field(default_factory=list)


@dataclass
class ResolvedInputFile:
    path: Optional[str]
    cleanup_path: Optional[str]


def _env_truthy(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
        if parsed <= 0:
            return default
        return parsed
    except ValueError:
        return default


def _resolve_verify_option() -> bool | str:
    if _env_truthy("WECHAT_DISABLE_SSL_VERIFY", "0"):
        return False

    custom_ca = os.getenv("WECHAT_CA_BUNDLE", "").strip()
    if custom_ca:
        if not Path(custom_ca).exists():
            raise ValueError(f"WECHAT_CA_BUNDLE file not found: {custom_ca}")
        return custom_ca

    # Keep verify=True so requests can honor REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE
    # when trust_env is enabled in cloud runtime.
    return True


def _http_request(method: str, url: str, *, timeout: int, **kwargs) -> requests.Response:
    global _HTTP_TRUST_ENV_HINT
    configured_trust_env = _env_truthy("WECHAT_REQUESTS_TRUST_ENV", "1")
    verify_option = _resolve_verify_option()

    trust_env_order: list[bool] = []
    for trust_env in (_HTTP_TRUST_ENV_HINT, configured_trust_env, not configured_trust_env):
        if isinstance(trust_env, bool) and trust_env not in trust_env_order:
            trust_env_order.append(trust_env)

    attempts: list[tuple[bool, bool | str]] = []
    for trust_env in trust_env_order:
        candidate = (trust_env, verify_option)
        if candidate not in attempts:
            attempts.append(candidate)

    last_error: Optional[Exception] = None
    for index, (attempt_trust_env, attempt_verify) in enumerate(attempts):
        attempt_timeout: int | tuple[int, int] = timeout
        # If we have a fallback route, make the first connect attempt fail fast
        # to avoid long blocking when proxy/env chain is unavailable.
        if len(attempts) > 1 and index == 0 and isinstance(timeout, int):
            connect_timeout = min(3, max(1, timeout))
            attempt_timeout = (connect_timeout, timeout)

        with requests.Session() as session:
            session.trust_env = attempt_trust_env
            try:
                response = session.request(
                    method=method,
                    url=url,
                    timeout=attempt_timeout,
                    verify=attempt_verify,
                    **kwargs,
                )
                _HTTP_TRUST_ENV_HINT = attempt_trust_env
                return response
            except requests.exceptions.RequestException as exc:
                last_error = exc
                continue

    host = urlparse(url).netloc
    err_type = type(last_error).__name__ if last_error else "RequestException"
    raise ValueError(
        "wechat api ssl verify failed for "
        f"{host}. set WECHAT_CA_BUNDLE to trusted CA file; "
        "or verify runtime proxy/cert chain; "
        f"last_error={err_type}; "
        "for emergency only, set WECHAT_DISABLE_SSL_VERIFY=1"
    ) from last_error


def resolve_local_path(path_value: Optional[str], field_name: str) -> Optional[str]:
    if not path_value:
        return None

    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = (API_ROOT / candidate).resolve()

    if not candidate.exists():
        raise ValueError(f"{field_name} not found: {candidate}")
    if not candidate.is_file():
        raise ValueError(f"{field_name} is not a file: {candidate}")

    return str(candidate)


def cleanup_temp_files(paths: list[str]) -> None:
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            # 清理失败不应中断主流程
            pass


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"missing required env var: {key}")
    return value


def _get_access_token() -> str:
    token = _TOKEN_CACHE.get("token")
    expires_at = _TOKEN_CACHE.get("expires_at")
    if token and isinstance(expires_at, float) and time.time() < expires_at:
        return str(token)

    app_id = _require_env("WECHAT_APP_ID")
    app_secret = _require_env("WECHAT_APP_SECRET")

    response = _http_request(
        "GET",
        f"{WECHAT_API_BASE}/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        },
        timeout=_env_int("WECHAT_TOKEN_TIMEOUT_SEC", 8),
    )
    response.raise_for_status()
    payload = response.json()

    if "access_token" not in payload:
        errcode = payload.get("errcode")
        errmsg = payload.get("errmsg")
        raise ValueError(f"failed to get access token: {errcode} {errmsg}")

    access_token = str(payload["access_token"])
    expires_in = int(payload.get("expires_in", 7200))
    _TOKEN_CACHE["token"] = access_token
    _TOKEN_CACHE["expires_at"] = time.time() + max(expires_in - 120, 60)
    return access_token


def _extract_cloud_env_from_file_id(file_id: str) -> Optional[str]:
    if not file_id.startswith("cloud://"):
        return None

    # fileID format is usually: cloud://<env-id>.<bucket-suffix>/path
    # Only the part before first '.' is the real env id.
    content = file_id[len("cloud://") :]
    first_segment = content.split("/", maxsplit=1)[0].strip()
    if not first_segment:
        return None

    env_name = first_segment.split(".", maxsplit=1)[0].strip()
    return env_name or None


def _get_cloudbase_download_url(file_id: str) -> str:
    env_name = _extract_cloud_env_from_file_id(file_id) or os.getenv("WECHAT_CLOUDBASE_ENV")
    if not env_name:
        raise ValueError(
            "missing cloud env: file_id has no env prefix and WECHAT_CLOUDBASE_ENV is not set"
        )

    access_token = _get_access_token()

    response = _http_request(
        "POST",
        f"{WECHAT_API_BASE}/tcb/batchdownloadfile",
        params={"access_token": access_token},
        json={
            "env": env_name,
            "file_list": [{"fileid": file_id, "max_age": 3600}],
        },
        timeout=_env_int("WECHAT_BATCHDOWNLOAD_TIMEOUT_SEC", 10),
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("errcode", 0) != 0:
        raise ValueError(
            f"cloudbase batchdownloadfile failed (env={env_name}): {payload.get('errcode')} {payload.get('errmsg')}"
        )

    file_list = payload.get("file_list", [])
    if not file_list:
        raise ValueError("cloudbase batchdownloadfile returned empty file_list")

    entry = file_list[0]
    status = int(entry.get("status", -1))
    if status != 0:
        raise ValueError(
            f"cloud file resolve failed: status={status}, errmsg={entry.get('errmsg')}"
        )

    download_url = entry.get("download_url")
    if not download_url:
        raise ValueError("cloud file resolve failed: missing download_url")

    return str(download_url)


def delete_cloud_file_ids(file_ids: list[str]) -> dict[str, list[str]]:
    normalized: list[str] = []
    for item in file_ids:
        value = (item or "").strip()
        if not value or not value.startswith("cloud://"):
            continue
        if value not in normalized:
            normalized.append(value)

    if not normalized:
        return {"deleted_ids": [], "failed_ids": []}

    grouped: dict[str, list[str]] = {}
    failed_ids: list[str] = []
    for file_id in normalized:
        env_name = _extract_cloud_env_from_file_id(file_id) or os.getenv("WECHAT_CLOUDBASE_ENV", "").strip()
        if not env_name:
            failed_ids.append(file_id)
            continue
        grouped.setdefault(env_name, []).append(file_id)

    deleted_ids: list[str] = []
    access_token: Optional[str] = None
    for env_name, env_file_ids in grouped.items():
        try:
            if access_token is None:
                access_token = _get_access_token()

            response = _http_request(
                "POST",
                f"{WECHAT_API_BASE}/tcb/batchdeletefile",
                params={"access_token": access_token},
                json={
                    "env": env_name,
                    "fileid_list": env_file_ids,
                },
                timeout=_env_int("WECHAT_BATCHDELETE_TIMEOUT_SEC", 10),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errcode", 0) != 0:
                failed_ids.extend(env_file_ids)
                continue

            entry_list = payload.get("delete_list")
            if not isinstance(entry_list, list):
                entry_list = payload.get("file_list")
            status_map: dict[str, int] = {}
            if isinstance(entry_list, list):
                for entry in entry_list:
                    if not isinstance(entry, dict):
                        continue
                    file_id = str(entry.get("fileid") or entry.get("file_id") or "").strip()
                    if not file_id:
                        continue
                    try:
                        status_map[file_id] = int(entry.get("status", -1))
                    except Exception:
                        status_map[file_id] = -1

            for file_id in env_file_ids:
                status = status_map.get(file_id)
                # If API omits per-file status, treat as success when request itself succeeded.
                if status is None or status == 0:
                    deleted_ids.append(file_id)
                else:
                    failed_ids.append(file_id)
        except Exception as exc:
            logger.warning("cloud file delete failed(env=%s): %s", env_name, exc)
            failed_ids.extend(env_file_ids)

    return {"deleted_ids": deleted_ids, "failed_ids": failed_ids}


def _guess_suffix(source: str) -> str:
    parsed = urlparse(source)
    path = parsed.path or ""
    suffix = Path(path).suffix
    if suffix and len(suffix) <= 8:
        return suffix
    return ".bin"


def _download_to_temp(url: str) -> str:
    suffix = _guess_suffix(url)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="wechat_media_")
    temp_path = temp_file.name
    temp_file.close()

    response = _http_request(
        "GET",
        url,
        stream=True,
        timeout=_env_int("WECHAT_MEDIA_DOWNLOAD_TIMEOUT_SEC", 20),
    )
    response.raise_for_status()

    with open(temp_path, "wb") as file_obj:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)

    return temp_path


def _resolve_assets_file_id(file_id: str, field_name: str) -> Optional[str]:
    parsed = urlparse(file_id)

    if parsed.scheme in ("http", "https"):
        asset_path = parsed.path
    else:
        asset_path = file_id

    if not asset_path:
        return None

    if asset_path.startswith("/assets/"):
        relative = asset_path[len("/assets/") :]
    elif asset_path.startswith("assets/"):
        relative = asset_path[len("assets/") :]
    else:
        return None

    base_dir = CORE_IMAGES_DIR.resolve()
    candidate = (base_dir / relative).resolve()

    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"{field_name} has invalid assets path") from exc

    if not candidate.exists():
        raise ValueError(f"{field_name} assets file not found: {candidate}")
    if not candidate.is_file():
        raise ValueError(f"{field_name} assets path is not a file: {candidate}")

    return str(candidate)


def resolve_file_id_to_temp_path(file_id: str, field_name: str) -> str:
    try:
        if file_id.startswith("http://") or file_id.startswith("https://"):
            return _download_to_temp(file_id)

        if file_id.startswith("cloud://"):
            temp_url = _get_cloudbase_download_url(file_id)
            return _download_to_temp(temp_url)
    except requests.RequestException as exc:
        raise ValueError(f"{field_name} download failed: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"{field_name} local write failed: {exc}") from exc

    raise ValueError(f"{field_name} must be cloud://... or http(s) URL")


def resolve_input_file(
    local_path: Optional[str],
    file_url: Optional[str],
    file_id: Optional[str],
    field_name: str,
    *,
    prefer_file_id: bool = True,
) -> ResolvedInputFile:
    if local_path:
        return ResolvedInputFile(
            path=resolve_local_path(local_path, field_name),
            cleanup_path=None,
        )

    normalized_file_id = (file_id or "").strip()
    preferred_file_id_error: Optional[Exception] = None
    # By default, cloud file_id is preferred when both temp URL and file_id are provided.
    # Callers can set prefer_file_id=False to prioritize temp URL and keep cloud:// as fallback.
    if prefer_file_id and normalized_file_id.startswith("cloud://"):
        try:
            temp_path = resolve_file_id_to_temp_path(normalized_file_id, field_name)
            return ResolvedInputFile(path=temp_path, cleanup_path=temp_path)
        except ValueError as exc:
            preferred_file_id_error = exc
            if not file_url:
                raise

    url_error: Optional[Exception] = None
    if file_url:
        try:
            temp_path = resolve_file_id_to_temp_path(file_url, f"{field_name}(url)")
            return ResolvedInputFile(path=temp_path, cleanup_path=temp_path)
        except ValueError as exc:
            url_error = exc
            if not normalized_file_id:
                raise

    if normalized_file_id:
        local_assets_file = _resolve_assets_file_id(normalized_file_id, field_name)
        if local_assets_file:
            return ResolvedInputFile(path=local_assets_file, cleanup_path=None)

        # For cloud:// file_id we already attempted once above to avoid duplicate long retries.
        if normalized_file_id.startswith("cloud://") and preferred_file_id_error is not None:
            if url_error:
                raise url_error
            raise preferred_file_id_error

        temp_path = resolve_file_id_to_temp_path(normalized_file_id, field_name)
        return ResolvedInputFile(path=temp_path, cleanup_path=temp_path)

    if url_error:
        raise url_error
    if preferred_file_id_error:
        raise preferred_file_id_error

    return ResolvedInputFile(path=None, cleanup_path=None)


def resolve_media_paths(payload: AnalyzeRequest) -> ResolvedMediaPaths:
    image = resolve_input_file(
        local_path=payload.resolved_image_local_path(),
        file_url=payload.resolved_image_url(),
        file_id=payload.resolved_image_file_id(),
        field_name="image_path/image_url/image_file_id",
    )
    audio = resolve_input_file(
        local_path=payload.resolved_audio_local_path(),
        file_url=payload.resolved_audio_url(),
        file_id=payload.resolved_audio_file_id(),
        field_name="audio_path/audio_url/audio_file_id",
    )

    cleanup_paths = [path for path in [image.cleanup_path, audio.cleanup_path] if path]
    return ResolvedMediaPaths(image_path=image.path, audio_path=audio.path, cleanup_paths=cleanup_paths)
