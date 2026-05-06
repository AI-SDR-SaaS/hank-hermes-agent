"""Smoke tests for publisher_tools.

Confirm: each tool registers under the publisher toolset, gating fails
closed without env vars, and one happy-path call per tool returns
parseable JSON when the publisher client is mocked.
"""

import json
from unittest.mock import patch

import pytest

from tools import publisher_client, publisher_tools
from tools.publisher_tools import (
    PUBLISHER_TOOLSET,
    _discord_dm_owner,
    _generate_caption,
    _get_post,
    _ingest_adhoc,
    _list_pending,
    _publish_post,
    _queue_post,
)
from tools.registry import registry


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "publisher_generate_caption",
        "publisher_queue_post",
        "publisher_publish_post",
        "publisher_get_post",
        "publisher_list_pending",
        "publisher_ingest_adhoc",
        "discord_dm_owner",
    ],
)
def test_tool_registered_under_publisher_toolset(name):
    entry = registry.get_entry(name)
    assert entry is not None, f"{name} is not registered"
    assert entry.toolset == PUBLISHER_TOOLSET
    assert entry.schema.get("name") == name
    assert entry.schema.get("parameters", {}).get("type") == "object"


# ---------------------------------------------------------------------------
# Toolset gating
# ---------------------------------------------------------------------------


def test_check_publisher_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("PUBLISHER_BASE_URL", raising=False)
    monkeypatch.delenv("PUBLISHER_API_KEY", raising=False)
    assert publisher_client.check_publisher_requirements() is False


def test_check_publisher_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("PUBLISHER_BASE_URL", "https://publisher.example.com")
    monkeypatch.setenv("PUBLISHER_API_KEY", "test-key")
    assert publisher_client.check_publisher_requirements() is True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_generate_caption_rejects_missing_args():
    result = json.loads(_generate_caption({}))
    assert "error" in result


def test_queue_post_rejects_missing_args():
    result = json.loads(_queue_post({"caption": "hi"}))
    assert "error" in result


def test_ingest_adhoc_requires_source_or_path():
    result = json.loads(_ingest_adhoc({"content_type": "video"}))
    assert "error" in result
    assert "source_url" in result["error"] or "dropbox_path" in result["error"]


def test_get_post_requires_post_id():
    result = json.loads(_get_post({}))
    assert "error" in result


def test_list_pending_rejects_invalid_status():
    result = json.loads(_list_pending({"status": "bogus"}))
    assert "error" in result


# ---------------------------------------------------------------------------
# Happy path (publisher_client.request mocked)
# ---------------------------------------------------------------------------


def test_generate_caption_happy_path():
    fake = {
        "caption": "Test caption",
        "hashtags": ["#test"],
        "confidence": 0.92,
    }
    args = {
        "media_path": "/content/videos/abc.mp4",
        "content_type": "video",
        "target_platforms": ["instagram", "tiktok"],
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake) as mock:
        result = json.loads(_generate_caption(args))
    assert result["caption"] == "Test caption"
    assert result["confidence"] == 0.92
    mock.assert_called_once()
    method, path = mock.call_args.args[:2]
    assert method == "POST"
    assert path == "/api/captions/generate"


def test_queue_post_happy_path():
    fake = {
        "post_id": "post_123",
        "status": "pending_approval",
        "discord_message_id": "msg_456",
        "warnings": [],
    }
    args = {
        "dropbox_root_path": "/content/videos/abc.mp4",
        "content_type": "video",
        "caption": "hi",
        "platforms": ["instagram"],
        "require_approval": True,
        "source": "dropbox_watch",
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake):
        result = json.loads(_queue_post(args))
    assert result["post_id"] == "post_123"
    assert result["status"] == "pending_approval"


def test_publish_post_happy_path():
    fake = {
        "post_id": "post_123",
        "zernio_response": {"id": "z_abc"},
        "status": "published",
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake):
        result = json.loads(_publish_post({"post_id": "post_123"}))
    assert result["status"] == "published"


def test_list_pending_accepts_bare_list():
    fake = [
        {
            "id": "post_1",
            "content_type": "video",
            "source": "dropbox_watch",
            "dropbox_root_path": "/content/videos/a.mp4",
            "status": "pending_approval",
            "created_at": "2026-05-06T12:00:00Z",
        }
    ]
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake):
        result = json.loads(_list_pending({}))
    assert result["count"] == 1
    assert result["posts"][0]["id"] == "post_1"


def test_list_pending_accepts_wrapped_list():
    fake = {
        "posts": [
            {
                "id": "post_2",
                "content_type": "carousel",
                "source": "ad_hoc",
                "dropbox_root_path": "/content/ad-hoc/carousels/x",
                "status": "pending_approval",
                "created_at": "2026-05-06T12:00:00Z",
            }
        ]
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake):
        result = json.loads(_list_pending({}))
    assert result["count"] == 1
    assert result["posts"][0]["content_type"] == "carousel"


def test_ingest_adhoc_happy_path():
    fake = {
        "media_path": "/content/ad-hoc/videos/2026-05-06_adhoc_x.mp4",
        "content_type": "video",
        "ready": True,
    }
    args = {
        "content_type": "video",
        "source_url": "https://example.com/clip.mp4",
        "notes": "drop from discord",
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake):
        result = json.loads(_ingest_adhoc(args))
    assert result["ready"] is True
    assert result["media_path"].endswith(".mp4")


def test_publisher_client_error_surfaces_as_tool_error():
    err = publisher_client.PublisherClientError(
        500, "publisher down", body={"detail": "boom"}
    )
    with patch.object(publisher_tools.publisher_client, "request", side_effect=err):
        result = json.loads(_publish_post({"post_id": "post_x"}))
    assert "error" in result
    assert result["status"] == 500


# ---------------------------------------------------------------------------
# discord_dm_owner
# ---------------------------------------------------------------------------


def test_discord_dm_owner_requires_env(monkeypatch):
    monkeypatch.delenv("DISCORD_OWNER_USER_ID", raising=False)
    result = json.loads(_discord_dm_owner({"message": "hello"}))
    assert "error" in result
    assert "DISCORD_OWNER_USER_ID" in result["error"]


def test_discord_dm_owner_requires_message(monkeypatch):
    monkeypatch.setenv("DISCORD_OWNER_USER_ID", "111222333")
    result = json.loads(_discord_dm_owner({"message": "  "}))
    assert "error" in result


def test_discord_dm_owner_delegates_to_send_message(monkeypatch):
    monkeypatch.setenv("DISCORD_OWNER_USER_ID", "111222333")
    fake_response = json.dumps({"success": True, "platform": "discord"})

    def fake_send(args, **_kw):
        assert args["target"] == "discord:111222333"
        assert args["message"] == "queue is backed up"
        assert args["action"] == "send"
        return fake_response

    with patch("tools.send_message_tool.send_message_tool", side_effect=fake_send):
        result = json.loads(_discord_dm_owner({"message": "queue is backed up"}))
    assert result["success"] is True
