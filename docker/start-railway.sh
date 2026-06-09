#!/bin/bash
# Railway start command for the Hermes agents (Social + Web/Analytics/Ads).
#
# The GATEWAY (Telegram + cron) is the critical path and runs first, independent
# of Tailscale. The DASHBOARD (web API for Hermes Desktop) is exposed privately
# over Tailscale on a best-effort basis: if Tailscale or the dashboard fails, the
# gateway/crons keep running.
#
# NOTE: intentionally NOT `set -e` — a Tailscale/dashboard hiccup must not abort
# the gateway. See docs/superpowers/plans/2026-06-08-split-hermes-agents.md (Task 3).
set -uo pipefail

HERMES_BIN=/opt/hermes/.venv/bin/hermes
TS_SOCK=/opt/data/tailscaled.sock

# --- Gateway first (critical) ---
"$HERMES_BIN" gateway run &
GATEWAY_PID=$!

# Liveness watcher: bring the container down (signal tini, PID 1) the moment the
# gateway dies — even if a Tailscale step below is blocked — so Railway restarts
# it instead of leaving a gateway-less container "up".
( while kill -0 "$GATEWAY_PID" 2>/dev/null; do sleep 5; done
  echo "gateway exited — stopping container"; kill -TERM 1 ) &

# --- Tailscale + dashboard (best-effort; only when TS_AUTHKEY is provided) ---
# Until TS_AUTHKEY is set, the container simply runs the gateway (same as before),
# so this change is safe to deploy before the operator provisions Tailscale.
if [ -n "${TS_AUTHKEY:-}" ] && command -v tailscaled >/dev/null 2>&1; then
  # Userspace networking: Railway containers have no TUN device. Use --statedir
  # (a directory, not --state=<file>) so Tailscale has a writable var root for
  # HTTPS certs (`tailscale serve` needs it; --state alone gives "no
  # TailscaleVarRoot"). On the volume so the non-root hermes user can write it
  # and the node identity + cert persist across redeploys.
  mkdir -p /opt/data/tailscale
  tailscaled --tun=userspace-networking \
    --statedir=/opt/data/tailscale --socket="$TS_SOCK" &

  # Wait for the daemon socket before `tailscale up` (avoids a boot race).
  for _ in $(seq 1 30); do
    tailscale --socket="$TS_SOCK" status >/dev/null 2>&1 && break
    sleep 1
  done

  timeout 30 tailscale --socket="$TS_SOCK" up --authkey="${TS_AUTHKEY}" \
    --hostname="${TS_HOSTNAME:-hank-${RAILWAY_SERVICE_NAME:-hermes}}" \
    || echo "WARN: tailscale up failed/timed out — dashboard unreachable; gateway continues"

  # Bind 0.0.0.0 (--insecure), NOT loopback: the dashboard's Host-header guard
  # only accepts the bound host, and `tailscale serve` forwards the original Host
  # (the MagicDNS name) — binding 0.0.0.0 is the documented opt-in that accepts
  # a proxied Host. Still private: Railway maps no public port and `tailscale
  # serve` is the only inbound path. HERMES_WEB_DIST is baked into the image.
  # --tui enables the embedded chat surface; without it the live /api/ws socket
  # Hermes Desktop opens is rejected (4403), so HTTP connects but the WebSocket
  # fails. See web_server.py gateway_ws().
  "$HERMES_BIN" dashboard --no-open --insecure --tui --host 0.0.0.0 --port 9119 &

  # Publish on the tailnet two ways: HTTPS at the root (browser-friendly) and
  # plain HTTP on :9119 — the form Hermes Desktop expects (its client resets the
  # serve TLS handshake, so it needs the HTTP endpoint). Tailnet traffic is
  # WireGuard-encrypted either way.
  timeout 15 tailscale --socket="$TS_SOCK" serve --bg 9119 \
    || echo "WARN: tailscale serve (https) failed/timed out"
  timeout 15 tailscale --socket="$TS_SOCK" serve --bg --http=9119 http://127.0.0.1:9119 \
    || echo "WARN: tailscale serve (http :9119) failed/timed out"
else
  echo "INFO: TS_AUTHKEY unset or tailscale missing — running gateway only (no dashboard)"
fi

# Foreground: the container lives as long as the gateway lives. The watcher above
# is the backstop in case anything before this point had blocked.
wait "$GATEWAY_PID"
