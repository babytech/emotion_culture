from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.history import HistoryEmotionBrief


class CalendarDaySummary(BaseModel):
    date: date
    has_checkin: bool = False
    analyzed_at: Optional[str] = None
    primary_emotion: Optional[HistoryEmotionBrief] = None
    analyses_count: int = 0
    input_modes: list[str] = Field(default_factory=list)


class CalendarOverviewResponse(BaseModel):
    month: str
    month_start: date
    month_end: date
    total_days: int
    checked_days: int
    checked_today: bool = False
    current_streak: int = 0
    longest_streak: int = 0
    items: list[CalendarDaySummary] = Field(default_factory=list)


class WeeklyEmotionStat(BaseModel):
    code: str
    label: str
    days: int


class WeeklyTriggerStat(BaseModel):
    tag: str
    count: int


class WeeklyDailyDigest(BaseModel):
    date: date
    has_checkin: bool = False
    primary_emotion: Optional[HistoryEmotionBrief] = None
    trigger_tags: list[str] = Field(default_factory=list)
    suggestion_summary: Optional[str] = None
    analyzed_at: Optional[str] = None


class WeeklyReportResponse(BaseModel):
    week_start: date
    week_end: date
    generated_at: str
    total_checkin_days: int = 0
    checked_today: bool = False
    current_streak: int = 0
    dominant_emotions: list[WeeklyEmotionStat] = Field(default_factory=list)
    top_trigger_tags: list[WeeklyTriggerStat] = Field(default_factory=list)
    suggestion_highlights: list[str] = Field(default_factory=list)
    daily_digests: list[WeeklyDailyDigest] = Field(default_factory=list)
    insight: str
    source: str = "generated"
