#!/bin/bash
# Docker/Podman entrypoint: bootstrap config files into the mounted volume, then run hermes.
set -e

HERMES_HOME="${HERMES_HOME:-/opt/data}"
INSTALL_DIR="/opt/hermes"

# --- Privilege dropping via gosu ---
# When started as root (the default for Docker, or fakeroot in rootless Podman),
# optionally remap the hermes user/group to match host-side ownership, fix volume
# permissions, then re-exec as hermes.
if [ "$(id -u)" = "0" ]; then
    if [ -n "$HERMES_UID" ] && [ "$HERMES_UID" != "$(id -u hermes)" ]; then
        echo "Changing hermes UID to $HERMES_UID"
        usermod -u "$HERMES_UID" hermes
    fi

    if [ -n "$HERMES_GID" ] && [ "$HERMES_GID" != "$(id -g hermes)" ]; then
        echo "Changing hermes GID to $HERMES_GID"
        # -o allows non-unique GID (e.g. macOS GID 20 "staff" may already exist
        # as "dialout" in the Debian-based container image)
        groupmod -o -g "$HERMES_GID" hermes 2>/dev/null || true
    fi

    # Fix ownership of the data volume. When HERMES_UID remaps the hermes user,
    # files created by previous runs (under the old UID) become inaccessible.
    # Always chown -R when UID was remapped; otherwise only if top-level is wrong.
    actual_hermes_uid=$(id -u hermes)
    needs_chown=false
    if [ -n "$HERMES_UID" ] && [ "$HERMES_UID" != "10000" ]; then
        needs_chown=true
    elif [ "$(stat -c %u "$HERMES_HOME" 2>/dev/null)" != "$actual_hermes_uid" ]; then
        needs_chown=true
    fi
    if [ "$needs_chown" = true ]; then
        echo "Fixing ownership of $HERMES_HOME to hermes ($actual_hermes_uid)"
        # In rootless Podman the container's "root" is mapped to an unprivileged
        # host UID — chown will fail.  That's fine: the volume is already owned
        # by the mapped user on the host side.
        chown -R hermes:hermes "$HERMES_HOME" 2>/dev/null || \
            echo "Warning: chown failed (rootless container?) — continuing anyway"
    fi

    # Ensure config.yaml is readable by the hermes runtime user even if it was
    # edited on the host after initial ownership setup. Must run here (as root)
    # rather than after the gosu drop, otherwise a non-root caller like
    # `docker run -u $(id -u):$(id -g)` hits "Operation not permitted" (#15865).
    if [ -f "$HERMES_HOME/config.yaml" ]; then
        chown hermes:hermes "$HERMES_HOME/config.yaml" 2>/dev/null || true
        chmod 640 "$HERMES_HOME/config.yaml" 2>/dev/null || true
    fi

    echo "Dropping root privileges"
    exec gosu hermes "$0" "$@"
fi

# --- Running as hermes from here ---
source "${INSTALL_DIR}/.venv/bin/activate"

# Create essential directory structure.  Cache and platform directories
# (cache/images, cache/audio, platforms/whatsapp, etc.) are created on
# demand by the application — don't pre-create them here so new installs
# get the consolidated layout from get_hermes_dir().
# The "home/" subdirectory is a per-profile HOME for subprocesses (git,
# ssh, gh, npm …).  Without it those tools write to /root which is
# ephemeral and shared across profiles.  See issue #4426.
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}

# .env
if [ ! -f "$HERMES_HOME/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$HERMES_HOME/.env"
fi

# config.yaml
if [ ! -f "$HERMES_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
fi

# Idempotently inject the publisher webhook stanza into config.yaml.
# Runs only when PUBLISHER_WEBHOOK_HMAC_SECRET is set and the route isn't
# already present, so manual edits and reruns are safe.
if [ -n "$PUBLISHER_WEBHOOK_HMAC_SECRET" ] && \
   [ -f "$HERMES_HOME/config.yaml" ] && \
   ! grep -q "^        publisher:" "$HERMES_HOME/config.yaml"; then
    echo "Injecting publisher webhook stanza into $HERMES_HOME/config.yaml"
    cat >> "$HERMES_HOME/config.yaml" <<EOF

platforms:
  webhook:
    enabled: true
    extra:
      port: 8080
      routes:
        publisher:
          secret: "$PUBLISHER_WEBHOOK_HMAC_SECRET"
          prompt: |
            Publisher event: {event_type}
            Post ID: {post_id}
            Content type: {content_type}
            Source: {source}
            Dropbox path: {dropbox_path}
            Ad-hoc: {is_ad_hoc}
          deliver: "log"
EOF
fi

# Idempotently inject the PostHog MCP server stanza into config.yaml.
# Runs only when POSTHOG_PERSONAL_API_KEY is set and the server isn't already
# registered, so manual edits and reruns are safe. The values are written as
# ${VAR} templates so Hermes's _expand_env_vars() substitutes them at config
# load time — no secrets get baked into config.yaml on disk.
if [ -n "$POSTHOG_PERSONAL_API_KEY" ] && \
   [ -f "$HERMES_HOME/config.yaml" ] && \
   ! grep -q "# --- posthog mcp (managed) ---" "$HERMES_HOME/config.yaml"; then
    echo "Injecting PostHog MCP stanza into $HERMES_HOME/config.yaml"
    HERMES_HOME="$HERMES_HOME" python3 <<'PY_EOF'
import os
from pathlib import Path

path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
text = path.read_text(encoding="utf-8")

block = """
# --- posthog mcp (managed) ---
# Injected by docker/entrypoint.sh when POSTHOG_PERSONAL_API_KEY is set.
# Edit-safe: the entrypoint won't touch this once present. To remove, delete
# from "# --- posthog mcp (managed) ---" through the closing "# --- end posthog mcp ---".
mcp_servers:
  posthog:
    url: https://mcp.posthog.com/mcp/
    transport: streamable-http
    headers:
      Authorization: "Bearer ${POSTHOG_PERSONAL_API_KEY}"
    pinned_context:
      projectId: "${POSTHOG_PROJECT_ID}"
# --- end posthog mcp ---
"""

# If there's already an mcp_servers: block, splice the posthog entry under it.
# Otherwise append the whole managed block at EOF.
lines = text.splitlines(keepends=True)
mcp_idx = None
for i, line in enumerate(lines):
    stripped = line.rstrip("\n")
    if stripped == "mcp_servers:" or stripped.startswith("mcp_servers:"):
        mcp_idx = i
        break

if mcp_idx is None:
    # No existing top-level mcp_servers — append the whole block
    if not text.endswith("\n"):
        text += "\n"
    text += block
else:
    # Existing mcp_servers — only splice if it's block style. Flow-style
    # variants like `mcp_servers: {}` or `mcp_servers: {github: {...}}`
    # would produce invalid YAML if we inserted indented block children
    # under them, so we bail with a clear message instead.
    head = lines[mcp_idx]
    after_colon = head.split(":", 1)[1] if ":" in head else ""
    after_colon = after_colon.split("#", 1)[0].strip()  # ignore trailing comment
    if after_colon:
        import sys
        print(
            f"entrypoint: refusing to splice into flow-style/scalar mcp_servers "
            f"in {path} (line {mcp_idx + 1}: {head.rstrip()!r}). "
            f"Add the posthog stanza manually, or convert mcp_servers to "
            f"block style and re-run.",
            file=sys.stderr,
        )
        raise SystemExit(0)
    # Block style — insert the posthog entry just after the key line.
    insert = """  # --- posthog mcp (managed) ---
  posthog:
    url: https://mcp.posthog.com/mcp/
    transport: streamable-http
    headers:
      Authorization: "Bearer ${POSTHOG_PERSONAL_API_KEY}"
    pinned_context:
      projectId: "${POSTHOG_PROJECT_ID}"
  # --- end posthog mcp ---
"""
    lines.insert(mcp_idx + 1, insert)
    text = "".join(lines)

path.write_text(text, encoding="utf-8")
print(f"entrypoint: posthog mcp stanza injected into {path}")
PY_EOF
fi

# SOUL.md
if [ ! -f "$HERMES_HOME/SOUL.md" ]; then
    cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"
fi

# Idempotently patch the marketing-voice files so the publisher_quick_post
# workflow doesn't conflict with the "drafts only, never post live" rules.
# Replacements only fire when the exact OLD strings are still present —
# once changed, this block becomes a no-op. If Jonathan rewrites the
# rules in his own wording, we leave them alone.
if [ -f "$HERMES_HOME/SOUL.md" ] || [ -f "$HERMES_HOME/AGENTS.md" ]; then
    HERMES_HOME="$HERMES_HOME" python3 <<'PY_EOF'
import os
HOME = os.environ.get("HERMES_HOME", "/opt/data")

def patch(path, edits):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        s = f.read()
    changed = False
    for old, new in edits:
        if old in s:
            s = s.replace(old, new)
            changed = True
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"entrypoint: patched publisher_quick_post carve-out into {path}")

patch(
    f"{HOME}/SOUL.md",
    [
        (
            "You never publish, send, or post anything live. Jonathan approves everything. Drafts only.",
            "You never publish content directly. Jonathan approves every post before it goes live. "
            "For ad-hoc social posts: read the image, draft 3 caption variations, let Jonathan pick one in chat, "
            "then call publisher_quick_post with auto_publish=true. His chat-side pick IS the approval, "
            "so the publisher skips its own Telegram DM and ships. This is the gate, not a bypass.",
        ),
    ],
)

patch(
    f"{HOME}/AGENTS.md",
    [
        (
            "- Save all drafts to the location Jonathan specifies (Notion, Airtable, etc.). Never publish or post anything.",
            "- For ad-hoc social posts (Jonathan DMs photos asking to post): draft 3 caption variations in chat, "
            "wait for him to pick, then call publisher_quick_post with auto_publish=true. The publisher uploads "
            "to Dropbox, writes caption.md, and ships to IG + TikTok. Do not also save to Airtable. "
            "For all other drafts (blog, ads, email, research): save to the location Jonathan specifies.",
        ),
        (
            "- Never auto-publish, auto-send, or auto-post. Drafts only.",
            "- Never auto-publish without Jonathan's review. For ad-hoc social posts, his pick from your 3 "
            "caption variations IS the review, and publisher_quick_post(auto_publish=true) is how you ship "
            "the picked caption. For everything else: drafts only, no auto-send.",
        ),
    ],
)
PY_EOF
fi

# Sync bundled skills (manifest-based so user edits are preserved)
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

# Final exec: two supported invocation patterns.
#
#   docker run <image>                 -> exec `hermes` with no args (legacy default)
#   docker run <image> chat -q "..."   -> exec `hermes chat -q "..."` (legacy wrap)
#   docker run <image> sleep infinity  -> exec `sleep infinity` directly
#   docker run <image> bash            -> exec `bash` directly
#
# If the first positional arg resolves to an executable on PATH, we assume the
# caller wants to run it directly (needed by the launcher which runs long-lived
# `sleep infinity` sandbox containers — see tools/environments/docker.py).
# Otherwise we treat the args as a hermes subcommand and wrap with `hermes`,
# preserving the documented `docker run <image> <subcommand>` behavior.
if [ $# -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
    exec "$@"
fi
exec hermes "$@"
