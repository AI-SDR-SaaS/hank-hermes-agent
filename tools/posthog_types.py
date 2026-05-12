"""PostHog API types — hand-mirrored from PostHog's public REST API.

PostHog owns the contract; this file mirrors only the slices we use. Keep this
file as the single source of truth for what fields the posthog tools read out
of responses, so drift between PostHog and our parsing is easy to spot and fix.

No ``registry.register()`` calls — helper module imported by ``posthog_tools.py``.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# HogQL query — POST /api/projects/{id}/query/
# ---------------------------------------------------------------------------


class HogQLQueryRequest(BaseModel):
    """Wire shape: {"query": {"kind": "HogQLQuery", "query": "<sql>"}}.

    Pydantic-side we expose just the SQL string; the wrapper kind is fixed.
    """

    query: str = Field(min_length=1)


class HogQLQueryResponse(BaseModel):
    """Subset of fields PostHog returns for a sync HogQL query result."""

    results: list[list[Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    hogql: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Session recordings — GET /api/projects/{id}/session_recordings/
# ---------------------------------------------------------------------------

RecordingOrder = Literal[
    "start_time",
    "duration",
    "active_seconds",
    "console_error_count",
    "click_count",
    "keypress_count",
]


class SessionRecording(BaseModel):
    """Subset of session recording fields useful for digest summaries."""

    id: str
    distinct_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: int | None = None
    active_seconds: int | None = None
    click_count: int | None = None
    keypress_count: int | None = None
    console_error_count: int | None = None
    start_url: str | None = None
    person: dict[str, Any] | None = None


class ListRecordingsResponse(BaseModel):
    results: list[SessionRecording] = Field(default_factory=list)
    next: str | None = None


# ---------------------------------------------------------------------------
# Error tracking — GET /api/projects/{id}/error_tracking/issues/
# ---------------------------------------------------------------------------


class ErrorIssue(BaseModel):
    """Subset of error-tracking issue fields."""

    id: str
    name: str | None = None
    description: str | None = None
    status: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    occurrences: int | None = None
    sessions: int | None = None
    users: int | None = None


class ListErrorIssuesResponse(BaseModel):
    results: list[ErrorIssue] = Field(default_factory=list)
    next: str | None = None


# ---------------------------------------------------------------------------
# Feature flags — GET /api/projects/{id}/feature_flags/
# ---------------------------------------------------------------------------


class FeatureFlag(BaseModel):
    """Subset of feature flag fields useful for rollout state checks."""

    id: int
    key: str
    name: str | None = None
    active: bool | None = None
    rollout_percentage: float | None = None
    created_at: datetime | None = None
    created_by: dict[str, Any] | None = None
    filters: dict[str, Any] | None = None


class ListFeatureFlagsResponse(BaseModel):
    results: list[FeatureFlag] = Field(default_factory=list)
    next: str | None = None


# ---------------------------------------------------------------------------
# Dashboards — GET /api/projects/{id}/dashboards/{id}/
# ---------------------------------------------------------------------------


class DashboardTile(BaseModel):
    """One tile inside a dashboard. Keeps just what's useful for a digest."""

    id: int | None = None
    name: str | None = None
    insight: dict[str, Any] | None = None
    last_refresh: datetime | None = None


class Dashboard(BaseModel):
    id: int
    name: str | None = None
    description: str | None = None
    tiles: list[DashboardTile] = Field(default_factory=list)
