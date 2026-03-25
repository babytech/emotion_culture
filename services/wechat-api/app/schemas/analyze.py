from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InputMode(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    SELFIE = "selfie"
    PC_CAMERA = "pc_camera"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClientMeta(BaseModel):
    platform: Optional[str] = None
    version: Optional[str] = None


class MediaInput(BaseModel):
    url: Optional[str] = None
    file_id: Optional[str] = None
    local_path: Optional[str] = Field(default=None, description="Local debug path")


class AnalyzeRequest(BaseModel):
    # New normalized fields.
    input_modes: list[InputMode] = Field(
        default_factory=list,
        description="Input modes used for this request, e.g. text/voice/selfie/pc_camera",
    )
    text: Optional[str] = Field(default=None, max_length=4000)
    image: Optional[MediaInput] = None
    audio: Optional[MediaInput] = None

    # Legacy fields kept for backward compatibility.
    image_url: Optional[str] = None
    image_file_id: Optional[str] = None
    audio_url: Optional[str] = None
    audio_file_id: Optional[str] = None
    image_path: Optional[str] = Field(default=None, description="Local debug path")
    audio_path: Optional[str] = Field(default=None, description="Local debug path")

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

    def resolved_image_url(self) -> Optional[str]:
        return self._coalesce(self.image.url if self.image else None, self.image_url)

    def resolved_image_file_id(self) -> Optional[str]:
        return self._coalesce(self.image.file_id if self.image else None, self.image_file_id)

    def resolved_image_local_path(self) -> Optional[str]:
        return self._coalesce(self.image.local_path if self.image else None, self.image_path)

    def resolved_audio_url(self) -> Optional[str]:
        return self._coalesce(self.audio.url if self.audio else None, self.audio_url)

    def resolved_audio_file_id(self) -> Optional[str]:
        return self._coalesce(self.audio.file_id if self.audio else None, self.audio_file_id)

    def resolved_audio_local_path(self) -> Optional[str]:
        return self._coalesce(self.audio.local_path if self.audio else None, self.audio_path)

    def normalized_input_modes(self) -> list[InputMode]:
        modes: list[InputMode] = []

        def append_mode(mode: InputMode) -> None:
            if mode not in modes:
                modes.append(mode)

        for mode in self.input_modes:
            append_mode(mode)

        if (self.text or "").strip():
            append_mode(InputMode.TEXT)

        has_voice = bool(
            self.resolved_audio_local_path()
            or self.resolved_audio_url()
            or self.resolved_audio_file_id()
        )
        if has_voice:
            append_mode(InputMode.VOICE)

        has_image = bool(
            self.resolved_image_local_path()
            or self.resolved_image_url()
            or self.resolved_image_file_id()
        )
        if has_image and InputMode.SELFIE not in modes and InputMode.PC_CAMERA not in modes:
            append_mode(InputMode.SELFIE)

        return modes


class EmotionSources(BaseModel):
    text: Optional[str] = None
    face: Optional[str] = None
    speech: Optional[str] = None


class EmotionResult(BaseModel):
    code: str
    label: str
    sources: EmotionSources
    weights: dict[str, float]


class PoemResult(BaseModel):
    poet: str
    text: str
    interpretation: str


class GuochaoResult(BaseModel):
    name: str
    comfort: str


class EmotionBrief(BaseModel):
    code: str
    label: str


class ResultCard(BaseModel):
    primary_emotion: EmotionBrief
    secondary_emotions: list[EmotionBrief] = Field(default_factory=list)
    emotion_overview: str
    trigger_tags: list[str] = Field(default_factory=list)
    poem_response: str
    poem_interpretation: str
    guochao_comfort: str
    daily_suggestion: str


class SystemFields(BaseModel):
    request_id: str
    analyzed_at: str
    input_modes: list[InputMode] = Field(default_factory=list)
    primary_emotion_code: str
    secondary_emotion_codes: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel
    trigger_tags: list[str] = Field(default_factory=list)
    poem_id: str
    guochao_id: str
    mail_sent: bool = False
    tts_ready: bool = False
    analysis_text: Optional[str] = None
    speech_transcript: Optional[str] = None
    speech_transcript_provider: Optional[str] = None


class AnalyzeResponse(BaseModel):
    request_id: str
    input_modes: list[InputMode] = Field(default_factory=list)
    result_card: ResultCard
    system_fields: SystemFields

    # Legacy fields kept for existing clients.
    emotion: EmotionResult
    poem: PoemResult
    poet_image_url: Optional[str] = None
    guochao: GuochaoResult
    guochao_image_url: Optional[str] = None
