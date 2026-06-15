"""Shared HTTP client for the xgrowth platform.

Sync httpx.Client with bearer auth, tenacity retries on transient errors
(connect/read timeouts, 5xx). Used by every tool in ``xgrowth_tools.py``.
Helper module — no ``registry.register()`` calls here.
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

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=15.0, pool=5.0)


class XgrowthClientError(Exception):
    """Raised for non-2xx responses (after retry budget) or unparseable bodies."""

    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": str(self), "body": self.body}


class _RetryableHTTPError(Exception):
    """Internal — raised on transient HTTP failure to trigger a tenacity retry."""


# Connection-phase failures: the request provably never reached the server,
# so they are safe to retry for ANY method.
_CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
# Read/write-phase failures: the server may already have processed the request,
# so they are only safe to retry for idempotent methods.
_READWRITE_ERRORS = (
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)

# DELETE is idempotent per HTTP semantics (deleting the same resource twice
# leaves the same end state), so transient DELETE failures are safe to retry.
# PATCH/POST are excluded — retrying them could duplicate a non-idempotent action.
_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


def check_xgrowth_requirements() -> bool:
    """True when both required env vars are set — gates the xgrowth toolset."""
    return bool(os.getenv("XGROWTH_API_BASE") and os.getenv("XGROWTH_API_KEY"))


def _build_client() -> httpx.Client:
    base_url = os.getenv("XGROWTH_API_BASE", "").rstrip("/")
    api_key = os.getenv("XGROWTH_API_KEY", "")
    return httpx.Client(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=DEFAULT_TIMEOUT,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type(_RetryableHTTPError),
)
def _request_once(method: str, path: str, *, json: dict | None = None,
                  params: dict | None = None) -> dict:
    idempotent = method.upper() in _IDEMPOTENT_METHODS
    try:
        with _build_client() as client:
            response = client.request(method, path, json=json, params=params)
    except _CONNECT_ERRORS as e:
        # Never reached the server -> safe to retry regardless of method.
        raise _RetryableHTTPError(f"xgrowth connect error: {e}") from e
    except _READWRITE_ERRORS as e:
        if idempotent:
            raise _RetryableHTTPError(f"xgrowth network error: {e}") from e
        # Non-idempotent: the request may have been processed. Do NOT retry,
        # to avoid duplicate live actions (e.g. a double-post).
        raise XgrowthClientError(
            0, f"xgrowth network error (no retry on {method}): {e}"
        ) from e

    if 500 <= response.status_code < 600:
        if idempotent:
            raise _RetryableHTTPError(f"xgrowth {method} {path} -> {response.status_code}")
        raise XgrowthClientError(
            response.status_code,
            f"xgrowth {method} {path} -> {response.status_code} (no retry on {method})",
        )

    if not response.is_success:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text[:500]
        raise XgrowthClientError(
            response.status_code,
            f"xgrowth {method} {path} -> {response.status_code}",
            body=body,
        )

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as e:
        raise XgrowthClientError(
            response.status_code, f"xgrowth returned invalid JSON: {e}"
        ) from e


def request(method: str, path: str, *, json: dict | None = None,
            params: dict | None = None) -> dict:
    """Call xgrowth and return parsed JSON.

    Retries are idempotency-aware: connection-phase failures retry for any
    method; read/write-phase failures and 5xx retry only for idempotent
    methods (GET/HEAD/OPTIONS), so a transient failure on POST/PATCH/DELETE
    never replays a non-idempotent action (e.g. a double live-post).
    """
    logger.debug("xgrowth %s %s", method, path)
    try:
        return _request_once(method, path, json=json, params=params)
    except _RetryableHTTPError as e:
        raise XgrowthClientError(503, f"xgrowth unavailable: {e}") from e
