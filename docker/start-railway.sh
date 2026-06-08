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
  # Userspace networking: Railway containers have no TUN device. State + socket
  # live on the volume so the non-root hermes user can write them.
  tailscaled --tun=userspace-networking \
    --state=/opt/data/tailscaled.state --socket="$TS_SOCK" &

  # Wait for the daemon socket before `tailscale up` (avoids a boot race).
  for _ in $(seq 1 30); do
    tailscale --socket="$TS_SOCK" status >/dev/null 2>&1 && break
    sleep 1
  done

  timeout 30 tailscale --socket="$TS_SOCK" up --authkey="${TS_AUTHKEY}" \
    --hostname="${TS_HOSTNAME:-hank-${RAILWAY_SERVICE_NAME:-hermes}}" \
    || echo "WARN: tailscale up failed/timed out — dashboard unreachable; gateway continues"

  # The tailnet IP is virtual in userspace mode and NOT bindable, so the dashboard
  # binds loopback and `tailscale serve` proxies inbound tailnet traffic to it.
  # HERMES_WEB_DIST is already baked into the image (/opt/hermes/hermes_cli/web_dist).
  "$HERMES_BIN" dashboard --no-open --host 127.0.0.1 --port 9119 &

  timeout 15 tailscale --socket="$TS_SOCK" serve --bg 9119 \
    || echo "WARN: tailscale serve failed/timed out — dashboard not on tailnet"
else
  echo "INFO: TS_AUTHKEY unset or tailscale missing — running gateway only (no dashboard)"
fi

# Foreground: the container lives as long as the gateway lives. The watcher above
# is the backstop in case anything before this point had blocked.
wait "$GATEWAY_PID"
