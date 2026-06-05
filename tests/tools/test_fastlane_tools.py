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
    assert "error" in payload


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
    assert "error" in payload


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


from tools.fastlane_tools import _mark_posted


def test_mark_posted_updates_both_files():
    fastlane_state.save_slot(
        "2026-05-23", "a",
        content_id="abc", media_url="https://cdn/abc.mp4", chosen_caption="cap",
    )
    payload = json.loads(_mark_posted({
        "content_id": "abc",
        "platforms": ["instagram", "tiktok"],
    }))
    assert payload["ok"] is True
    assert fastlane_state.has_posted("abc") is True
    # Slot status is also flipped (we find the slot by content_id).
    slot = fastlane_state.get_slot("2026-05-23", "a")
    assert slot["status"] == "posted"


def test_mark_posted_without_matching_slot_still_dedups():
    payload = json.loads(_mark_posted({
        "content_id": "no-slot-match",
        "platforms": ["instagram"],
    }))
    assert payload["ok"] is True
    assert fastlane_state.has_posted("no-slot-match") is True


from tools.fastlane_tools import _log_caption_choice, _recent_caption_history


def test_log_caption_choice_appends_record():
    payload = json.loads(_log_caption_choice({
        "content_id": "p123",
        "type": "video-hook",
        "chosen": "## Caption\nhello\n## Hashtags\n#tag",
        "rejected": ["variant 2", "variant 3"],
    }))
    assert payload["ok"] is True
    records = fastlane_state.read_recent_caption_history(limit=5)
    assert len(records) == 1
    assert records[0]["content_id"] == "p123"
    assert records[0]["rejected"] == ["variant 2", "variant 3"]


def test_log_caption_choice_rejects_empty_chosen():
    payload = json.loads(_log_caption_choice({
        "content_id": "p123",
        "type": "video-hook",
        "chosen": "",
        "rejected": [],
    }))
    assert "error" in payload


def test_recent_caption_history_empty_returns_empty_list():
    payload = json.loads(_recent_caption_history({"limit": 5}))
    assert payload["ok"] is True
    assert payload["records"] == []
    assert payload["count"] == 0


def test_recent_caption_history_returns_newest_first():
    for i in range(4):
        fastlane_state.append_caption_history(
            content_id=f"p{i}", type_="video-hook",
            chosen=f"cap{i}", rejected=[],
        )
    payload = json.loads(_recent_caption_history({"limit": 3}))
    assert payload["ok"] is True
    assert payload["count"] == 3
    assert [r["content_id"] for r in payload["records"]] == ["p3", "p2", "p1"]


@pytest.mark.parametrize(
    "name",
    [
        "fastlane_list_unposted",
        "fastlane_save_daily_plan",
        "fastlane_get_daily_plan",
        "fastlane_mark_posted",
        "fastlane_log_caption_choice",
        "fastlane_recent_caption_history",
        "fastlane_save_picker",
        "fastlane_resolve_pick",
    ],
)
def test_tool_registered_under_fastlane_toolset(name):
    entry = registry.get_entry(name)
    assert entry is not None, f"{name} is not registered"
    assert entry.toolset == FASTLANE_TOOLSET
    assert entry.schema.get("name") == name
    assert entry.schema.get("parameters", {}).get("type") == "object"


from tools.fastlane_tools import _save_picker, _resolve_pick


def test_save_picker_persists():
    payload = json.loads(_save_picker({
        "date": "2026-06-05",
        "slot_a": {
            "content_id": "p1",
            "media_url": "https://x/1.mp4",
            "thumbnail_url": "https://x/1.webp",
            "type": "video-hook",
            "variants": [
                "## Caption\nA1\n\n## Hashtags\n#a",
                "## Caption\nA2\n\n## Hashtags\n#a",
                "## Caption\nA3\n\n## Hashtags\n#a",
            ],
        },
        "slot_b": {
            "content_id": "p2",
            "media_url": "https://x/2.mp4",
            "type": "wall-of-text",
            "variants": ["B1", "B2", "B3"],
        },
    }))
    assert payload["ok"] is True
    loaded = fastlane_state.load_picker("2026-06-05")
    assert loaded["slot_a"]["content_id"] == "p1"
    assert loaded["slot_b"]["variants"] == ["B1", "B2", "B3"]


def test_resolve_pick_basic():
    # Seed a picker
    fastlane_state.save_picker(
        "2026-06-05",
        slot_a={
            "content_id": "p1", "media_url": "https://x/1.mp4",
            "thumbnail_url": "https://x/1.webp", "type": "video-hook",
            "variants": [
                "## Caption\nA1\n\n## Hashtags\n#a",
                "## Caption\nA2\n\n## Hashtags\n#a",
                "## Caption\nA3\n\n## Hashtags\n#a",
            ],
        },
        slot_b=None,
    )
    payload = json.loads(_resolve_pick({
        "date": "2026-06-05",
        "slot": "a",
        "variant_index": 2,
    }))
    assert payload["ok"] is True
    assert "A2" in payload["chosen_caption"]
    # Daily plan slot was written
    slot = fastlane_state.get_slot("2026-06-05", "a")
    assert slot is not None
    assert slot["content_id"] == "p1"
    assert "A2" in slot["chosen_caption"]
    # History was appended with the two rejected variants
    history = fastlane_state.read_recent_caption_history(limit=5)
    assert len(history) == 1
    assert history[0]["content_id"] == "p1"
    assert len(history[0]["rejected"]) == 2


def test_resolve_pick_applies_replacements():
    fastlane_state.save_picker(
        "2026-06-05",
        slot_a={
            "content_id": "p1", "media_url": "u", "type": "x",
            "variants": [
                "## Caption\nMeet Hank AI now.\n\n## Hashtags\n#hankai",
                "## Caption\nHank AI is here.\n\n## Hashtags\n#hankai",
            ],
        },
        slot_b=None,
    )
    payload = json.loads(_resolve_pick({
        "date": "2026-06-05",
        "slot": "a",
        "variant_index": 1,
        "replacements": [{"old": "Hank AI", "new": "Hank the Pro"}],
    }))
    assert payload["ok"] is True
    assert "Hank the Pro" in payload["chosen_caption"]
    assert "Hank AI" not in payload["chosen_caption"]


def test_resolve_pick_missing_picker_errors():
    payload = json.loads(_resolve_pick({
        "date": "1999-01-01", "slot": "a", "variant_index": 1,
    }))
    assert "error" in payload


def test_resolve_pick_index_out_of_range_errors():
    fastlane_state.save_picker(
        "2026-06-05",
        slot_a={"content_id": "p1", "media_url": "u", "type": "x", "variants": ["v1", "v2"]},
        slot_b=None,
    )
    payload = json.loads(_resolve_pick({
        "date": "2026-06-05", "slot": "a", "variant_index": 5,
    }))
    assert "error" in payload


def test_resolve_pick_missing_slot_errors():
    fastlane_state.save_picker(
        "2026-06-05",
        slot_a={"content_id": "p1", "media_url": "u", "type": "x", "variants": ["v1"]},
        slot_b=None,
    )
    payload = json.loads(_resolve_pick({
        "date": "2026-06-05", "slot": "b", "variant_index": 1,
    }))
    assert "error" in payload

