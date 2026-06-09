---
name: blog-publisher-cron
description: |
  Publish approved blog posts from Airtable to meethank.ai/api/blog/posts.
  Runs Tuesdays and Thursdays at 8 AM ET via cron.
  Validates posts before publishing (slug format, no headers, valid MDX, allowed CTAs).
  Sends Telegram notifications on success or failure.
author: Ace
created: 2026-05-07
tags:
  - blog
  - publishing
  - automation
  - airtable
---

# Blog Publisher Cron

**Path:** `/opt/data/cron/blog-publisher.py`
**Schedule:** Tuesday and Thursday, 8:00 AM ET
**Cron Job ID:** `4f1adb9d7423`

## What It Does

1. Queries Airtable for records with Status = "Approved" (max 25 per run)
2. Validates each post (slug, headers, MDX components, CTA hrefs)
3. Skips invalid posts and Telegrams the failures
4. POSTs valid posts as a batch to `meethank.ai/api/blog/posts`
5. On 200 response, updates Airtable Status to "Published" and sets Posted Date
6. Sends Telegram summary with PR URL, branch, and file list

## Validation Rules

- **Slug:** Derived from Name, must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`
- **Headers:** Body cannot contain `#`, `##`, or `###` markdown headers
- **MDX Components:** Only allowed: `<Cta>`, `<CtaPair>`, `<Callout>`, `<KeyStat>`, `<Quote>`, `<PricingTeaser>`
- **CTA hrefs:** Must match one of:
  - `^/$`
  - `^/how-it-works$`
  - `^/pricing$`
  - `^/pricing#plans$`
  - `^/contact$`
  - `^/blog$`
  - `^/industries/.*`
  - `^/integrations/.*`
  - `^/vs/.*`
  - `^/best-ai-receptionist-for-hvac$`
  - `^/privacy$`
  - `^/terms$`

## Environment Variables (Required in Railway)

```
AIRTABLE_API_KEY       Bearer token with data.records:read/write (REQUIRED)
BLOG_API_KEY           Bearer token for meethank.ai/api/blog/posts (REQUIRED)
TELEGRAM_BOT_TOKEN     Telegram bot token (REQUIRED — script will fail loudly if not set)
TELEGRAM_CHAT_ID       Telegram chat ID (REQUIRED — script will fail loudly if not set)
```

**IMPORTANT:** If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not set, the script will:
1. Print a warning with clear instructions
2. Exit with code 1 (failure)
3. This forces you to configure Telegram before the cron can run

This is by design — Telegram notifications are mandatory for production visibility.

## Usage

### Live Run (production)
```bash
/opt/data/cron/blog-publisher.py
```

### Dry Run (test without changes)
```bash
/opt/data/cron/blog-publisher.py --dry-run
```

### Custom Limit
```bash
/opt/data/cron/blog-publisher.py --limit 5
/opt/data/cron/blog-publisher.py --dry-run --limit 10
```

## API Spec

**POST** `https://meethank.ai/api/blog/posts`
**Headers:** `Authorization: Bearer ${BLOG_API_KEY}`, `Content-Type: application/json`

**Request body:**
```json
{
  "posts": [
    {
      "slug": "post-title-kebab-case",
      "frontmatter": {
        "title": "Post Title",
        "description": "First 180 chars of body or Description field",
        "date": "YYYY-MM-DD",
        "author": "Jonathan S",
        "pillar": "ANSWER|BOOK|QUALIFY|FOLLOW UP|MONITOR",
        "format": "blog|guide|...",
        "keyword": "primary-seo-keyword",
        "draft": false,
        "tags": [],
        "image": null
      },
      "content": "# Full MDX body content as-is"
    }
  ],
  "branchSuffix": "YYYYMMDD"
}
```

**Success response (200):**
```json
{
  "ok": true,
  "prUrl": "https://github.com/AI-SDR-SaaS/ai-assistant-website/pull/9",
  "prNumber": 9,
  "branch": "blog/posts-20260507-2",
  "files": ["content/blog/test-post-live-publisher-run.mdx"],
  "previewHint": "Vercel will deploy a preview URL on this PR within ~60 seconds. Check the PR for the preview link."
}
```

## Error Handling

- **Validation fails:** Skipped post logged, remaining posts published, Telegram notified
- **All posts fail validation:** Exit 1, Telegram notified, no Airtable changes
- **API error:** Exit 1, error body sent to Telegram, no Airtable changes
- **Missing env vars:** Exit 1 with clear error message. This is intentional—the script requires all env vars to be set in Railway before it runs.

### Troubleshooting: "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"

If you see this error locally but the vars are set in Railway:
1. This is normal. Local Hermes agent sessions do NOT automatically inherit Railway env vars.
2. Do NOT retry manually. The cron job in Railway will have access to the vars.
3. On Tuesday/Thursday 8 AM ET, the cron job will run in a fresh Railway process with full env var access.
4. If the cron job fails, check the Railway logs to verify the vars are actually set on the service.

## Exit Codes

- 0: Success (or dry-run complete)
- 1: Failure (API error, all posts invalid, missing config)

## Notes

- Uses Python 3 stdlib only (urllib, json, re). No external dependencies.
- **Telegram is mandatory:** Script exits 1 with a clear error if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are missing. This forces configuration before production use.
- DRY-RUN never updates Airtable or hits blog API; all output is logged stdout.
- **Railway env var isolation:** When testing in a local Hermes agent session, env vars may not be visible even though they are set in Railway. This is expected. The cron job runs in Railway as a fresh process and will have access to all configured vars. Do NOT retry or assume missing local visibility = missing from Railway.

## Test Invocation

```bash
python3 /opt/data/cron/blog-publisher.py --dry-run --limit 2
```

Expected dry-run output:
```
[2026-05-07T13:48:15.515496] Starting blog publisher (dry_run=True)
Found 1 approved posts
✓ Post Title
Publishing 1 valid posts...
[DRY-RUN] Would POST to blog API
[DRY-RUN] Would update Airtable record recX... to Published
[DRY-RUN OK] Published 1 posts
```

## Cron Job Management

**List jobs:**
```
cronjob action=list
```

**Pause/Resume:**
```
cronjob action=pause job_id=4f1adb9d7423
cronjob action=resume job_id=4f1adb9d7423
```

**Test run now:**
```
cronjob action=run job_id=4f1adb9d7423
```

**Remove job:**
```
cronjob action=remove job_id=4f1adb9d7423
```
