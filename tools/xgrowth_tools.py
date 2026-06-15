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
    """Return a tool_error string if any required key is missing/empty, else None."""
    missing = [k for k in keys if not args.get(k)]
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
