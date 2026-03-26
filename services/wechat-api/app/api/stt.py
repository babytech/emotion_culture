import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.services.tencent_stt_service import recognize_sentence


router = APIRouter()


def _resolve_uploaded_audio(
    audio: UploadFile | None,
    file: UploadFile | None,
    voice: UploadFile | None,
) -> UploadFile | None:
    return audio or file or voice


def _require_gateway_token_if_configured(request: Request) -> None:
    expected = os.getenv("TENCENT_STT_GATEWAY_TOKEN", "").strip()
    if not expected:
        return
    got = (request.headers.get("X-STT-GATEWAY-TOKEN") or "").strip()
    if got != expected:
        raise HTTPException(status_code=401, detail="invalid stt gateway token")


@router.post("/stt/tencent")
async def tencent_stt_gateway(
    request: Request,
    audio: UploadFile | None = File(default=None),
    file: UploadFile | None = File(default=None),
    voice: UploadFile | None = File(default=None),
    # Reserved for compatibility with external form fields, no-op for now.
    engine_model_type: str | None = Form(default=None, alias="engine_model_type"),
) -> dict:
    _ = engine_model_type
    _require_gateway_token_if_configured(request)

    uploaded = _resolve_uploaded_audio(audio, file, voice)
    if uploaded is None:
        raise HTTPException(status_code=400, detail="missing audio file in form-data")

    raw = await uploaded.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty audio file")

    try:
        result = recognize_sentence(
            raw,
            filename=uploaded.filename or "",
            content_type=uploaded.content_type or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"stt config/input invalid: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"tencent stt failed: {exc}") from exc

    return {
        "text": result.text,
        "provider": "tencent_asr",
        "request_id": result.request_id,
        "audio_duration_ms": result.audio_duration_ms,
    }
