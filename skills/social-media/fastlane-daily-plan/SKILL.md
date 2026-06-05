---
name: fastlane-daily-plan
description: Runs once per morning. Pulls unposted Fastlane videos, takes the first 2 oldest-first, drafts 3 caption variants per post, sends Jonathan Telegram pickers for both. When he taps, saves the chosen caption into today's plan; the publish-slot crons drain it later.
---

# Fastlane daily plan

This skill is loaded by the **`fastlane-daily-plan`** cron entry that fires at
08:00 ET. It DOES NOT post anything itself — it only curates and parks the
plan on disk. Two separate cron entries (`fastlane-publish-slot-a` at 11:30
ET and `fastlane-publish-slot-b` at 18:00 ET) drain the plan via
`publisher_quick_post(auto_publish=true)`.

## Workflow

0. **Load recent picks for tone context.** Call `fastlane_recent_caption_history({"limit": 10})`.
   Use the returned `records` (each has `chosen` + `rejected`) as concrete examples
   of Jonathan's taste when drafting today's variants. Match the patterns you see —
   tone, hashtag density, length, what he picks vs what he rejects.

1. **Pull candidates.** Call `fastlane_list_unposted({"limit": 20})`.
   - If `items` is empty → reply with the single token `[SILENT]` and stop.
     The publish slots will silently skip too. No Telegram noise.

2. **Take the first 2.** The tool returns oldest-first (drains backlog). The
   first item becomes slot A (11:30 ET), the second becomes slot B (18:00 ET).
   If only 1 item is available, plan slot A only and tell Jonathan slot B will
   skip today.

3. **Read the on-screen text from each thumbnail, then draft 3 caption variants per pick.**
   Every Fastlane video has its script burned in as a text overlay. The
   `thumbnail_url` in each item is a still frame that captures that text — open
   the image and read it. The text IS the video's script and the SOLE source of
   truth for what the clip is about. The `type` field is just a layout hint
   (`wall-of-text`, `green-screen`, `video-hook`, `slideshow`, `remix`); it
   doesn't tell you the topic.

   For each post:
   - Vision-read the `thumbnail_url` and transcribe the on-screen text mentally —
     that's the video's actual script.
   - Captions should COMPLEMENT what's on screen, not restate it. The viewer will
     watch the clip; your caption is the hook above/below that adds context,
     curiosity, or a CTA.
   - Voice follows `skills/social-media/ad-hoc-post/SKILL.md`, refined by the
     recent-history examples from step 0.
   - **Each variant MUST be the full publisher-format markdown:**
     ```
     ## Caption
     <body>

     ## Hashtags
     #tag1 #tag2 #tag3
     ```
     A bare one-line caption with no `## Hashtags` block will fail the publisher
     parser downstream. This format is non-negotiable.
   - No `# Title` (TikTok carousel only; these are videos).

4. **Persist the picker BEFORE sending Telegram.** Call `fastlane_save_picker` with
   today's ET date, both slot objects (each containing `content_id`, `media_url`,
   `thumbnail_url`, `type`, and the 3 full-format `variants`). This is the source
   of truth the chat-mode agent will consult when Jonathan replies with "A2" or
   "B1 with edits" — without it, Jonathan's tap can't be resolved.

5. **Send Telegram pickers.** Two messages, one per post:
   - **First line of message body must be the `media_url` (.mp4) on its own line** so
     Telegram auto-embeds the video preview.
   - Below the URL: a numbered label + the first line of each caption variant.
     Format each line as `A1: <first line of variant 1>` etc. for slot A, `B1:`
     etc. for slot B.
   - Tell Jonathan he can reply with the label (e.g. `A2`) or with edits
     (e.g. `A2 but change "Hank AI" to "Hank the Pro"`).

6. **Confirmation message.** After both pickers are sent, end with a single line:
   `Picker saved for <YYYY-MM-DD>. Reply with A1/A2/A3 (slot A) and B1/B2/B3
   (slot B), with optional edits.`

## How Jonathan's taps get resolved (NOT part of this cron)

When Jonathan replies in Telegram with something like `A2` or `B1 with Hank AI -> Hank the Pro`, the chat-mode Ace agent (different session) handles it by calling:

```
fastlane_resolve_pick({
  "date": "<today in ET>",
  "slot": "a" | "b",
  "variant_index": 1 | 2 | 3,
  "replacements": [{"old": "...", "new": "..."}]  # optional
})
```

That one tool loads the picker, resolves the variant, applies replacements, writes the daily plan slot, and appends to caption history. No further action needed from this cron.

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
