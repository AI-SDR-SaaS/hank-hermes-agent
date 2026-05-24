"""Tests for tools/fastlane_client.py."""

import httpx
import pytest

from tools import fastlane_client


def test_check_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("FASTLANE_API_KEY", raising=False)
    assert fastlane_client.check_fastlane_requirements() is False


def test_check_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    assert fastlane_client.check_fastlane_requirements() is True


def test_base_url_default(monkeypatch):
    monkeypatch.delenv("FASTLANE_API_BASE", raising=False)
    assert fastlane_client._base_url() == "https://api.usefastlane.ai/api/v1"


def test_base_url_override(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_BASE", "https://api.staging.fastlane/api/v1")
    assert fastlane_client._base_url() == "https://api.staging.fastlane/api/v1"


class _FakeResponse:
    def __init__(self, status: int, body: dict | None = None, text: str = ""):
        self.status_code = status
        self._body = body
        self.text = text
        self.content = b"x" if (body is not None or text) else b""

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def _stub_client(monkeypatch, response: _FakeResponse):
    class _StubHTTPX:
        def __init__(self, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def request(self, method, path, params=None):
            self.last = {"method": method, "path": path, "params": params}
            _stub_client.last = self.last
            return response
    monkeypatch.setattr(fastlane_client, "_build_client", lambda: _StubHTTPX())


def test_list_content_happy_path(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    body = {
        "data": [
            {
                "_id": "abc",
                "_creationTime": 1.0,
                "files": ["https://cdn/x.mp4"],
                "thumbnailUrl": "https://cdn/x.webp",
                "status": "CREATED",
                "type": "wall-of-text",
            }
        ],
        "pagination": {"cursor": "cur1", "hasMore": True},
    }
    _stub_client(monkeypatch, _FakeResponse(200, body))
    result = fastlane_client.list_content(limit=5)
    assert result["data"][0]["_id"] == "abc"
    assert _stub_client.last["path"] == "/content"
    assert _stub_client.last["params"] == {"limit": 5}


def test_list_content_passes_cursor(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    _stub_client(monkeypatch, _FakeResponse(200, {"data": [], "pagination": {}}))
    fastlane_client.list_content(limit=20, cursor="abc123")
    assert _stub_client.last["params"] == {"limit": 20, "cursor": "abc123"}


def test_get_content(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    body = {"data": {"_id": "xyz", "_creationTime": 2.0, "files": [], "status": "CREATED", "type": "video-hook"}}
    _stub_client(monkeypatch, _FakeResponse(200, body))
    result = fastlane_client.get_content("xyz")
    assert result["data"]["_id"] == "xyz"
    assert _stub_client.last["path"] == "/content/xyz"


def test_non_2xx_raises(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    _stub_client(monkeypatch, _FakeResponse(403, {"error": {"code": "forbidden"}}))
    with pytest.raises(fastlane_client.FastlaneClientError) as exc:
        fastlane_client.list_content()
    assert exc.value.status == 403
    assert exc.value.body == {"error": {"code": "forbidden"}}
