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


def test_append_caption_history_then_read(state_dir):
    fastlane_state.append_caption_history(
        content_id="p1", type_="video-hook",
        chosen="## Caption\nA\n## Hashtags\n#x", rejected=["B", "C"],
    )
    fastlane_state.append_caption_history(
        content_id="p2", type_="wall-of-text",
        chosen="## Caption\nD\n## Hashtags\n#y", rejected=["E", "F"],
    )
    records = fastlane_state.read_recent_caption_history(limit=5)
    assert len(records) == 2
    # Newest-first
    assert records[0]["content_id"] == "p2"
    assert records[1]["content_id"] == "p1"
    assert records[0]["rejected"] == ["E", "F"]


def test_read_recent_caption_history_respects_limit(state_dir):
    for i in range(5):
        fastlane_state.append_caption_history(
            content_id=f"p{i}", type_="video-hook",
            chosen=f"cap{i}", rejected=[],
        )
    records = fastlane_state.read_recent_caption_history(limit=3)
    assert len(records) == 3
    assert [r["content_id"] for r in records] == ["p4", "p3", "p2"]


def test_read_recent_caption_history_missing_file_returns_empty(state_dir):
    assert fastlane_state.read_recent_caption_history(limit=10) == []


def test_read_recent_caption_history_skips_corrupt_lines(state_dir):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "caption_history.jsonl").write_text(
        '{"ts":"2026-01-01T00:00:00Z","content_id":"good","type":"x","chosen":"c","rejected":[]}\n'
        '{not json this line\n'
        '{"ts":"2026-01-02T00:00:00Z","content_id":"also_good","type":"y","chosen":"c","rejected":[]}\n'
    )
    records = fastlane_state.read_recent_caption_history(limit=10)
    assert [r["content_id"] for r in records] == ["also_good", "good"]
