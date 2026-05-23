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
