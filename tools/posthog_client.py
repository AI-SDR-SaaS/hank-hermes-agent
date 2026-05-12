"""Shared HTTP client for the PostHog REST API.

Sync httpx.Client with bearer auth, tenacity retries on transient errors
(connect/read timeouts, 5xx), and structured logging. Used by every tool
in ``posthog_tools.py``.

PostHog's public API base is ``https://us.posthog.com`` for US Cloud or
``https://eu.posthog.com`` for EU Cloud. Override with ``POSTHOG_BASE_URL``
if you're on a different region or a self-hosted instance.

All project-scoped endpoints are addressed through ``project_request()``,
which prepends ``/api/projects/{POSTHOG_PROJECT_ID}/`` so individual tools
don't have to remember the project id.

No ``registry.register()`` calls — helper module.
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

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=15.0, pool=5.0)
DEFAULT_BASE_URL = "https://us.posthog.com"


class PostHogClientError(Exception):
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


def check_posthog_requirements() -> bool:
    """True when both required env vars are set — gates the posthog toolset."""
    return bool(
        os.getenv("POSTHOG_PERSONAL_API_KEY") and os.getenv("POSTHOG_PROJECT_ID")
    )


def _base_url() -> str:
    return os.getenv("POSTHOG_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _project_id() -> str:
    return os.getenv("POSTHOG_PROJECT_ID", "").strip()


def _build_client() -> httpx.Client:
    api_key = os.getenv("POSTHOG_PERSONAL_API_KEY", "")
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
            f"posthog {method} {path} -> {response.status_code}"
        )

    if not response.is_success:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:500]
        raise PostHogClientError(
            response.status_code,
            f"posthog {method} {path} -> {response.status_code}",
            body=body,
        )

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError as e:
        raise PostHogClientError(
            response.status_code, f"posthog returned invalid JSON: {e}"
        ) from e


def request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Call the PostHog API and return parsed JSON.

    Retries on transient network errors and 5xx (3 attempts, exponential
    backoff). Raises ``PostHogClientError`` on persistent failure.

    ``path`` should start with ``/api/`` — use ``project_request()`` for
    the common project-scoped case.
    """
    logger.debug("posthog %s %s", method, path)
    try:
        return _request_once(method, path, json=json, params=params)
    except _RetryableHTTPError as e:
        raise PostHogClientError(503, f"posthog unavailable: {e}") from e
    except _TRANSIENT_NETWORK_ERRORS as e:
        raise PostHogClientError(0, f"posthog network error: {e}") from e


def project_request(
    method: str,
    subpath: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Call a project-scoped PostHog endpoint.

    ``subpath`` is appended to ``/api/projects/{POSTHOG_PROJECT_ID}/``. Leading
    slash on ``subpath`` is normalized away so callers can pass either form.
    """
    project_id = _project_id()
    if not project_id:
        raise PostHogClientError(0, "POSTHOG_PROJECT_ID is not set")
    path = f"/api/projects/{project_id}/{subpath.lstrip('/')}"
    return request(method, path, json=json, params=params)
