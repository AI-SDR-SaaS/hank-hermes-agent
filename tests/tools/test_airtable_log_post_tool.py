"""Smoke tests for airtable_log_post.

Confirm: tool registered, validation fails closed on missing required fields,
JSONL fallback writes when AIRTABLE_* env vars are unset, Airtable mode sends
the right payload when env vars are set.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools import airtable_log_post_tool as mod
from tools.airtable_log_post_tool import _airtable_log_post
from tools.registry import registry


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_tool_registered():
    entry = registry.get_entry("airtable_log_post")
    assert entry is not None
    assert entry.toolset == "airtable"
    assert entry.schema["name"] == "airtable_log_post"


def test_always_available_check():
    assert mod.check_requirements() is True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


REQUIRED_OK = {
    "post_id": "post_1",
    "content_type": "video",
    "source": "scheduled",
    "status": "queued",
}


@pytest.mark.parametrize("missing", ["post_id", "content_type", "source", "status"])
def test_required_fields_enforced(missing, monkeypatch):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    monkeypatch.delenv("AIRTABLE_CONTENT_LOG_TABLE", raising=False)
    args = {**REQUIRED_OK}
    args.pop(missing)
    result = json.loads(_airtable_log_post(args))
    assert "error" in result
    assert missing in result["error"]


def test_invalid_content_type_rejected():
    args = {**REQUIRED_OK, "content_type": "bogus"}
    result = json.loads(_airtable_log_post(args))
    assert "error" in result


def test_invalid_source_rejected():
    args = {**REQUIRED_OK, "source": "bogus"}
    result = json.loads(_airtable_log_post(args))
    assert "error" in result


def test_invalid_status_rejected():
    args = {**REQUIRED_OK, "status": "bogus"}
    result = json.loads(_airtable_log_post(args))
    assert "error" in result


# ---------------------------------------------------------------------------
# JSONL fallback
# ---------------------------------------------------------------------------


def test_jsonl_fallback_when_airtable_env_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    monkeypatch.delenv("AIRTABLE_CONTENT_LOG_TABLE", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    args = {
        **REQUIRED_OK,
        "caption": "test caption",
        "platforms": ["instagram", "tiktok"],
        "confidence_score": 0.85,
        "dropbox_path": "/content/videos/abc.mp4",
    }
    result = json.loads(_airtable_log_post(args))
    assert result["success"] is True
    assert result["mode"] == "jsonl"

    log_path = tmp_path / mod.JSONL_FILENAME
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["post_id"] == "post_1"
    assert record["caption"] == "test caption"
    assert record["platforms"] == ["instagram", "tiktok"]
    assert record["confidence_score"] == 0.85
    assert record["dropbox_path"] == "/content/videos/abc.mp4"
    assert "created_at" in record  # auto-filled


def test_jsonl_fallback_appends_multiple_lines(monkeypatch, tmp_path):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    _airtable_log_post({**REQUIRED_OK, "post_id": "p1"})
    _airtable_log_post({**REQUIRED_OK, "post_id": "p2"})

    log_path = tmp_path / mod.JSONL_FILENAME
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["post_id"] == "p1"
    assert json.loads(lines[1])["post_id"] == "p2"


def test_bad_confidence_score_silently_dropped(monkeypatch, tmp_path):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    args = {**REQUIRED_OK, "confidence_score": "not-a-number"}
    result = json.loads(_airtable_log_post(args))
    assert result["success"] is True
    record = json.loads(
        (tmp_path / mod.JSONL_FILENAME).read_text(encoding="utf-8").strip()
    )
    assert "confidence_score" not in record


# ---------------------------------------------------------------------------
# Airtable mode (mocked)
# ---------------------------------------------------------------------------


def _mock_response(status_code=200, json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.is_success = 200 <= status_code < 300
    response.json.return_value = json_body or {"id": "rec_xyz"}
    response.text = json.dumps(json_body or {"id": "rec_xyz"})
    return response


def test_airtable_mode_posts_payload(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key_xxx")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appBASE")
    monkeypatch.setenv("AIRTABLE_CONTENT_LOG_TABLE", "Content Log")

    args = {**REQUIRED_OK, "caption": "hi", "platforms": ["instagram"]}
    with patch("tools.airtable_log_post_tool.httpx.post", return_value=_mock_response()) as mock_post:
        result = json.loads(_airtable_log_post(args))

    assert result["success"] is True
    assert result["mode"] == "airtable"
    assert result["airtable_record_id"] == "rec_xyz"

    call_url = mock_post.call_args.args[0]
    assert call_url == "https://api.airtable.com/v0/appBASE/Content Log"

    headers = mock_post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer key_xxx"

    payload = mock_post.call_args.kwargs["json"]
    fields = payload["fields"]
    assert fields["post_id"] == "post_1"
    assert fields["caption"] == "hi"
    assert fields["platforms"] == ["instagram"]


def test_airtable_mode_surfaces_4xx_error(monkeypatch):
    monkeypatch.setenv("AIRTABLE_API_KEY", "key_xxx")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appBASE")
    monkeypatch.setenv("AIRTABLE_CONTENT_LOG_TABLE", "Content Log")

    error_resp = _mock_response(
        status_code=422, json_body={"error": {"message": "Invalid field"}}
    )
    with patch("tools.airtable_log_post_tool.httpx.post", return_value=error_resp):
        result = json.loads(_airtable_log_post(REQUIRED_OK))

    assert "error" in result
    assert result["status"] == 422
