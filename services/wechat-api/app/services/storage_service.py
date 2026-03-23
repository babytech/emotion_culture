import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from app.schemas.analyze import AnalyzeRequest


API_ROOT = Path(__file__).resolve().parents[2]
CORE_IMAGES_DIR = Path(__file__).resolve().parents[1] / "core" / "images"
WECHAT_API_BASE = "https://api.weixin.qq.com"

_TOKEN_CACHE: dict[str, Optional[object]] = {"token": None, "expires_at": None}


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


def _http_request(method: str, url: str, *, timeout: int, **kwargs) -> requests.Response:
    trust_env = _env_truthy("WECHAT_REQUESTS_TRUST_ENV", "0")
    verify_ssl = not _env_truthy("WECHAT_DISABLE_SSL_VERIFY", "0")

    with requests.Session() as session:
        session.trust_env = trust_env
        try:
            return session.request(
                method=method,
                url=url,
                timeout=timeout,
                verify=verify_ssl,
                **kwargs,
            )
        except requests.exceptions.SSLError as exc:
            raise ValueError(
                "wechat api ssl verify failed. "
                "check outbound proxy/certificate chain; "
                "for emergency only, set WECHAT_DISABLE_SSL_VERIFY=1"
            ) from exc


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
        timeout=15,
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
        timeout=20,
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

    response = _http_request("GET", url, stream=True, timeout=30)
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
    file_id: Optional[str],
    field_name: str,
) -> ResolvedInputFile:
    if local_path:
        return ResolvedInputFile(
            path=resolve_local_path(local_path, field_name),
            cleanup_path=None,
        )

    if file_id:
        local_assets_file = _resolve_assets_file_id(file_id, field_name)
        if local_assets_file:
            return ResolvedInputFile(path=local_assets_file, cleanup_path=None)

        temp_path = resolve_file_id_to_temp_path(file_id, field_name)
        return ResolvedInputFile(path=temp_path, cleanup_path=temp_path)

    return ResolvedInputFile(path=None, cleanup_path=None)


def resolve_media_paths(payload: AnalyzeRequest) -> ResolvedMediaPaths:
    image = resolve_input_file(
        local_path=payload.image_path,
        file_id=payload.image_file_id,
        field_name="image_path/image_file_id",
    )
    audio = resolve_input_file(
        local_path=payload.audio_path,
        file_id=payload.audio_file_id,
        field_name="audio_path/audio_file_id",
    )

    cleanup_paths = [path for path in [image.cleanup_path, audio.cleanup_path] if path]
    return ResolvedMediaPaths(image_path=image.path, audio_path=audio.path, cleanup_paths=cleanup_paths)
