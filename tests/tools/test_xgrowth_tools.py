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


from tools import xgrowth_tools  # noqa: E402
from tools.xgrowth_tools import XGROWTH_TOOLSET  # noqa: E402


def test_toolset_constant():
    assert XGROWTH_TOOLSET == "xgrowth"


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


def test_edit_draft_requires_id_and_parts():
    assert "error" in json.loads(xgrowth_tools._edit_draft({"draft_id": "d1"}))
    assert "error" in json.loads(xgrowth_tools._edit_draft({"parts": ["x"]}))


def test_require_allows_falsy_non_string_values():
    # An explicitly-supplied empty list is "present", not "missing" — the API
    # validates its semantics; the tool must not mis-reject it as missing.
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        result = json.loads(xgrowth_tools._edit_draft({"draft_id": "d1", "parts": []}))
    assert "error" not in result
    assert m.call_args.args[:2] == ("PATCH", "/api/queue/d1")
    assert m.call_args.kwargs["json"]["parts"] == []


def test_approve_draft_path():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._approve_draft({"draft_id": "abc"}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/abc/approve")


def test_schedule_draft_sends_when_epoch():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._schedule_draft({"draft_id": "d1", "when_epoch": 1812345678}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/d1/schedule")
    assert m.call_args.kwargs["json"] == {"when_epoch": 1812345678}


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


def test_module_is_auto_discoverable():
    from pathlib import Path
    from tools.registry import _module_registers_tools
    assert _module_registers_tools(Path("tools/xgrowth_tools.py")) is True


def test_post_string_dry_run_stays_safe():
    # a non-boolean dry_run must NOT go live; only literal False does
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._post({"draft_id": "d1", "dry_run": "false"}))
    assert m.call_args.kwargs["json"]["dry_run"] is True


def test_post_force_only_on_literal_true():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._post({"draft_id": "d1", "force": "true"}))
    assert m.call_args.kwargs["json"]["force"] is False


def test_post_read_timeout_not_retried(monkeypatch):
    import httpx
    calls = {"n": 0}

    class _C:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def request(self, *a, **k):
            calls["n"] += 1
            raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(xgrowth_client, "_build_client", lambda: _C())
    with pytest.raises(xgrowth_client.XgrowthClientError):
        xgrowth_client.request("POST", "/api/post", json={"draft_id": "d1"})
    assert calls["n"] == 1  # non-idempotent: no replay


def test_get_read_timeout_is_retried(monkeypatch):
    import httpx
    calls = {"n": 0}

    class _C:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def request(self, *a, **k):
            calls["n"] += 1
            raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(xgrowth_client, "_build_client", lambda: _C())
    with pytest.raises(xgrowth_client.XgrowthClientError):
        xgrowth_client.request("GET", "/api/queue")
    assert calls["n"] == 3  # idempotent: retried to the stop limit


def test_delete_read_timeout_is_retried(monkeypatch):
    import httpx
    calls = {"n": 0}

    class _C:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def request(self, *a, **k):
            calls["n"] += 1
            raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(xgrowth_client, "_build_client", lambda: _C())
    with pytest.raises(xgrowth_client.XgrowthClientError):
        xgrowth_client.request("DELETE", "/api/queue/d1")
    assert calls["n"] == 3  # DELETE is idempotent: retried to the stop limit
