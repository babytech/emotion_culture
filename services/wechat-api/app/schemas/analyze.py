from typing import Optional

from pydantic import BaseModel, Field


class ClientMeta(BaseModel):
    platform: Optional[str] = None
    version: Optional[str] = None


class AnalyzeRequest(BaseModel):
    text: Optional[str] = Field(default=None, max_length=4000)
    image_url: Optional[str] = None
    image_file_id: Optional[str] = None
    audio_url: Optional[str] = None
    audio_file_id: Optional[str] = None
    image_path: Optional[str] = Field(default=None, description="Local debug path")
    audio_path: Optional[str] = Field(default=None, description="Local debug path")
    client: Optional[ClientMeta] = None


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


class AnalyzeResponse(BaseModel):
    request_id: str
    emotion: EmotionResult
    poem: PoemResult
    poet_image_url: Optional[str] = None
    guochao: GuochaoResult
    guochao_image_url: Optional[str] = None
