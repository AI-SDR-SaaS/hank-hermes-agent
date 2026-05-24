# Fastlane → Hank Publisher Daily Cron — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `fastlane` toolset and supporting skill so Hermes can pull video content from `usefastlane.ai`, curate 2 posts/day with Telegram-gated captions, and auto-publish via the existing publisher at 11:30 ET and 18:00 ET.

**Architecture:** Three Hermes cron entries (1 planning + 2 publish) consume a workspace-scoped Fastlane API key over plain HTTPS. State (posted-IDs + today's plan) lives on disk under `HERMES_HOME/fastlane/`. Posting happens through the existing `publisher_quick_post` tool — Fastlane's own scheduler is not used.

**Tech Stack:** Python 3.11+, httpx, tenacity, pydantic, pytest. Mirrors the pattern of `tools/posthog_client.py` + `tools/posthog_tools.py`.

**Design spec:** `docs/superpowers/specs/2026-05-23-fastlane-cron-design.md`

---

## File Map

**Create:**
- `tools/fastlane_client.py` — httpx wrapper for Fastlane REST API
- `tools/fastlane_types.py` — pydantic models for API and tool args
- `tools/fastlane_state.py` — atomic-write JSON persistence for posted-IDs + daily plan
- `tools/fastlane_tools.py` — registers four agent tools
- `tests/tools/test_fastlane_client.py`
- `tests/tools/test_fastlane_state.py`
- `tests/tools/test_fastlane_tools.py`
- `skills/social-media/fastlane-daily-plan/SKILL.md`

**Modify:**
- `toolsets.py` — add `"fastlane"` toolset entry, include in `"hermes-cli"`, `"hermes-cron"`, `"hermes-telegram"`
- `.env.example` — document `FASTLANE_API_KEY`, `FASTLANE_API_BASE`

---

## Task 1: Scaffold pydantic types

**Files:**
- Create: `tools/fastlane_types.py`

- [ ] **Step 1: Create the file with API + tool models**

```python
"""Pydantic models for the Fastlane API and fastlane_* tools.

Mirrors the pattern in tools/posthog_types.py. API response shapes are
verified against api.usefastlane.ai/api/v1/content as of 2026-05-23.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Fastlane API response shapes
# ---------------------------------------------------------------------------


class FastlaneContent(BaseModel):
    """One content item from GET /api/v1/content."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    content_id: str = Field(alias="_id")
    creation_time: float = Field(alias="_creationTime")
    files: list[str]
    thumbnail_url: Optional[str] = Field(default=None, alias="thumbnailUrl")
    status: str
    type: str


class FastlanePagination(BaseModel):
    cursor: Optional[str] = None
    hasMore: bool = False


class FastlaneListResponse(BaseModel):
    data: list[FastlaneContent]
    pagination: FastlanePagination


class FastlaneGetResponse(BaseModel):
    data: FastlaneContent


# ---------------------------------------------------------------------------
# State file shapes (persisted to disk under HERMES_HOME/fastlane/)
# ---------------------------------------------------------------------------


SlotName = Literal["a", "b"]
SlotStatus = Literal["pending", "chosen", "posted", "failed"]


class DailyPlanSlot(BaseModel):
    content_id: str
    media_url: str
    chosen_caption: str
    status: SlotStatus = "pending"
    posted_at: Optional[str] = None  # ISO UTC


class DailyPlan(BaseModel):
    date: str  # YYYY-MM-DD in ET
    slot_a: Optional[DailyPlanSlot] = None
    slot_b: Optional[DailyPlanSlot] = None


class PostedRecord(BaseModel):
    content_id: str
    posted_at: str  # ISO UTC
    platforms: list[str]


# ---------------------------------------------------------------------------
# Tool input args
# ---------------------------------------------------------------------------


class ListUnpostedRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class SaveDailyPlanRequest(BaseModel):
    date: str
    slot: SlotName
    content_id: str
    media_url: str
    chosen_caption: str


class GetDailyPlanRequest(BaseModel):
    date: str
    slot: SlotName


class MarkPostedRequest(BaseModel):
    content_id: str
    platforms: list[str] = Field(default_factory=lambda: ["instagram", "tiktok"])
```

- [ ] **Step 2: Commit**

```bash
git add tools/fastlane_types.py
git commit -m "Add fastlane_types: pydantic models for API + tools"
```

---

## Task 2: HTTP client base + requirements gate

**Files:**
- Create: `tools/fastlane_client.py`
- Create: `tests/tools/test_fastlane_client.py`

- [ ] **Step 1: Write failing test for the gate**

`tests/tools/test_fastlane_client.py`:

```python
"""Tests for tools/fastlane_client.py."""

from unittest.mock import patch

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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'tools.fastlane_client'`

- [ ] **Step 3: Create the client module**

`tools/fastlane_client.py`:

```python
"""Shared HTTP client for the Fastlane REST API.

Sync httpx.Client with bearer auth, tenacity retries on transient errors
(connect/read timeouts, 5xx). Used by tools/fastlane_tools.py.

Workspace API keys (prefix `fsln_live_`) only see content / blitz /
analytics endpoints. Partner endpoints (`/api/v1/partner/*`) return 403.

Required env:
  FASTLANE_API_KEY      Workspace-scoped key from app.usefastlane.ai
  FASTLANE_API_BASE     Optional override (defaults to api.usefastlane.ai)
"""

import logging
import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=5.0)
DEFAULT_BASE_URL = "https://api.usefastlane.ai/api/v1"


class FastlaneClientError(Exception):
    """Raised for non-2xx responses (after retry budget) or unparseable bodies."""

    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": str(self), "body": self.body}


class _RetryableHTTPError(Exception):
    """Internal — triggers a tenacity retry on transient HTTP failure."""


_TRANSIENT_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)

_RETRYABLE = _TRANSIENT_NETWORK_ERRORS + (_RetryableHTTPError,)


def check_fastlane_requirements() -> bool:
    """True when FASTLANE_API_KEY is set — gates the fastlane toolset."""
    return bool(os.getenv("FASTLANE_API_KEY"))


def _base_url() -> str:
    return os.getenv("FASTLANE_API_BASE", DEFAULT_BASE_URL).rstrip("/")


def _build_client() -> httpx.Client:
    api_key = os.getenv("FASTLANE_API_KEY", "")
    return httpx.Client(
        base_url=_base_url(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=DEFAULT_TIMEOUT,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type(_RETRYABLE),
)
def _request_once(method: str, path: str, *, params: dict | None = None) -> dict:
    with _build_client() as client:
        response = client.request(method, path, params=params)

    if 500 <= response.status_code < 600:
        raise _RetryableHTTPError(
            f"fastlane {method} {path} -> {response.status_code}"
        )

    if not response.is_success:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        raise FastlaneClientError(
            response.status_code,
            f"fastlane {method} {path} -> {response.status_code}",
            body=body,
        )

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError as e:
        raise FastlaneClientError(
            response.status_code, f"fastlane returned invalid JSON: {e}"
        ) from e


def request(method: str, path: str, *, params: dict | None = None) -> dict:
    """Call the Fastlane API and return parsed JSON.

    Retries on transient network errors and 5xx (3 attempts, exponential
    backoff). Raises ``FastlaneClientError`` on persistent failure.
    """
    logger.debug("fastlane %s %s", method, path)
    try:
        return _request_once(method, path, params=params)
    except _RetryableHTTPError as e:
        raise FastlaneClientError(503, f"fastlane unavailable: {e}") from e
    except _TRANSIENT_NETWORK_ERRORS as e:
        raise FastlaneClientError(0, f"fastlane network error: {e}") from e
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_client.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_client.py tests/tools/test_fastlane_client.py
git commit -m "Add fastlane_client: httpx wrapper + requirements gate"
```

---

## Task 3: Client methods — `list_content` + `get_content`

**Files:**
- Modify: `tools/fastlane_client.py`
- Modify: `tests/tools/test_fastlane_client.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/tools/test_fastlane_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_client.py -v
```

Expected: `AttributeError: module 'tools.fastlane_client' has no attribute 'list_content'` (4 new failing tests).

- [ ] **Step 3: Add the methods**

Append to `tools/fastlane_client.py`:

```python
def list_content(limit: int = 20, cursor: str | None = None) -> dict:
    """GET /content. Returns {"data": [...], "pagination": {...}}."""
    params: dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    return request("GET", "/content", params=params)


def get_content(content_id: str) -> dict:
    """GET /content/{id}. Returns {"data": {...}}."""
    return request("GET", f"/content/{content_id}")
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_client.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_client.py tests/tools/test_fastlane_client.py
git commit -m "Add fastlane_client.list_content + get_content"
```

---

## Task 4: State file — posted-ID dedup

**Files:**
- Create: `tools/fastlane_state.py`
- Create: `tests/tools/test_fastlane_state.py`

- [ ] **Step 1: Write failing tests**

`tests/tools/test_fastlane_state.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'tools.fastlane_state'`.

- [ ] **Step 3: Implement state module**

`tools/fastlane_state.py`:

```python
"""On-disk state for Fastlane integration.

Lives under HERMES_HOME/fastlane/. Two files:
  - posted.json       Dedup map: {content_id: {posted_at, platforms}}
  - daily_plan.json   Today's plan: {date, slot_a, slot_b}

All writes are atomic (write-temp-then-rename) so a crash mid-write
doesn't corrupt the file.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _state_dir() -> Path:
    return get_hermes_home() / "fastlane"


def _posted_path() -> Path:
    return _state_dir() / "posted.json"


def _plan_path() -> Path:
    return _state_dir() / "daily_plan.json"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        logger.warning("fastlane state file %s is unreadable: %s", path, e)
        return None


# ---------------------------------------------------------------------------
# posted.json — Fastlane content_id dedup
# ---------------------------------------------------------------------------


def load_posted_ids() -> set[str]:
    """Return the set of Fastlane content_ids we have ever posted."""
    data = _read_json(_posted_path())
    if not isinstance(data, dict):
        return set()
    return set(data.keys())


def has_posted(content_id: str) -> bool:
    return content_id in load_posted_ids()


def mark_posted(content_id: str, *, platforms: list[str]) -> dict:
    """Idempotent — overwrites the record for ``content_id``."""
    data = _read_json(_posted_path()) or {}
    if not isinstance(data, dict):
        data = {}
    data[content_id] = {
        "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platforms": list(platforms),
    }
    _atomic_write_json(_posted_path(), data)
    return data[content_id]
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_state.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_state.py tests/tools/test_fastlane_state.py
git commit -m "Add fastlane_state: posted-ID dedup with atomic writes"
```

---

## Task 5: State file — daily plan slots

**Files:**
- Modify: `tools/fastlane_state.py`
- Modify: `tests/tools/test_fastlane_state.py`

- [ ] **Step 1: Append failing tests**

Add to `tests/tools/test_fastlane_state.py`:

```python
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


def test_save_slot_wrong_date_does_not_clobber_other_date(state_dir):
    fastlane_state.save_slot("2026-05-23", "a", content_id="abc", media_url="u", chosen_caption="c")
    fastlane_state.save_slot("2026-05-24", "a", content_id="def", media_url="u2", chosen_caption="c2")
    # Saving for a new date REPLACES the plan — slot_b under old date is gone.
    # Only one day's plan is kept at a time.
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_state.py -v
```

Expected: 5 new failing tests with `AttributeError: module 'tools.fastlane_state' has no attribute 'get_slot'`.

- [ ] **Step 3: Append plan helpers to fastlane_state.py**

Append to `tools/fastlane_state.py`:

```python
# ---------------------------------------------------------------------------
# daily_plan.json — today's two slots
# ---------------------------------------------------------------------------


def _load_plan() -> Optional[dict]:
    data = _read_json(_plan_path())
    if not isinstance(data, dict):
        return None
    return data


def get_slot(date: str, slot: str) -> Optional[dict]:
    """Return today's slot record or None.

    Returns None if the plan file doesn't exist, is for a different date,
    or the requested slot is missing.
    """
    plan = _load_plan()
    if not plan or plan.get("date") != date:
        return None
    return plan.get(f"slot_{slot}")


def save_slot(
    date: str,
    slot: str,
    *,
    content_id: str,
    media_url: str,
    chosen_caption: str,
) -> dict:
    """Upsert a slot. If the on-disk plan is for a different date, the file
    is REPLACED (single-day window). Status is set to ``"chosen"``.
    """
    plan = _load_plan()
    if not plan or plan.get("date") != date:
        plan = {"date": date, "slot_a": None, "slot_b": None}
    plan[f"slot_{slot}"] = {
        "content_id": content_id,
        "media_url": media_url,
        "chosen_caption": chosen_caption,
        "status": "chosen",
        "posted_at": None,
    }
    _atomic_write_json(_plan_path(), plan)
    return plan[f"slot_{slot}"]


def mark_slot_posted(date: str, slot: str) -> Optional[dict]:
    """Mark a chosen slot as ``"posted"``. No-op if slot missing / date mismatched."""
    plan = _load_plan()
    if not plan or plan.get("date") != date:
        return None
    rec = plan.get(f"slot_{slot}")
    if not rec:
        return None
    rec["status"] = "posted"
    rec["posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _atomic_write_json(_plan_path(), plan)
    return rec


def mark_slot_failed(date: str, slot: str, error: str) -> Optional[dict]:
    """Mark a chosen slot as ``"failed"`` (e.g. publisher 400 after retry)."""
    plan = _load_plan()
    if not plan or plan.get("date") != date:
        return None
    rec = plan.get(f"slot_{slot}")
    if not rec:
        return None
    rec["status"] = "failed"
    rec["error"] = error
    _atomic_write_json(_plan_path(), plan)
    return rec
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_state.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_state.py tests/tools/test_fastlane_state.py
git commit -m "Add fastlane_state.save_slot / get_slot / mark_slot_posted"
```

---

## Task 6: Tool — `fastlane_list_unposted`

**Files:**
- Create: `tools/fastlane_tools.py`
- Create: `tests/tools/test_fastlane_tools.py`

- [ ] **Step 1: Write failing test**

`tests/tools/test_fastlane_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: `ModuleNotFoundError: No module named 'tools.fastlane_tools'`.

- [ ] **Step 3: Create tools module with `fastlane_list_unposted`**

`tools/fastlane_tools.py`:

```python
"""Fastlane tools — list unposted, plan slots, mark posted.

Registers four tools under the ``fastlane`` toolset. Gated on
``FASTLANE_API_KEY``. Designed for the planning + publish cron entries
described in docs/superpowers/specs/2026-05-23-fastlane-cron-design.md.
"""

import logging
from typing import Any

from pydantic import ValidationError

from tools import fastlane_client, fastlane_state
from tools import fastlane_types as t
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

FASTLANE_TOOLSET = "fastlane"
_REQUIRES_ENV = ["FASTLANE_API_KEY"]


def _validation_error(e: ValidationError) -> str:
    return tool_error("invalid arguments", details=e.errors())


def _client_error(e: fastlane_client.FastlaneClientError) -> str:
    return tool_error(
        f"fastlane request failed: {e}", status=e.status, body=e.body
    )


# ---------------------------------------------------------------------------
# fastlane_list_unposted
# ---------------------------------------------------------------------------

LIST_UNPOSTED_SCHEMA = {
    "name": "fastlane_list_unposted",
    "description": (
        "Return up to ``limit`` Fastlane content items that have NOT yet "
        "been posted via our publisher. Items are oldest-first so the "
        "backlog drains before newer content is served. Each item has: "
        "content_id (stable Fastlane _id), media_url (direct CDN url, "
        ".mp4), thumbnail_url, type (wall-of-text, green-screen, "
        "video-hook, slideshow, remix), and creation_time (epoch ms)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max items to fetch from Fastlane before dedup. 1–100, default 20.",
                "minimum": 1,
                "maximum": 100,
            },
        },
    },
}


def _list_unposted(args: dict, **_kw: Any) -> str:
    try:
        req = t.ListUnpostedRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = fastlane_client.list_content(limit=req.limit)
    except fastlane_client.FastlaneClientError as e:
        return _client_error(e)
    try:
        resp = t.FastlaneListResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from fastlane: {e.errors()}", body=body
        )
    posted = fastlane_state.load_posted_ids()
    candidates = [c for c in resp.data if c.content_id not in posted]
    candidates.sort(key=lambda c: c.creation_time)
    items = [
        {
            "content_id": c.content_id,
            "media_url": c.files[0] if c.files else None,
            "thumbnail_url": c.thumbnail_url,
            "type": c.type,
            "creation_time": c.creation_time,
        }
        for c in candidates
    ]
    return tool_result({"items": items, "count": len(items)})


registry.register(
    name="fastlane_list_unposted",
    toolset=FASTLANE_TOOLSET,
    schema=LIST_UNPOSTED_SCHEMA,
    handler=lambda args, **kw: _list_unposted(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_tools.py tests/tools/test_fastlane_tools.py
git commit -m "Add fastlane_list_unposted tool"
```

---

## Task 7: Tool — `fastlane_save_daily_plan`

**Files:**
- Modify: `tools/fastlane_tools.py`
- Modify: `tests/tools/test_fastlane_tools.py`

- [ ] **Step 1: Write failing test**

Append to `tests/tools/test_fastlane_tools.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_tools.py::test_save_daily_plan_persists -v
```

Expected: `ImportError: cannot import name '_save_daily_plan'`.

- [ ] **Step 3: Add the tool**

Append to `tools/fastlane_tools.py`:

```python
# ---------------------------------------------------------------------------
# fastlane_save_daily_plan
# ---------------------------------------------------------------------------

SAVE_DAILY_PLAN_SCHEMA = {
    "name": "fastlane_save_daily_plan",
    "description": (
        "Persist Jonathan's caption choice for one of today's two post "
        "slots. Call this AFTER he taps a caption variant in Telegram. "
        "The slot is marked status='chosen'; the publish cron will read "
        "it later and ship via publisher_quick_post(auto_publish=true)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "ET date YYYY-MM-DD."},
            "slot": {"type": "string", "enum": ["a", "b"]},
            "content_id": {"type": "string", "description": "Fastlane _id."},
            "media_url": {"type": "string", "description": "Public CDN URL from Fastlane.files[0]."},
            "chosen_caption": {"type": "string", "description": "Full ## Caption + ## Hashtags markdown."},
        },
        "required": ["date", "slot", "content_id", "media_url", "chosen_caption"],
    },
}


def _save_daily_plan(args: dict, **_kw: Any) -> str:
    try:
        req = t.SaveDailyPlanRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    slot = fastlane_state.save_slot(
        req.date,
        req.slot,
        content_id=req.content_id,
        media_url=req.media_url,
        chosen_caption=req.chosen_caption,
    )
    return tool_result({"date": req.date, "slot": req.slot, "record": slot})


registry.register(
    name="fastlane_save_daily_plan",
    toolset=FASTLANE_TOOLSET,
    schema=SAVE_DAILY_PLAN_SCHEMA,
    handler=lambda args, **kw: _save_daily_plan(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_tools.py tests/tools/test_fastlane_tools.py
git commit -m "Add fastlane_save_daily_plan tool"
```

---

## Task 8: Tool — `fastlane_get_daily_plan`

**Files:**
- Modify: `tools/fastlane_tools.py`
- Modify: `tests/tools/test_fastlane_tools.py`

- [ ] **Step 1: Write failing test**

Append:

```python
from tools.fastlane_tools import _get_daily_plan


def test_get_daily_plan_returns_slot():
    fastlane_state.save_slot(
        "2026-05-23", "b",
        content_id="zzz", media_url="https://cdn/zzz.mp4", chosen_caption="cap",
    )
    payload = json.loads(_get_daily_plan({"date": "2026-05-23", "slot": "b"}))
    assert payload["ok"] is True
    assert payload["data"]["slot"]["content_id"] == "zzz"
    assert payload["data"]["status"] == "chosen"


def test_get_daily_plan_missing_returns_pending():
    payload = json.loads(_get_daily_plan({"date": "2026-05-23", "slot": "a"}))
    assert payload["ok"] is True
    assert payload["data"]["status"] == "pending"
    assert payload["data"]["slot"] is None
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: `ImportError: cannot import name '_get_daily_plan'`.

- [ ] **Step 3: Add the tool**

Append to `tools/fastlane_tools.py`:

```python
# ---------------------------------------------------------------------------
# fastlane_get_daily_plan
# ---------------------------------------------------------------------------

GET_DAILY_PLAN_SCHEMA = {
    "name": "fastlane_get_daily_plan",
    "description": (
        "Read one slot from today's plan. Used by the publish-cron "
        "prompt: if status=='chosen' it ships via publisher_quick_post; "
        "if status=='pending' or no plan exists, the cron silently skips."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string"},
            "slot": {"type": "string", "enum": ["a", "b"]},
        },
        "required": ["date", "slot"],
    },
}


def _get_daily_plan(args: dict, **_kw: Any) -> str:
    try:
        req = t.GetDailyPlanRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    rec = fastlane_state.get_slot(req.date, req.slot)
    status = rec["status"] if rec else "pending"
    return tool_result({"date": req.date, "slot_name": req.slot, "status": status, "slot": rec})


registry.register(
    name="fastlane_get_daily_plan",
    toolset=FASTLANE_TOOLSET,
    schema=GET_DAILY_PLAN_SCHEMA,
    handler=lambda args, **kw: _get_daily_plan(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_tools.py tests/tools/test_fastlane_tools.py
git commit -m "Add fastlane_get_daily_plan tool"
```

---

## Task 9: Tool — `fastlane_mark_posted`

**Files:**
- Modify: `tools/fastlane_tools.py`
- Modify: `tests/tools/test_fastlane_tools.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: `ImportError: cannot import name '_mark_posted'`.

- [ ] **Step 3: Add the tool**

Append to `tools/fastlane_tools.py`:

```python
# ---------------------------------------------------------------------------
# fastlane_mark_posted
# ---------------------------------------------------------------------------

MARK_POSTED_SCHEMA = {
    "name": "fastlane_mark_posted",
    "description": (
        "Record that a Fastlane content_id has been shipped. Adds to the "
        "dedup map (so fastlane_list_unposted never returns it again) and, "
        "if today's plan has a slot with that content_id, flips that slot's "
        "status to 'posted'. Idempotent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string"},
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Platforms posted to. Default ['instagram', 'tiktok'].",
            },
        },
        "required": ["content_id"],
    },
}


def _mark_posted(args: dict, **_kw: Any) -> str:
    try:
        req = t.MarkPostedRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    record = fastlane_state.mark_posted(req.content_id, platforms=req.platforms)
    # Best-effort: find a slot in today's plan that matches and flip its status.
    plan_path = fastlane_state._plan_path()
    flipped_slot: str | None = None
    plan = fastlane_state._read_json(plan_path)
    if isinstance(plan, dict):
        for slot_name in ("a", "b"):
            slot = plan.get(f"slot_{slot_name}")
            if slot and slot.get("content_id") == req.content_id:
                fastlane_state.mark_slot_posted(plan.get("date", ""), slot_name)
                flipped_slot = slot_name
                break
    return tool_result(
        {"content_id": req.content_id, "record": record, "flipped_slot": flipped_slot}
    )


registry.register(
    name="fastlane_mark_posted",
    toolset=FASTLANE_TOOLSET,
    schema=MARK_POSTED_SCHEMA,
    handler=lambda args, **kw: _mark_posted(args, **kw),
    check_fn=fastlane_client.check_fastlane_requirements,
    requires_env=_REQUIRES_ENV,
)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/fastlane_tools.py tests/tools/test_fastlane_tools.py
git commit -m "Add fastlane_mark_posted tool"
```

---

## Task 10: Register the `fastlane` toolset

**Files:**
- Modify: `toolsets.py`

- [ ] **Step 1: Add toolset definition**

In `toolsets.py`, after the `"posthog"` entry (around line 241), add:

```python
    "fastlane": {
        "description": "Fastlane content tools — list unposted videos from usefastlane.ai, manage today's plan, mark posted. Gated on FASTLANE_API_KEY.",
        "tools": [
            "fastlane_list_unposted",
            "fastlane_save_daily_plan",
            "fastlane_get_daily_plan",
            "fastlane_mark_posted",
        ],
        "includes": [],
    },
```

- [ ] **Step 2: Include it in the Hermes parent toolsets**

In the same file, find each of these `"includes"` lists and append `"fastlane"`:

- `"hermes-cli"` (currently `["publisher", "airtable", "posthog"]`) → add `"fastlane"`
- `"hermes-discord"` (currently `["publisher", "airtable", "posthog"]`) → add `"fastlane"`

Leave `"hermes-cron"`, `"hermes-telegram"`, `"hermes-whatsapp"`, `"hermes-slack"`, `"hermes-signal"` unchanged. Cron + Telegram bots load toolsets via `hermes tools` config at runtime; we'll opt the cron entries into `fastlane` by name in Task 13.

- [ ] **Step 3: Ensure `tools/fastlane_tools` is imported at startup**

Find the file that imports the tool modules at startup (typically `toolset_distributions.py` or `tools/__init__.py`). Grep:

```bash
grep -rn "from tools import posthog_tools\|import posthog_tools" /c/Users/jonat/hank-hermes-agent --include="*.py" | head
```

Add an identical line for `fastlane_tools` next to the existing `posthog_tools` import, so the `registry.register()` calls fire on startup.

- [ ] **Step 4: Run the existing registry smoke test pattern**

Append to `tests/tools/test_fastlane_tools.py`:

```python
@pytest.mark.parametrize(
    "name",
    [
        "fastlane_list_unposted",
        "fastlane_save_daily_plan",
        "fastlane_get_daily_plan",
        "fastlane_mark_posted",
    ],
)
def test_tool_registered_under_fastlane_toolset(name):
    entry = registry.get_entry(name)
    assert entry is not None, f"{name} is not registered"
    assert entry.toolset == FASTLANE_TOOLSET
    assert entry.schema.get("name") == name
    assert entry.schema.get("parameters", {}).get("type") == "object"


def test_check_fastlane_requirements_fails_closed(monkeypatch):
    monkeypatch.delenv("FASTLANE_API_KEY", raising=False)
    assert fastlane_client.check_fastlane_requirements() is False


def test_check_fastlane_requirements_true_when_set(monkeypatch):
    monkeypatch.setenv("FASTLANE_API_KEY", "fsln_live_test")
    assert fastlane_client.check_fastlane_requirements() is True
```

Run:

```bash
pytest tests/tools/test_fastlane_tools.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add toolsets.py tests/tools/test_fastlane_tools.py
git commit -m "Register fastlane toolset and include in hermes-cli/discord"
```

If Step 3 also modified a startup importer file (e.g. `toolset_distributions.py`), include that path in the `git add` above.

---

## Task 11: Document env vars in `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Locate the existing publisher / posthog block**

```bash
grep -n "POSTHOG\|PUBLISHER" /c/Users/jonat/hank-hermes-agent/.env.example
```

- [ ] **Step 2: Add Fastlane block beneath the POSTHOG block**

Add these lines (preserve existing formatting style — single-quote `#` headers if that's the convention in surrounding entries):

```bash
# ---------------------------------------------------------------------------
# Fastlane (usefastlane.ai) — content source for the daily IG/TikTok cron
# ---------------------------------------------------------------------------
# Workspace-scoped API key from app.usefastlane.ai → API keys.
# Partner keys are NOT supported; use the workspace key shape (fsln_live_*).
FASTLANE_API_KEY=
# Optional override (default: https://api.usefastlane.ai/api/v1)
FASTLANE_API_BASE=
```

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "Document FASTLANE_API_KEY in .env.example"
```

---

## Task 12: Write the `fastlane-daily-plan` skill

**Files:**
- Create: `skills/social-media/fastlane-daily-plan/SKILL.md`

- [ ] **Step 1: Inspect the existing ad-hoc-post skill for tone and structure**

```bash
cat skills/social-media/ad-hoc-post/SKILL.md
```

Read the caption voice rules, hashtag conventions, and the Telegram pick-1-of-3 idiom. The new skill should match this voice.

- [ ] **Step 2: Create the new skill**

`skills/social-media/fastlane-daily-plan/SKILL.md`:

```markdown
---
name: fastlane-daily-plan
description: Runs once per morning. Pulls unposted Fastlane videos, picks 2 for the day, drafts 3 caption variants per post, sends Jonathan Telegram pickers for both. When he taps, saves the chosen caption into today's plan; the publish-slot crons drain it later.
---

# Fastlane daily plan

This skill is loaded by the **`fastlane-daily-plan`** cron entry that fires at
08:00 ET. It DOES NOT post anything itself — it only curates and parks the
plan on disk. Two separate cron entries (`fastlane-publish-slot-a` at 11:30
ET and `fastlane-publish-slot-b` at 18:00 ET) drain the plan via
`publisher_quick_post(auto_publish=true)`.

## Workflow

1. **Pull candidates.** Call `fastlane_list_unposted({"limit": 20})`.
   - If `items` is empty → reply with the single token `[SILENT]` and stop.
     The publish slots will silently skip too. No Telegram noise.

2. **Inspect thumbnails.** For each candidate, the `thumbnail_url` is a
   `.webp` on a public CDN. Look at them. The `type` field is your other
   signal (`wall-of-text`, `green-screen`, `video-hook`, `slideshow`, `remix`).

3. **Pick 2.** Choose the two strongest based on visual content. Prefer
   variety: don't pick two `wall-of-text` back-to-back when there's a
   `green-screen` or `video-hook` available. The earlier-creation-time one
   becomes slot A (11:30 ET), the later one becomes slot B (18:00 ET).

4. **Draft 3 caption variants per pick.** For each post:
   - Captions follow Hank's voice from `skills/social-media/ad-hoc-post/SKILL.md`.
   - Format each variant as the markdown the publisher expects:
     ```
     ## Caption
     <body>

     ## Hashtags
     #tag1 #tag2 #tag3
     ```
   - No `# Title` (TikTok carousel only; these are videos).

5. **Send Telegram pickers.** Two messages, one per post:
   - Message body: thumbnail URL + a 1-line summary per variant.
   - Inline keyboard: three buttons, payload encodes `slot` + `variant_index`
     so the bot adapter can route the tap back to a handler that calls
     `fastlane_save_daily_plan(...)` with the chosen caption.

6. **On each tap, persist.** Call:
   ```
   fastlane_save_daily_plan({
     "date": "<YYYY-MM-DD in ET>",
     "slot": "a" | "b",
     "content_id": "<from step 3>",
     "media_url": "<from step 1 items[i].media_url>",
     "chosen_caption": "<the full ## Caption + ## Hashtags markdown>"
   })
   ```

7. **Confirmation.** When both slots are status="chosen", reply with a 1-line
   summary to Jonathan: "Plan locked — A at 11:30 ET (<short caption>), B at
   18:00 ET (<short caption>)."

## Failure handling

| Situation | Action |
|---|---|
| `fastlane_list_unposted` returns 0 items | Reply `[SILENT]`. No Telegram messages. |
| Returns only 1 item | Plan only slot A. Tell Jonathan slot B will skip today. |
| `fastlane_list_unposted` returns an error | Forward the error to Jonathan in Telegram so he knows the cron tried and failed. Do not silently swallow. |
| Jonathan ignores the picker | The slot stays `status="pending"`. The publish cron will silently skip at slot time. No retry. |

## What you do NOT do

- Do NOT call `publisher_quick_post` from this skill. That's the publish-cron's job.
- Do NOT use Fastlane's own `/posts` or `/connections` endpoints. We post via the publisher only.
- Do NOT pick more than 2 posts. Cadence is fixed.
- Do NOT skip the Telegram approval. Even though this is automated, Jonathan
  has final say on every caption.
```

- [ ] **Step 3: Commit**

```bash
git add skills/social-media/fastlane-daily-plan/SKILL.md
git commit -m "Add fastlane-daily-plan skill"
```

---

## Task 13: Document Railway env + cron commands

**Files:**
- Create: `docs/superpowers/runbooks/fastlane-cron-setup.md`

- [ ] **Step 1: Create runbook directory if it doesn't exist**

```bash
mkdir -p docs/superpowers/runbooks
```

- [ ] **Step 2: Write the setup runbook**

`docs/superpowers/runbooks/fastlane-cron-setup.md`:

```markdown
# Fastlane Cron — Setup Runbook

One-time deploy steps to activate the Fastlane → Hank publisher daily
cron after the implementation has been merged.

## 1. Set the API key on Hermes Railway

In the `kind-generosity` project → `hermes` service → Variables:

| Key | Value |
|---|---|
| `FASTLANE_API_KEY` | Workspace key from app.usefastlane.ai → API keys (shape: `fsln_live_*`) |
| `FASTLANE_API_BASE` | Leave unset (defaults to `https://api.usefastlane.ai/api/v1`) |

Redeploy after setting. Confirm:

```bash
railway run -- python -c "from tools.fastlane_client import check_fastlane_requirements; print(check_fastlane_requirements())"
```

Expected: `True`.

## 2. Smoke test the live API

From the Hermes shell (`railway ssh` into hermes):

```bash
python -c "
from tools import fastlane_client
r = fastlane_client.list_content(limit=3)
print('items:', len(r['data']))
print('first id:', r['data'][0]['_id'] if r['data'] else 'none')
"
```

Expected: 3 items, an `_id` prefixed `p...`. If `403 forbidden`, the key
is a Partner key, not a workspace key — regenerate as workspace.

## 3. Create the three cron entries

All times are in UTC (Railway containers run UTC). The cron expressions
below assume **EDT** (UTC-4). When EST kicks in (first Sunday of November)
the expressions need to shift by 1h, or set `TZ=America/New_York` on the
container and rewrite in ET.

```bash
# Planning — daily at 08:00 ET (= 12:00 UTC during EDT)
hermes cron create "0 12 * * *" \
  "Run the fastlane-daily-plan workflow. Curate 2 posts from Fastlane, draft 3 caption variants per post, send Telegram pickers." \
  --skills "fastlane-daily-plan" \
  --toolsets "fastlane" \
  --name "Fastlane daily plan" \
  --deliver telegram

# Publish slot A — daily at 11:30 ET (= 15:30 UTC during EDT)
hermes cron create "30 15 * * *" \
  "Today's date in ET is \$(date -u -d '5 hours ago' +%Y-%m-%d). Call fastlane_get_daily_plan(date=that, slot='a'). If status=='chosen', call publisher_quick_post(media_urls=[plan.slot.media_url], caption=plan.slot.chosen_caption, auto_publish=true). On success, call fastlane_mark_posted(content_id=plan.slot.content_id, platforms=['instagram','tiktok']). On Zernio 400, wait 60s and retry once before giving up. If status=='pending' or no plan, reply [SILENT]." \
  --toolsets "fastlane,publisher" \
  --name "Fastlane publish slot A (11:30 ET)" \
  --deliver telegram

# Publish slot B — daily at 18:00 ET (= 22:00 UTC during EDT)
hermes cron create "0 22 * * *" \
  "Today's date in ET is \$(date -u -d '4 hours ago' +%Y-%m-%d). Call fastlane_get_daily_plan(date=that, slot='b'). Same logic as slot A." \
  --toolsets "fastlane,publisher" \
  --name "Fastlane publish slot B (18:00 ET)" \
  --deliver telegram
```

Verify with:

```bash
hermes cron list
```

## 4. End-to-end smoke

Pick a Fastlane content_id that is safe to actually post (e.g. one you'd
ship today anyway). Manually trigger the planning cron earlier than 08:00
ET to dry-run:

```bash
hermes cron run "Fastlane daily plan" --now
```

Watch for both Telegram messages. Tap a caption on each. Then run a
single publish cron manually:

```bash
hermes cron run "Fastlane publish slot A (11:30 ET)" --now
```

Confirm the post landed on IG and TikTok. Confirm `fastlane_posted.json`
on the Hermes Railway disk now contains the `_id`:

```bash
railway run -- cat /opt/data/fastlane/posted.json
```

## 5. Three-day observation window

Leave it running for three days. Each morning, check:
- Both Telegram pickers arrived at 08:00 ET ± a couple of minutes.
- Captions look on-voice.
- Posts landed at 11:30 ET and 18:00 ET.
- No item shipped twice (`posted.json` grows by 2 per day).

If any of the above drift, treat as v1 issues and iterate on the skill
or cron prompts before bothering with new features.

## DST cutover

EST starts on Sunday Nov 2, 2026 at 02:00 ET. On Nov 1, recreate the three
cron entries with UTC expressions shifted +1h:

| Slot | EDT cron | EST cron |
|---|---|---|
| Planning | `0 12 * * *` | `0 13 * * *` |
| Publish A | `30 15 * * *` | `30 16 * * *` |
| Publish B | `0 22 * * *` | `0 23 * * *` |
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/runbooks/fastlane-cron-setup.md
git commit -m "Add Fastlane cron deploy runbook"
```

---

## Self-Review Notes

Checked against the spec at `docs/superpowers/specs/2026-05-23-fastlane-cron-design.md`:

| Spec section | Where in plan |
|---|---|
| Fastlane API surface (verified) | Task 2/3 mirror the verified endpoints |
| `tools/fastlane_client.py` | Tasks 2–3 |
| `tools/fastlane_tools.py` — 4 tools | Tasks 6, 7, 8, 9 |
| State files in `/opt/data/fastlane/` | Tasks 4–5 (under `HERMES_HOME/fastlane/`) |
| Skill `fastlane-daily-plan` | Task 12 |
| Toolset registration (2-step pattern) | Task 10 |
| Env vars + cron commands | Tasks 11 + 13 |
| Retry-on-Zernio-400 with 60s wait | Task 13 (embedded in publish-cron prompt) |
| Silent skip when slot pending | Task 8 (tool returns status), Task 13 (prompt branches on it) |
| Dedup via `_id` forever | Task 4 |

**Known deviations from spec:**

- Spec said state lives at `/opt/data/fastlane_state.json` + `/opt/data/fastlane_daily_plan.json`. Plan puts them under `<HERMES_HOME>/fastlane/posted.json` + `<HERMES_HOME>/fastlane/daily_plan.json` — cleaner namespace, same content. On Railway with `HERMES_HOME=/opt/data` this is `/opt/data/fastlane/...`.
- Retry-on-Zernio-400 lives in the publish-cron prompt (not in code) since it's per-call orchestration, not a library concern. The cron prompt explicitly tells the agent to wait 60s and retry once before giving up.
- The spec lists "failed-slot Telegram alert" — in v1 the agent's normal cron output is delivered to Telegram via `--deliver telegram`, so a failed slot becomes a Telegram message naturally. No extra alerting code needed.

**Placeholder scan:** none — every step has actual code, exact paths, and a runnable command.
