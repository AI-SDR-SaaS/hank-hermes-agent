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
    return tool_error("invalid arguments", details=e.errors())


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


# ---------------------------------------------------------------------------
# fastlane_mark_posted
# ---------------------------------------------------------------------------

MARK_POSTED_SCHEMA = {
    "name": "fastlane_mark_posted",
    "description": (
        "Record that a Fastlane content_id has been shipped. Adds to the "
        "dedup map (so fastlane_list_unposted never returns it again) and, "
        "if today's plan has a slot with that content_id, flips that slot's "
        "status to 'posted'. Idempotent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string"},
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Platforms posted to. Default ['instagram', 'tiktok'].",
            },
        },
        "required": ["content_id"],
    },
}


def _mark_posted(args: dict, **_kw: Any) -> str:
    try:
        req = t.MarkPostedRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    record = fastlane_state.mark_posted(req.content_id, platforms=req.platforms)
    # Best-effort: find a slot in today's plan that matches and flip its status.
    flipped_slot: str | None = None
    plan = fastlane_state._read_json(fastlane_state._plan_path())
    if isinstance(plan, dict):
        for slot_name in ("a", "b"):
            slot = plan.get(f"slot_{slot_name}")
            if slot and slot.get("content_id") == req.content_id:
                fastlane_state.mark_slot_posted(plan.get("date", ""), slot_name)
                flipped_slot = slot_name
                break
    return tool_result({
        "ok": True,
        "content_id": req.content_id,
        "record": record,
        "flipped_slot": flipped_slot,
    })


registry.register(
    name="fastlane_mark_posted",
    toolset=FASTLANE_TOOLSET,
    schema=MARK_POSTED_SCHEMA,
    handler=lambda args, **kw: _mark_posted(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_log_caption_choice
# ---------------------------------------------------------------------------

LOG_CAPTION_CHOICE_SCHEMA = {
    "name": "fastlane_log_caption_choice",
    "description": (
        "Record Jonathan's caption pick (and the 2 rejected variants) for "
        "in-context learning on future runs. Call this in addition to "
        "fastlane_save_daily_plan whenever he taps a caption variant in "
        "Telegram. Append-only; never overwrites prior entries."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "description": "Fastlane _id."},
            "type": {"type": "string", "description": "Fastlane content type (wall-of-text, green-screen, video-hook, slideshow, remix)."},
            "chosen": {"type": "string", "description": "The full caption markdown Jonathan picked."},
            "rejected": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The 2 caption variants he did NOT pick.",
            },
        },
        "required": ["content_id", "type", "chosen"],
    },
}


def _log_caption_choice(args: dict, **_kw: Any) -> str:
    try:
        req = t.LogCaptionChoiceRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    record = fastlane_state.append_caption_history(
        content_id=req.content_id,
        type_=req.type,
        chosen=req.chosen,
        rejected=req.rejected,
    )
    return tool_result({"ok": True, "record": record})


registry.register(
    name="fastlane_log_caption_choice",
    toolset=FASTLANE_TOOLSET,
    schema=LOG_CAPTION_CHOICE_SCHEMA,
    handler=lambda args, **kw: _log_caption_choice(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_recent_caption_history
# ---------------------------------------------------------------------------

RECENT_CAPTION_HISTORY_SCHEMA = {
    "name": "fastlane_recent_caption_history",
    "description": (
        "Fetch the last N caption picks (chosen + rejected pairs) for "
        "in-context tone learning. Call this at the START of the "
        "fastlane-daily-plan workflow before drafting today's variants — "
        "the returned records show Jonathan's recent taste so future "
        "captions can match what he picks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max records to return, newest-first. 1-100, default 10.",
                "minimum": 1,
                "maximum": 100,
            },
        },
    },
}


def _recent_caption_history(args: dict, **_kw: Any) -> str:
    try:
        req = t.RecentCaptionHistoryRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    records = fastlane_state.read_recent_caption_history(limit=req.limit)
    return tool_result({"ok": True, "records": records, "count": len(records)})


registry.register(
    name="fastlane_recent_caption_history",
    toolset=FASTLANE_TOOLSET,
    schema=RECENT_CAPTION_HISTORY_SCHEMA,
    handler=lambda args, **kw: _recent_caption_history(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_save_picker
# ---------------------------------------------------------------------------

SAVE_PICKER_SCHEMA = {
    "name": "fastlane_save_picker",
    "description": (
        "Persist today's picker (both slots' full caption variants + "
        "content_ids + media_urls) to disk so the chat-mode agent can "
        "resolve Jonathan's 'A2'/'B1' taps later. Call this in the "
        "planning skill RIGHT BEFORE sending the Telegram picker "
        "messages. slot_b may be null if only one unposted item was "
        "available today."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "ET date YYYY-MM-DD."},
            "slot_a": {
                "type": ["object", "null"],
                "description": "Slot A: content_id, media_url, thumbnail_url, type, variants (list of full publisher-format caption markdown).",
            },
            "slot_b": {
                "type": ["object", "null"],
                "description": "Slot B: same shape as slot_a, or null if only one unposted item today.",
            },
        },
        "required": ["date"],
    },
}


def _save_picker(args: dict, **_kw: Any) -> str:
    try:
        req = t.SavePickerRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    record = fastlane_state.save_picker(
        req.date,
        slot_a=req.slot_a.model_dump() if req.slot_a else None,
        slot_b=req.slot_b.model_dump() if req.slot_b else None,
    )
    return tool_result({"ok": True, "record": record})


registry.register(
    name="fastlane_save_picker",
    toolset=FASTLANE_TOOLSET,
    schema=SAVE_PICKER_SCHEMA,
    handler=lambda args, **kw: _save_picker(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)


# ---------------------------------------------------------------------------
# fastlane_resolve_pick
# ---------------------------------------------------------------------------

RESOLVE_PICK_SCHEMA = {
    "name": "fastlane_resolve_pick",
    "description": (
        "Resolve Jonathan's tap on a Telegram caption picker. When he "
        "replies with 'A2' or 'B1 with Hank AI -> Hank the Pro', "
        "the chat-mode agent calls this tool: it loads today's picker "
        "from disk, picks the right variant (1-indexed: A1->1, A2->2, "
        "A3->3), applies any text replacements, then atomically writes "
        "to the daily plan + appends to caption history. Returns the "
        "final resolved caption."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "ET date YYYY-MM-DD."},
            "slot": {"type": "string", "enum": ["a", "b"]},
            "variant_index": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "1-indexed variant Jonathan picked (A1->1, A2->2, A3->3).",
            },
            "replacements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                    },
                    "required": ["old", "new"],
                },
                "description": "Optional text replacements to apply to the chosen variant in order. E.g., [{old: 'Hank AI', new: 'Hank the Pro'}].",
            },
        },
        "required": ["date", "slot", "variant_index"],
    },
}


def _resolve_pick(args: dict, **_kw: Any) -> str:
    try:
        req = t.ResolvePickRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    picker = fastlane_state.load_picker(req.date)
    if not picker:
        return tool_error(f"no picker found for date {req.date}")
    slot = picker.get(f"slot_{req.slot}")
    if not slot:
        return tool_error(f"slot {req.slot} is empty in the {req.date} picker")
    variants = slot.get("variants", [])
    if req.variant_index < 1 or req.variant_index > len(variants):
        return tool_error(
            f"variant_index {req.variant_index} out of range (have {len(variants)} variants in slot {req.slot})"
        )
    chosen = variants[req.variant_index - 1]
    rejected = [v for i, v in enumerate(variants) if i != req.variant_index - 1]
    # Apply text replacements to the chosen variant (in order, not to rejected).
    for r in req.replacements:
        chosen = chosen.replace(r.old, r.new)
    # Atomic-ish: save daily plan slot, then append caption history.
    fastlane_state.save_slot(
        req.date,
        req.slot,
        content_id=slot["content_id"],
        media_url=slot["media_url"],
        chosen_caption=chosen,
    )
    fastlane_state.append_caption_history(
        content_id=slot["content_id"],
        type_=slot.get("type", "unknown"),
        chosen=chosen,
        rejected=rejected,
    )
    return tool_result({
        "ok": True,
        "date": req.date,
        "slot": req.slot,
        "content_id": slot["content_id"],
        "media_url": slot["media_url"],
        "chosen_caption": chosen,
        "rejected_count": len(rejected),
    })


registry.register(
    name="fastlane_resolve_pick",
    toolset=FASTLANE_TOOLSET,
    schema=RESOLVE_PICK_SCHEMA,
    handler=lambda args, **kw: _resolve_pick(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
