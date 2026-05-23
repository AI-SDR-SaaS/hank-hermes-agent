"""Fastlane tools — list unposted, plan slots, mark posted.

Registers four tools under the ``fastlane`` toolset. Gated on
``FASTLANE_API_KEY``. Designed for the planning + publish cron entries
described in docs/superpowers/specs/2026-05-23-fastlane-cron-design.md.
"""

import logging
from typing import Any

from pydantic import ValidationError

from tools import fastlane_client, fastlane_state
from tools import fastlane_types as t
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

FASTLANE_TOOLSET = "fastlane"
_REQUIRES_ENV = ["FASTLANE_API_KEY"]


def _validation_error(e: ValidationError) -> str:
    return tool_error("invalid arguments", ok=False, details=e.errors())


def _client_error(e: fastlane_client.FastlaneClientError) -> str:
    return tool_error(
        f"fastlane request failed: {e}", status=e.status, body=e.body
    )


# ---------------------------------------------------------------------------
# fastlane_list_unposted
# ---------------------------------------------------------------------------

LIST_UNPOSTED_SCHEMA = {
    "name": "fastlane_list_unposted",
    "description": (
        "Return up to ``limit`` Fastlane content items that have NOT yet "
        "been posted via our publisher. Items are oldest-first so the "
        "backlog drains before newer content is served. Each item has: "
        "content_id (stable Fastlane _id), media_url (direct CDN url, "
        ".mp4), thumbnail_url, type (wall-of-text, green-screen, "
        "video-hook, slideshow, remix), and creation_time (epoch ms)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max items to fetch from Fastlane before dedup. 1–100, default 20.",
                "minimum": 1,
                "maximum": 100,
            },
        },
    },
}


def _list_unposted(args: dict, **_kw: Any) -> str:
    try:
        req = t.ListUnpostedRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = fastlane_client.list_content(limit=req.limit)
    except fastlane_client.FastlaneClientError as e:
        return _client_error(e)
    try:
        resp = t.FastlaneListResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from fastlane: {e.errors()}", body=body
        )
    posted = fastlane_state.load_posted_ids()
    candidates = [c for c in resp.data if c.content_id not in posted]
    candidates.sort(key=lambda c: c.creation_time)
    items = [
        {
            "content_id": c.content_id,
            "media_url": c.files[0] if c.files else None,
            "thumbnail_url": c.thumbnail_url,
            "type": c.type,
            "creation_time": c.creation_time,
        }
        for c in candidates
    ]
    return tool_result({"ok": True, "items": items, "count": len(items)})


registry.register(
    name="fastlane_list_unposted",
    toolset=FASTLANE_TOOLSET,
    schema=LIST_UNPOSTED_SCHEMA,
    handler=lambda args, **kw: _list_unposted(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_save_daily_plan
# ---------------------------------------------------------------------------

SAVE_DAILY_PLAN_SCHEMA = {
    "name": "fastlane_save_daily_plan",
    "description": (
        "Persist Jonathan's caption choice for one of today's two post "
        "slots. Call this AFTER he taps a caption variant in Telegram. "
        "The slot is marked status='chosen'; the publish cron will read "
        "it later and ship via publisher_quick_post(auto_publish=true)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "ET date YYYY-MM-DD."},
            "slot": {"type": "string", "enum": ["a", "b"]},
            "content_id": {"type": "string", "description": "Fastlane _id."},
            "media_url": {"type": "string", "description": "Public CDN URL from Fastlane.files[0]."},
            "chosen_caption": {"type": "string", "description": "Full ## Caption + ## Hashtags markdown."},
        },
        "required": ["date", "slot", "content_id", "media_url", "chosen_caption"],
    },
}


def _save_daily_plan(args: dict, **_kw: Any) -> str:
    try:
        req = t.SaveDailyPlanRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    slot = fastlane_state.save_slot(
        req.date,
        req.slot,
        content_id=req.content_id,
        media_url=req.media_url,
        chosen_caption=req.chosen_caption,
    )
    return tool_result({"ok": True, "date": req.date, "slot": req.slot, "record": slot})


registry.register(
    name="fastlane_save_daily_plan",
    toolset=FASTLANE_TOOLSET,
    schema=SAVE_DAILY_PLAN_SCHEMA,
    handler=lambda args, **kw: _save_daily_plan(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_get_daily_plan
# ---------------------------------------------------------------------------

GET_DAILY_PLAN_SCHEMA = {
    "name": "fastlane_get_daily_plan",
    "description": (
        "Read one slot from today's plan. Used by the publish-cron "
        "prompt: if status=='chosen' it ships via publisher_quick_post; "
        "if status=='pending' or no plan exists, the cron silently skips."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "slot": {"type": "string", "enum": ["a", "b"]},
        },
        "required": ["date", "slot"],
    },
}


def _get_daily_plan(args: dict, **_kw: Any) -> str:
    try:
        req = t.GetDailyPlanRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    rec = fastlane_state.get_slot(req.date, req.slot)
    status = rec["status"] if rec else "pending"
    return tool_result({
        "ok": True,
        "date": req.date,
        "slot_name": req.slot,
        "status": status,
        "slot": rec,
    })


registry.register(
    name="fastlane_get_daily_plan",
    toolset=FASTLANE_TOOLSET,
    schema=GET_DAILY_PLAN_SCHEMA,
    handler=lambda args, **kw: _get_daily_plan(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
