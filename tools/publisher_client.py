"""Shared HTTP client for the publisher service.

Sync httpx.Client with bearer auth, tenacity retries on transient errors
(connect/read timeouts, 5xx), and structured logging. Used by every tool
in ``publisher_tools.py``.

No ``registry.register()`` calls here — helper module.
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


class PublisherClientError(Exception):
    """Raised for non-2xx responses (after retry budget) or unparseable bodies."""

    def __init__(self, status: int, message: str, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": str(self), "body": self.body}


class _RetryableHTTPError(Exception):
    """Internal — raised on transient HTTP failure to trigger a tenacity retry."""


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


def check_publisher_requirements() -> bool:
    """True when both required env vars are set — gates the publisher toolset."""
    return bool(os.getenv("PUBLISHER_BASE_URL") and os.getenv("PUBLISHER_API_KEY"))


def _build_client() -> httpx.Client:
    base_url = os.getenv("PUBLISHER_BASE_URL", "").rstrip("/")
    api_key = os.getenv("PUBLISHER_API_KEY", "")
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
    retry=retry_if_exception_type(_RETRYABLE),
)
def _request_once(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    with _build_client() as client:
        response = client.request(method, path, json=json, params=params)

    if 500 <= response.status_code < 600:
        raise _RetryableHTTPError(
            f"publisher {method} {path} -> {response.status_code}"
        )

    if not response.is_success:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        raise PublisherClientError(
            response.status_code,
            f"publisher {method} {path} -> {response.status_code}",
            body=body,
        )

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError as e:
        raise PublisherClientError(
            response.status_code, f"publisher returned invalid JSON: {e}"
        ) from e


def request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Call the publisher and return parsed JSON.

    Retries on transient network errors and 5xx (3 attempts, exponential
    backoff). Raises ``PublisherClientError`` on persistent failure.
    """
    logger.debug("publisher %s %s", method, path)
    try:
        return _request_once(method, path, json=json, params=params)
    except _RetryableHTTPError as e:
        # Retry budget exhausted on a 5xx — surface as a normal client error
        raise PublisherClientError(503, f"publisher unavailable: {e}") from e
    except _TRANSIENT_NETWORK_ERRORS as e:
        raise PublisherClientError(0, f"publisher network error: {e}") from e
