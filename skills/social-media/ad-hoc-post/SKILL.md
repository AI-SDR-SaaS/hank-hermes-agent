---
name: ad-hoc-post
description: "Post ad-hoc content to Jonathan's Instagram + TikTok via the publisher service. Use when Jonathan sends photos/video and asks to post."
version: 2.0.0
metadata:
  hermes:
    tags: [social-media, instagram, tiktok, publisher, ad-hoc, hank]
---

# Ad-hoc social media posting

When Jonathan DMs you 1-N photos (or a single video) and any message that reads like "post this", "put this on socials", "share this", or similar, the flow is:

1. **Read the image/video.** You have vision. Actually look at it before drafting.
2. **Draft 3 caption variations** in Hank's voice, each with a different angle (per your existing "Output 3 distinct variations" rule). Show them to Jonathan in chat. Each variation should be one approved-to-ship caption, not a sketch.
3. **Wait for Jonathan to pick one** (or iterate). His pick IS the approval.
4. **Once he picks, call `publisher_quick_post_file` with `auto_publish=true`** (or `publisher_quick_post` if you have URLs not local paths — see "The tool" section). The publisher uploads media to Dropbox, writes caption.md, and ships immediately to IG + TikTok. No second approval DM.
5. **Confirm in chat** with the post_id and zernio_post_id from the tool response. Reply concisely; the post is already live.

## The tool (pick one based on media source)

**For Telegram-attached photos/videos — default for this flow:** Hermes caches each attachment at `/opt/data/cache/images/img_<hash>.<ext>`. Pass those paths directly to `publisher_quick_post_file`:

```
publisher_quick_post_file(
  angle="<short-slug>",                          # required
  media_file_paths=["/opt/data/cache/images/img_xyz.jpg", ...],  # 1-10 local paths
  caption="<the variation Jonathan picked>",     # required
  title="<optional short headline>",             # TikTok carousels only
  hashtags=["tag1", "tag2", ...],                # NO leading #
  auto_publish=True,                             # always true for this flow
)
```

**For media that's already at a public HTTPS URL** (Dropbox temp link, a URL Jonathan pasted): use `publisher_quick_post` with `media_urls=[...]` instead. Same shape otherwise.

Both return `{ post_id, dropbox_root_path, uploaded_paths, publish_outcome: { kind, zernio_post_id } }`. If `publish_outcome.kind == "ok"`, it shipped. Other kinds (`zernio_failed`, `media_resolution_failed`, etc.) mean publish failed — surface that to Jonathan.

## Finding the cached file paths

Hermes's Telegram adapter writes incoming photo/video attachments to `/opt/data/cache/images/img_<hash>.<ext>`. When Jonathan DMs you a photo, the file appears there immediately. Use the terminal tool to find the most recent ones:

```
ls -tr /opt/data/cache/images/ | tail -N
```

(where `N` = number of attachments he just sent). Pass full paths (prepend `/opt/data/cache/images/`) to `publisher_quick_post_file`. You don't need `file_id`, Telegram's getFile API, or a public URL — the multipart upload handles everything.

## Variation guidance

Three captions, three angles. Pick from these (use the best 3 for the image):

- **Confidence / brand strength** — direct, identity-led. Best for IG feed.
- **Operator to operator** — relatable, explains the why. Best for longer captions.
- **TikTok native** — lowercase, faster pacing, more punctuation. Best for short-form.
- **Number-first** — lead with a stat from your verified-stats list. Best when the image illustrates a data point.
- **Storm / season tied** — anchor to a real trades scenario from AGENTS.md. Best for trades posts.

Pick the 3 that fit the image best. Label each with its angle so Jonathan can compare. Add the CTA from your rotation. Add hashtags (`["plumber", "hvactech", "servicetitan", "meethank"]` style — no leading `#`).

If the image is a carousel candidate (multiple slides), generate a `title` field too — short, with a `·` separator, e.g. `"Plumber · Sewer Backup Triage"`. TikTok shows it above the photos.

## Format your 3 drafts like this

```
**Reading the image:** [1 sentence on what you saw]

**Variation 1 — Confidence:**
[caption]
Hashtags: [list, no #]

**Variation 2 — Operator to operator:**
[caption]
Hashtags: [list, no #]

**Variation 3 — TikTok native:**
[caption]
Hashtags: [list, no #]

Which one? Or iterate?
```

When Jonathan picks (or says "go with 2" / "tweak variation 1 to ..."), call the tool. No extra "are you sure?" — the pick is the approval.

## Things NOT to do

- ❌ **Don't save drafts to Airtable.** The publisher DB is the system of record for posts. Airtable stays for retrospective logging only.
- ❌ **Don't ask "which platforms?"** Default to IG + TikTok. YouTube isn't connected.
- ❌ **Don't add a second approval step after Jonathan picks.** His pick IS the approval. Call the tool with `auto_publish=true`.
- ❌ **Don't drop the 3-variation pattern.** It's how Jonathan reviews. Don't pre-decide for him.
- ❌ **Don't use hyphens or em-dashes in captions.** Hard rule from AGENTS.md.

## Edge cases

- **Mixed media (photos + video together):** publisher rejects. Tell Jonathan it has to be all-one-type. Offer to split into two separate posts.
- **One video file:** content_type=video server-side. Title field has no effect. Generate 1 caption per variation as normal.
- **Carousel with 2+ photos:** order matters — pass `media_urls` in the order they should appear. Title shows on TikTok only.
- **Rate-limit 429s from publisher:** if `publish_outcome.kind == "media_resolution_failed"` with a 429 error, wait 60s and retry the SAME tool call once. If still failing, tell Jonathan to retry in 5-10 min (Dropbox is throttling him from a recent bulk upload).
- **publish_outcome.kind != "ok"`:** publishing failed after upload. The post row exists. Tell Jonathan what failed and offer to retry. Don't claim it shipped.

## Defaults for Hank's voice

Per SOUL.md and AGENTS.md:
- Direct, operator-to-operator. No hyphens or em-dashes (use periods, commas, or `·` for separators).
- Short, punchy sentences. Active voice. Lead with a number, a verb, or a scene.
- No SaaS buzzwords. No 🚀💡. No "let me know in the comments".
- Real trade scenarios over abstract claims. Specific dollar figures, unit ages, truck counts.
- CTA at the end (rotate: "Talk to Hank live" / "Start Your Free Trial" / "Try the Live Demo" / "Book my call with Hank" / "Ready to stop missing jobs?").
- Map each variation to one of the 5 pillars (ANSWER / BOOK / QUALIFY / FOLLOW UP / MONITOR) if it fits naturally.
