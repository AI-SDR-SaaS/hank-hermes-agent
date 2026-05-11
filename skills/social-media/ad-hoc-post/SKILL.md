---
name: ad-hoc-post
description: "Post ad-hoc content to Jonathan's Instagram + TikTok via the publisher service. Use when Jonathan sends photos/video and asks to post."
version: 1.0.0
metadata:
  hermes:
    tags: [social-media, instagram, tiktok, publisher, ad-hoc]
---

# Ad-hoc social media posting

**Default to action, not over-clarification.** When Jonathan sends you 1-N photos (or a single video) and any message that reads like "post this", "put this on socials", "share this", or similar, your job is to put it through the publisher pipeline IMMEDIATELY — no Airtable drafts, no asking which platforms (default is IG + TikTok), no asking him to pick between three variations.

## The one tool that matters: `publisher_quick_post`

This tool does the whole job in one call: uploads the media to Dropbox, writes a `caption.md`, creates a Post row, and sends Jonathan an approval DM in Telegram (from a separate bot — the **Hank Publisher Approvals** bot, not you). Jonathan reviews the caption + tap Approve there. **You don't post anything; the publisher does, after he taps Approve.** So you can just call the tool — that's the human gate.

```
publisher_quick_post(
  angle="<short-slug>",                   # required, e.g. "logo-rebrand-tease"
  media_urls=[<https URLs>, ...],         # required, 1-10 fetchable URLs
  caption="<your caption text>",          # required, non-whitespace
  title="<optional short headline>",      # optional, only used by TikTok carousels
  hashtags=["tag1", "tag2", ...],         # optional, no leading #
  # brand defaults to "hankai", cta defaults to "book-demo" — usually skip these
)
```

Returns `{ post_id, dropbox_root_path, uploaded_paths }`. The approval DM is already on its way to Jonathan when this returns.

## Workflow when Jonathan DMs you with attached photos

1. **Get the media URLs from Telegram.** Each attached photo/video comes with a `file_id` in the Telegram update. To turn that into a downloadable URL: call Telegram's `getFile` API with `file_id`, get back `file_path`, then construct `https://api.telegram.org/file/bot<TELEGRAM_BOT_TOKEN>/<file_path>`. This URL is fetchable for ~1 hour. If you don't have a wrapper tool for this, do it inline with `curl` or the terminal.

2. **Pick `angle` from Jonathan's message.** Short hyphen-joined slug, no underscores. Examples: `logo-rebrand-tease`, `customer-win-screenshot`, `behind-the-scenes-shop`. If his message gives you nothing, use a generic + the date: `adhoc-2026-05-11`.

3. **Write the caption** in Hank's voice (punchy, trades-floor tone, no corporate fluff, no hyphens for stylistic flair). Don't write multiple "variations" — write ONE caption. Jonathan will reject or iterate in Telegram if he wants different wording.

4. **Add hashtags** (3-8 is fine). Same voice as everything else — `#plumber #hvactech #servicetitan #meethank` over `#smallbusinessowner #entrepreneur #grindset`.

5. **Optionally add a `title`** if it's a carousel — TikTok shows it above the photos. Examples: `Plumber · Sewer Backup Triage`, `Solo · $18/day`. Short, punchy, with a `·` separator. Skip for single video/static posts.

6. **Call `publisher_quick_post`**. Reply to Jonathan with a short confirmation that the approval DM is on its way (the **Hank Publisher Approvals** bot will DM him a preview within seconds).

## Things NOT to do

- ❌ **Don't save to Airtable as a draft.** The publisher's DB is the system of record. Airtable is for retrospective logging only.
- ❌ **Don't write 3 caption variations and ask him to pick.** Write the one you'd ship. He has the Approve/Reject buttons in Telegram for the rare case where it's wrong.
- ❌ **Don't ask "which platforms?"** Defaults are IG + TikTok. YouTube isn't connected. Unless he explicitly says "just IG" or "just TikTok", post to both.
- ❌ **Don't refuse with "Jonathan approves first" boilerplate.** The publisher's Telegram approval IS his approval. You're not bypassing it by calling the tool — you're triggering it.
- ❌ **Don't run his caption past him before calling the tool.** Just call it; the Telegram DM gives him the same review opportunity, faster.

## When to actually ask a clarifying question

Only if:
- The angle is genuinely ambiguous AND a wrong guess would be embarrassing (e.g., he says "post this" with no description and the image is a screenshot of something not obviously brand-related)
- He's sending multiple photos and it's unclear whether they're a single carousel or N separate posts
- He hasn't given enough text to write a caption that won't sound generic

Otherwise: action first, iterate in Telegram if he rejects.

## Defaults for Hank's voice

Read `SOUL.md` for the full guide. Quick reminders for captions:
- Direct, operator-to-operator. No hyphens for stylistic dashes (use periods or `·`).
- One-clause sentences are fine. Active voice.
- The CTA at the end of most captions: book a demo, start a trial, DM us — match what the post is about.
- No "🚀", no "💡", no "let me know in the comments". Hank doesn't talk like a SaaS LinkedIn poster.

## Edge cases

- **One video file:** content_type will be inferred as `video` server-side. Caption + (optional) hashtags work the same.
- **One photo:** inferred as `static`. Title field has no effect.
- **2+ photos:** inferred as `carousel`. Order matters — pass `media_urls` in the order you want them shown. Title appears on TikTok only.
- **Mixed media (photo + video):** publisher rejects. Tell Jonathan it has to be all-one-type.
- **Rate-limit 429s from Dropbox:** if `publisher_quick_post` returns an upload error, wait 60 seconds and retry once. If still failing, tell Jonathan to retry in 5-10 minutes (he probably just did a bulk upload).
