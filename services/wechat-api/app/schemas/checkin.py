from typing import Optional

from pydantic import BaseModel, Field


class CheckinDayItem(BaseModel):
    day_index: int
    label: str
    points: int
    state: str


class CheckinStatusResponse(BaseModel):
    today: str
    signed_today: bool
    current_streak: int
    total_signed_days: int
    daily_points: int
    points_balance: int
    cycle_length: int = 12
    cycle_position: int = 0
    last_signed_day: Optional[str] = None
    message: str = ""
    days: list[CheckinDayItem] = Field(default_factory=list)


class CheckinSignResponse(BaseModel):
    just_signed: bool
    awarded_points: int
    status: CheckinStatusResponse
