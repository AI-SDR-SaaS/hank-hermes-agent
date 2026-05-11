"""Publisher API types — hand-mirrored from the publisher service (TypeScript).

The publisher service owns the contract; this file mirrors it. When the
publisher API shape changes, update this file in the SAME PR — drift between
the two sides is the failure mode this discipline prevents.

Single file by design. Add new request/response models alongside existing
ones rather than splitting into a package — the goal is one place to look
when reconciling with the TS source of truth.

No ``registry.register()`` calls here — this module is a helper imported by
``publisher_tools.py``.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations (mirror TS string-literal unions)
# ---------------------------------------------------------------------------

ContentType = Literal["video", "static", "carousel"]
PostSource = Literal["dropbox_watch", "ad_hoc"]
PostStatus = Literal[
    "pending_approval",
    "queued",
    "published",
    "failed",
    "rejected",
]
Platform = Literal["instagram", "tiktok", "youtube_shorts"]

CONTENT_TYPE_VALUES: list[str] = ["video", "static", "carousel"]
POST_SOURCE_VALUES: list[str] = ["dropbox_watch", "ad_hoc"]
POST_STATUS_VALUES: list[str] = [
    "pending_approval",
    "queued",
    "published",
    "failed",
    "rejected",
]
PLATFORM_VALUES: list[str] = ["instagram", "tiktok", "youtube_shorts"]


# ---------------------------------------------------------------------------
# /api/captions/generate
# ---------------------------------------------------------------------------

class GenerateCaptionRequest(BaseModel):
    media_path: str
    content_type: ContentType
    target_platforms: list[Platform]
    context: str | None = None


class GenerateCaptionResponse(BaseModel):
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    confidence: float


# ---------------------------------------------------------------------------
# /api/posts/queue
# ---------------------------------------------------------------------------

class QueuePostRequest(BaseModel):
    dropbox_root_path: str
    content_type: ContentType
    caption: str
    platforms: list[Platform]
    require_approval: bool
    source: PostSource


class QueuePostResponse(BaseModel):
    post_id: str
    status: PostStatus
    discord_message_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /api/posts/publish
# ---------------------------------------------------------------------------

class PublishPostRequest(BaseModel):
    post_id: str


class PublishPostResponse(BaseModel):
    post_id: str
    zernio_response: dict[str, Any] = Field(default_factory=dict)
    status: Literal["published", "failed"]


# ---------------------------------------------------------------------------
# /api/posts/:id  and  /api/posts?status=...
# ---------------------------------------------------------------------------

class PostEvent(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class Post(BaseModel):
    id: str
    content_type: ContentType
    source: PostSource
    dropbox_root_path: str
    media_paths: list[str] = Field(default_factory=list)
    caption: str | None = None
    platforms: list[Platform] = Field(default_factory=list)
    status: PostStatus
    zernio_post_id: str | None = None
    discord_message_id: str | None = None
    created_at: datetime
    published_at: datetime | None = None
    events: list[PostEvent] = Field(default_factory=list)


class ListPostsResponse(BaseModel):
    posts: list[Post] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /api/ad-hoc/ingest
# ---------------------------------------------------------------------------

class IngestAdHocRequest(BaseModel):
    content_type: ContentType
    source_url: str | None = None
    dropbox_path: str | None = None
    notes: str | None = None


class IngestAdHocResponse(BaseModel):
    media_path: str
    content_type: ContentType
    ready: bool


# ---------------------------------------------------------------------------
# /api/ad-hoc/quick-post
# ---------------------------------------------------------------------------

class QuickPostRequest(BaseModel):
    """One-shot ad-hoc post: agent sends media URLs + caption, publisher
    uploads to Dropbox, writes caption.md, triggers ingest → Telegram
    approval DM. The Dropbox folder gets a unique timestamp+random
    suffix server-side, so identical brand/angle/cta inputs always
    produce distinct posts.

    Validation mirrors the publisher's Zod schema so the agent fails
    fast on bad inputs instead of round-tripping a 400."""

    angle: str = Field(min_length=1, pattern=r"^[^_/\s]+$")
    media_urls: list[str] = Field(min_length=1, max_length=10)
    caption: str = Field(min_length=1)
    # Optional — defaults applied server-side.
    brand: str = Field(default="hankai", pattern=r"^[^_/\s]+$")
    cta: str = Field(default="book-demo", pattern=r"^[^_/\s]+$")
    title: str | None = None
    hashtags: list[str] = Field(default_factory=list)


class QuickPostResponse(BaseModel):
    post_id: str
    dropbox_root_path: str
    uploaded_paths: list[str] = Field(default_factory=list)
