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
            "Content-Type": "application/json",
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
