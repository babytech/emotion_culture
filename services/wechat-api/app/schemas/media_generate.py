from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.analyze import ClientMeta, MediaInput


class MediaGenerateStyle(str, Enum):
    TECH = "tech"
    GUOCHAO = "guochao"


class MediaGenerateTaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MediaGenerateRequest(BaseModel):
    request_token: Optional[str] = Field(
        default=None,
        description="Client generated idempotency token.",
    )
    analysis_request_id: Optional[str] = Field(
        default=None,
        description="Optional analysis request id for traceability.",
    )
    style: MediaGenerateStyle
    prompt: Optional[str] = Field(default=None, max_length=400)
    consent_confirmed: bool = Field(
        default=False,
        description="Must be true when user explicitly confirms selfie usage authorization.",
    )
    consent_version: Optional[str] = Field(
        default=None,
        description="Optional consent copy/version identifier for audit.",
    )
    source_image: Optional[MediaInput] = None
    source_image_url: Optional[str] = None
    source_image_file_id: Optional[str] = None
    source_image_path: Optional[str] = Field(default=None, description="Local debug path")
    client: Optional[ClientMeta] = None

    @staticmethod
    def _coalesce(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            stripped = value.strip()
            if stripped:
                return stripped
        return None

    def resolved_source_image_url(self) -> Optional[str]:
        return self._coalesce(self.source_image.url if self.source_image else None, self.source_image_url)

    def resolved_source_image_file_id(self) -> Optional[str]:
        return self._coalesce(
            self.source_image.file_id if self.source_image else None,
            self.source_image_file_id,
        )

    def resolved_source_image_local_path(self) -> Optional[str]:
        return self._coalesce(
            self.source_image.local_path if self.source_image else None,
            self.source_image_path,
        )


class MediaGenerateResult(BaseModel):
    generated_image_url: str
    generated_image_file_id: Optional[str] = None
    provider: str
    style: MediaGenerateStyle
    generated_at: str
    prompt: Optional[str] = None
    analysis_request_id: Optional[str] = None


class MediaGenerateCreateResponse(BaseModel):
    task_id: str
    status: MediaGenerateTaskStatus = MediaGenerateTaskStatus.QUEUED
    accepted_at: str
    poll_after_ms: int = 2500
    status_message: Optional[str] = None


class MediaGenerateStatusResponse(BaseModel):
    task_id: str
    status: MediaGenerateTaskStatus
    accepted_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    poll_after_ms: int = 2500
    status_message: Optional[str] = None
    retryable: bool = False
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    queue_wait_ms: Optional[int] = None
    run_elapsed_ms: Optional[int] = None
    total_elapsed_ms: Optional[int] = None
    result: Optional[MediaGenerateResult] = None
