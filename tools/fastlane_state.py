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
