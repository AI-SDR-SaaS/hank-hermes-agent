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
from collections import deque
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


# ---------------------------------------------------------------------------
# caption_history.jsonl — append-only log of caption picks for in-context learning
# ---------------------------------------------------------------------------


def _history_path() -> Path:
    return _state_dir() / "caption_history.jsonl"


def append_caption_history(
    *,
    content_id: str,
    type_: str,
    chosen: str,
    rejected: list[str],
) -> dict:
    """Append a record to caption_history.jsonl. Always succeeds (creates file if needed)."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "content_id": content_id,
        "type": type_,
        "chosen": chosen,
        "rejected": list(rejected),
    }
    # Append, not atomic-rewrite — history is append-only and we tolerate
    # a torn final line (the read path skips corrupt lines).
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_recent_caption_history(*, limit: int = 10) -> list[dict]:
    """Return up to `limit` most recent caption records, newest-first.

    Memory is bounded to `limit` records via a ring buffer — works even if
    the on-disk JSONL grows large over time. Tolerates missing file (returns
    []) and corrupt lines (skips them).
    """
    path = _history_path()
    if not path.exists():
        return []
    buf: deque[dict] = deque(maxlen=limit)
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    buf.append(rec)
    except OSError as e:
        logger.warning("caption_history.jsonl unreadable: %s", e)
        return []
    return list(reversed(buf))
