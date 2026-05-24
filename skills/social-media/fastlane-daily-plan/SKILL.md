---
name: fastlane-daily-plan
description: Runs once per morning. Pulls unposted Fastlane videos, picks 2 for the day, drafts 3 caption variants per post, sends Jonathan Telegram pickers for both. When he taps, saves the chosen caption into today's plan; the publish-slot crons drain it later.
---

# Fastlane daily plan

This skill is loaded by the **`fastlane-daily-plan`** cron entry that fires at
08:00 ET. It DOES NOT post anything itself — it only curates and parks the
plan on disk. Two separate cron entries (`fastlane-publish-slot-a` at 11:30
ET and `fastlane-publish-slot-b` at 18:00 ET) drain the plan via
`publisher_quick_post(auto_publish=true)`.

## Workflow

1. **Pull candidates.** Call `fastlane_list_unposted({"limit": 20})`.
   - If `items` is empty → reply with the single token `[SILENT]` and stop.
     The publish slots will silently skip too. No Telegram noise.

2. **Inspect thumbnails.** For each candidate, the `thumbnail_url` is a
   `.webp` on a public CDN. Look at them. The `type` field is your other
   signal (`wall-of-text`, `green-screen`, `video-hook`, `slideshow`, `remix`).

3. **Pick 2.** Choose the two strongest based on visual content. Prefer
   variety: don't pick two `wall-of-text` back-to-back when there's a
   `green-screen` or `video-hook` available. The earlier-creation-time one
   becomes slot A (11:30 ET), the later one becomes slot B (18:00 ET).

4. **Draft 3 caption variants per pick.** For each post:
   - Captions follow Hank's voice from `skills/social-media/ad-hoc-post/SKILL.md`.
   - Format each variant as the markdown the publisher expects:
     ```
     ## Caption
     <body>

     ## Hashtags
     #tag1 #tag2 #tag3
     ```
   - No `# Title` (TikTok carousel only; these are videos).

5. **Send Telegram pickers.** Two messages, one per post:
   - Message body: thumbnail URL + a 1-line summary per variant.
   - Inline keyboard: three buttons, payload encodes `slot` + `variant_index`
     so the bot adapter can route the tap back to a handler that calls
     `fastlane_save_daily_plan(...)` with the chosen caption.

6. **On each tap, persist.** Call:
   ```
   fastlane_save_daily_plan({
     "date": "<YYYY-MM-DD in ET>",
     "slot": "a" | "b",
     "content_id": "<from step 3>",
     "media_url": "<from step 1 items[i].media_url>",
     "chosen_caption": "<the full ## Caption + ## Hashtags markdown>"
   })
   ```

7. **Confirmation.** When both slots are status="chosen", reply with a 1-line
   summary to Jonathan: "Plan locked — A at 11:30 ET (<short caption>), B at
   18:00 ET (<short caption>)."

## Failure handling

| Situation | Action |
|---|---|
| `fastlane_list_unposted` returns 0 items | Reply `[SILENT]`. No Telegram messages. |
| Returns only 1 item | Plan only slot A. Tell Jonathan slot B will skip today. |
| `fastlane_list_unposted` returns an error | Forward the error to Jonathan in Telegram so he knows the cron tried and failed. Do not silently swallow. |
| Jonathan ignores the picker | The slot stays `status="pending"`. The publish cron will silently skip at slot time. No retry. |

## What you do NOT do

- Do NOT call `publisher_quick_post` from this skill. That's the publish-cron's job.
- Do NOT use Fastlane's own `/posts` or `/connections` endpoints. We post via the publisher only.
- Do NOT pick more than 2 posts. Cadence is fixed.
- Do NOT skip the Telegram approval. Even though this is automated, Jonathan
  has final say on every caption.
