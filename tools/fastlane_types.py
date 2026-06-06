"""Pydantic models for the Fastlane API and fastlane_* tools.

Mirrors the pattern in tools/posthog_types.py. API response shapes are
verified against api.usefastlane.ai/api/v1/content as of 2026-05-23.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Fastlane API response shapes
# ---------------------------------------------------------------------------


class FastlaneContent(BaseModel):
    """One content item from GET /api/v1/content."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    content_id: str = Field(alias="_id")
    creation_time: float = Field(alias="_creationTime")
    files: list[str]
    thumbnail_url: Optional[str] = Field(default=None, alias="thumbnailUrl")
    status: str
    type: str


class FastlanePagination(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cursor: Optional[str] = None
    has_more: bool = Field(default=False, alias="hasMore")


class FastlaneListResponse(BaseModel):
    data: list[FastlaneContent]
    pagination: FastlanePagination


class FastlaneGetResponse(BaseModel):
    data: FastlaneContent


# ---------------------------------------------------------------------------
# State file shapes (persisted to disk under HERMES_HOME/fastlane/)
# ---------------------------------------------------------------------------


SlotName = Literal["a", "b"]
SlotStatus = Literal["pending", "chosen", "posted", "failed"]


class DailyPlanSlot(BaseModel):
    content_id: str
    media_url: str
    chosen_caption: str
    status: SlotStatus = "pending"
    posted_at: Optional[str] = None  # ISO UTC


class DailyPlan(BaseModel):
    date: str  # YYYY-MM-DD in ET
    slot_a: Optional[DailyPlanSlot] = None
    slot_b: Optional[DailyPlanSlot] = None


class PostedRecord(BaseModel):
    content_id: str
    posted_at: str  # ISO UTC
    platforms: list[str]


# ---------------------------------------------------------------------------
# Tool input args
# ---------------------------------------------------------------------------


class ListUnpostedRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class SaveDailyPlanRequest(BaseModel):
    date: str
    slot: SlotName
    content_id: str
    media_url: str
    chosen_caption: str


class GetDailyPlanRequest(BaseModel):
    date: str
    slot: SlotName


class MarkPostedRequest(BaseModel):
    content_id: str
    platforms: list[str] = Field(default_factory=lambda: ["instagram", "tiktok"])


class CaptionHistoryRecord(BaseModel):
    ts: str  # ISO UTC
    content_id: str
    type: str
    chosen: str
    rejected: list[str]


class LogCaptionChoiceRequest(BaseModel):
    content_id: str
    type: str
    chosen: str = Field(min_length=1)
    rejected: list[str] = Field(default_factory=list)


class RecentCaptionHistoryRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class PickerSlot(BaseModel):
    content_id: str
    media_url: str
    thumbnail_url: Optional[str] = None
    type: str
    variants: list[str] = Field(min_length=1)


class DailyPicker(BaseModel):
    date: str
    created_at: str
    slot_a: Optional[PickerSlot] = None
    slot_b: Optional[PickerSlot] = None


class SavePickerRequest(BaseModel):
    date: str
    slot_a: Optional[PickerSlot] = None
    slot_b: Optional[PickerSlot] = None


class TextReplacement(BaseModel):
    old: str
    new: str


class ResolvePickRequest(BaseModel):
    date: str
    slot: Literal["a", "b"]
    variant_index: int = Field(ge=1, le=10)
    replacements: list[TextReplacement] = Field(default_factory=list)
