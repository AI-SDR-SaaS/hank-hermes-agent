# Split Hermes Agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the overloaded single Hermes agent into two focused Hermes agents (Social, and Web/Analytics/Ads) plus the unchanged publisher, each managed via Hermes Desktop.

**Architecture:** One engine repo (`hank-hermes-agent`) builds both Hermes services; they are differentiated only by Railway env vars + per-volume config. Each service runs `hermes gateway run` (Telegram + cron) and `hermes dashboard` (the web API Hermes Desktop connects to) together. **Dashboards are Tailscale-private** — each container joins the tailnet via `tailscaled` and the dashboard binds to the node's tailnet IP (no public Railway port). Hermes Desktop reaches each dashboard over the tailnet by MagicDNS name. Cutover is sequenced so the new Social agent is fully proven before social capabilities are removed from `kind-generosity`.

**Tech Stack:** Hermes (Python) engine, Railway (deploy + volumes + env), Railway GraphQL API + CLI, Tailscale (userspace networking in-container for private dashboard access), Telegram BotFather, Hermes Desktop, Dropbox (file-transfer bridge between volumes — already integrated).

**Spec:** `docs/superpowers/specs/2026-06-08-split-hermes-agents-design.md`

**Conventions used below:**
- `KG` = current service `hank-hermes-agent` (project `kind-generosity`, service `e7d29fc1-9dd0-4715-98af-3b7fe9d5e567`).
- `SOC` = the new Social service (created in Task 5).
- Run `railway link` to point the CLI at the intended service before service-scoped commands, or pass `--service <id>`.
- "Verify" steps are this plan's tests: run the command, confirm the expected output before moving on.

---

## Phase 0 — Inventory & prerequisites

### Task 1: Enumerate the current agent's crons, toolsets, and skills (name-only)

**Files:** none (produces `docs/superpowers/plans/inventory-2026-06-08.md`, a working note).

> `hermes` is not on the SSH `$PATH` — use the full venv path `/opt/hermes/.venv/bin/hermes`.
> On Windows, run these via PowerShell, not Git Bash (Git Bash mangles `/opt/...` paths).
> There is **no `hermes toolsets` subcommand** — enabled toolsets live in `config.yaml`.

- [ ] **Step 1: One-shot SSH into KG and list crons**

```powershell
railway link   # choose: kind-generosity → production → hank-hermes-agent
railway ssh "/opt/hermes/.venv/bin/hermes cron list"
```
Expected: a table of cron jobs with names/IDs/schedules. Record each.

- [ ] **Step 2: List installed skills and enabled toolsets**

```powershell
railway ssh "/opt/hermes/.venv/bin/hermes skills list"
railway ssh "grep -A40 '^toolsets:' /opt/data/config.yaml"   # toolset NAMES only (no secret values)
```
Expected: skill names (local Hank skills are the split signal); toolset names from config.

- [ ] **Step 3: List configured MCP servers (to catch the Higgsfield noise)**

```powershell
railway ssh "/opt/hermes/.venv/bin/hermes mcp list"
```
Expected: includes a Higgsfield entry (the headless-OAuth loop). Note it for Task 12.

- [ ] **Step 4: Classify each item Social vs Web and write the inventory note**

Create `docs/superpowers/plans/inventory-2026-06-08.md` with three columns: item | current | target-agent (social/web/both/drop). Use the spec's assignment table as the guide (Fastlane + captions + publisher tools → social; PostHog + website edit loop → web). Flag anything ambiguous for a human decision.

- [ ] **Step 5: Commit the inventory note**

```bash
git add docs/superpowers/plans/inventory-2026-06-08.md
git commit -m "docs: inventory of live crons/toolsets/skills for the agent split"
```

### Task 2: Create the new "Hank Social" Telegram bot

**Files:** none (produces a secret token, stored in Railway in Task 6).

- [ ] **Step 1: Create the bot**

In Telegram, message **@BotFather** → `/newbot` → name it (e.g. "Hank Social") → choose a username ending in `bot`. Copy the HTTP API token.

- [ ] **Step 2: Stash the token safely**

Do NOT put the token in git. Hold it for Task 6 (set as `TELEGRAM_BOT_TOKEN` on `SOC`). Confirm the token works:

```bash
curl -s "https://api.telegram.org/bot<NEW_TOKEN>/getMe"
```
Expected: `{"ok":true,...,"username":"<your_bot>"}`.

---

## Phase 1 — Make Hermes services Desktop-connectable

### Task 3: Add a combined gateway + dashboard start script

**Files:**
- Create: `docker/start-railway.sh`
- Modify: `railway.toml` (the `startCommand`)
- Modify: `Dockerfile` (install Tailscale; mark the script executable)

- [ ] **Step 1: Write the start script (Tailscale-private dashboard)**

```bash
#!/bin/bash
# Railway start: gateway (Telegram + cron) is the CRITICAL path and runs first,
# independent of Tailscale. The dashboard (web API for Hermes Desktop) is exposed
# privately over Tailscale on a best-effort basis — if Tailscale or the dashboard
# fails, the gateway/crons keep running.
#
# NOTE: not `set -e` — Tailscale/dashboard hiccups must not abort the gateway.
set -uo pipefail

# --- Gateway first (critical) ---
hermes gateway run &
GATEWAY_PID=$!

# Track gateway liveness IMMEDIATELY (before any Tailscale work): if the gateway
# dies at any point — even while a Tailscale step is blocked — bring the container
# down so Railway restarts it. `kill -TERM 1` signals tini (PID 1).
( while kill -0 "$GATEWAY_PID" 2>/dev/null; do sleep 5; done
  echo "gateway exited — stopping container"; kill -TERM 1 ) &

# --- Tailscale (best-effort, time-bounded so a hang can't mask a dead gateway) ---
# Userspace networking (Railway has no TUN device). Use --statedir (a directory)
# so Tailscale has a writable var root for HTTPS certs that `tailscale serve`
# needs (--state=<file> alone yields "no TailscaleVarRoot"). On the volume so the
# node identity + cert persist across redeploys.
mkdir -p /opt/data/tailscale
tailscaled --tun=userspace-networking --statedir=/opt/data/tailscale \
  --socket=/opt/data/tailscaled.sock &
# Wait for the daemon socket before `tailscale up` (fixes the boot race).
for _ in $(seq 1 30); do tailscale status >/dev/null 2>&1 && break; sleep 1; done
timeout 30 tailscale up --authkey="${TS_AUTHKEY}" \
  --hostname="${TS_HOSTNAME:-hank-${RAILWAY_SERVICE_NAME:-hermes}}" \
  || echo "WARN: tailscale up failed/timed out — dashboard unreachable; gateway continues"

# --- Dashboard on 0.0.0.0 (--insecure); Tailscale serves it on the tailnet ---
# Bind 0.0.0.0 not loopback: the dashboard's Host-header guard only accepts the
# bound host, and `tailscale serve` forwards the MagicDNS Host — 0.0.0.0 is the
# documented opt-in that accepts a proxied Host. Still private (no public port;
# serve is the only inbound path).
hermes dashboard --no-open --insecure --host 0.0.0.0 --port 9119 &
timeout 15 tailscale serve --bg 9119 || echo "WARN: tailscale serve failed/timed out"

# Foreground: container lives as long as the gateway lives (watcher above is the
# backstop if anything between here and now had blocked).
wait "$GATEWAY_PID"
```

- [ ] **Step 2: Install Tailscale + make the script executable in the image**

In `Dockerfile`, install the Tailscale binaries and mark the script executable:

```dockerfile
RUN curl -fsSL https://pkgs.tailscale.com/stable/tailscale_latest_amd64.tgz \
      | tar -xzf - --strip-components=1 -C /usr/local/bin \
        tailscale_latest_amd64/tailscale tailscale_latest_amd64/tailscaled
RUN chmod +x /opt/hermes/docker/start-railway.sh
```

- [ ] **Step 3: Point Railway at the script and ensure the web dist is found**

In `railway.toml`:

```toml
[deploy]
startCommand = "/opt/hermes/docker/start-railway.sh"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
healthcheckTimeout = 300
```

No `HERMES_WEB_DIST` env needed — the Dockerfile already bakes it
(`ENV HERMES_WEB_DIST=/opt/hermes/hermes_cli/web_dist`) and builds the UI there, so
`hermes dashboard` uses the prebuilt assets and won't rebuild at boot.

- [ ] **Step 4: Verify the script parses**

```bash
bash -n docker/start-railway.sh
```
Expected: no output (syntax OK).

- [ ] **Step 5: Commit**

```bash
git add docker/start-railway.sh railway.toml Dockerfile
git commit -m "feat(deploy): run gateway + dashboard together for Hermes Desktop access"
```

### Task 4: Deploy the start-command change to KG and confirm the dashboard is reachable

**Files:** none (deploy + verify).

- [ ] **Step 1: Set Tailscale + dashboard-auth + web-dist env on KG**

Dashboard access is Tailscale-private; basic-auth is defense-in-depth behind the tailnet
(it's the only dashboard auth this Hermes version has). Generate a **reusable, ephemeral**
auth key in the Tailscale admin console. **Set the secrets in the Railway dashboard UI**
(not the CLI, to avoid shell-history exposure):

- `TS_AUTHKEY` = the Tailscale reusable/ephemeral auth key
- `TS_HOSTNAME` = `hank-web` (the tailnet name Desktop will connect to)
- `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` = `admin`
- `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` = a strong, unique password
- `HERMES_DASHBOARD_BASIC_AUTH_SECRET` = `openssl rand -base64 32` (generate locally; paste in UI)

(No `HERMES_WEB_DIST` — baked into the image at `/opt/hermes/hermes_cli/web_dist`.)

- [ ] **Step 2: Deploy**

```powershell
railway up --service e7d29fc1-9dd0-4715-98af-3b7fe9d5e567
```
Expected: build succeeds, deployment goes `SUCCESS`.

- [ ] **Step 3: Verify gateway runs, Tailscale joined, and the dashboard is served**

```powershell
railway ssh "/opt/hermes/.venv/bin/hermes gateway status; /opt/hermes/.venv/bin/hermes cron status"
railway ssh "tailscale status; tailscale serve status"
```
Expected: gateway + cron scheduler running (independent of Tailscale); the node is online in `tailscale status`; `tailscale serve status` shows `:9119` proxied. Confirm the node in the Tailscale admin console.

- [ ] **Step 4: Verify reachability over the tailnet (from a tailnet machine)**

From Jonathan's machine (on the same tailnet). `tailscale serve` exposes it as HTTPS on the node's MagicDNS name:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://hank-web.<your-tailnet>.ts.net/health
```
Expected: `200` over the tailnet; unreachable from off-tailnet (confirms it's private). The basic-auth prompt appears for the dashboard UI.

- [ ] **Step 5: Commit (state checkpoint, no code change)**

No code to commit; record success in the inventory note and proceed.

---

## Phase 2 — Stand up the new Social service

### Task 5: Create the Social Railway service from the same repo

**Files:** none (Railway resources).

- [ ] **Step 1: Create the service**

Decide the host project (a new project, or alongside KG in `kind-generosity`). Then in the Railway dashboard: New → Deploy from GitHub repo → `AI-SDR-SaaS/hank-hermes-agent`. Name it `hank-social`. Do NOT deploy yet (no env set).

- [ ] **Step 2: Attach a fresh volume at `/opt/data`**

Add a Volume to `hank-social` mounted at `/opt/data` (mirrors KG's mount). Capture the new service ID:

```bash
railway link   # select the new hank-social service
railway status
```
Expected: prints the `hank-social` service ID. Record it as `SOC`.

### Task 6: Configure Social env vars (clone KG's, swap the bot, add dashboard auth)

**Files:** none (Railway env).

> **Do NOT dump secret values to the terminal** (no `railway variables --kv`) — it
> leaks credentials into shell history/logs. Copy secrets via the Railway dashboard's
> in-browser Variables editor, and verify by **name only**.

- [ ] **Step 1: Identify which variables KG has (names only)**

In the Railway dashboard → KG service → **Variables** tab, read the variable **names**
(values stay masked in the UI). From the Task 1 inventory, mark which the social agent
needs (model/provider keys, `DROPBOX_APP_KEY`/`DROPBOX_APP_SECRET`/`DROPBOX_REFRESH_TOKEN`,
publisher-integration vars) vs. web-only (`WEBSITE_GITHUB_TOKEN`, PostHog keys → exclude).

- [ ] **Step 2: Copy the needed secrets onto SOC via the Railway UI (no terminal)**

In the Railway dashboard → KG **Variables** → **Raw Editor**, copy the lines for the
social-needed vars, then paste them into SOC's Raw Editor. This stays in-browser — values
never touch shell history. Then set SOC-specific values (the new bot token from Task 2 and
a fresh dashboard password). Enter these **in the UI** too (they're secrets):

- `TELEGRAM_BOT_TOKEN` = the new "Hank Social" token (Task 2)
- `TS_AUTHKEY` = a fresh Tailscale reusable/ephemeral auth key (its own, not KG's)
- `TS_HOSTNAME` = `hank-social` (the tailnet name Desktop's Social profile connects to)
- `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` = `admin`
- `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` = a strong, unique password
- `HERMES_DASHBOARD_BASIC_AUTH_SECRET` = output of `openssl rand -base64 32` (generate locally; paste into the UI)
- Blog publishing (Social owns it): `AIRTABLE_API_KEY`, `BLOG_API_KEY`, `TELEGRAM_CHAT_ID` (copy from KG via the Raw Editor)

(No `HERMES_WEB_DIST` — baked into the image.)

Do NOT set web-only vars (`WEBSITE_GITHUB_TOKEN`, PostHog keys) on SOC.

- [ ] **Step 3: Verify the var set by name only**

```bash
railway link   # select SOC
railway variables | awk '{print $1}'   # names column only — do NOT print values
```
Expected (by name): social + Dropbox vars + `TELEGRAM_BOT_TOKEN` + dashboard auth vars present; no `WEBSITE_GITHUB_TOKEN`/PostHog names. (Or just confirm names in the Railway UI.)

### Task 7: Seed SOC's volume with social config + memory (Dropbox bridge)

**Files:** none (volume content). Uses Dropbox as the transfer medium since Railway volumes have no direct scp.

- [ ] **Step 1: On KG, archive the config + persona + memory + crons**

```bash
railway link   # KG
railway ssh "cd /opt/data && tar czf /opt/data/social-seed.tgz config.yaml SOUL.md AGENTS.md memories cron 2>/dev/null; ls -la /opt/data/social-seed.tgz"
```
Expected: `social-seed.tgz` created.

- [ ] **Step 2: Push the archive to Dropbox from KG**

Use the agent's Dropbox tool (DM the KG agent: "upload /opt/data/social-seed.tgz to Dropbox at /transfers/social-seed.tgz"), or a one-off `hermes chat -q` invocation that calls the Dropbox upload tool. Verify it appears in Dropbox.

- [ ] **Step 3: First boot of SOC (creates the volume skeleton), then pull the archive**

```bash
railway up --service <SOC_ID>      # boots once, entrypoint creates /opt/data skeleton
railway link   # SOC
railway ssh "cd /opt/data && <download social-seed.tgz from Dropbox to here> && tar xzf social-seed.tgz && ls config.yaml SOUL.md"
```
Expected: `config.yaml`, `SOUL.md`, `memories/`, `cron/` present on SOC's volume. (Download via the SOC agent's Dropbox tool, same mechanism as Step 2 in reverse.)

- [ ] **Step 4: Verify SOC starts with the seeded identity**

```bash
railway ssh "hermes gateway status; hermes cron list"
```
Expected: gateway running; cron list shows the (still full) job set — pruned next.

### Task 8: Prune SOC down to social-only

**Files:** edits to `/opt/data/config.yaml` and crons on SOC's volume.

- [ ] **Step 1: Remove web/analytics crons on SOC**

For each web cron ID from the Task 1 inventory (PostHog monitor, website edit loop):

```bash
railway ssh "hermes cron remove <web_cron_id>"
```
Expected: each confirms removal. Then `hermes cron list` shows only Fastlane/social jobs.

- [ ] **Step 2: Disable web toolsets on SOC**

Edit `config.yaml` to drop the web/analytics/posthog/website toolsets (keep Fastlane/publisher/Dropbox/social). Use name-only edits (no secret values touched):

```bash
railway ssh "cp /opt/data/config.yaml /opt/data/config.yaml.bak && nano /opt/data/config.yaml"   # or sed the toolsets list
railway ssh "hermes toolsets list"
```
Expected: only social toolsets enabled.

- [ ] **Step 3: Remove the Higgsfield MCP server on SOC (headless OAuth noise)**

```bash
railway ssh "hermes mcp remove higgsfield 2>/dev/null; hermes mcp list"
```
Expected: no Higgsfield entry.

- [ ] **Step 4: Redeploy SOC and verify it boots clean**

```bash
railway up --service <SOC_ID>
railway logs --deployment   # confirm: gateway banner, no Higgsfield OAuth loop, cron scheduler up
```
Expected: clean startup, Fastlane cron scheduled, no OAuth tracebacks.

### Task 9: End-to-end social proof (the cutover gate)

**Files:** none (functional verification).

- [ ] **Step 1: Chat smoke test on the new bot**

DM the new "Hank Social" bot a photo + "draft 3 captions". Expected: it replies with 3 caption variations (the ad-hoc workflow).

- [ ] **Step 2: Publisher drive-through**

Pick a caption; confirm `publisher_quick_post(auto_publish=true)` ships through the existing publisher (the publisher service is unchanged). Expected: post appears / publisher logs the job.

- [ ] **Step 3: Fastlane cron dry-run**

```bash
railway ssh "hermes cron tick"
```
Expected: the Fastlane daily-plan job runs once and completes without error.

- [ ] **GATE:** Do not proceed to Phase 3 until Steps 1–3 all pass. The Social agent must be fully working before social capability is removed from KG.

---

## Phase 3 — Repurpose KG into the Web/Analytics/Ads agent

### Task 10: Remove social capability from KG

**Files:** edits to KG `/opt/data/config.yaml` + crons; KG env.

- [ ] **Step 1: Back up KG's volume first**

```bash
railway link   # KG
railway ssh "hermes backup"   # or tar config.yaml/SOUL.md/memories/cron like Task 7 Step 1
```
Expected: backup archive created (rollback safety).

- [ ] **Step 2: Remove the social crons on KG**

For each social cron ID (Fastlane/daily-plan) from inventory:

```bash
railway ssh "hermes cron remove <social_cron_id>"
railway ssh "hermes cron list"
```
Expected: only web/analytics crons remain (PostHog monitor, website loop).

- [ ] **Step 3: Disable social skills/toolsets on KG; keep web + Ace chat**

Disable the social skills (and edit the `toolsets:` block in `/opt/data/config.yaml`) so KG
keeps only web/analytics/ads: drop `hank-x-*`, `hank-ig-tiktok-drafter`, `fastlane-*`,
`hank-reddit-engagement`, `hank-blog-*`, `blog-publisher-cron`, `hank-hormozi-copywriter`,
`ad-hoc-post`, `airtable`; keep `posthog-monitor`, the website edit-loop, cold-outbound
(`hank-cold-email-drafter`, `hank-smartlead-operator`, `hank-where-they-live`). Also disable
the ~80 irrelevant builtins (mlops/gaming/smart-home/etc.) to cut context bloat.

```powershell
railway ssh "/opt/hermes/.venv/bin/hermes skills list"   # confirm only web/ads skills enabled
railway ssh "grep -A40 '^toolsets:' /opt/data/config.yaml"   # confirm toolset names (no values)
```
Expected: social skills/toolsets gone; web/analytics/ads only.

- [ ] **Step 4: Revert the social SOUL/AGENTS patches on KG**

The `entrypoint.sh` patches social `publisher_quick_post` rules into SOUL/AGENTS. Update KG's `/opt/data/SOUL.md` + `AGENTS.md` to the web/analytics/ads persona (remove the social posting carve-out). Keep the Ace identity/name.

### Task 11: Drop the publisher webhook on KG

**Files:** KG env + `/opt/data/config.yaml`.

- [ ] **Step 1: Unset the webhook secret so the entrypoint stops injecting the route**

```bash
railway variables --remove "PUBLISHER_WEBHOOK_HMAC_SECRET"
```
Expected: variable removed.

- [ ] **Step 2: Remove the existing webhook stanza from KG config**

```bash
railway ssh "cp /opt/data/config.yaml /opt/data/config.yaml.bak2 && nano /opt/data/config.yaml"   # delete the platforms.webhook block
```
Expected: no `webhook:` platform remains.

### Task 12: Remove the Higgsfield MCP noise on KG and redeploy

**Files:** KG `/opt/data/config.yaml`.

- [ ] **Step 1: Remove the Higgsfield MCP server**

```bash
railway ssh "hermes mcp remove higgsfield 2>/dev/null; hermes mcp list"
```
Expected: no Higgsfield entry.

- [ ] **Step 2: Redeploy KG and verify web-only behavior**

```bash
railway up --service e7d29fc1-9dd0-4715-98af-3b7fe9d5e567
railway logs --deployment
railway ssh "hermes cron list; hermes toolsets list"
```
Expected: clean boot, no Higgsfield OAuth loop, only web crons + toolsets, Ace bot still answers.

- [ ] **Step 3: Verify a web cron fires**

```bash
railway ssh "hermes cron tick"
```
Expected: the PostHog monitor digest job runs and posts to the Ace bot chat.

---

## Phase 4 — Hermes Desktop wiring

### Task 13: Install Desktop and create two profiles

**Files:** none (local desktop app).

- [ ] **Step 1: Install Hermes Desktop + join the tailnet**

Download for your OS (macOS `.dmg` / Windows `.exe`) from the Nous desktop page and install.
Install Tailscale on the same machine and sign into the **same tailnet** as the services
(so `hank-social` / `hank-web` resolve via MagicDNS).

- [ ] **Step 2: Create the Social profile → SOC dashboard (over tailnet)**

In Desktop: Profiles → new profile "social" → Settings → Gateway → Remote gateway → URL =
`https://hank-social.<your-tailnet>.ts.net` (the `tailscale serve` HTTPS MagicDNS URL) →
sign in with SOC's basic-auth creds (Task 6). Save & reconnect.

- [ ] **Step 3: Create the Web profile → KG dashboard (over tailnet)**

New profile "web" → Remote gateway URL = `https://hank-web.<your-tailnet>.ts.net` →
sign in with KG's basic-auth creds (Task 4). Save & reconnect.

- [ ] **Step 4: Verify the profile switcher**

Switch between "social" and "web" profiles. Expected: each connects to its own backend; sessions/crons shown differ per agent.

---

## Phase 5 — Soak & confirm the fix

### Task 14: Observe a full cron cycle on both agents

**Files:** none.

- [ ] **Step 1: Let both agents run through a natural cron cycle (e.g. 24h)**

Watch for: Fastlane posts twice/day on SOC; PostHog digest on KG; no dropped crons.

- [ ] **Step 2: Confirm no "Deploy Crashed" emails and stable deployments**

```bash
# For each service, confirm current deployment SUCCESS + single container start (no restart loop)
railway status
```
Expected: both services `SUCCESS`/Online, no crash emails since cutover.

- [ ] **Step 3: Final commit — record outcomes**

Update the inventory note with the final cron/toolset placement and mark the migration complete.

```bash
git add docs/superpowers/plans/inventory-2026-06-08.md
git commit -m "docs: record final agent-split placement and soak results"
```

---

## Rollback

- **SOC problems:** SOC is additive until Phase 3; if it fails, KG still has full social capability — just don't proceed past the Task 9 gate.
- **KG problems after Phase 3:** restore `config.yaml`/SOUL/crons from the Task 10 Step 1 backup (or `config.yaml.bak*`), re-set `PUBLISHER_WEBHOOK_HMAC_SECRET` if needed, redeploy.

## Risks

- **Dashboard security = Tailscale-private (decided):** dashboards are not internet-facing. The dashboard binds to `127.0.0.1:9119` and `tailscale serve` proxies inbound tailnet traffic to it, so it's reachable only over the tailnet (HTTPS via MagicDNS), with basic-auth as defense-in-depth. The `TS_AUTHKEY` is a secret — use reusable+ephemeral keys so dead Railway nodes auto-expire.
- **Gateway is independent of Tailscale (by design):** the start script runs the gateway first and treats Tailscale/dashboard as best-effort (not `set -e`), so if `tailscaled`/`tailscale serve` fails, the dashboard is simply unreachable while the gateway/crons keep running. The container's lifetime tracks the gateway, not the dashboard.
- **Tailscale in-container:** uses userspace networking (no TUN). The tailnet IP is virtual and not bindable — hence loopback bind + `tailscale serve` (do NOT bind the dashboard to the tailnet IP). Confirm `tailscale`/`tailscaled` install in the image (Task 3 Step 2), the boot-race wait, and that `tailscale serve status` shows `:9119` (Task 4 Step 3) before relying on Desktop access.
- **Cross-volume seed transfer (Task 7):** the Dropbox bridge is the fiddliest step; if it stalls, fall back to recreating social config from defaults + `hermes cron create` and copying `memories/MEMORY.md` manually.
- **Dashboard UI assets:** `HERMES_WEB_DIST` is baked into the image at `/opt/hermes/hermes_cli/web_dist` (built during `docker build`), so `hermes dashboard` serves prebuilt assets and won't rebuild at boot. No env override needed.
- **Splitting may not fix a non-load cron bug:** Task 9 / Task 12 cron-tick checks confirm crons actually run post-split before declaring success.
