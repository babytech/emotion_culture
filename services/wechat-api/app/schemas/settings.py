from typing import Optional

from pydantic import BaseModel


class UserSettingsResponse(BaseModel):
    save_history: bool = True
    history_retention_days: int = 180
    updated_at: Optional[str] = None


class UpdateUserSettingsRequest(BaseModel):
    save_history: bool
