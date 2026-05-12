"""PostHog tools — HogQL queries, session recordings, errors, flags, dashboards.

Registers five tools under the ``posthog`` toolset:

  - ``posthog_query``                POST /api/projects/:id/query/  (HogQL)
  - ``posthog_list_recordings``      GET  /api/projects/:id/session_recordings/
  - ``posthog_list_errors``          GET  /api/projects/:id/error_tracking/issues/
  - ``posthog_list_feature_flags``   GET  /api/projects/:id/feature_flags/
  - ``posthog_get_dashboard``        GET  /api/projects/:id/dashboards/:id/

These replace the previous PostHog MCP integration. HTTP API direct so we
control the request/response format and don't depend on PostHog's MCP
server transport quirks. Gated on ``POSTHOG_PERSONAL_API_KEY`` +
``POSTHOG_PROJECT_ID``; both must be set for the toolset to register.
"""

import logging
from typing import Any

from pydantic import ValidationError

from tools import posthog_client
from tools import posthog_types as t
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

POSTHOG_TOOLSET = "posthog"
_REQUIRES_ENV = ["POSTHOG_PERSONAL_API_KEY", "POSTHOG_PROJECT_ID"]


def _validation_error(e: ValidationError) -> str:
    return tool_error("invalid arguments", details=e.errors())


def _client_error(e: posthog_client.PostHogClientError) -> str:
    return tool_error(
        f"posthog request failed: {e}", status=e.status, body=e.body
    )


# ---------------------------------------------------------------------------
# posthog_query — HogQL
# ---------------------------------------------------------------------------

QUERY_SCHEMA = {
    "name": "posthog_query",
    "description": (
        "Run a HogQL query against the configured PostHog project. HogQL is "
        "PostHog's SQL dialect — query the events table directly, plus virtual "
        "tables like persons, sessions, $web_vitals. Returns columns + rows.\n\n"
        "Examples:\n"
        "  SELECT count() FROM events WHERE event = '$pageview' "
        "AND timestamp >= now() - INTERVAL 7 DAY\n"
        "  SELECT properties.$current_url, count() FROM events "
        "WHERE event = '$exception' AND timestamp >= now() - INTERVAL 1 DAY "
        "GROUP BY properties.$current_url ORDER BY count() DESC LIMIT 10\n\n"
        "Use this for funnel digests, Web Vitals (events: $web_vitals), "
        "error groupings, and anything not covered by the convenience tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The HogQL SQL to execute. Required.",
            },
        },
        "required": ["query"],
    },
}


def _query(args: dict, **_kw: Any) -> str:
    try:
        req = t.HogQLQueryRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = posthog_client.project_request(
            "POST",
            "query/",
            json={"query": {"kind": "HogQLQuery", "query": req.query}},
        )
    except posthog_client.PostHogClientError as e:
        return _client_error(e)
    try:
        resp = t.HogQLQueryResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from posthog: {e.errors()}", body=body
        )
    if resp.error:
        return tool_error(f"hogql error: {resp.error}", hogql=resp.hogql)
    return tool_result(
        {
            "columns": resp.columns,
            "row_count": len(resp.results),
            "rows": resp.results,
        }
    )


# ---------------------------------------------------------------------------
# posthog_list_recordings
# ---------------------------------------------------------------------------

LIST_RECORDINGS_SCHEMA = {
    "name": "posthog_list_recordings",
    "description": (
        "List recent session recordings, optionally filtered by date range or "
        "ordering. Returns a slim summary per recording (id, duration, click/"
        "keypress/error counts, start URL, person). Use to spot high-error or "
        "high-rage sessions worth deeper inspection."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "date_from": {
                "type": "string",
                "description": (
                    "ISO timestamp or PostHog relative date "
                    "(e.g. '-7d', '-24h'). Defaults to '-1d'."
                ),
            },
            "date_to": {
                "type": "string",
                "description": "ISO timestamp; defaults to now.",
            },
            "order": {
                "type": "string",
                "enum": [
                    "start_time",
                    "duration",
                    "active_seconds",
                    "console_error_count",
                    "click_count",
                    "keypress_count",
                ],
                "default": "start_time",
                "description": "Sort field. Descending order is implied for all options.",
            },
        },
        "required": [],
    },
}


def _list_recordings(args: dict, **_kw: Any) -> str:
    try:
        limit = int(args.get("limit") or 10)
    except (TypeError, ValueError):
        return tool_error("'limit' must be an integer")
    limit = max(1, min(limit, 50))

    params: dict[str, Any] = {"limit": limit}
    if args.get("date_from"):
        params["date_from"] = args["date_from"]
    if args.get("date_to"):
        params["date_to"] = args["date_to"]
    order = (args.get("order") or "start_time").strip()
    if order:
        params["order"] = order

    try:
        body = posthog_client.project_request(
            "GET", "session_recordings/", params=params
        )
    except posthog_client.PostHogClientError as e:
        return _client_error(e)
    try:
        resp = t.ListRecordingsResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from posthog: {e.errors()}", body=body
        )
    return tool_result(
        {
            "count": len(resp.results),
            "recordings": [r.model_dump(mode="json") for r in resp.results],
        }
    )


# ---------------------------------------------------------------------------
# posthog_list_errors
# ---------------------------------------------------------------------------

LIST_ERRORS_SCHEMA = {
    "name": "posthog_list_errors",
    "description": (
        "List error-tracking issues from PostHog, sorted by recent activity. "
        "Returns issue id, name/message, status, occurrence counts, first/last "
        "seen. Use for daily error digests; pair with posthog_query against "
        "the events table for deeper drill-down on a specific issue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "status": {
                "type": "string",
                "enum": ["active", "resolved", "suppressed", "all"],
                "default": "active",
            },
        },
        "required": [],
    },
}


def _list_errors(args: dict, **_kw: Any) -> str:
    try:
        limit = int(args.get("limit") or 10)
    except (TypeError, ValueError):
        return tool_error("'limit' must be an integer")
    limit = max(1, min(limit, 50))

    params: dict[str, Any] = {"limit": limit}
    status = (args.get("status") or "active").strip()
    if status and status != "all":
        params["status"] = status

    try:
        body = posthog_client.project_request(
            "GET", "error_tracking/issues/", params=params
        )
    except posthog_client.PostHogClientError as e:
        return _client_error(e)
    try:
        resp = t.ListErrorIssuesResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from posthog: {e.errors()}", body=body
        )
    return tool_result(
        {
            "count": len(resp.results),
            "issues": [i.model_dump(mode="json") for i in resp.results],
        }
    )


# ---------------------------------------------------------------------------
# posthog_list_feature_flags
# ---------------------------------------------------------------------------

LIST_FLAGS_SCHEMA = {
    "name": "posthog_list_feature_flags",
    "description": (
        "List feature flags configured in the PostHog project, including "
        "active state and rollout percentage. Useful for correlating a metric "
        "change with a flag rollout in the same window."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 50,
                "minimum": 1,
                "maximum": 200,
            },
            "active_only": {
                "type": "boolean",
                "default": False,
                "description": "When true, filter to flags with active=true.",
            },
        },
        "required": [],
    },
}


def _list_feature_flags(args: dict, **_kw: Any) -> str:
    try:
        limit = int(args.get("limit") or 50)
    except (TypeError, ValueError):
        return tool_error("'limit' must be an integer")
    limit = max(1, min(limit, 200))

    params: dict[str, Any] = {"limit": limit}
    if args.get("active_only") is True:
        params["active"] = "true"

    try:
        body = posthog_client.project_request(
            "GET", "feature_flags/", params=params
        )
    except posthog_client.PostHogClientError as e:
        return _client_error(e)
    try:
        resp = t.ListFeatureFlagsResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from posthog: {e.errors()}", body=body
        )
    return tool_result(
        {
            "count": len(resp.results),
            "flags": [f.model_dump(mode="json") for f in resp.results],
        }
    )


# ---------------------------------------------------------------------------
# posthog_get_dashboard
# ---------------------------------------------------------------------------

GET_DASHBOARD_SCHEMA = {
    "name": "posthog_get_dashboard",
    "description": (
        "Fetch a specific dashboard by numeric id, including its tiles. Use "
        "when Jonathan has a curated dashboard you want to read into a digest "
        "without re-deriving the queries yourself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dashboard_id": {"type": "integer"},
        },
        "required": ["dashboard_id"],
    },
}


def _get_dashboard(args: dict, **_kw: Any) -> str:
    dashboard_id = args.get("dashboard_id")
    if not isinstance(dashboard_id, int):
        return tool_error("'dashboard_id' must be an integer")
    try:
        body = posthog_client.project_request(
            "GET", f"dashboards/{dashboard_id}/"
        )
    except posthog_client.PostHogClientError as e:
        return _client_error(e)
    try:
        resp = t.Dashboard.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from posthog: {e.errors()}", body=body
        )
    return tool_result(resp.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="posthog_query",
    toolset=POSTHOG_TOOLSET,
    schema=QUERY_SCHEMA,
    handler=lambda args, **kw: _query(args, **kw),
    check_fn=posthog_client.check_posthog_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="posthog_list_recordings",
    toolset=POSTHOG_TOOLSET,
    schema=LIST_RECORDINGS_SCHEMA,
    handler=lambda args, **kw: _list_recordings(args, **kw),
    check_fn=posthog_client.check_posthog_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="posthog_list_errors",
    toolset=POSTHOG_TOOLSET,
    schema=LIST_ERRORS_SCHEMA,
    handler=lambda args, **kw: _list_errors(args, **kw),
    check_fn=posthog_client.check_posthog_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="posthog_list_feature_flags",
    toolset=POSTHOG_TOOLSET,
    schema=LIST_FLAGS_SCHEMA,
    handler=lambda args, **kw: _list_feature_flags(args, **kw),
    check_fn=posthog_client.check_posthog_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="posthog_get_dashboard",
    toolset=POSTHOG_TOOLSET,
    schema=GET_DASHBOARD_SCHEMA,
    handler=lambda args, **kw: _get_dashboard(args, **kw),
    check_fn=posthog_client.check_posthog_requirements,
    requires_env=_REQUIRES_ENV,
)
