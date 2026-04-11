from typing import Optional

from pydantic import BaseModel, Field


class TodayHistoryEntry(BaseModel):
    month_day: str = Field(default="", description="MM-DD")
    event_year: Optional[str] = Field(default=None, description="Historical event year label")
    headline: str = Field(default="", description="Short headline for the event")
    summary: str = Field(default="", description="Concise factual summary")
    optional_note: Optional[str] = Field(default=None, description="Optional lightweight extension line")
    source_label: str = Field(default="历史资料", description="Display source label")


class TodayHistoryResponse(BaseModel):
    date: str = Field(default="", description="YYYY-MM-DD")
    month_day: str = Field(default="", description="MM-DD")
    available: bool = Field(default=False, description="Whether a displayable entry is available")
    collapsed_default: bool = Field(default=True, description="Whether frontend should default to collapsed")
    status: str = Field(default="empty", description="ok | degraded | empty | filtered")
    status_message: str = Field(default="", description="User-facing status hint")
    cache_hit: bool = Field(default=False, description="Whether cache was used")
    entry: Optional[TodayHistoryEntry] = Field(default=None, description="Structured entry payload")
