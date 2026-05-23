# Fastlane Cron — Setup Runbook

One-time deploy steps to activate the Fastlane → Hank publisher daily
cron after the implementation has been merged.

## 1. Set the API key on Hermes Railway

In the `kind-generosity` project → `hermes` service → Variables:

| Key | Value |
|---|---|
| `FASTLANE_API_KEY` | Workspace key from app.usefastlane.ai → API keys (shape: `fsln_live_*`) |
| `FASTLANE_API_BASE` | Leave unset (defaults to `https://api.usefastlane.ai/api/v1`) |

Redeploy after setting. Confirm:

```bash
railway run -- python -c "from tools.fastlane_client import check_fastlane_requirements; print(check_fastlane_requirements())"
```

Expected: `True`.

## 2. Smoke test the live API

From the Hermes shell (`railway ssh` into hermes):

```bash
python -c "
from tools import fastlane_client
r = fastlane_client.list_content(limit=3)
print('items:', len(r['data']))
print('first id:', r['data'][0]['_id'] if r['data'] else 'none')
"
```

Expected: 3 items, an `_id` prefixed `p...`. If `403 forbidden`, the key
is a Partner key, not a workspace key — regenerate as workspace.

## 3. Create the three cron entries

All times are in UTC (Railway containers run UTC). The cron expressions
below assume **EDT** (UTC-4). When EST kicks in (first Sunday of November)
the expressions need to shift by 1h, or set `TZ=America/New_York` on the
container and rewrite in ET.

```bash
# Planning — daily at 08:00 ET (= 12:00 UTC during EDT)
hermes cron create "0 12 * * *" \
  "Run the fastlane-daily-plan workflow. Curate 2 posts from Fastlane, draft 3 caption variants per post, send Telegram pickers." \
  --skills "fastlane-daily-plan" \
  --toolsets "fastlane" \
  --name "Fastlane daily plan" \
  --deliver telegram

# Publish slot A — daily at 11:30 ET (= 15:30 UTC during EDT)
hermes cron create "30 15 * * *" \
  "Today's date in ET is \$(date -u -d '5 hours ago' +%Y-%m-%d). Call fastlane_get_daily_plan(date=that, slot='a'). If status=='chosen', call publisher_quick_post(media_urls=[plan.slot.media_url], caption=plan.slot.chosen_caption, auto_publish=true). On success, call fastlane_mark_posted(content_id=plan.slot.content_id, platforms=['instagram','tiktok']). On Zernio 400, wait 60s and retry once before giving up. If status=='pending' or no plan, reply [SILENT]." \
  --toolsets "fastlane,publisher" \
  --name "Fastlane publish slot A (11:30 ET)" \
  --deliver telegram

# Publish slot B — daily at 18:00 ET (= 22:00 UTC during EDT)
hermes cron create "0 22 * * *" \
  "Today's date in ET is \$(date -u -d '4 hours ago' +%Y-%m-%d). Call fastlane_get_daily_plan(date=that, slot='b'). Same logic as slot A." \
  --toolsets "fastlane,publisher" \
  --name "Fastlane publish slot B (18:00 ET)" \
  --deliver telegram
```

Verify with:

```bash
hermes cron list
```

## 4. End-to-end smoke

Pick a Fastlane content_id that is safe to actually post (e.g. one you'd
ship today anyway). Manually trigger the planning cron earlier than 08:00
ET to dry-run:

```bash
hermes cron run "Fastlane daily plan" --now
```

Watch for both Telegram messages. Tap a caption on each. Then run a
single publish cron manually:

```bash
hermes cron run "Fastlane publish slot A (11:30 ET)" --now
```

Confirm the post landed on IG and TikTok. Confirm `posted.json`
on the Hermes Railway disk now contains the `_id`:

```bash
railway run -- cat /opt/data/fastlane/posted.json
```

## 5. Three-day observation window

Leave it running for three days. Each morning, check:
- Both Telegram pickers arrived at 08:00 ET ± a couple of minutes.
- Captions look on-voice.
- Posts landed at 11:30 ET and 18:00 ET.
- No item shipped twice (`posted.json` grows by 2 per day).

If any of the above drift, treat as v1 issues and iterate on the skill
or cron prompts before bothering with new features.

## DST cutover

EST starts on Sunday Nov 2, 2026 at 02:00 ET. On Nov 1, recreate the three
cron entries with UTC expressions shifted +1h:

| Slot | EDT cron | EST cron |
|---|---|---|
| Planning | `0 12 * * *` | `0 13 * * *` |
| Publish A | `30 15 * * *` | `30 16 * * *` |
| Publish B | `0 22 * * *` | `0 23 * * *` |
