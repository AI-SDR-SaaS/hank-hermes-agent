"""xgrowth platform tools — radar, generate, queue, post, reporting.

Registers tools under the ``xgrowth`` toolset, each gated on
XGROWTH_API_BASE + XGROWTH_API_KEY. Thin wrappers over the xgrowth REST API
(see docs/superpowers/specs/2026-06-15-xgrowth-agent-design.md).
"""

import logging
from typing import Any, Callable

from tools import xgrowth_client
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

XGROWTH_TOOLSET = "xgrowth"
_REQUIRES_ENV = ["XGROWTH_API_BASE", "XGROWTH_API_KEY"]


def _client_error(e: xgrowth_client.XgrowthClientError) -> str:
    return tool_error(f"xgrowth request failed: {e}", status=e.status, body=e.body)


def _call(method: str, path: str, *, json: dict | None = None,
          params: dict | None = None) -> str:
    """Run a request and return a tool_result / tool_error JSON string."""
    try:
        body = xgrowth_client.request(method, path, json=json, params=params)
    except xgrowth_client.XgrowthClientError as e:
        return _client_error(e)
    return tool_result(body)


def _require(args: dict, *keys: str) -> str | None:
    """Return a tool_error string if any required key is missing, else None.

    "Missing" means the key is absent, None, or an empty/whitespace string.
    Other falsy values (empty list, 0, False) count as present so required
    non-string fields are not mis-rejected; the API enforces their semantics.
    """
    def _is_missing(k: str) -> bool:
        if k not in args or args[k] is None:
            return True
        v = args[k]
        return isinstance(v, str) and not v.strip()

    missing = [k for k in keys if _is_missing(k)]
    if missing:
        return tool_error(f"missing required argument(s): {', '.join(missing)}")
    return None


def _register(schema: dict, handler: Callable) -> None:
    registry.register(
        name=schema["name"],
        toolset=XGROWTH_TOOLSET,
        schema=schema,
        handler=handler,
        check_fn=xgrowth_client.check_xgrowth_requirements,
        requires_env=_REQUIRES_ENV,
    )


# ----- Radar (scope: radar) -----

RADAR_FEED_SCHEMA = {
    "name": "xgrowth_radar_feed",
    "description": "Get the radar feed: spiking posts and timely topics worth posting about. Call xgrowth_radar_refresh first for fresh data.",
    "parameters": {"type": "object", "properties": {}},
}

def _radar_feed(args: dict, **_kw: Any) -> str:
    return _call("GET", "/api/radar/feed")

RADAR_REFRESH_SCHEMA = {
    "name": "xgrowth_radar_refresh",
    "description": "Refresh the radar (re-scan watched handles/keywords on X). Returns refresh status. Follow with xgrowth_radar_feed.",
    "parameters": {"type": "object", "properties": {}},
}

def _radar_refresh(args: dict, **_kw: Any) -> str:
    return _call("POST", "/api/radar/refresh")

# ----- Generate (scope: generate) -----

GENERATE_SCHEMA = {
    "name": "xgrowth_generate",
    "description": (
        "Generate a draft post for @jonathan_sherm. Returns {id, parts, score, status}. "
        "Auto-saved to the queue. Gate on score (>=70 to publish). Use kind='single' "
        "unless a thread is genuinely wanted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "niche": {"type": "string", "description": "Niche name (call xgrowth_list_niches for valid values, e.g. ai_entrepreneur, alex_finn)."},
            "kind": {"type": "string", "enum": ["single", "thread"], "description": "single = one tweet (default). thread = multi-tweet."},
            "topic": {"type": "string", "description": "What the post is about."},
            "thread_len": {"type": "integer", "description": "Tweets in the thread when kind='thread'."},
            "sponsored": {"type": "boolean"},
        },
        "required": ["niche"],
    },
}

def _generate(args: dict, **_kw: Any) -> str:
    err = _require(args, "niche")
    if err:
        return err
    payload = {"niche": args["niche"], "kind": args.get("kind", "single")}
    for k in ("topic", "thread_len", "sponsored"):
        if k in args:
            payload[k] = args[k]
    return _call("POST", "/api/generate", json=payload)

SCORE_SCHEMA = {
    "name": "xgrowth_score",
    "description": "Score draft text against the algorithm heuristics (>=70 is the publish bar). Returns score + score_detail.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The post text to score."},
            "kind": {"type": "string", "enum": ["single", "thread"]},
        },
        "required": ["text"],
    },
}

def _score(args: dict, **_kw: Any) -> str:
    err = _require(args, "text")
    if err:
        return err
    return _call("POST", "/api/score", json={"text": args["text"], "kind": args.get("kind", "single")})

HOOKS_SCHEMA = {
    "name": "xgrowth_hooks",
    "description": "Generate hook ideas for a niche + topic (to seed a post).",
    "parameters": {
        "type": "object",
        "properties": {
            "niche": {"type": "string"},
            "topic": {"type": "string"},
        },
        "required": ["niche", "topic"],
    },
}

def _hooks(args: dict, **_kw: Any) -> str:
    err = _require(args, "niche", "topic")
    if err:
        return err
    return _call("POST", "/api/hooks", json={"niche": args["niche"], "topic": args["topic"]})

LIST_NICHES_SCHEMA = {
    "name": "xgrowth_list_niches",
    "description": "List valid niche names for xgrowth_generate (e.g. ai_entrepreneur, alex_finn).",
    "parameters": {"type": "object", "properties": {}},
}

def _list_niches(args: dict, **_kw: Any) -> str:
    return _call("GET", "/api/niches")

_register(RADAR_FEED_SCHEMA, _radar_feed)
_register(RADAR_REFRESH_SCHEMA, _radar_refresh)
_register(GENERATE_SCHEMA, _generate)
_register(SCORE_SCHEMA, _score)
_register(HOOKS_SCHEMA, _hooks)
_register(LIST_NICHES_SCHEMA, _list_niches)

# ----- Queue (scope: queue) -----

LIST_QUEUE_SCHEMA = {
    "name": "xgrowth_list_queue",
    "description": "List drafts in the queue. Optional status filter (e.g. generated, approved, scheduled, posted, failed).",
    "parameters": {"type": "object", "properties": {"status": {"type": "string"}}},
}

def _list_queue(args: dict, **_kw: Any) -> str:
    params = {"status": args["status"]} if args.get("status") else None
    return _call("GET", "/api/queue", params=params)

EDIT_DRAFT_SCHEMA = {
    "name": "xgrowth_edit_draft",
    "description": "Edit a draft's tweet parts (and/or poll options) before publishing.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {"type": "string"},
            "parts": {"type": "array", "items": {"type": "string"}, "description": "Tweet text parts (one per tweet)."},
            "poll_options": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["draft_id", "parts"],
    },
}

def _edit_draft(args: dict, **_kw: Any) -> str:
    err = _require(args, "draft_id", "parts")
    if err:
        return err
    payload: dict = {"parts": args["parts"]}
    if "poll_options" in args:
        payload["poll_options"] = args["poll_options"]
    return _call("PATCH", f"/api/queue/{args['draft_id']}", json=payload)

def _make_draft_action(name: str, suffix: str, method: str, desc: str):
    schema = {
        "name": name,
        "description": desc,
        "parameters": {"type": "object", "properties": {"draft_id": {"type": "string"}}, "required": ["draft_id"]},
    }
    def handler(args: dict, **_kw: Any) -> str:
        err = _require(args, "draft_id")
        if err:
            return err
        path = f"/api/queue/{args['draft_id']}" + (f"/{suffix}" if suffix else "")
        return _call(method, path)
    handler.__name__ = "_" + name.replace("xgrowth_", "")
    return schema, handler

APPROVE_SCHEMA, _approve_draft = _make_draft_action(
    "xgrowth_approve_draft", "approve", "POST", "Approve a queued draft (marks it ready to post).")
REJECT_SCHEMA, _reject_draft = _make_draft_action(
    "xgrowth_reject_draft", "reject", "POST", "Reject a queued draft.")
UNSCHEDULE_SCHEMA, _unschedule_draft = _make_draft_action(
    "xgrowth_unschedule_draft", "unschedule", "POST", "Remove a draft's schedule (back to unscheduled).")
DELETE_SCHEMA, _delete_draft = _make_draft_action(
    "xgrowth_delete_draft", "", "DELETE",
    "Delete the draft RECORD. Does NOT remove a live tweet from X (use xgrowth_takedown for that).")

SCHEDULE_DRAFT_SCHEMA = {
    "name": "xgrowth_schedule_draft",
    "description": "Schedule a draft to post at a unix epoch time (seconds). A periodic xgrowth_post_due tick publishes it when due.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {"type": "string"},
            "when_epoch": {"type": "number", "description": "Unix epoch seconds for when to post."},
        },
        "required": ["draft_id", "when_epoch"],
    },
}

def _schedule_draft(args: dict, **_kw: Any) -> str:
    err = _require(args, "draft_id", "when_epoch")
    if err:
        return err
    return _call("POST", f"/api/queue/{args['draft_id']}/schedule", json={"when_epoch": args["when_epoch"]})

_register(LIST_QUEUE_SCHEMA, _list_queue)
_register(EDIT_DRAFT_SCHEMA, _edit_draft)
_register(APPROVE_SCHEMA, _approve_draft)
_register(REJECT_SCHEMA, _reject_draft)
_register(SCHEDULE_DRAFT_SCHEMA, _schedule_draft)
_register(UNSCHEDULE_SCHEMA, _unschedule_draft)
_register(DELETE_SCHEMA, _delete_draft)

# ----- Post (scope: post) -----

GET_SCHEDULE_SCHEMA = {
    "name": "xgrowth_get_schedule",
    "description": "List currently scheduled posts and their times.",
    "parameters": {"type": "object", "properties": {}},
}

def _get_schedule(args: dict, **_kw: Any) -> str:
    return _call("GET", "/api/schedule")

POST_SCHEMA = {
    "name": "xgrowth_post",
    "description": (
        "Publish a draft to X. SAFETY: dry_run defaults to TRUE (simulate only). "
        "Posts a REAL tweet to @jonathan_sherm ONLY when dry_run is explicitly false, "
        "which requires Jonathan's explicit go-ahead. Cadence guard (8/day, 45min apart) "
        "returns 409; set force=true only when Jonathan intends to override."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {"type": "string"},
            "dry_run": {"type": "boolean", "description": "Default true. Set false ONLY on explicit instruction to post live."},
            "force": {"type": "boolean", "description": "Override the cadence guard (409). Default false."},
        },
        "required": ["draft_id"],
    },
}

def _post(args: dict, **_kw: Any) -> str:
    err = _require(args, "draft_id")
    if err:
        return err
    payload = {
        "draft_id": args["draft_id"],
        "dry_run": bool(args.get("dry_run", True)),   # live-by-default API -> dry-run-by-default tool
        "force": bool(args.get("force", False)),
    }
    return _call("POST", "/api/post", json=payload)

POST_DUE_SCHEMA = {
    "name": "xgrowth_post_due",
    "description": "Publish any scheduled drafts whose time is due (periodic tick). dry_run defaults to TRUE; set false only on explicit instruction.",
    "parameters": {"type": "object", "properties": {"dry_run": {"type": "boolean"}}},
}

def _post_due(args: dict, **_kw: Any) -> str:
    return _call("POST", "/api/post-due", json={"dry_run": bool(args.get("dry_run", True))})

TAKEDOWN_SCHEMA = {
    "name": "xgrowth_takedown",
    "description": "Retract a bad LIVE post: deletes the tweet(s) from X for this draft. (xgrowth_delete_draft only removes the record.)",
    "parameters": {"type": "object", "properties": {"draft_id": {"type": "string"}}, "required": ["draft_id"]},
}

def _takedown(args: dict, **_kw: Any) -> str:
    err = _require(args, "draft_id")
    if err:
        return err
    return _call("POST", f"/api/post/{args['draft_id']}/takedown")

# ----- Reporting (scope: reporting) -----

REPORTING_SUMMARY_SCHEMA = {
    "name": "xgrowth_reporting_summary",
    "description": "Analytics summary (engagement, follower growth) over the last N days (default platform setting).",
    "parameters": {"type": "object", "properties": {"days": {"type": "integer"}}},
}

def _reporting_summary(args: dict, **_kw: Any) -> str:
    params = {"days": args["days"]} if args.get("days") is not None else None
    return _call("GET", "/api/reporting/summary", params=params)

REPORTING_DRIFT_SCHEMA = {
    "name": "xgrowth_reporting_drift",
    "description": "Content drift analysis for a niche (how output is trending vs the target voice).",
    "parameters": {"type": "object", "properties": {"niche": {"type": "string"}}, "required": ["niche"]},
}

def _reporting_drift(args: dict, **_kw: Any) -> str:
    err = _require(args, "niche")
    if err:
        return err
    return _call("GET", "/api/reporting/drift", params={"niche": args["niche"]})

REPORTING_SYNC_SCHEMA = {
    "name": "xgrowth_reporting_sync",
    "description": "Pull fresh post metrics from X and record a follower snapshot. Run before reading summaries.",
    "parameters": {"type": "object", "properties": {}},
}

def _reporting_sync(args: dict, **_kw: Any) -> str:
    return _call("POST", "/api/reporting/sync")

INSIGHTS_SCHEMA = {
    "name": "xgrowth_insights",
    "description": "Compute insights about what is driving engagement (feeds back into future generation).",
    "parameters": {"type": "object", "properties": {}},
}

def _insights(args: dict, **_kw: Any) -> str:
    return _call("POST", "/api/insights")

_register(GET_SCHEDULE_SCHEMA, _get_schedule)
_register(POST_SCHEMA, _post)
_register(POST_DUE_SCHEMA, _post_due)
_register(TAKEDOWN_SCHEMA, _takedown)
_register(REPORTING_SUMMARY_SCHEMA, _reporting_summary)
_register(REPORTING_DRIFT_SCHEMA, _reporting_drift)
_register(REPORTING_SYNC_SCHEMA, _reporting_sync)
_register(INSIGHTS_SCHEMA, _insights)
