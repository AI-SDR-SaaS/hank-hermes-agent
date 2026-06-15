"""xgrowth platform tools — radar, generate, queue, post, reporting.

Registers tools under the ``xgrowth`` toolset, each gated on
XGROWTH_API_BASE + XGROWTH_API_KEY. Thin wrappers over the xgrowth REST API
(see docs/superpowers/specs/2026-06-15-xgrowth-agent-design.md).
"""

import logging
from typing import Any, Callable

from tools import xgrowth_client
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

XGROWTH_TOOLSET = "xgrowth"
_REQUIRES_ENV = ["XGROWTH_API_BASE", "XGROWTH_API_KEY"]


def _client_error(e: xgrowth_client.XgrowthClientError) -> str:
    return tool_error(f"xgrowth request failed: {e}", status=e.status, body=e.body)


def _call(method: str, path: str, *, json: dict | None = None,
          params: dict | None = None) -> str:
    """Run a request and return a tool_result / tool_error JSON string."""
    try:
        body = xgrowth_client.request(method, path, json=json, params=params)
    except xgrowth_client.XgrowthClientError as e:
        return _client_error(e)
    return tool_result(body)


def _require(args: dict, *keys: str) -> str | None:
    """Return a tool_error string if any required key is missing/empty, else None."""
    missing = [k for k in keys if not args.get(k)]
    if missing:
        return tool_error(f"missing required argument(s): {', '.join(missing)}")
    return None


def _register(schema: dict, handler: Callable) -> None:
    registry.register(
        name=schema["name"],
        toolset=XGROWTH_TOOLSET,
        schema=schema,
        handler=handler,
        check_fn=xgrowth_client.check_xgrowth_requirements,
        requires_env=_REQUIRES_ENV,
    )
