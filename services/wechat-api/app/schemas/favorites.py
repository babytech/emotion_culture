from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FavoriteType(str, Enum):
    POEM = "poem"
    GUOCHAO = "guochao"


class FavoriteItem(BaseModel):
    favorite_id: str
    favorite_type: FavoriteType
    target_id: str
    title: str
    subtitle: Optional[str] = None
    content_summary: Optional[str] = None
    created_at: str
    updated_at: str


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItem] = Field(default_factory=list)
    total: int = 0


class FavoriteUpsertRequest(BaseModel):
    favorite_type: FavoriteType
    target_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    subtitle: Optional[str] = Field(default=None, max_length=200)
    content_summary: Optional[str] = Field(default=None, max_length=800)
    request_id: Optional[str] = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FavoriteUpsertResponse(BaseModel):
    success: bool
    created: bool
    item: FavoriteItem
    message: str


class FavoriteStatusResponse(BaseModel):
    is_favorited: bool
    item: Optional[FavoriteItem] = None


class FavoriteDeleteResponse(BaseModel):
    success: bool
    deleted_count: int = 0
    message: str
