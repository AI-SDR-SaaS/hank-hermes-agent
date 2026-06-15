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


def test_approve_draft_path():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._approve_draft({"draft_id": "abc"}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/abc/approve")


def test_schedule_draft_sends_when_epoch():
    with patch.object(xgrowth_tools.xgrowth_client, "request", return_value={"ok": True}) as m:
        json.loads(xgrowth_tools._schedule_draft({"draft_id": "d1", "when_epoch": 1812345678}))
    assert m.call_args.args[:2] == ("POST", "/api/queue/d1/schedule")
    assert m.call_args.kwargs["json"] == {"when_epoch": 1812345678}
