from pydantic import BaseModel, Field

from app.schemas.analyze import ConfidenceLevel, InputMode, ResultCard


class HistoryEmotionBrief(BaseModel):
    code: str
    label: str


class HistoryInternalFields(BaseModel):
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


class HistorySummary(BaseModel):
    history_id: str
    request_id: str
    analyzed_at: str
    input_modes: list[InputMode] = Field(default_factory=list)
    primary_emotion: HistoryEmotionBrief
    secondary_emotions: list[HistoryEmotionBrief] = Field(default_factory=list)
    emotion_overview_summary: str
    trigger_tags: list[str] = Field(default_factory=list)
    poem_response_summary: str
    guochao_name: str
    daily_suggestion_summary: str
    mail_sent: bool = False


class HistoryListResponse(BaseModel):
    items: list[HistorySummary] = Field(default_factory=list)
    total: int = 0


class HistoryDetailResponse(BaseModel):
    summary: HistorySummary
    result_card: ResultCard
    internal_fields: HistoryInternalFields


class DeleteHistoryResponse(BaseModel):
    success: bool
    deleted_count: int = 0
    message: str
