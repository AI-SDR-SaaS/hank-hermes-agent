"""Tests for tools/fastlane_tools.py."""

import json
from unittest.mock import patch

import pytest

from tools import fastlane_client, fastlane_state, fastlane_tools
from tools.fastlane_tools import FASTLANE_TOOLSET, _list_unposted
from tools.registry import registry


@pytest.fixture(autouse=True)
def isolate_state(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    yield


def _api_item(content_id: str, ctime: float, type_: str = "video-hook") -> dict:
    return {
        "_id": content_id,
        "_creationTime": ctime,
        "files": [f"https://cdn/{content_id}.mp4"],
        "thumbnailUrl": f"https://cdn/{content_id}.webp",
        "status": "CREATED",
        "type": type_,
    }


def test_list_unposted_filters_out_posted(monkeypatch):
    monkeypatch.setattr(
        fastlane_client,
        "list_content",
        lambda limit=20, cursor=None: {
            "data": [_api_item("a", 1.0), _api_item("b", 2.0), _api_item("c", 3.0)],
            "pagination": {"cursor": None, "hasMore": False},
        },
    )
    fastlane_state.mark_posted("b", platforms=["instagram"])

    payload = json.loads(_list_unposted({"limit": 20}))
    assert payload["ok"] is True
    ids = [item["content_id"] for item in payload["items"]]
    assert "b" not in ids
    assert set(ids) == {"a", "c"}


def test_list_unposted_returns_oldest_first(monkeypatch):
    monkeypatch.setattr(
        fastlane_client,
        "list_content",
        lambda limit=20, cursor=None: {
            "data": [_api_item("new", 3.0), _api_item("old", 1.0), _api_item("mid", 2.0)],
            "pagination": {"cursor": None, "hasMore": False},
        },
    )
    payload = json.loads(_list_unposted({"limit": 20}))
    ids = [item["content_id"] for item in payload["items"]]
    assert ids == ["old", "mid", "new"]


def test_list_unposted_validates_limit():
    payload = json.loads(_list_unposted({"limit": 0}))
    assert payload["ok"] is False


from tools.fastlane_tools import _save_daily_plan


def test_save_daily_plan_persists():
    payload = json.loads(_save_daily_plan({
        "date": "2026-05-23",
        "slot": "a",
        "content_id": "abc",
        "media_url": "https://cdn/abc.mp4",
        "chosen_caption": "post caption text",
    }))
    assert payload["ok"] is True
    slot = fastlane_state.get_slot("2026-05-23", "a")
    assert slot["chosen_caption"] == "post caption text"
    assert slot["status"] == "chosen"


def test_save_daily_plan_rejects_bad_slot():
    payload = json.loads(_save_daily_plan({
        "date": "2026-05-23",
        "slot": "c",
        "content_id": "x",
        "media_url": "https://cdn/x.mp4",
        "chosen_caption": "hello",
    }))
    assert payload["ok"] is False


from tools.fastlane_tools import _get_daily_plan


def test_get_daily_plan_returns_slot():
    fastlane_state.save_slot(
        "2026-05-23", "b",
        content_id="zzz", media_url="https://cdn/zzz.mp4", chosen_caption="cap",
    )
    payload = json.loads(_get_daily_plan({"date": "2026-05-23", "slot": "b"}))
    assert payload["ok"] is True
    assert payload["status"] == "chosen"
    assert payload["slot"]["content_id"] == "zzz"


def test_get_daily_plan_missing_returns_pending():
    payload = json.loads(_get_daily_plan({"date": "2026-05-23", "slot": "a"}))
    assert payload["ok"] is True
    assert payload["status"] == "pending"
    assert payload["slot"] is None
