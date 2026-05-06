"""Append a content-log entry. Writes to Airtable when configured, JSONL otherwise.

Tool: ``airtable_log_post``

Without ``AIRTABLE_API_KEY``, ``AIRTABLE_BASE_ID``, and
``AIRTABLE_CONTENT_LOG_TABLE`` set, the tool appends one JSON line per call
to ``{HERMES_HOME}/content_log.jsonl``. Set all three env vars to flip to
Airtable mode — no other code changes needed. The tool always returns
success-shape JSON so callers use the same code path in both modes.

Note on the ``source`` field: Airtable's Content Log uses
``scheduled``/``ad_hoc`` while the publisher service uses
``dropbox_watch``/``ad_hoc``. The agent maps ``dropbox_watch`` →
``scheduled`` when calling this tool.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from hermes_constants import get_hermes_home
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

JSONL_FILENAME = "content_log.jsonl"
AIRTABLE_API_BASE = "https://api.airtable.com/v0"
AIRTABLE_TIMEOUT = 15.0

_CONTENT_TYPES = ["video", "static", "carousel"]
_SOURCES = ["scheduled", "ad_hoc"]
_STATUSES = ["pending_approval", "queued", "published", "failed", "rejected"]


def _airtable_configured() -> bool:
    return bool(
        os.getenv("AIRTABLE_API_KEY")
        and os.getenv("AIRTABLE_BASE_ID")
        and os.getenv("AIRTABLE_CONTENT_LOG_TABLE")
    )


def check_requirements() -> bool:
    """Always available — JSONL fallback works without any env vars."""
    return True


SCHEMA = {
    "name": "airtable_log_post",
    "description": (
        "Log a publisher post to the Content Log. Writes to Airtable when "
        "AIRTABLE_API_KEY/BASE_ID/CONTENT_LOG_TABLE are set, otherwise appends "
        "to a local JSONL file. Use after every publisher_queue_post or "
        "publisher_publish_post so the activity log stays complete. Map "
        "publisher source 'dropbox_watch' to 'scheduled' when logging."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "post_id": {"type": "string"},
            "content_type": {"type": "string", "enum": _CONTENT_TYPES},
            "source": {"type": "string", "enum": _SOURCES},
            "status": {"type": "string", "enum": _STATUSES},
            "caption": {"type": "string"},
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target platforms (subset of instagram/tiktok/youtube_shorts).",
            },
            "dropbox_path": {"type": "string"},
            "confidence_score": {
                "type": "number",
                "description": "Caption confidence (0-1).",
            },
            "created_at": {
                "type": "string",
                "description": "ISO 8601 timestamp. Defaults to now if omitted.",
            },
            "published_at": {
                "type": "string",
                "description": "ISO 8601 timestamp. Omit if not yet published.",
            },
            "notes": {"type": "string"},
        },
        "required": ["post_id", "content_type", "source", "status"],
    },
}


def _build_record(args: dict) -> dict[str, Any]:
    record: dict[str, Any] = {
        "post_id": args["post_id"],
        "content_type": args["content_type"],
        "source": args["source"],
        "status": args["status"],
    }
    for optional in ("caption", "dropbox_path", "notes"):
        value = args.get(optional)
        if value:
            record[optional] = value

    platforms = args.get("platforms")
    if platforms:
        record["platforms"] = list(platforms)

    confidence = args.get("confidence_score")
    if confidence is not None:
        try:
            record["confidence_score"] = float(confidence)
        except (TypeError, ValueError):
            pass

    record["created_at"] = (
        args.get("created_at") or datetime.now(tz=timezone.utc).isoformat()
    )
    if args.get("published_at"):
        record["published_at"] = args["published_at"]
    return record


def _validate_required(args: dict) -> str | None:
    for field in ("post_id", "content_type", "source", "status"):
        if not args.get(field):
            return tool_error(f"'{field}' is required")
    if args["content_type"] not in _CONTENT_TYPES:
        return tool_error(
            f"invalid content_type: {args['content_type']}", allowed=_CONTENT_TYPES
        )
    if args["source"] not in _SOURCES:
        return tool_error(f"invalid source: {args['source']}", allowed=_SOURCES)
    if args["status"] not in _STATUSES:
        return tool_error(f"invalid status: {args['status']}", allowed=_STATUSES)
    return None


def _append_jsonl(record: dict) -> str:
    path = get_hermes_home() / JSONL_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        return tool_error(f"failed to append to {path}: {e}")
    return tool_result(success=True, mode="jsonl", path=str(path))


def _post_airtable(record: dict) -> str:
    api_key = os.environ["AIRTABLE_API_KEY"]
    base_id = os.environ["AIRTABLE_BASE_ID"]
    table = os.environ["AIRTABLE_CONTENT_LOG_TABLE"]
    url = f"{AIRTABLE_API_BASE}/{base_id}/{table}"
    payload = {"fields": record}
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=AIRTABLE_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return tool_error(f"airtable request failed: {e}")
    if not response.is_success:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        return tool_error(
            f"airtable returned {response.status_code}",
            status=response.status_code,
            body=body,
        )
    try:
        data = response.json()
    except ValueError:
        data = {}
    return tool_result(
        success=True, mode="airtable", airtable_record_id=data.get("id")
    )


def _airtable_log_post(args: dict, **_kw: Any) -> str:
    err = _validate_required(args)
    if err:
        return err
    record = _build_record(args)
    if _airtable_configured():
        return _post_airtable(record)
    return _append_jsonl(record)


registry.register(
    name="airtable_log_post",
    toolset="airtable",
    schema=SCHEMA,
    handler=lambda args, **kw: _airtable_log_post(args, **kw),
    check_fn=check_requirements,
    requires_env=[],
)
