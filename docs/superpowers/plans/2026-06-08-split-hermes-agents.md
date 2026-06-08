# Split Hermes Agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the overloaded single Hermes agent into two focused Hermes agents (Social, and Web/Analytics/Ads) plus the unchanged publisher, each managed via Hermes Desktop.

**Architecture:** One engine repo (`hank-hermes-agent`) builds both Hermes services; they are differentiated only by Railway env vars + per-volume config. Each service runs `hermes gateway run` (Telegram + cron) and `hermes dashboard` (the web API Hermes Desktop connects to) together, with the dashboard bound to Railway's single public `$PORT`. Cutover is sequenced so the new Social agent is fully proven before social capabilities are removed from `kind-generosity`.

**Tech Stack:** Hermes (Python) engine, Railway (deploy + volumes + env), Railway GraphQL API + CLI, Telegram BotFather, Hermes Desktop, Dropbox (used as a file-transfer bridge between volumes — already integrated).

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

- [ ] **Step 1: Open a one-shot SSH into KG and list crons**

```bash
railway link   # choose: kind-generosity → production → hank-hermes-agent
railway ssh "hermes cron list"
```
Expected: a table of cron jobs with names/IDs/schedules. Record each.

- [ ] **Step 2: List enabled toolsets and installed skills**

```bash
railway ssh "hermes toolsets list; echo '---SKILLS---'; hermes skills list"
```
Expected: toolset names and skill names. Record each.

- [ ] **Step 3: List configured MCP servers (to catch the Higgsfield noise)**

```bash
railway ssh "hermes mcp list"
```
Expected: includes a Higgsfield entry (the headless-OAuth loop). Note it for removal in Task 12.

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
- Modify: `Dockerfile` (mark the script executable)

- [ ] **Step 1: Write the start script**

```bash
#!/bin/bash
# Railway start command: run the gateway (Telegram + cron) and the dashboard
# (web API for Hermes Desktop) in one container. Only the dashboard needs the
# public port; the gateway uses outbound Telegram polling + an internal cron loop.
set -euo pipefail

# Gateway in the background (Telegram channels + cron scheduler).
hermes gateway run &
GATEWAY_PID=$!

# If the gateway dies, take the container down so Railway restarts it cleanly.
trap 'kill -TERM "$GATEWAY_PID" 2>/dev/null || true' EXIT
( while kill -0 "$GATEWAY_PID" 2>/dev/null; do sleep 5; done; echo "gateway exited"; kill -TERM 1 ) &

# Dashboard in the foreground on Railway's public port (for Hermes Desktop).
exec hermes dashboard --no-open --host 0.0.0.0 --port "${PORT:-9119}"
```

- [ ] **Step 2: Make it executable in the image**

In `Dockerfile`, near the other `COPY`/`chmod` lines for `docker/`, ensure:

```dockerfile
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

Add (Task 6 sets this per service, but record it here): set env `HERMES_WEB_DIST=/opt/hermes/web/dist` so `hermes dashboard` uses the image-built UI instead of rebuilding at boot. (Confirm the build output path: `railway ssh "ls /opt/hermes/web/dist"` should list `index.html`.)

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

- [ ] **Step 1: Set dashboard auth + web-dist env on KG**

Basic-auth is used because it works headless (no interactive browser flow); Railway terminates TLS so it travels over HTTPS. (Security note: acceptable for single-user; harden later with Tailscale or Nous Portal OAuth — see Risks.)

```bash
railway link   # kind-generosity → production → hank-hermes-agent
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin"
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong-password>"
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)"
railway variables --set "HERMES_WEB_DIST=/opt/hermes/web/dist"
```

- [ ] **Step 2: Deploy**

```bash
railway up --service e7d29fc1-9dd0-4715-98af-3b7fe9d5e567
```
Expected: build succeeds, deployment goes `SUCCESS`.

- [ ] **Step 3: Verify the dashboard responds and the gateway still runs**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://hank-hermes-agent-production.up.railway.app/health
railway ssh "hermes gateway status; hermes cron status"
```
Expected: HTTP `200` from `/health`; gateway status = running; cron scheduler = running.

- [ ] **Step 4: Verify auth gate is engaged**

Open the public URL in a browser → expect a basic-auth prompt; the credentials from Step 1 log you into the dashboard UI.

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

- [ ] **Step 1: List KG's variable names**

```bash
railway variables --service e7d29fc1-9dd0-4715-98af-3b7fe9d5e567 --kv
```
Expected: all KG env vars (names + values). These are the integration secrets (model keys, Dropbox refresh-token trio, publisher creds, etc.).

- [ ] **Step 2: Copy the integration vars onto SOC, EXCEPT the bot token and web-only keys**

Set on `SOC` everything social needs: model/provider keys, Dropbox (`DROPBOX_APP_KEY`/`DROPBOX_APP_SECRET`/`DROPBOX_REFRESH_TOKEN`), and any publisher-integration vars the social agent uses to drive the publisher. Use the new bot token from Task 2:

```bash
railway link   # select SOC
railway variables --set "TELEGRAM_BOT_TOKEN=<NEW_HANK_SOCIAL_TOKEN>"
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin"
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<strong-password-2>"
railway variables --set "HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)"
railway variables --set "HERMES_WEB_DIST=/opt/hermes/web/dist"
# ...plus each social integration var identified in Step 1
```
Do NOT set web-only vars (e.g. `WEBSITE_GITHUB_TOKEN`, PostHog keys) on SOC.

- [ ] **Step 3: Verify the var set**

```bash
railway variables --service <SOC_ID> --kv
```
Expected: social + Dropbox + new bot token present; no website/PostHog keys.

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

- [ ] **Step 3: Disable social toolsets on KG; keep web + Ace chat**

Edit KG `config.yaml`: drop Fastlane/publisher-posting/caption toolsets; keep PostHog tools, the website edit-loop tools, general chat. Then:

```bash
railway ssh "hermes toolsets list"
```
Expected: web/analytics toolsets only.

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

- [ ] **Step 1: Install Hermes Desktop**

Download for your OS (macOS `.dmg` / Windows `.exe`) from the Nous desktop page and install.

- [ ] **Step 2: Create the Social profile → SOC dashboard**

In Desktop: Profiles → new profile "social" → Settings → Gateway → Remote gateway → URL = `https://<hank-social-public-url>` → sign in with SOC's basic-auth creds (Task 6). Save & reconnect.

- [ ] **Step 3: Create the Web profile → KG dashboard**

New profile "web" → Remote gateway URL = `https://hank-hermes-agent-production.up.railway.app` → sign in with KG's basic-auth creds (Task 4). Save & reconnect.

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

- **Dashboard exposed publicly with basic-auth:** acceptable over Railway HTTPS for a single user; harden by binding behind Tailscale or switching to Nous Portal OAuth (`hermes dashboard register`) once the split is stable.
- **Cross-volume seed transfer (Task 7):** the Dropbox bridge is the fiddliest step; if it stalls, fall back to recreating social config from defaults + `hermes cron create` and copying `memories/MEMORY.md` manually.
- **`HERMES_WEB_DIST` path:** if `/opt/hermes/web/dist` is wrong, `hermes dashboard` will try to rebuild at boot (slow). Confirm the path in Task 3 Step 3.
- **Splitting may not fix a non-load cron bug:** Task 9 / Task 12 cron-tick checks confirm crons actually run post-split before declaring success.
