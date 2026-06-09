---
name: fastlane-publish-slot
description: Publishes pre-planned Fastlane content to Instagram + TikTok at scheduled times (slots A and B). Runs twice daily via cron (11:30 ET for slot A, 18:00 ET for slot B). Fetches the day's plan, checks if the slot is marked 'chosen', publishes to both platforms with auto_publish=true, then marks the content as posted. On Zernio 400 error, retries once after 60s.
---

# Fastlane Publish Slot

Publishes pre-planned Fastlane content (video + caption) to Instagram and TikTok at two fixed times per day: **slot A at 11:30 ET** and **slot B at 18:00 ET**.

This cron job is part of the Fastlane daily publishing workflow:
1. **08:00 ET**: `fastlane-daily-plan` skill curates 2 videos, drafts captions, sends Telegram pickers for Jonathan approval.
2. **11:30 ET**: `fastlane-publish-slot` (slot=a) drains approved slot A → publishes.
3. **18:00 ET**: `fastlane-publish-slot` (slot=b) drains approved slot B → publishes.

No manual approval between plan curation and publishing — Jonathan's Telegram tap IS the approval, already saved to the plan.

## Workflow

### 1. Compute today's date in America/New_York timezone
Use datetime with timezone offset or equivalent. Result must be `YYYY-MM-DD` format.

### 2. Fetch the day's plan for this slot
```
fastlane_get_daily_plan(date="<YYYY-MM-DD>", slot="a" | "b")
```

Response structure:
```json
{
  "status": "chosen" | "pending" | "skipped",
  "slot": {
    "content_id": "<string>",
    "media_url": "<string>",
    "chosen_caption": "<markdown: ## Caption ... ## Hashtags ...>"
  }
}
```

### 3. Check status
- **status == "chosen"**: Proceed to step 4 (publish).
- **status == "pending"**: Reply with `[SILENT]`. Jonathan hasn't picked a caption yet. No noise.
- **status == "skipped"**: Reply with `[SILENT]`. Slot was manually skipped or no backlog.
- Any other status: Reply with `[SILENT]`.

### 4. Publish to Instagram + TikTok
Call:
```
publisher_quick_post(
  media_urls=[plan.slot.media_url],
  caption=plan.slot.chosen_caption,
  auto_publish=true
)
```

Response on success:
```json
{
  "status": "success",
  "posts": [
    {
      "platform": "instagram",
      "post_id": "<string>",
      "url": "<string>"
    },
    {
      "platform": "tiktok",
      "post_id": "<string>",
      "url": "<string>"
    }
  ]
}
```

### 5. Mark content as posted
On success, call:
```
fastlane_mark_posted(
  content_id=plan.slot.content_id,
  platforms=["instagram", "tiktok"]
)
```

### 6. Report
On successful publish + mark:
- Reply with `[SILENT]` (no noise for routine posts).
- Internally log: "Slot X published: <short caption> → Instagram + TikTok".

## Failure Handling

| Scenario | Condition | Action |
|---|---|---|
| No plan available | `fastlane_get_daily_plan` error or empty response | Reply `[SILENT]`. ✓ Normal — slot may be empty. |
| Pending slot | status="pending" | Reply `[SILENT]`. Jonathan hasn't approved yet. ✓ Normal. |
| Zernio 400 on publisher | `publisher_quick_post` returns HTTP 400 | **Retry once**: wait 60s, call again. If still 400 → give up, log error, report to Jonathan in Telegram. |
| Publisher error (other) | `publisher_quick_post` returns 5xx or network error | Report to Jonathan in Telegram. Do not retry. |
| Mark posted fails | `fastlane_mark_posted` returns error | Report to Jonathan in Telegram (post did publish, but tracking failed). |

## What you do NOT do

- Do NOT invent or hardcode captions. Use only `plan.slot.chosen_caption` from the daily plan.
- Do NOT call Fastlane's own `/posts` endpoints. All Fastlane posting goes through the publisher.
- Do NOT retry indefinitely on Zernio 400. Retry ONCE after 60s, then give up.
- Do NOT publish if status != "chosen". Silent skip is the right behavior.
- Do NOT post to any platform other than Instagram and TikTok.

## Exit Codes

- **[SILENT]**: No plan, pending slot, or routine success. Normal flow.
- **Error logged to Telegram**: Publisher failure, API error, or retry exhaustion.
