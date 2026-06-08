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
- **Dashboard auth:** Nous Portal OAuth per service (`hermes dashboard register`), suitable
  for a public Railway URL. Basic-auth is a fallback but is not recommended for a
  public-facing URL.

## Workload / cron assignment

| Social agent | Web/Analytics/Ads agent (`kind-generosity`) |
|---|---|
| Fastlane daily-plan cron (2 posts/day) | PostHog monitor digest cron |
| Caption drafting, ad-hoc quick-post | `ai-assistant-website` PR/edit loop (Vercel + Cubic) |
| `publisher_quick_post*` tools, Dropbox | Paid-ads work *(scope TBD — separate spec)* |

Exact cron names and enabled toolsets are enumerated from each live config as
implementation step 1, using **name-only inspection** (no config/secret value dumps).

## Decisions

- **Webhook dropped:** the publisher → Hermes webhook (port 8080) is no longer
  load-bearing (the publisher DMs Telegram directly; the route only logs). Removing it
  means each service needs only the single public port for the dashboard.
- **Bots:** Web agent keeps the existing Ace bot; Social agent gets a new bot token.
- **Paid-ads deferred:** kept off this split's critical path; specced separately so the
  split does not block on it.
- **Dashboard auth:** default to Nous Portal OAuth per service.

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
