"""Publisher service tools — caption generation, post queue/publish, ad-hoc ingest, owner DM.

Registers seven tools under the ``publisher`` toolset:

  - ``publisher_generate_caption``     POST /api/captions/generate
  - ``publisher_queue_post``           POST /api/posts/queue
  - ``publisher_publish_post``         POST /api/posts/publish
  - ``publisher_get_post``             GET  /api/posts/:post_id
  - ``publisher_list_pending``         GET  /api/posts?status=...
  - ``publisher_ingest_adhoc``         POST /api/ad-hoc/ingest
  - ``telegram_dm_owner``              thin wrapper over send_message_tool

Inbound publisher → Hermes notifications go through the existing webhook
gateway adapter (``gateway/platforms/webhook.py``). To wire it up, add this
to ~/.hermes/config.yaml on the Railway volume:

    platforms:
      webhook:
        enabled: true
        extra:
          port: 8644
          routes:
            publisher:
              secret: "${PUBLISHER_WEBHOOK_HMAC_SECRET}"
              prompt: |
                New content arrived from the publisher service.

                post_id: {post_id}
                content_type: {content_type}
                source: {source}
                dropbox_path: {dropbox_path}
                is_ad_hoc: {is_ad_hoc}

                Use publisher_generate_caption, evaluate confidence, then
                publisher_queue_post with require_approval=true. Log the
                result with airtable_log_post.
              deliver: log

The publisher signs requests with HMAC-SHA256 over the body using
``PUBLISHER_WEBHOOK_HMAC_SECRET``, sent in the ``X-Webhook-Signature`` header.
"""

import json
import logging
import os
from typing import Any

from pydantic import ValidationError

from tools import publisher_client
from tools import publisher_types as t
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

PUBLISHER_TOOLSET = "publisher"
_REQUIRES_ENV = ["PUBLISHER_BASE_URL", "PUBLISHER_API_KEY"]


def _validation_error(e: ValidationError) -> str:
    return tool_error("invalid arguments", details=e.errors())


def _client_error(e: publisher_client.PublisherClientError) -> str:
    return tool_error(
        f"publisher request failed: {e}", status=e.status, body=e.body
    )


# ---------------------------------------------------------------------------
# publisher_generate_caption
# ---------------------------------------------------------------------------

GENERATE_CAPTION_SCHEMA = {
    "name": "publisher_generate_caption",
    "description": (
        "Ask the publisher service to generate a caption for media at a "
        "Dropbox path. Returns caption text, hashtags, and a confidence score "
        "(0-1). Use the confidence to decide whether to regenerate with more "
        "context or proceed to queue."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "media_path": {
                "type": "string",
                "description": "Dropbox path to the file (video/static) or folder (carousel).",
            },
            "content_type": {
                "type": "string",
                "enum": t.CONTENT_TYPE_VALUES,
            },
            "target_platforms": {
                "type": "array",
                "items": {"type": "string", "enum": t.PLATFORM_VALUES},
            },
            "context": {
                "type": "string",
                "description": "Optional extra context to inject into the caption prompt.",
            },
        },
        "required": ["media_path", "content_type", "target_platforms"],
    },
}


def _generate_caption(args: dict, **_kw: Any) -> str:
    try:
        req = t.GenerateCaptionRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = publisher_client.request(
            "POST", "/api/captions/generate", json=req.model_dump(exclude_none=True)
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.GenerateCaptionResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# publisher_queue_post
# ---------------------------------------------------------------------------

QUEUE_POST_SCHEMA = {
    "name": "publisher_queue_post",
    "description": (
        "Queue a post in the publisher service. With require_approval=true, "
        "the post lands in the Discord approval queue. Ad-hoc posts are "
        "always forced through approval regardless of this flag."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dropbox_root_path": {
                "type": "string",
                "description": "Dropbox path (file for video/static, folder for carousel).",
            },
            "content_type": {"type": "string", "enum": t.CONTENT_TYPE_VALUES},
            "caption": {"type": "string"},
            "platforms": {
                "type": "array",
                "items": {"type": "string", "enum": t.PLATFORM_VALUES},
            },
            "require_approval": {"type": "boolean"},
            "source": {"type": "string", "enum": t.POST_SOURCE_VALUES},
        },
        "required": [
            "dropbox_root_path",
            "content_type",
            "caption",
            "platforms",
            "require_approval",
            "source",
        ],
    },
}


def _queue_post(args: dict, **_kw: Any) -> str:
    try:
        req = t.QueuePostRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = publisher_client.request(
            "POST", "/api/posts/queue", json=req.model_dump()
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.QueuePostResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# publisher_publish_post
# ---------------------------------------------------------------------------

PUBLISH_POST_SCHEMA = {
    "name": "publisher_publish_post",
    "description": (
        "Publish a queued post immediately, bypassing the approval gate. "
        "Use only for posts that have already been approved."
    ),
    "parameters": {
        "type": "object",
        "properties": {"post_id": {"type": "string"}},
        "required": ["post_id"],
    },
}


def _publish_post(args: dict, **_kw: Any) -> str:
    try:
        req = t.PublishPostRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = publisher_client.request(
            "POST", "/api/posts/publish", json=req.model_dump()
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.PublishPostResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# publisher_get_post
# ---------------------------------------------------------------------------

GET_POST_SCHEMA = {
    "name": "publisher_get_post",
    "description": "Fetch the full record for a single post including status history.",
    "parameters": {
        "type": "object",
        "properties": {"post_id": {"type": "string"}},
        "required": ["post_id"],
    },
}


def _get_post(args: dict, **_kw: Any) -> str:
    post_id = (args.get("post_id") or "").strip()
    if not post_id:
        return tool_error("'post_id' is required")
    try:
        body = publisher_client.request("GET", f"/api/posts/{post_id}")
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.Post.model_validate(body)
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(resp.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# publisher_list_pending
# ---------------------------------------------------------------------------

LIST_PENDING_SCHEMA = {
    "name": "publisher_list_pending",
    "description": (
        "List posts in the publisher service. Defaults to status=pending_approval "
        "for checking what's stuck waiting for review."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": t.POST_STATUS_VALUES,
                "default": "pending_approval",
            },
            "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
        },
        "required": [],
    },
}


def _list_pending(args: dict, **_kw: Any) -> str:
    status = (args.get("status") or "pending_approval").strip()
    if status not in t.POST_STATUS_VALUES:
        return tool_error(f"invalid status: {status}", allowed=t.POST_STATUS_VALUES)
    try:
        limit = int(args.get("limit") or 20)
    except (TypeError, ValueError):
        return tool_error("'limit' must be an integer")
    limit = max(1, min(limit, 100))
    try:
        body = publisher_client.request(
            "GET", "/api/posts", params={"status": status, "limit": limit}
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)

    # Publisher may return a bare list or a wrapped object — accept both.
    posts_raw = body if isinstance(body, list) else body.get("posts", [])
    try:
        posts = [t.Post.model_validate(p) for p in posts_raw]
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(
        {"count": len(posts), "posts": [p.model_dump(mode="json") for p in posts]}
    )


# ---------------------------------------------------------------------------
# publisher_ingest_adhoc
# ---------------------------------------------------------------------------

INGEST_ADHOC_SCHEMA = {
    "name": "publisher_ingest_adhoc",
    "description": (
        "Ingest ad-hoc media (clip Jonathan dropped, screenshot, etc.) into the "
        "standard /content/ad-hoc/ Dropbox structure. Provide either source_url "
        "OR dropbox_path, plus content_type and optional notes for caption context. "
        "Returns the normalized media_path; pass that to publisher_generate_caption "
        "and publisher_queue_post next. Ad-hoc posts always require approval."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content_type": {"type": "string", "enum": t.CONTENT_TYPE_VALUES},
            "source_url": {
                "type": "string",
                "description": "Direct URL to media (signed Dropbox link, Discord attachment, etc.).",
            },
            "dropbox_path": {
                "type": "string",
                "description": "Existing Dropbox path to copy/normalize.",
            },
            "notes": {
                "type": "string",
                "description": "Free-form context for the caption prompt.",
            },
        },
        "required": ["content_type"],
    },
}


def _ingest_adhoc(args: dict, **_kw: Any) -> str:
    try:
        req = t.IngestAdHocRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    if not req.source_url and not req.dropbox_path:
        return tool_error("provide either 'source_url' or 'dropbox_path'")
    try:
        body = publisher_client.request(
            "POST", "/api/ad-hoc/ingest", json=req.model_dump(exclude_none=True)
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.IngestAdHocResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(f"invalid response from publisher: {e.errors()}", body=body)
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# publisher_quick_post — one-shot ad-hoc post (upload + caption.md + ingest)
# ---------------------------------------------------------------------------

QUICK_POST_SCHEMA = {
    "name": "publisher_quick_post",
    "description": (
        "Post ad-hoc creative AFTER Jonathan has approved a caption "
        "(e.g., he picked from your 3 variations in chat). Provide the "
        "media URLs (Telegram file URLs via getFile work), the approved "
        "caption text, optional hashtags + title. For the ad-hoc chat "
        "flow pass auto_publish=true: Jonathan's caption choice IS his "
        "approval, so the publisher skips its own Telegram DM and ships "
        "to IG + TikTok in ~30s. Only set auto_publish=false if there's "
        "a specific reason to route through the publisher bot's separate "
        "approval gate.\n\n"
        "brand/cta default to 'hankai' and 'book-demo'. angle is required and "
        "should be a short slug describing the post (e.g., 'emergency-storm-promo'). "
        "No underscores or spaces in brand/angle/cta. Use hyphens. The folder "
        "path gets a server-side timestamp suffix so repeat calls always create "
        "fresh posts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "angle": {
                "type": "string",
                "description": "Short slug for the post angle (e.g., 'emergency-storm-promo'). Hyphens OK, no underscores.",
            },
            "media_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-10 publicly fetchable HTTPS URLs to the media (Telegram file URLs, Dropbox temporary links, etc.). Order matters for carousels.",
                "minItems": 1,
                "maxItems": 10,
            },
            "caption": {
                "type": "string",
                "description": "The caption Jonathan approved (typically the variation he picked from your 3 drafts). Must contain non-whitespace content.",
            },
            "title": {
                "type": "string",
                "description": "Optional short headline. Only displayed by TikTok on carousel posts; ignored elsewhere.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hashtags WITHOUT leading '#'. The publisher prepends '#' server-side. Optional.",
            },
            "brand": {
                "type": "string",
                "description": "Brand segment of the ad-hoc folder name. Default 'hankai'.",
                "default": "hankai",
            },
            "cta": {
                "type": "string",
                "description": "CTA segment of the ad-hoc folder name. Default 'book-demo'.",
                "default": "book-demo",
            },
            "auto_publish": {
                "type": "boolean",
                "description": "When true, publisher skips its Telegram approval DM and ships immediately to IG + TikTok. Use true for the ad-hoc chat flow where Jonathan already approved the caption in chat. Default false.",
                "default": False,
            },
        },
        "required": ["angle", "media_urls", "caption"],
    },
}


def _quick_post(args: dict, **_kw: Any) -> str:
    try:
        req = t.QuickPostRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)
    try:
        body = publisher_client.request(
            "POST",
            "/api/ad-hoc/quick-post",
            json=req.model_dump(exclude_none=True),
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)
    try:
        resp = t.QuickPostResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from publisher: {e.errors()}", body=body
        )
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# publisher_quick_post_file — multipart upload variant for Telegram-cached
# photos that don't have a public URL
# ---------------------------------------------------------------------------

QUICK_POST_FILE_SCHEMA = {
    "name": "publisher_quick_post_file",
    "description": (
        "Same as publisher_quick_post but for local file paths instead of "
        "URLs. Use this when Jonathan sends photos via Telegram — the adapter "
        "caches them at /opt/data/cache/images/img_<hash>.jpg without "
        "exposing a public URL. This tool reads each path and ships the bytes "
        "directly to the publisher via multipart upload.\n\n"
        "Workflow: after Jonathan picks one of your 3 caption variations, "
        "find the cached file path(s) for the photos he attached and pass "
        "them in media_file_paths. The publisher uploads to Dropbox, writes "
        "caption.md, and (with auto_publish=true) ships to IG + TikTok in "
        "~30s. Same defaults and validation rules as publisher_quick_post."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "angle": {
                "type": "string",
                "description": "Short slug for the post angle (e.g., 'emergency-storm-promo'). Hyphens OK, no underscores.",
            },
            "media_file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1-10 absolute paths to local files on the Hermes container (typically /opt/data/cache/images/img_<hash>.<ext>). Order matters for carousels.",
                "minItems": 1,
                "maxItems": 10,
            },
            "caption": {
                "type": "string",
                "description": "The caption Jonathan approved (typically the variation he picked from your 3 drafts). Must contain non-whitespace content.",
            },
            "title": {
                "type": "string",
                "description": "Optional short headline. Only displayed by TikTok on carousel posts.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hashtags WITHOUT leading '#'. The publisher prepends '#' server-side.",
            },
            "brand": {
                "type": "string",
                "description": "Brand segment of the ad-hoc folder name. Default 'hankai'.",
                "default": "hankai",
            },
            "cta": {
                "type": "string",
                "description": "CTA segment of the ad-hoc folder name. Default 'book-demo'.",
                "default": "book-demo",
            },
            "auto_publish": {
                "type": "boolean",
                "description": "When true, publisher skips its Telegram approval DM and ships immediately. Use true for the ad-hoc chat flow.",
                "default": False,
            },
        },
        "required": ["angle", "media_file_paths", "caption"],
    },
}


_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


def _quick_post_file(args: dict, **_kw: Any) -> str:
    try:
        req = t.QuickPostFileRequest.model_validate(args)
    except ValidationError as e:
        return _validation_error(e)

    # Read each file. Surface a clean error for missing paths rather
    # than letting OSError bubble up — agents iterate better on tool
    # errors than tracebacks.
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for p in req.media_file_paths:
        if not os.path.isfile(p):
            return tool_error(
                f"file not found: {p}",
                hint="Telegram-cached photos live under /opt/data/cache/images/",
            )
        try:
            with open(p, "rb") as f:
                content = f.read()
        except OSError as e:
            return tool_error(f"could not read {p}: {e}")
        ext = os.path.splitext(p)[1].lower()
        mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
        filename = os.path.basename(p)
        files.append(("media", (filename, content, mime)))

    # Form fields are always strings on the multipart side; the
    # publisher's handler JSON-parses hashtags and string-compares
    # auto_publish.
    data: dict[str, str] = {
        "angle": req.angle,
        "caption": req.caption,
        "brand": req.brand,
        "cta": req.cta,
        "hashtags": json.dumps(req.hashtags),
        "auto_publish": "true" if req.auto_publish else "false",
    }
    if req.title is not None:
        data["title"] = req.title

    try:
        body = publisher_client.request_multipart(
            "/api/ad-hoc/quick-post-file", files=files, data=data
        )
    except publisher_client.PublisherClientError as e:
        return _client_error(e)

    try:
        resp = t.QuickPostResponse.model_validate(body)
    except ValidationError as e:
        return tool_error(
            f"invalid response from publisher: {e.errors()}", body=body
        )
    return tool_result(resp.model_dump())


# ---------------------------------------------------------------------------
# telegram_dm_owner — thin wrapper over send_message_tool
# ---------------------------------------------------------------------------

TELEGRAM_DM_OWNER_SCHEMA = {
    "name": "telegram_dm_owner",
    "description": (
        "DM the owner (Jonathan) on Telegram. Use for nudges about pending "
        "approvals, summaries of recent activity, and ad-hoc clarifications. "
        "The recipient is read from TELEGRAM_OWNER_USER_ID at call time. "
        "Supports MEDIA:<local_path> in the message body to attach files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message text to send."},
        },
        "required": ["message"],
    },
}


def _check_telegram_dm_owner_requirements() -> bool:
    return bool(os.getenv("TELEGRAM_OWNER_USER_ID"))


def _telegram_dm_owner(args: dict, **kw: Any) -> str:
    user_id = (os.getenv("TELEGRAM_OWNER_USER_ID") or "").strip()
    if not user_id:
        return tool_error("TELEGRAM_OWNER_USER_ID is not set")
    message = (args.get("message") or "").strip()
    if not message:
        return tool_error("'message' is required")

    from tools.send_message_tool import send_message_tool

    return send_message_tool(
        {
            "action": "send",
            "target": f"telegram:{user_id}",
            "message": message,
        },
        **kw,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
# Order matters: the FIRST tool registered with a check_fn becomes the
# toolset's availability check (see ToolRegistry.register). We want the
# toolset gated on PUBLISHER_BASE_URL + PUBLISHER_API_KEY, so the first
# registration here uses ``check_publisher_requirements``.

registry.register(
    name="publisher_generate_caption",
    toolset=PUBLISHER_TOOLSET,
    schema=GENERATE_CAPTION_SCHEMA,
    handler=lambda args, **kw: _generate_caption(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_queue_post",
    toolset=PUBLISHER_TOOLSET,
    schema=QUEUE_POST_SCHEMA,
    handler=lambda args, **kw: _queue_post(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_publish_post",
    toolset=PUBLISHER_TOOLSET,
    schema=PUBLISH_POST_SCHEMA,
    handler=lambda args, **kw: _publish_post(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_get_post",
    toolset=PUBLISHER_TOOLSET,
    schema=GET_POST_SCHEMA,
    handler=lambda args, **kw: _get_post(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_list_pending",
    toolset=PUBLISHER_TOOLSET,
    schema=LIST_PENDING_SCHEMA,
    handler=lambda args, **kw: _list_pending(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_ingest_adhoc",
    toolset=PUBLISHER_TOOLSET,
    schema=INGEST_ADHOC_SCHEMA,
    handler=lambda args, **kw: _ingest_adhoc(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_quick_post",
    toolset=PUBLISHER_TOOLSET,
    schema=QUICK_POST_SCHEMA,
    handler=lambda args, **kw: _quick_post(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="publisher_quick_post_file",
    toolset=PUBLISHER_TOOLSET,
    schema=QUICK_POST_FILE_SCHEMA,
    handler=lambda args, **kw: _quick_post_file(args, **kw),
    check_fn=publisher_client.check_publisher_requirements,
    requires_env=_REQUIRES_ENV,
)

registry.register(
    name="telegram_dm_owner",
    toolset=PUBLISHER_TOOLSET,
    schema=TELEGRAM_DM_OWNER_SCHEMA,
    handler=lambda args, **kw: _telegram_dm_owner(args, **kw),
    check_fn=_check_telegram_dm_owner_requirements,
    requires_env=["TELEGRAM_OWNER_USER_ID"],
)
