# xgrowth Hermes Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `tools/xgrowth_tools.py` toolset that lets a Hermes agent drive the `AI-SDR-SaaS/xgrowth` X content engine over its REST API, then scaffold the xgrowth agent (Jonathan's personal @jonathan_sherm growth operator) on a new Railway service.

**Architecture:** Engine code mirrors the existing `publisher_tools.py`/`publisher_client.py` pattern: a thin `xgrowth_client.py` (httpx + bearer auth + tenacity retries, env-gated) and `xgrowth_tools.py` (schemas + handlers + top-level `registry.register` calls, auto-discovered by `tools/registry.py`). A new `xgrowth` entry in `toolsets.py`. Then the proven per-agent deploy recipe (bot + Railway service + volume + persona + Tailscale dashboard).

**Tech Stack:** Python, httpx, tenacity, pytest, FastAPI platform (remote), Hermes engine (this repo), Railway, Tailscale.

**Spec:** `docs/superpowers/specs/2026-06-15-xgrowth-agent-design.md`

---

## File structure

- Create: `tools/xgrowth_client.py` — HTTP client (auth, retries, env gate). Helper module, no `registry.register`.
- Create: `tools/xgrowth_tools.py` — schemas + handlers + registrations. Auto-discovered.
- Modify: `toolsets.py` — add the `"xgrowth"` toolset entry to the `TOOLSETS` dict.
- Create: `tests/tools/test_xgrowth_tools.py` — registration, gating, validation, happy-path (client mocked).

Env contract (gates the toolset): `XGROWTH_API_BASE`, `XGROWTH_API_KEY`. Agent key scopes: `generate, queue, post, radar, reporting`.

---

## Task 1: xgrowth HTTP client

**Files:**
- Create: `tools/xgrowth_client.py`
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Write the failing test** (create the test file)

```python
import json
import os
from unittest.mock import patch

import pytest

from tools import xgrowth_client


def test_check_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("XGROWTH_API_BASE", raising=False)
    monkeypatch.delenv("XGROWTH_API_KEY", raising=False)
    assert xgrowth_client.check_xgrowth_requirements() is False


def test_check_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("XGROWTH_API_BASE", "https://xgrowth.example.com")
    monkeypatch.setenv("XGROWTH_API_KEY", "k")
    assert xgrowth_client.check_xgrowth_requirements() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_xgrowth_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.xgrowth_client'`

- [ ] **Step 3: Write `tools/xgrowth_client.py`** (mirror of `publisher_client.py`, no multipart)

```python
"""Shared HTTP client for the xgrowth platform.

Sync httpx.Client with bearer auth, tenacity retries on transient errors
(connect/read timeouts, 5xx). Used by every tool in ``xgrowth_tools.py``.
Helper module — no ``registry.register()`` calls here.
"""

import logging
import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=15.0, pool=5.0)


class XgrowthClientError(Exception):
    """Raised for non-2xx responses (after retry budget) or unparseable bodies."""

    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": str(self), "body": self.body}


class _RetryableHTTPError(Exception):
    """Internal — raised on transient HTTP failure to trigger a tenacity retry."""


_TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)
_RETRYABLE = _TRANSIENT_NETWORK_ERRORS + (_RetryableHTTPError,)


def check_xgrowth_requirements() -> bool:
    """True when both required env vars are set — gates the xgrowth toolset."""
    return bool(os.getenv("XGROWTH_API_BASE") and os.getenv("XGROWTH_API_KEY"))


def _build_client() -> httpx.Client:
    base_url = os.getenv("XGROWTH_API_BASE", "").rstrip("/")
    api_key = os.getenv("XGROWTH_API_KEY", "")
    return httpx.Client(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=DEFAULT_TIMEOUT,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type(_RETRYABLE),
)
def _request_once(method: str, path: str, *, json: dict | None = None,
                  params: dict | None = None) -> dict:
    with _build_client() as client:
        response = client.request(method, path, json=json, params=params)

    if 500 <= response.status_code < 600:
        raise _RetryableHTTPError(f"xgrowth {method} {path} -> {response.status_code}")

    if not response.is_success:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text[:500]
        raise XgrowthClientError(
            response.status_code,
            f"xgrowth {method} {path} -> {response.status_code}",
            body=body,
        )

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as e:
        raise XgrowthClientError(
            response.status_code, f"xgrowth returned invalid JSON: {e}"
        ) from e


def request(method: str, path: str, *, json: dict | None = None,
            params: dict | None = None) -> dict:
    """Call xgrowth and return parsed JSON. Retries transient errors/5xx."""
    logger.debug("xgrowth %s %s", method, path)
    try:
        return _request_once(method, path, json=json, params=params)
    except _RetryableHTTPError as e:
        raise XgrowthClientError(503, f"xgrowth unavailable: {e}") from e
    except _TRANSIENT_NETWORK_ERRORS as e:
        raise XgrowthClientError(0, f"xgrowth network error: {e}") from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_xgrowth_tools.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/xgrowth_client.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): HTTP client with bearer auth + env gating"
```

---

## Task 2: Tool module skeleton + shared helpers

**Files:**
- Create: `tools/xgrowth_tools.py`
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Add the failing test** (append)

```python
from tools import xgrowth_tools  # noqa: E402
from tools.xgrowth_tools import XGROWTH_TOOLSET  # noqa: E402


def test_toolset_constant():
    assert XGROWTH_TOOLSET == "xgrowth"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/tools/test_xgrowth_tools.py::test_toolset_constant -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.xgrowth_tools'`

- [ ] **Step 3: Create `tools/xgrowth_tools.py` with helpers + a DRY register helper**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/tools/test_xgrowth_tools.py::test_toolset_constant -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/xgrowth_tools.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): tool module skeleton + shared call/register helpers"
```

---

## Task 3: Radar + generate tools

**Files:**
- Modify: `tools/xgrowth_tools.py`
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Append tests**

```python
def test_generate_rejects_missing_niche():
    result = json.loads(xgrowth_tools._generate({"topic": "x"}))
    assert "error" in result


def test_generate_happy_path():
    fake = {"id": "d1", "parts": ["hi"], "score": 82, "status": "generated"}
    args = {"niche": "alex_finn", "topic": "missed calls", "kind": "single"}
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value=fake) as m:
        result = json.loads(xgrowth_tools._generate(args))
    assert result["id"] == "d1"
    method, path = m.call_args.args[:2]
    assert (method, path) == ("POST", "/api/generate")
    assert m.call_args.kwargs["json"]["kind"] == "single"


def test_radar_feed_happy_path():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"feed": []}) as m:
        json.loads(xgrowth_tools._radar_feed({}))
    assert m.call_args.args[:2] == ("GET", "/api/radar/feed")
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "generate or radar_feed" -v`
Expected: FAIL (`_generate`/`_radar_feed` not defined)

- [ ] **Step 3: Append radar + generate tools to `tools/xgrowth_tools.py`**

```python
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "generate or radar_feed" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/xgrowth_tools.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): radar + generate tools"
```

---

## Task 4: Queue tools

**Files:**
- Modify: `tools/xgrowth_tools.py`
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Append tests**

```python
def test_edit_draft_requires_id_and_parts():
    assert "error" in json.loads(xgrowth_tools._edit_draft({"draft_id": "d1"}))
    assert "error" in json.loads(xgrowth_tools._edit_draft({"parts": ["x"]}))


def test_approve_draft_path():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._approve_draft({"draft_id": "abc"}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/abc/approve")


def test_schedule_draft_sends_when_epoch():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._schedule_draft({"draft_id": "d1", "when_epoch": 1812345678}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/d1/schedule")
    assert m.call_args.kwargs["json"] == {"when_epoch": 1812345678}
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "draft" -v`
Expected: FAIL

- [ ] **Step 3: Append queue tools to `tools/xgrowth_tools.py`**

```python
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
```

Note: `_require(args, "when_epoch")` treats `0` as missing; epoch 0 (1970) is never a valid schedule time, so this is acceptable.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "draft" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/xgrowth_tools.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): queue tools (list/edit/approve/reject/schedule/unschedule/delete)"
```

---

## Task 5: Post tools (dry_run-by-default safety) + reporting tools

**Files:**
- Modify: `tools/xgrowth_tools.py`
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Append tests** (the dry_run default is the critical safety behavior)

```python
def test_post_defaults_to_dry_run_true():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._post({"draft_id": "d1"}))
    body = m.call_args.kwargs["json"]
    assert body["dry_run"] is True   # live-by-default API made safe at the tool boundary


def test_post_live_only_when_explicit_false():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._post({"draft_id": "d1", "dry_run": False}))
    assert m.call_args.kwargs["json"]["dry_run"] is False


def test_post_due_defaults_dry_run_true():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"posted": 0}) as m:
        json.loads(xgrowth_tools._post_due({}))
    assert m.call_args.kwargs["json"]["dry_run"] is True


def test_takedown_path():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._takedown({"draft_id": "d9"}))
    assert m.call_args.args[:2] == ("POST", "/api/post/d9/takedown")


def test_reporting_summary_passes_days_param():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"summary": {}}) as m:
        json.loads(xgrowth_tools._reporting_summary({"days": 7}))
    assert m.call_args.args[:2] == ("GET", "/api/reporting/summary")
    assert m.call_args.kwargs["params"] == {"days": 7}
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "post or takedown or reporting" -v`
Expected: FAIL

- [ ] **Step 3: Append post + reporting tools to `tools/xgrowth_tools.py`**

```python
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
        "dry_run": bool(args.get("dry_run", True)),   # live-by-default API → dry-run-by-default tool
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "post or takedown or reporting" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/xgrowth_tools.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): post tools (dry_run-by-default) + reporting tools"
```

---

## Task 6: Register the xgrowth toolset + full registration test

**Files:**
- Modify: `toolsets.py` (add to the `TOOLSETS` dict, after the `fastlane` entry)
- Test: `tests/tools/test_xgrowth_tools.py`

- [ ] **Step 1: Append the registration + gating tests**

```python
ALL_XGROWTH_TOOLS = [
    "xgrowth_radar_feed", "xgrowth_radar_refresh",
    "xgrowth_generate", "xgrowth_score", "xgrowth_hooks", "xgrowth_list_niches",
    "xgrowth_list_queue", "xgrowth_edit_draft", "xgrowth_approve_draft",
    "xgrowth_reject_draft", "xgrowth_schedule_draft", "xgrowth_unschedule_draft",
    "xgrowth_delete_draft",
    "xgrowth_get_schedule", "xgrowth_post", "xgrowth_post_due", "xgrowth_takedown",
    "xgrowth_reporting_summary", "xgrowth_reporting_drift", "xgrowth_reporting_sync",
    "xgrowth_insights",
]


@pytest.mark.parametrize("name", ALL_XGROWTH_TOOLS)
def test_tool_registered_under_xgrowth_toolset(name):
    from tools.registry import registry
    entry = registry.get_entry(name)
    assert entry is not None, f"{name} not registered"
    assert entry.toolset == "xgrowth"
    assert entry.schema.get("name") == name
    assert entry.schema.get("parameters", {}).get("type") == "object"


def test_xgrowth_toolset_resolves():
    from toolsets import resolve_toolset
    tools = set(resolve_toolset("xgrowth"))
    for name in ALL_XGROWTH_TOOLS:
        assert name in tools, f"{name} missing from resolved xgrowth toolset"
```

- [ ] **Step 2: Run to verify the resolve test fails**

Run: `pytest tests/tools/test_xgrowth_tools.py -k "resolves or registered_under_xgrowth" -v`
Expected: registration tests PASS (auto-discovery already imports the module), `test_xgrowth_toolset_resolves` FAILS (toolset not in `TOOLSETS`)

- [ ] **Step 3: Add the `xgrowth` entry to the `TOOLSETS` dict in `toolsets.py`** (immediately after the `"fastlane": {...},` entry)

```python
    "xgrowth": {
        "description": "xgrowth platform tools — drive the AI-SDR-SaaS/xgrowth X content engine: radar (trends), generate/score/hooks, queue, post (dry-run by default), and reporting. Gated on XGROWTH_API_BASE + XGROWTH_API_KEY.",
        "tools": [
            "xgrowth_radar_feed",
            "xgrowth_radar_refresh",
            "xgrowth_generate",
            "xgrowth_score",
            "xgrowth_hooks",
            "xgrowth_list_niches",
            "xgrowth_list_queue",
            "xgrowth_edit_draft",
            "xgrowth_approve_draft",
            "xgrowth_reject_draft",
            "xgrowth_schedule_draft",
            "xgrowth_unschedule_draft",
            "xgrowth_delete_draft",
            "xgrowth_get_schedule",
            "xgrowth_post",
            "xgrowth_post_due",
            "xgrowth_takedown",
            "xgrowth_reporting_summary",
            "xgrowth_reporting_drift",
            "xgrowth_reporting_sync",
            "xgrowth_insights",
        ],
        "includes": [],
    },
```

- [ ] **Step 4: Run to verify all pass**

Run: `pytest tests/tools/test_xgrowth_tools.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the broader toolset + registry suites for regressions**

Run: `pytest tests/test_toolsets.py tests/tools/ -q`
Expected: PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add toolsets.py tests/tools/test_xgrowth_tools.py
git commit -m "feat(xgrowth): register xgrowth toolset in toolsets.py"
```

---

## Task 7: Open the PR

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feat/xgrowth-agent
gh pr create --title "feat(xgrowth): Hermes tools for the xgrowth X content engine" \
  --body "Adds the xgrowth toolset (radar/generate/queue/post/reporting) driving AI-SDR-SaaS/xgrowth over REST. dry_run defaults to true at the tool boundary (the API is live-by-default). Spec: docs/superpowers/specs/2026-06-15-xgrowth-agent-design.md"
```

- [ ] **Step 2:** Wait for Cubic review + CI, address findings, merge. Merging `kind-generosity`/main triggers the image rebuild used by the new agent service.

---

## Task 8: Deploy the agent (ops — not TDD)

Runs after the engine PR merges and the image rebuilds. Uses the proven per-agent recipe (see Brian in `[[project_hermes_agent_split_architecture]]`).

**Operator prep (Jonathan):**
- [ ] BotFather: create the agent's Telegram bot, grab the token.
- [ ] xgrowth platform: mint a machine key in `XGROWTH_API_KEYS` (merge, don't clobber) with scopes `["generate","queue","post","radar","reporting"]`; note the key + the production base URL.
- [ ] Railway: new service from this repo + volume at `/opt/data` (US East). Set env: `XGROWTH_API_BASE`, `XGROWTH_API_KEY`, the bot token, `TS_AUTHKEY`, `TS_HOSTNAME=<agent>`, `HERMES_DASHBOARD_TUI=1`, basic-auth user/pass/secret, OpenRouter brain. Provide the agent NAME.

**Config + persona (me, via stdin pipe, no rebuild needed for SOUL/AGENTS):**
- [ ] Write `/opt/data/config.yaml`: `model: anthropic/claude-haiku-4.5`, `toolsets: [hermes-cli, xgrowth]`, `skills.disabled` trimming to the X toolkit and **disabling the retired skills** `hank-x-drafter`, `hank-x-publisher`, `hank-x-scheduler`, `hank-x-trend-watcher`, `xurl` + the junk builtins. Validate with the venv python (`yaml.safe_load`).
- [ ] Write `/opt/data/SOUL.md`: the personal @jonathan_sherm founder-voice persona (built from the `hank-x-drafter` voice spec; name from operator).
- [ ] Write `/opt/data/AGENTS.md`: operating rules with the hard safety rules verbatim — **dry_run:true default, score >=70 gate, cadence 8/day·45min, kind=single default, takedown for retraction, human-gated live posting**, plus the radar→generate→score→approve→post loop.
- [ ] `hermes pairing approve telegram <code>` after Jonathan DMs the bot.
- [ ] `railway redeploy --yes` to load config.
- [ ] Verify: `hermes chat -q` answers in persona; `hermes tools list` shows the `xgrowth` toolset enabled; registry check that `xgrowth_post` is available and `check_tool_availability` shows no missing reqs; a `xgrowth_list_niches` call returns the live niches (proves auth + connectivity).

---

## Notes / follow-ups
- Autonomous cron (radar refresh tick, post-due tick) is deferred until Jonathan trusts the loop. When added, also add `xgrowth` to the `cron-default` toolset includes in `toolsets.py` (cron uses its own toolset).
- Media (image/video) and radar watchlist/keyword management are phase 2.
- Update `[[project_xgrowth_agent_design]]` memory when the agent goes live (name, service IDs, deploy URL).
