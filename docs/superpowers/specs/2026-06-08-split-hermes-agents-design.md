# Split the monolithic Hermes agent into focused agents

**Date:** 2026-06-08
**Status:** Approved (design) — pending implementation plan
**Author:** Jonathan + Claude

## Problem

A single Hermes agent (`hank-hermes-agent`, Railway project `kind-generosity`) is doing
too many unrelated jobs: social-media content (Fastlane planning, caption drafting,
ad-hoc posting), website + product analytics (PostHog monitor, `ai-assistant-website`
edits), and general chat. Cron jobs have started failing.

### Root cause (evidence-based, not load)

- **CPU is idle** (~0.001 vCPU steady-state) — the container is not compute-bound.
- **No container restarts** since the 2026-06-06 redeploy; deployment status is `SUCCESS`,
  instance `RUNNING`. Earlier "Deploy Crashed" emails (last seen 2026-06-03) were from
  pre-06-06 deployments that auto-recovered.
- Therefore the cron failures are **logical contention**, not resource exhaustion: one
  config, one agent session, and one cron scheduler are juggling everything.

The fix is to give each domain its **own gateway process** — and therefore its own cron
scheduler and session — by splitting into focused services. (See related noise issue:
the Higgsfield MCP server in the runtime `config.yaml` loops on headless OAuth; tracked
separately, not part of this split.)

## Goals

- Each domain runs as an isolated agent with its own cron scheduler, config, skills, and
  memory, so a busy/failing job in one domain cannot starve another's crons.
- Manage the agents from **Hermes Desktop** using its per-profile remote-backend feature
  (each Desktop profile points at one remote backend; switching profiles switches host).
- Keep the change low-risk and incremental; do not disturb the working publisher.

## Non-goals

- Defining the paid-ads capability set (deferred to its own spec — see Open Items).
- Reducing compute cost (not the problem; box is idle).
- Migrating the publisher off Node/TS or changing how it posts.

## Target architecture — three services

| Service | Project | Role | Type |
|---|---|---|---|
| **Publisher** | `athletic-joy` | Posts to IG/TikTok, cron auto-publish — the "hands" | Node/TS (unchanged) |
| **Social agent** | NEW | Fastlane planning, captions, ad-hoc posts, chat — the "social brain"; drives the publisher | Hermes agent (new) |
| **Web/Analytics/Ads agent** | `kind-generosity` | PostHog monitor, `ai-assistant-website` edits, paid-ads | Hermes agent (repurposed; keeps the "Ace" bot + identity + memory) |

**Hermes Desktop:** two local profiles — *Social* → new service dashboard URL, *Web* →
`kind-generosity` dashboard URL — switchable in the Profiles pane. The publisher is not a
Hermes backend and stays managed as it is today.

## How each piece is built

### Social agent (new)
- Created by cloning the current agent's social surface (config, social memory, SOUL/AGENTS
  rules, Fastlane skill, publisher toolset, Dropbox), then **stripping** web/analytics/ads
  toolsets, skills, and crons.
- Keeps: Fastlane daily-plan cron and skill, caption-drafting flow, ad-hoc quick-post
  workflow, `publisher_quick_post*` tools, Dropbox integration, social SOUL/AGENTS rules.
- Gets its **own new Telegram bot** ("Hank Social") — a distinct bot token (a shared bot
  conflicts across agents).

### Web/Analytics/Ads agent (repurpose `kind-generosity`)
- **Removes** the social surface: Fastlane skill + cron, caption flow, publisher posting
  toolset.
- Keeps: PostHog tools + monitor digest cron, the `ai-assistant-website` edit loop
  (GitHub PR via `WEBSITE_GITHUB_TOKEN`, Vercel preview, Cubic), the existing **Ace** bot
  token + identity + accumulated memory.
- **Adds** paid-ads as a new focus area (capabilities specced separately).

### Both Hermes services — deployment mechanics
- `hermes dashboard` (web UI/API that Desktop connects to) and `hermes gateway run`
  (Telegram + cron) are **separate processes**. Each service must run **both**.
- Railway exposes **one public port per service**: bind the **dashboard** to
  `0.0.0.0:$PORT` (public, for Desktop). The gateway needs no inbound port — Telegram
  uses outbound polling and the cron scheduler is internal.
- Change each service's Railway start command from `hermes gateway run` to a wrapper that
  starts the gateway in the background and runs the dashboard in the foreground on `$PORT`
  (or the equivalent supported multi-process invocation). Confirm both processes share the
  same `HERMES_HOME`/profile so the dashboard controls the same agent the gateway runs.
- **Dashboard auth:** this Hermes version supports **basic-auth only** for dashboard
  access (`HERMES_DASHBOARD_BASIC_AUTH_*`); there is no Nous-Portal OAuth for the dashboard
  in this codebase (OAuth here is for model providers). Binding a public host requires the
  `--insecure` flag. The remaining security lever is **network reachability** — see the
  "Dashboard exposure" decision below.

## Workload / cron assignment

Finalized from the live inventory + operator decisions (2026-06-08). See
`docs/superpowers/plans/inventory-2026-06-08.md` for the full item-by-item mapping.

| Social / Content agent | Web / Analytics / Ads agent (`kind-generosity`) |
|---|---|
| Fastlane (daily-plan + publish slots A/B), IG/TikTok, ad-hoc quick-post | PostHog analytics: monitor skill + daily-digest cron + posthog MCP |
| X (drafter/publisher/scheduler/trend-watcher), Reddit engagement | `ai-assistant-website` code-edit loop (GitHub PR + Vercel + Cubic) |
| **Blog** (drafter/restructure/publisher cron) | Cold outbound / SDR: cold-email-drafter, smartlead-operator + smartlead MCP, where-they-live |
| Hormozi copywriting, higgsfield (image/video), airtable approval hub, publisher tools, Dropbox | Paid-ads work *(scope TBD — separate spec)*; keeps the **Ace** bot |

**Note (broader split than first sketched):** the Social agent owns the *entire content
motion* (incl. blog + reddit + copy), and the Web agent is analytics + website engineering
+ cold outbound. **Blog dependency resolved:** blog publishing is API-based —
`blog-publisher-cron` reads Approved posts from Airtable and POSTs to
`meethank.ai/api/blog/posts` via `BLOG_API_KEY` (no website-repo push), so the Social agent
owns it end-to-end with `AIRTABLE_API_KEY` + `BLOG_API_KEY` + `TELEGRAM_*` + the
`/opt/data/cron/blog-publisher.py` script. No `WEBSITE_GITHUB_TOKEN` or Social→Web handoff.

Also disable the ~80 irrelevant always-on builtin skills per agent (mlops, gaming,
smart-home, etc.) — a direct reduction of the context bloat that contributed to the
overload, independent of the split.

## Decisions

- **Webhook dropped:** the publisher → Hermes webhook (port 8080) is no longer
  load-bearing (the publisher DMs Telegram directly; the route only logs). Removing it
  means each service needs only the single public port for the dashboard.
- **Bots:** Web agent keeps the existing Ace bot; Social agent gets a new bot token.
- **Paid-ads deferred:** kept off this split's critical path; specced separately so the
  split does not block on it.
- **Dashboard auth:** basic-auth (the only dashboard auth in this Hermes version), with a
  strong unique password per service.
- **Dashboard exposure (PENDING operator decision):** either (a) expose each dashboard on
  its public Railway HTTPS URL behind basic-auth (simple; acceptable single-user), or
  (b) keep dashboards private and reach them over Tailscale/VPN (more secure, more setup).
  This is the real security lever now that OAuth isn't an option.

## Repository layout & git management

Both Hermes agents run the **same engine code** from a single repo. They are *not* forked
per agent — differentiation is entirely runtime (Railway env + volume state).

| Repo | Deploys to | Role in the split |
|---|---|---|
| `AI-SDR-SaaS/hank-hermes-agent` | `kind-generosity` **and** the new social service | One repo builds **both** Hermes agents |
| `AI-SDR-SaaS/hermes-social-media` | `athletic-joy` (publisher) | Unchanged |
| `AI-SDR-SaaS/ai-assistant-website` | website (Vercel) | Web agent edits via PR |

**Code vs. config:**

- **Code (shared, in git):** the Hermes engine, `Dockerfile`, `entrypoint.sh`,
  `railway.toml`, bundled skills — in `hank-hermes-agent`. A push redeploys both Hermes
  services. Both need the same structural change (gateway + dashboard start command), so a
  shared repo is appropriate; no per-agent fork or branch is required.
- **Per-agent differences (NOT forked in git):**
  - **Railway env vars** (per service): Telegram bot token, API keys, feature flags.
  - **Volume state** (`/opt/data`, per service): `config.yaml` (enabled toolsets),
    `SOUL.md`/`AGENTS.md` (persona), crons, memory.
- The existing `entrypoint.sh` already gates Hank/social-specific behavior on env
  (publisher webhook injected only when `PUBLISHER_WEBHOOK_HMAC_SECRET` is set; SOUL
  patched only when the social strings are present), so one repo cleanly produces two
  differentiated agents.

**Where artifacts are committed:**

- Design + planning docs (this spec, future plans) → `hank-hermes-agent`,
  `docs/superpowers/specs/`.
- Engine/structural code (start command, entrypoint, skills) → `hank-hermes-agent`.
- Publisher changes → `hermes-social-media`. Website changes → `ai-assistant-website`.

**Version-controlling per-agent config (decision):** hybrid approach —

- Keep *structural* per-agent bootstrapping (which toolsets/crons/SOUL each agent gets) in
  the repo behind env flags, extending the existing `entrypoint.sh` pattern, so deploys are
  reproducible.
- Let *memory and live tweaks* remain volume state, protected by `hermes backup` / profile
  export rather than git.

**Deploy behavior:** both Hermes services set their Railway source to `hank-hermes-agent`.
A push redeploys both; per-service env + volume keep them differentiated. If independent
deploy timing is later needed, use Railway watch paths or per-service branches — not
required for the initial split.

## Implementation sequencing (low-risk order)

1. Enumerate live crons/toolsets on the current agent (name-only).
2. Stand up the **new social service** (clone → strip web → new bot → gateway+dashboard);
   verify Fastlane planning and one end-to-end test post through the publisher.
3. Once social is proven, **strip the social surface** from `kind-generosity` and add the
   dashboard there.
4. Connect Hermes Desktop: create two profiles; verify the profile switcher reaches each
   backend.
5. Observe a full cron cycle on both agents; confirm no dropped crons and no
   "Deploy Crashed" emails.

## Risks & mitigations

- **Two inbound ports wanted on one service** — avoided by dropping the webhook; only the
  dashboard is exposed.
- **Bot conflict** — each agent gets a distinct Telegram bot token.
- **Social regression during cutover** — the new social service is fully proven (step 2)
  *before* social capabilities are removed from `kind-generosity` (step 3), so there is no
  window where social work has no home.
- **Dashboard exposed publicly** — mitigated by per-service OAuth auth; never expose an
  unauthenticated dashboard.
- **Splitting may not fix a cron bug that is not load-related** — step 1's enumeration and
  step 5's observation confirm the failures were contention before we declare success.

## Open items (tracked, not blocking)

- Paid-ads capability definition → separate spec.
- Which Railway project hosts the new social service (new project vs. an existing one) —
  decide at implementation time; does not affect the design.
