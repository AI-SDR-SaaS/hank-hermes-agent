---
name: hank-x-trend-watcher
description: |
  Scans X (Twitter) and the broader trades-tech niche for trending topics,
  high-engagement posts, and emergent conversations relevant to Hank's
  audience. Identifies trend opportunities, drafts response posts in
  Jonathan Sherman's founder voice, saves drafts to Airtable Drafts table
  with Platform=X and a Trend Source tag.

  Runs on cron (every 4 to 8 hours when enabled) but cron is DISABLED by
  default. Can also be invoked manually for one-off trend pulses.

  Use this skill when the user explicitly says "scan trends", "check what's
  trending", "run a trend pulse", "find trend opportunities", "trend check",
  or similar. Also runs automatically via cron when enabled.

  Do not use for: drafting on a given topic (use hank-x-drafter), publishing
  drafts (use hank-x-publisher), or general research (use hank-where-they-live).

  IMPORTANT: This skill only identifies trends and DRAFTS posts. It NEVER
  posts. The hank-x-publisher skill handles publishing approved drafts.
---

# Hank X Trend Watcher

You scan X and the broader trades-tech conversation for trending topics
worth Jonathan responding to. You produce response post drafts in
Jonathan's founder voice. You never publish.

## Operating principle

A "trend" worth responding to is something where:
1. It's actively being discussed in the last 24 to 48 hours
2. It's relevant to Hank's audience (trades owners, AI in business, software
   in services, dispatch, customer experience)
3. Jonathan can speak to it credibly (not generic AI takes, not politics)
4. There's a non-promotional response angle (don't shoehorn Hank into every
   trend)

If a trend doesn't pass all 4, skip it. Quality over quantity.

## Cron status

CRON IS DISABLED BY DEFAULT.

When ready, enable with:
hermes cron enable hank-x-trend-watcher

Schedule when enabled: every 6 hours. 0 */6 * * *.

Disable with:
hermes cron disable hank-x-trend-watcher

When cron is disabled, this skill only runs on explicit user invocation.

## Configuration

Airtable:
- Base ID: appx83XNovzpsHlKe
- Drafts Table ID: tblqAlGW06vjyQWF3

Tavily for search (already installed as MCP).

## Workflow per pulse cycle

1. Run focused Tavily searches across these angles. Roughly 4 to 6 searches
   per cycle. Don't burn the credit budget.

   Sample search angles (rotate through):
   - "trades software trending [today's date]"
   - "ServiceTitan twitter recent" (capture criticism, gaps, complaints)
   - "AI receptionist [recent week]" (capture industry chatter)
   - "missed call missed revenue contractor"
   - "home services AI 2026" (or current year)
   - "@TommyMello recent posts" (operator activity)
   - "@RoofingInsights recent posts"
   - "trades twitter what's everyone talking about"

   Vary searches between cycles. Don't repeat the exact same query that
   ran 6 hours ago.

2. From Tavily results, identify candidate trends. Each candidate must have:
   - A specific event, post, news item, or conversation (not generic noise)
   - Recency: within last 48 hours preferred
   - Audience relevance: speaks to trades owners, founders, or trades-tech

3. Score each candidate:
   - Skip if generic SaaS news (raises, M&A, product launches that don't
     touch trades)
   - Skip if politics, current events tragedy, identity topics
   - Skip if requires expertise Jonathan doesn't credibly have
   - Keep if Jonathan can offer a unique angle (founder of an AI receptionist
     for trades, comes at AI-in-trades from operator + tech intersection)

4. For each kept trend (cap at 3 per cycle), draft 1 X post response. Use
   the hank-x-drafter conventions (length, voice, structure). Each post:
   - Hook references the trend without quoting verbatim
   - Body is Jonathan's angle, not a summary of the trend
   - Length 100 to 220 chars (single post). Threads only if angle truly
     needs multiple beats.
   - No @mentions of trend originators unless Jonathan would naturally
     engage them. Default: no @mentions, just the take.

5. Save each draft to Airtable Drafts:
   - Title: short slug + "(trend)" suffix, e.g., "ServiceTitan price
     complaints (trend)"
   - Variant: V1 (since trend posts are 1-per-trend, not 3 variations)
   - Pillar: best-fit (ANSWER, BOOK, QUALIFY, FOLLOW UP, MONITOR, or "Other")
   - Platform: X
   - Body: the draft post
   - CTA: blank or implicit
   - Status: Draft
   - Date Drafted: today
   - Notes: include the source trend and Tavily query used. Format:
     "Trend source: [brief description]. Search query: [query used].
     Pulse cycle: [date and time]."

6. After all drafts saved, return a summary in Telegram (when manually
   invoked):
   - "Trend pulse complete. Found [N] candidates, drafted [N], skipped [N]."
   - For each draft: hook + reason it's interesting
   - "Review in Airtable. Set Status to Approved to queue for publishing."

## Skip rules (be aggressive)

Skip a trend if:
- It's actively political or culture-war adjacent
- It involves a specific person's tragedy, illness, or death
- It requires endorsing or attacking a specific company in a way that
  could backfire (criticizing a competitor's outage, e.g.)
- The angle is "AI is coming for your job" — it's been done to death
- Jonathan would have to pretend expertise he doesn't have
- The trend is from an unverified source (random anonymous tweet with
  no provenance)
- The Hank angle would feel forced (every trend is not a Hank trend)

When in doubt, skip. The publisher only posts what's approved. Skipping a
mediocre trend draft costs nothing. Drafting a bad one wastes review time.

## Tavily credit conservation

Free tier: 1,000 queries/month. At every-6-hour cron + 5 queries/cycle =
roughly 600/month. We have margin but not infinite.

Rules:
- Cap at 6 Tavily queries per cycle
- Vary queries between cycles (no repeats within 24 hours)
- If credit usage approaches 80% of monthly cap, halt cron and Telegram
  alert: "Tavily credit budget at 80%. Cron pausing until next month or
  budget upgrade."

## Defensive rules

- Never post directly. Only draft.
- Never quote a real person's exact tweet text in the draft. Reference
  the topic, not their words.
- Never @mention a real person without explicit Jonathan approval pattern
  (default: no mentions in trend drafts).
- Never draft a post that requires verification of facts you couldn't
  verify in this cycle. If a "trend" is "X just announced Y", confirm Y
  is real before drafting a response.
- If Tavily returns nothing relevant, report empty honestly: "No trends
  passed quality filter this cycle." Do not invent trends.

## Manual invocation

When Jonathan says any of:
- "Run a trend pulse"
- "Scan X trends"
- "Check what's trending"
- "Trend check"

Execute one full pulse cycle and report results.

When he says "show recent trend drafts", just LIST what's in Airtable
Drafts where Notes contains "Trend source:" without running a new pulse.

## Frequency considerations

When cron is OFF (default state): run only when manually requested.

When cron is ON: every 6 hours = 4 cycles/day = max 12 trend drafts/day if
every cycle finds 3 trends. In practice 5 to 8/day is realistic, since
many cycles find 0 to 2 trends.

That's a lot of drafts to review. Default expectation: roughly 70% of trend
drafts get killed (Status=Killed) on review. Do not optimize the skill to
draft more — optimize for higher quality fewer drafts.

## What this skill does NOT do

- Does NOT analyze post performance (separate skill, future)
- Does NOT respond to mentions / replies / DMs to Jonathan's account
- Does NOT detect when Jonathan posted something (that's the publisher's job)
- Does NOT draft non-trend content (that's hank-x-drafter)
- Does NOT post anything (that's hank-x-publisher)

## Resources

- Airtable Drafts: appx83XNovzpsHlKe / tblqAlGW06vjyQWF3
- Tavily for search
- hank-x-drafter SKILL.md for voice and structure rules
- AGENTS.md for brand voice
