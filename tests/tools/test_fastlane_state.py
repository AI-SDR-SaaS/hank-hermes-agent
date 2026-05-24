"""Tests for tools/fastlane_state.py."""

import json
from pathlib import Path

import pytest

from tools import fastlane_state


@pytest.fixture
def state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # fastlane_state should derive its dir from HERMES_HOME at call time
    return tmp_path / "fastlane"


def test_has_posted_false_when_file_missing(state_dir):
    assert fastlane_state.has_posted("anything") is False


def test_mark_posted_then_has_posted(state_dir):
    fastlane_state.mark_posted("abc123", platforms=["instagram", "tiktok"])
    assert fastlane_state.has_posted("abc123") is True
    assert fastlane_state.has_posted("other") is False


def test_mark_posted_is_idempotent(state_dir):
    fastlane_state.mark_posted("abc123", platforms=["instagram"])
    fastlane_state.mark_posted("abc123", platforms=["tiktok"])
    raw = json.loads((state_dir / "posted.json").read_text())
    # Second call updates the record, not duplicates it.
    assert len(raw) == 1
    assert raw["abc123"]["platforms"] == ["tiktok"]


def test_load_posted_ids_returns_set(state_dir):
    fastlane_state.mark_posted("a", platforms=["instagram"])
    fastlane_state.mark_posted("b", platforms=["instagram"])
    assert fastlane_state.load_posted_ids() == {"a", "b"}


def test_load_posted_ids_corrupt_file_is_empty(state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "posted.json").write_text("{not json")
    assert fastlane_state.load_posted_ids() == set()


def test_get_slot_missing_plan_returns_none(state_dir):
    assert fastlane_state.get_slot("2026-05-23", "a") is None


def test_save_then_get_slot(state_dir):
    fastlane_state.save_slot(
        "2026-05-23",
        "a",
        content_id="abc",
        media_url="https://cdn/x.mp4",
        chosen_caption="hello",
    )
    slot = fastlane_state.get_slot("2026-05-23", "a")
    assert slot is not None
    assert slot["content_id"] == "abc"
    assert slot["status"] == "chosen"
    assert fastlane_state.get_slot("2026-05-23", "b") is None


def test_save_slot_for_new_date_replaces_plan(state_dir):
    fastlane_state.save_slot("2026-05-23", "a", content_id="abc", media_url="u", chosen_caption="c")
    fastlane_state.save_slot("2026-05-24", "a", content_id="def", media_url="u2", chosen_caption="c2")
    # Only one day's plan is kept at a time — saving for a new date REPLACES
    # the file, so any prior-day slots are gone.
    plan = json.loads((state_dir / "daily_plan.json").read_text())
    assert plan["date"] == "2026-05-24"
    assert plan["slot_a"]["content_id"] == "def"


def test_mark_slot_posted(state_dir):
    fastlane_state.save_slot("2026-05-23", "a", content_id="abc", media_url="u", chosen_caption="c")
    fastlane_state.mark_slot_posted("2026-05-23", "a")
    slot = fastlane_state.get_slot("2026-05-23", "a")
    assert slot["status"] == "posted"
    assert slot["posted_at"] is not None


def test_mark_slot_posted_missing_is_no_op(state_dir):
    result = fastlane_state.mark_slot_posted("2026-05-23", "b")
    assert result is None


def test_mark_slot_failed(state_dir):
    fastlane_state.save_slot("2026-05-23", "a", content_id="abc", media_url="u", chosen_caption="c")
    fastlane_state.mark_slot_failed("2026-05-23", "a", error="zernio 400 after retry")
    slot = fastlane_state.get_slot("2026-05-23", "a")
    assert slot["status"] == "failed"
    assert slot["error"] == "zernio 400 after retry"


def test_mark_slot_failed_missing_is_no_op(state_dir):
    result = fastlane_state.mark_slot_failed("2026-05-23", "b", error="nope")
    assert result is None
