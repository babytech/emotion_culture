from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DashboardSectionResult(BaseModel):
    status: Literal["fulfilled", "rejected"] = "rejected"
    value: Optional[dict[str, Any]] = None
    reason: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    generated_at: str = Field(default="", description="UTC ISO timestamp")
    month: str = Field(default="", description="YYYY-MM")
    date: str = Field(default="", description="YYYY-MM-DD")
    calendar: DashboardSectionResult
    weekly_report: DashboardSectionResult
    history: DashboardSectionResult
    favorites: DashboardSectionResult
    today_history: DashboardSectionResult
    checkin: DashboardSectionResult
