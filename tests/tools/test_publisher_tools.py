"""Smoke tests for publisher_tools.

Confirm: each tool registers under the publisher toolset, gating fails
closed without env vars, and one happy-path call per tool returns
parseable JSON when the publisher client is mocked.
"""

import json
import os
from unittest.mock import patch

import pytest

from tools import publisher_client, publisher_tools
from tools.publisher_tools import (
    PUBLISHER_TOOLSET,
    _telegram_dm_owner,
    _generate_caption,
    _get_post,
    _ingest_adhoc,
    _list_pending,
    _publish_post,
    _queue_post,
    _quick_post,
    _quick_post_file,
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
        "publisher_quick_post",
        "publisher_quick_post_file",
        "telegram_dm_owner",
    ],
)
def test_tool_registered_under_publisher_toolset(name):
    entry = registry.get_entry(name)
    assert entry is not None, f"{name} is not registered"
    assert entry.toolset == PUBLISHER_TOOLSET
    assert entry.schema.get("name") == name
    assert entry.schema.get("parameters", {}).get("type") == "object"


def test_static_toolset_lists_every_registered_publisher_tool():
    """The static TOOLSETS["publisher"] list must enumerate every tool the
    registry maps to the publisher toolset.

    Agent tool exposure flows through ``resolve_toolset("publisher")``, which
    returns the static list and never consults the registry (because
    "publisher" is a key in the static TOOLSETS dict). If a tool is registered
    under the toolset but missing from the static list, it is invisible to every
    agent — which is how publisher_quick_post / publisher_quick_post_file went
    AWOL despite being registered.
    """
    from toolsets import resolve_toolset

    registered = set(registry.get_tool_names_for_toolset(PUBLISHER_TOOLSET))
    exposed = set(resolve_toolset(PUBLISHER_TOOLSET))
    missing = registered - exposed
    assert not missing, (
        "Tools registered under the publisher toolset but missing from the "
        f"static TOOLSETS['publisher'] list (so never exposed to agents): {sorted(missing)}"
    )


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


# ---------------------------------------------------------------------------
# publisher_quick_post
# ---------------------------------------------------------------------------


def test_quick_post_rejects_missing_required_fields():
    # Missing angle, media_urls, caption.
    result = json.loads(_quick_post({}))
    assert "error" in result


def test_quick_post_rejects_empty_media_urls():
    result = json.loads(
        _quick_post(
            {"angle": "storm", "media_urls": [], "caption": "Body"}
        )
    )
    assert "error" in result


def test_quick_post_happy_path():
    fake = {
        "post_id": "cmp_abc",
        "dropbox_root_path": "/content/ad-hoc/hankai_storm-promo_book-demo-20260510120000-abcd",
        "uploaded_paths": [
            "/content/ad-hoc/hankai_storm-promo_book-demo-20260510120000-abcd/01.jpg",
            "/content/ad-hoc/hankai_storm-promo_book-demo-20260510120000-abcd/02.jpg",
        ],
    }
    args = {
        "angle": "storm-promo",
        "media_urls": [
            "https://api.telegram.org/file/bot.../01.jpg",
            "https://api.telegram.org/file/bot.../02.jpg",
        ],
        "caption": "Storm season is here.",
        "hashtags": ["roofing", "storm"],
        "title": "Storm Promo",
    }
    with patch.object(publisher_tools.publisher_client, "request", return_value=fake) as mock_req:
        result = json.loads(_quick_post(args))

    # Result mirrors the publisher response.
    assert result["post_id"] == "cmp_abc"
    assert result["dropbox_root_path"].endswith("-abcd")
    assert len(result["uploaded_paths"]) == 2

    # Verify the call hit the right endpoint with a sane body.
    mock_req.assert_called_once()
    call_args = mock_req.call_args
    assert call_args.args[0] == "POST"
    assert call_args.args[1] == "/api/ad-hoc/quick-post"
    body = call_args.kwargs["json"]
    assert body["angle"] == "storm-promo"
    assert body["caption"] == "Storm season is here."
    # Defaults from the Pydantic model.
    assert body["brand"] == "hankai"
    assert body["cta"] == "book-demo"


# ---------------------------------------------------------------------------
# publisher_quick_post_file (multipart upload)
# ---------------------------------------------------------------------------


def test_quick_post_file_rejects_missing_required_fields():
    result = json.loads(_quick_post_file({}))
    assert "error" in result


def test_quick_post_file_rejects_empty_media_file_paths():
    result = json.loads(
        _quick_post_file(
            {"angle": "storm", "media_file_paths": [], "caption": "Body"}
        )
    )
    assert "error" in result


def test_quick_post_file_returns_clear_error_on_missing_file(tmp_path, monkeypatch):
    # Point the allowlist at a real existing dir, then ask for a file
    # inside it that doesn't exist. Triggers the "not found" branch
    # (without hitting the security block first).
    monkeypatch.setattr(
        publisher_tools,
        "_ALLOWED_MEDIA_ROOTS",
        (str(tmp_path) + os.sep,),
    )
    result = json.loads(
        _quick_post_file(
            {
                "angle": "storm",
                "media_file_paths": [str(tmp_path / "does-not-exist.jpg")],
                "caption": "Body",
            }
        )
    )
    assert "error" in result
    assert "file not found" in result["error"]


def test_quick_post_file_blocks_paths_outside_allowed_roots(tmp_path):
    # File exists and is readable, but lives outside the allowlist —
    # tool must refuse without reading or uploading. Security regression
    # test for the original P0 (arbitrary local-file exfiltration).
    secret = tmp_path / "fake-soul.md"
    secret.write_bytes(b"sensitive contents that must not ship")
    with patch.object(
        publisher_tools.publisher_client, "request_multipart"
    ) as mock_req:
        result = json.loads(
            _quick_post_file(
                {
                    "angle": "storm",
                    "media_file_paths": [str(secret)],
                    "caption": "Body",
                }
            )
        )
    assert "error" in result
    assert "outside allowed media directory" in result["error"]
    mock_req.assert_not_called()


def test_quick_post_file_happy_path(tmp_path, monkeypatch):
    # Allow tmp_path so the test doesn't have to write under /opt/data/cache/
    # on the test host. os.sep keeps the prefix portable across Linux/Windows.
    monkeypatch.setattr(
        publisher_tools,
        "_ALLOWED_MEDIA_ROOTS",
        (str(tmp_path) + os.sep,),
    )
    f1 = tmp_path / "img1.jpg"
    f2 = tmp_path / "img2.png"
    f1.write_bytes(b"img1-bytes")
    f2.write_bytes(b"img2-bytes")

    fake_response = {
        "post_id": "cmp_abc",
        "dropbox_root_path": "/content/ad-hoc/hankai_storm-promo_book-demo-x",
        "uploaded_paths": [
            "/content/ad-hoc/.../01.jpg",
            "/content/ad-hoc/.../02.png",
        ],
        "publish_outcome": {"kind": "ok", "zernio_post_id": "zern_xyz"},
    }
    args = {
        "angle": "storm-promo",
        "media_file_paths": [str(f1), str(f2)],
        "caption": "Storm season.",
        "hashtags": ["roofing", "storm"],
        "title": "Storm Promo",
        "auto_publish": True,
    }
    with patch.object(
        publisher_tools.publisher_client,
        "request_multipart",
        return_value=fake_response,
    ) as mock_req:
        result = json.loads(_quick_post_file(args))

    assert result["post_id"] == "cmp_abc"
    assert result["publish_outcome"]["kind"] == "ok"

    mock_req.assert_called_once()
    call_kwargs = mock_req.call_args.kwargs
    assert mock_req.call_args.args[0] == "/api/ad-hoc/quick-post-file"
    files = call_kwargs["files"]
    assert len(files) == 2
    assert files[0][0] == "media"
    assert files[0][1][0] == "img1.jpg"
    assert files[0][1][1] == b"img1-bytes"
    assert files[0][1][2] == "image/jpeg"
    assert files[1][1][2] == "image/png"

    data = call_kwargs["data"]
    assert data["angle"] == "storm-promo"
    assert data["caption"] == "Storm season."
    assert data["auto_publish"] == "true"
    assert json.loads(data["hashtags"]) == ["roofing", "storm"]
    assert data["title"] == "Storm Promo"


def test_publisher_client_error_surfaces_as_tool_error():
    err = publisher_client.PublisherClientError(
        500, "publisher down", body={"detail": "boom"}
    )
    with patch.object(publisher_tools.publisher_client, "request", side_effect=err):
        result = json.loads(_publish_post({"post_id": "post_x"}))
    assert "error" in result
    assert result["status"] == 500


# ---------------------------------------------------------------------------
# telegram_dm_owner
# ---------------------------------------------------------------------------


def test_telegram_dm_owner_requires_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_USER_ID", raising=False)
    result = json.loads(_telegram_dm_owner({"message": "hello"}))
    assert "error" in result
    assert "TELEGRAM_OWNER_USER_ID" in result["error"]


def test_telegram_dm_owner_requires_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_USER_ID", "111222333")
    result = json.loads(_telegram_dm_owner({"message": "  "}))
    assert "error" in result


def test_telegram_dm_owner_delegates_to_send_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_USER_ID", "111222333")
    fake_response = json.dumps({"success": True, "platform": "telegram"})

    def fake_send(args, **_kw):
        assert args["target"] == "telegram:111222333"
        assert args["message"] == "queue is backed up"
        assert args["action"] == "send"
        return fake_response

    with patch("tools.send_message_tool.send_message_tool", side_effect=fake_send):
        result = json.loads(_telegram_dm_owner({"message": "queue is backed up"}))
    assert result["success"] is True
