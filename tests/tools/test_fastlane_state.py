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
