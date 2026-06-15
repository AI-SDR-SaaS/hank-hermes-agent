# xgrowth Hermes Agent — Design

**Date:** 2026-06-15
**Status:** Approved design, pre-implementation
**Owner:** Jonathan Sherman

## Goal

Stand up the 5th and final Hermes agent: a dedicated operator for Jonathan's **personal @jonathan_sherm X presence**, driving the `AI-SDR-SaaS/xgrowth` platform (the X algorithm-aligned content engine) over its HTTP API. This agent is Jonathan's founder-voice X ghostwriter and growth operator. It is NOT a Hank-brand persona (unlike Ace/Chad/Brian).

Scope: **posting + trend-watching (radar) + growth/analytics (reporting)**. Explicitly NOT engagement/replies.

## Architecture

- **Agent** (this engine repo, new Railway service) = the brain: judgment, orchestration, and the human approval loop.
- **xgrowth platform** (`AI-SDR-SaaS/xgrowth`, FastAPI on Vercel + Supabase) = the engine: generation, scoring, queue, scheduling, posting to X, analytics. It holds the X/Anthropic/Higgsfield creds and does the actual posting. The agent never touches X API keys.
- **Integration:** REST + custom Hermes tools (the `publisher_tools.py` pattern), NOT MCP (the platform exposes REST). New `tools/xgrowth_tools.py` + an `xgrowth` toolset in `toolsets.py`, gated on `XGROWTH_API_BASE` + `XGROWTH_API_KEY`.
- **Auth:** every call sends `Authorization: Bearer <XGROWTH_API_KEY>`. The agent is a scoped machine principal (key minted in the platform's `XGROWTH_API_KEYS` env as `{key,label,scopes}`). Agent scopes: `generate, queue, post, radar, reporting` (+ `media` if/when image tools are added). 403 = missing scope, 401 = bad token.

## Tool contract

All paths under `/api` on the production domain. Tools map 1:1 to endpoints.

**Radar (scope: radar)** — trend watching
- `xgrowth_radar_refresh` → `POST /api/radar/refresh`
- `xgrowth_radar_feed` → `GET /api/radar/feed` (spiking posts + timely topics)
- (watchlist/keywords management endpoints exist; deferred to phase 2)

**Generate (scope: generate)**
- `xgrowth_generate` → `POST /api/generate` `{niche, kind="single", topic="", thread_len?, sponsored?}` → draft `{id, parts, score, status}`, auto-saved to queue
- `xgrowth_score` → `POST /api/score` `{text/parts, kind}`
- `xgrowth_hooks` → `POST /api/hooks` `{niche, topic}`
- `xgrowth_list_niches` → `GET /api/niches` (valid niches, e.g. `ai_entrepreneur`, `alex_finn`)

**Queue (scope: queue)**
- `xgrowth_list_queue` → `GET /api/queue?status=`
- `xgrowth_edit_draft` → `PATCH /api/queue/{id}` `{parts?, poll_options?}`
- `xgrowth_approve_draft` → `POST /api/queue/{id}/approve`
- `xgrowth_reject_draft` → `POST /api/queue/{id}/reject`
- `xgrowth_schedule_draft` → `POST /api/queue/{id}/schedule` `{when_epoch}`
- `xgrowth_unschedule_draft` → `POST /api/queue/{id}/unschedule`
- `xgrowth_delete_draft` → `DELETE /api/queue/{id}` (removes the draft record only, NOT a live tweet)

**Post (scope: post)**
- `xgrowth_get_schedule` → `GET /api/schedule`
- `xgrowth_post` → `POST /api/post` `{draft_id, dry_run, force?}` (auto-approves generated/failed drafts)
- `xgrowth_post_due` → `POST /api/post-due` `{dry_run}` (publishes due scheduled posts; for a periodic tick)
- `xgrowth_takedown` → `POST /api/post/{draft_id}/takedown` (deletes the live tweet(s) from X)

**Reporting (scope: reporting)**
- `xgrowth_reporting_summary` → `GET /api/reporting/summary?days=`
- `xgrowth_reporting_drift` → `GET /api/reporting/drift?niche=`
- `xgrowth_reporting_sync` → `POST /api/reporting/sync` (pull real metrics + follower snapshot)
- `xgrowth_insights` → `POST /api/insights`

**Phase 2 (not in v1):** media (image/video/meme) tools, radar watchlist/keyword management, reply/engagement.

## Hard safety rules (baked into AGENTS.md, not just the skill)

The platform is **live by default** and posts to Jonathan's real main account, so the agent's persona must enforce:
1. **`dry_run:true` is the DEFAULT for `xgrowth_post`/`xgrowth_post_due`.** The agent posts live (`dry_run:false`) ONLY on Jonathan's explicit instruction. This is the deliberate inverse of Brian (who posts freely) because this is a personal main account.
2. **Score gate ≥70** to publish. Below that, regenerate or edit the draft, do not push it live.
3. **Cadence guard:** max 8 posts/day, ≥45 min apart. A blocked post returns 409; only retry with `force:true` if Jonathan explicitly wants it.
4. **`kind:"single"` by default** (one tweet, kept whole). Use `kind:"thread"` only when a thread is genuinely warranted.
5. **Retraction:** use `xgrowth_takedown` to remove a bad live post. `delete_draft` does NOT remove a live tweet.
6. **Anti-fabrication / account safety** (inherited brand rule): never fabricate, review every draft before live posting, never post politics/religion/NSFW/etc. Wrong posts damage Jonathan's real reputation.

## Persona

Jonathan's personal X founder-voice operator (name = deploy input). SOUL.md + AGENTS.md built on the existing `hank-x-drafter` voice spec: Alex Finn / Tommy Mello, ~220 char, lowercase fragments, anti-slop, structural templates, dry humor ~1 in 5. The agent's job: pull radar ideas → generate → score-gate → surface to Jonathan on Telegram → on his go, post live. Reports on demand.

## Approval flow

radar/generate → score-gate (≥70) → surface draft + score to Jonathan on Telegram → Jonathan approves → `xgrowth_post {dry_run:false}`. Without explicit approval, drafts stay queued or dry-run. Autonomous cron deferred until Jonathan trusts it.

## Agent shell / deploy

Proven per-agent recipe (see Brian): BotFather bot, new Railway service (this engine repo) + volume `/opt/data`, env, Tailscale dashboard, `model: anthropic/claude-haiku-4.5`.
- **config.yaml:** `model` + `toolsets: [hermes-cli, xgrowth]` + `skills.disabled` trimming to the X toolkit and **disabling the 4 retired `hank-x-*` skills** (hank-x-drafter/publisher/scheduler/trend-watcher) + xurl + the junk builtins.
- **Retire** the old skills: they posted via X API + Airtable directly; the platform replaces them.

## Build tracks

1. **Engine code (PR to this repo, TDD):** `tools/xgrowth_tools.py` + `xgrowth` toolset in `toolsets.py` + `tests/tools/test_xgrowth_tools.py` (mock the HTTP layer, mirror `test_publisher_tools.py`). Merge → image rebuild.
2. **Operator prep (Jonathan):** create BotFather bot; new Railway service + volume; set env (`XGROWTH_API_BASE`, `XGROWTH_API_KEY` machine key with the 5 scopes, bot token, `TS_AUTHKEY`, `TS_HOSTNAME`, basic-auth, model brain); mint the machine key in the platform's `XGROWTH_API_KEYS` (merge, don't clobber).
3. **Config/persona/wire (me, via stdin):** config.yaml, SOUL.md, AGENTS.md, pair Telegram, redeploy, verify.

## Deploy inputs (required before build completes)

- **Agent name:** TBD (Jonathan to provide).
- **`XGROWTH_API_BASE`:** the production xgrowth domain (TBD; rundown had a placeholder).
- **Machine API key** with scopes `generate, queue, post, radar, reporting` minted in `XGROWTH_API_KEYS`.

## Out of scope

Engagement/replies (`/api/reply`), the xgrowth backend itself (Jonathan's repo), the web dashboard, media generation tools (phase 2).
