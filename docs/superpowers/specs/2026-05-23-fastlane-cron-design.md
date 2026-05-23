# Fastlane → Hank Publisher Daily Cron

**Date:** 2026-05-23
**Owner:** Jonathan
**Status:** Design (pending plan + implementation)

## Goal

Pull video content from Jonathan's Fastlane (`usefastlane.ai`) workspace on a daily schedule, let Ace curate two posts per day and draft caption variants, gate on Jonathan's caption pick, then auto-publish to IG + TikTok via the existing publisher at fixed times.

## Why

Jonathan's Fastlane workspace generates a stream of short-form video assets (mp4 on a public CDN). Today these sit in Fastlane's tab UI — there's no dedup tracking, no scheduling, no caption pipeline. We want a hands-off-but-still-approved daily rhythm: Ace does the curation and caption work, Jonathan only taps to approve, the publisher does the actual posting on its existing Zernio pipeline.

## Non-goals

- **Use Fastlane's own scheduler.** Fastlane has its own post/schedule endpoints; we ignore them. Posting goes through Hank's publisher (Zernio) only.
- **Wire Fastlane connections.** Fastlane allows connecting IG/TikTok directly; we don't want that. Connections list stays empty on Fastlane.
- **Use Fastlane's MCP server.** `api.usefastlane.ai/mcp` exposes their full toolset including scheduling. Two-endpoint custom client keeps the agent on rails.
- **Multi-account.** Single Zernio profile (Hank) for now. No multi-brand fan-out in this design.
- **Static photos / carousels.** Fastlane only returns videos; this design targets video posts. Carousel content stays in the existing Dropbox day-folder pipeline.

## Architecture overview

Three Hermes cron entries, two state files, one new Python client + toolset, one new skill. Zero changes to the publisher service.

```
08:00 ET   fastlane-daily-plan        Ace curates 2 posts, drafts 3 caption variants each,
                                      Telegram pick-1-of-3 per post. Writes today's plan.

11:30 ET   fastlane-publish-slot-a    Reads slot A from plan, calls publisher_quick_post
                                      (auto_publish=true), marks Fastlane _id as posted.

18:00 ET   fastlane-publish-slot-b    Same for slot B.
```

State files (on Hermes Railway, `/opt/data/`):

- `fastlane_daily_plan.json` — today's two slots, each with `content_id`, `media_url`, `chosen_caption`, `status`
- `fastlane_posted.json` — append-only map of Fastlane `_id` → `{posted_at, platforms}`, dedup forever

## Fastlane API surface (verified 2026-05-23)

Verified live with a workspace API key against the real API:

| Method | Path | Use |
|---|---|---|
| GET | `/api/v1/content?limit=N&cursor=...` | List content, cursor-paginated, newest first |
| GET | `/api/v1/content/{id}` | Fetch one (same fields as list — no extra metadata) |

**Base URL:** `https://api.usefastlane.ai/api/v1`
**Auth:** `Authorization: Bearer <FASTLANE_API_KEY>` — workspace-scoped key (NOT partner key)
**Forbidden to workspace keys:** `/partner/*`, `/posts` (returns empty), `/connections` (returns empty)

**Content item shape:**

```json
{
  "_id": "p972fsym8fg13vf3ej9b91fp8586a49h",
  "_creationTime": 1778261692284.9177,
  "files": ["https://media.aftermark.workers.dev/videos/<hash>.mp4"],
  "thumbnailUrl": "https://media.aftermark.workers.dev/thumbnails/<hash>.webp",
  "status": "CREATED",
  "type": "wall-of-text" | "green-screen" | "video-hook" | "slideshow" | "remix"
}
```

Notes for implementation:
- `_id` is a Convex-style stable ID — use this as the dedup key.
- `files[0]` is a direct public CDN URL (Cloudflare workers, no auth) — publisher can fetch it directly via `publisher_quick_post(media_urls=...)`.
- `thumbnailUrl` is what Ace looks at when picking + drafting captions (no transcript or text description is provided).
- No description, no transcript, no tags. Ace gets ONLY the thumbnail + type field as context.

## Component design

### `tools/fastlane_client.py`

Thin requests-based HTTP client. Two methods:

```python
class FastlaneClient:
    def __init__(self, api_key: str, base_url: str = "https://api.usefastlane.ai/api/v1"): ...

    def list_content(self, limit: int = 20, cursor: str | None = None) -> dict:
        """GET /content. Returns {"data": [...], "pagination": {...}}."""

    def get_content(self, content_id: str) -> dict:
        """GET /content/{id}. Returns {"data": {...}}."""
```

- Reads `FASTLANE_API_KEY` from env (constructed in `fastlane_tools.py` via `os.environ`).
- Raises on non-2xx with body included.
- 10s timeout per request.

### `tools/fastlane_tools.py`

Four agent tools:

1. **`fastlane_list_unposted(limit: int = 20) -> list[dict]`**
   Calls `client.list_content(limit)`, filters out any `_id` present in `fastlane_posted.json`. Returns up to `limit` items oldest-first (so we drain the backlog before serving newer content). Each item is `{content_id, media_url, thumbnail_url, type, creation_time}`.

2. **`fastlane_save_daily_plan(date: str, slot: "a" | "b", content_id: str, media_url: str, chosen_caption: str) -> dict`**
   Upserts into today's plan file. `status` is set to `"chosen"`. Returns the updated plan.

3. **`fastlane_get_daily_plan(date: str, slot: "a" | "b") -> dict | None`**
   Reads today's plan, returns the slot record (or `None` if missing / `status != "chosen"`). Used by the publish crons.

4. **`fastlane_mark_posted(content_id: str, platforms: list[str]) -> dict`**
   Appends to `fastlane_posted.json` with `posted_at` (ISO UTC). Also updates the corresponding slot in `fastlane_daily_plan.json` to `status: "posted"`. Idempotent — re-marking is a no-op.

State files use atomic-rename writes (write to `*.tmp`, then `os.replace`).

### `toolsets.py`

Register a new `fastlane` toolset. Per the two-step loading requirement: add to `cli-config.yaml.example` `toolsets:` list AND import + register in `toolsets.py`.

### `skills/social-media/fastlane-daily-plan/SKILL.md`

A new skill teaching Ace the planning workflow. Concrete steps the skill enforces:

1. Call `fastlane_list_unposted(20)`. If empty → reply `[SILENT]` (no Telegram noise).
2. For each candidate, fetch and look at the `thumbnail_url`. Group by `type`.
3. Pick **2 strongest** posts based on visual content + variety (don't pick two same-type posts back-to-back when there's alternatives).
4. For each pick, draft **3 caption variants** following Hank's voice (existing ad-hoc-post skill has the voice rules — link/inherit them). Each variant is a complete `## Caption` block + `## Hashtags` block in the format publisher expects.
5. Send **two Telegram messages** to Jonathan (one per post): thumbnail preview + 3 inline-keyboard buttons labelled with a 1-line summary of each variant.
6. When Jonathan taps a button:
   - Resolve which slot (a or b) and which variant the tap maps to.
   - Call `fastlane_save_daily_plan(...)` with the chosen caption.
7. When both slots have `status: "chosen"` → done. Reply with a short confirmation summary.

If Jonathan doesn't tap before a publish slot fires, that slot silently skips (see Failure modes).

### Cron entries (Hermes)

Three entries created via `hermes cron create`:

```bash
# Planning — daily at 08:00 ET (= 12:00 UTC during EDT)
hermes cron create "0 12 * * *" \
  "Run the fastlane-daily-plan workflow. Curate 2 posts from Fastlane, draft 3 caption variants per post, send Telegram pickers." \
  --skills "fastlane-daily-plan" \
  --name "Fastlane daily plan" \
  --deliver telegram

# Publish slot A — daily at 11:30 ET (= 15:30 UTC during EDT)
hermes cron create "30 15 * * *" \
  "Read today's fastlane_daily_plan.json slot A. If status is 'chosen', call publisher_quick_post(media_urls=[plan.media_url], caption=plan.chosen_caption, auto_publish=true), then fastlane_mark_posted(plan.content_id, platforms=['instagram','tiktok']). If status is 'pending' or plan missing, reply [SILENT]." \
  --name "Fastlane publish slot A (11:30 ET)" \
  --deliver telegram

# Publish slot B — daily at 18:00 ET (= 22:00 UTC during EDT)
hermes cron create "0 22 * * *" \
  "Read today's fastlane_daily_plan.json slot B. Same logic as slot A." \
  --name "Fastlane publish slot B (18:00 ET)" \
  --deliver telegram
```

All cron expressions in UTC (Railway containers run UTC). ET → UTC offsets above assume EDT (UTC-4, summer); revisit when DST ends — or use a TZ env on the Hermes container.

### Env vars (Hermes Railway)

- `FASTLANE_API_KEY` — workspace-scoped key. Jonathan rotates the key shared during design and sets the new one here.
- `FASTLANE_API_BASE` — defaults to `https://api.usefastlane.ai/api/v1`; configurable for testing.

## Data flow

### Planning run

```
cron fires → Ace loads skill → fastlane_list_unposted(20)
   ↓
[item₁ ... itemₙ] (oldest-first, dedup-filtered)
   ↓
Ace inspects thumbnails → picks 2
   ↓
Ace drafts 3 captions per pick (6 total)
   ↓
Telegram message 1: post A thumbnail + [Variant 1][Variant 2][Variant 3]
Telegram message 2: post B thumbnail + [Variant 1][Variant 2][Variant 3]
   ↓
Jonathan taps → fastlane_save_daily_plan(...)
```

### Publish run

```
cron fires → fastlane_get_daily_plan(today, slot)
   ↓
status="pending"? → reply [SILENT], exit
status="chosen"?  → publisher_quick_post(media_urls=[...], caption=..., auto_publish=true)
   ↓
publisher returns OK → fastlane_mark_posted(content_id, platforms)
publisher returns Zernio 400 → retry once after 60s
publisher returns persistent error → mark slot status="failed", Telegram alert
```

## Failure modes

| Scenario | Behavior |
|---|---|
| Fastlane returns 0 unposted | Planning replies `[SILENT]`. No plan written. Both publish slots will silently skip later. |
| Fastlane returns 1 unposted | Plan only that one slot (A by default). Slot B silently skips. |
| Jonathan never taps a slot | Slot stays `pending`. Publish cron silently skips. No surprise posts. |
| Jonathan taps both, network dies before publish cron | Plan persisted on disk; publish cron reads from disk on next fire. Safe. |
| Publisher Zernio 400 | Retry once at +60s. If still failing, mark `status="failed"`, alert Telegram. Asset NOT marked posted → next day's planning may re-pick it. |
| Planning runs twice same day | Second run sees existing plan for today; if both slots already `posted`, replies `[SILENT]`. If any slot is `pending`/`chosen`, leave it alone (no overwrites). |
| Dedup file corrupt | Treat as empty (log + continue). Worst case: re-post one item. Backup is a daily snapshot left in `/opt/data/backups/fastlane_posted-YYYYMMDD.json`. |
| Fastlane API down at 08:00 | Planning fails loud (Telegram alert). No silent fallback. |

## Testing strategy

- **Unit:** `fastlane_client.py` with a mock HTTP layer (asserts URL, headers, retry behavior).
- **Unit:** `fastlane_tools.py` dedup logic — given a posted-set + an API response, returns the right filtered list.
- **Integration (manual):** Run `fastlane_list_unposted(20)` in a Hermes dev session against the live API once; confirm it lists items and dedup file is populated correctly.
- **Integration (manual):** Trigger one planning run on a dev cron; verify two Telegram messages arrive with thumbnails + buttons.
- **Integration (manual):** Manually populate `fastlane_daily_plan.json` with a known small test item; trigger a publish cron at a one-off time; confirm it ships via publisher and posts the marked file.
- **No live posting during tests** until end-to-end is verified — use a throwaway content_id known to be safe.

## Implementation order (preview, full plan in writing-plans)

1. `fastlane_client.py` + unit test
2. `fastlane_tools.py` (dedup, daily plan I/O, mark posted) + unit tests
3. Register in `toolsets.py` + `cli-config.yaml.example`
4. `fastlane-daily-plan` skill
5. Set `FASTLANE_API_KEY` on Hermes Railway (after rotation)
6. Create the three cron entries (planning + 2 publish)
7. End-to-end smoke test on one real post
8. Let it run for 3 days, watch for Zernio 400s / missed taps / dedup drift

## Open follow-ups (not blocking implementation)

- **DST handling:** UTC cron expressions assume EDT. When EST kicks in (Nov), times shift by 1h unless we add a TZ env or recreate the crons. Document this in the cron entry names.
- **Capacity ceiling:** at 2 posts/day with `_id` dedup forever, we consume Fastlane content at fixed rate. If Fastlane content generation is slower than 2/day, dedup-list eventually exhausts. Out of scope for v1; first warning sign will be planning replying `[SILENT]` for a few days running.
- **Analytics loopback:** `/api/v1/analytics/posts` exists on Fastlane. We don't use it (publisher tracks its own engagement via Zernio). Could be wired later for a unified dashboard.
