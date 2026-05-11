---
name: posthog-monitor
description: "Investigate PostHog data, discuss findings with Jonathan in Telegram, then ship copy/UX tweaks to the marketing site via PR with Vercel preview + Cubic review."
version: 1.0.0
metadata:
  hermes:
    tags: [posthog, analytics, monitoring, telegram, vercel, github, pr-workflow]
    related_skills: [ad-hoc-post]
---

# PostHog Monitor — Investigate, Discuss, Ship

You watch the marketing site's PostHog data, surface findings to Jonathan in Telegram, talk through what to do about them, and — when Jonathan says go — open a PR against the website repo with the tweak. Vercel auto-builds a preview; Cubic auto-reviews. You report both back. Jonathan says "merge" and you ship.

## The closed loop

```
cron / question  →  PostHog MCP  →  digest in Telegram
                                          ↓
                                 Jonathan discusses
                                          ↓
                              "do it" / specific tweak
                                          ↓
                  clone site repo → edit → branch → PR
                                          ↓
                Vercel preview build   +   Cubic review
                                          ↓
                     consolidated status in Telegram
                                          ↓
                              "merge" / iterate
                                          ↓
                              gh pr merge --squash
                                          ↓
                      Vercel auto-deploys to prod
                                          ↓
                  next digest measures whether it worked
```

## Inputs from environment

These come from Railway env vars — already injected into the process:

- `POSTHOG_PERSONAL_API_KEY` — read-only PostHog scopes
- `POSTHOG_PROJECT_ID` — numeric, pinned in MCP context
- `WEBSITE_GITHUB_TOKEN` — fine-grained PAT, scoped to the website repo only. Kept separate from `GITHUB_TOKEN` (which is for the skills hub) so neither over-permissions the other. Pass it to every `gh` and `git` call in this skill — see Phase 4.
- `WEBSITE_REPO_URL` — the marketing-site repo to edit (e.g. `https://github.com/AI-SDR-SaaS/ai-assistant-website`)
- `TELEGRAM_HOME_CHANNEL` — where scheduled digests land
- `TZ` — `America/New_York`, so cron times match Jonathan's clock

If any are missing, say so plainly in chat instead of guessing.

## Phase 1 — Investigate

Use the PostHog MCP tools registered under the `posthog` server. Common patterns:

- **Funnel digest:** run a HogQL query against `events` for the funnel steps Jonathan defined (signup, demo request, checkout, etc.), compare yesterday/last-week to the prior period, surface the steps where conversion moved.
- **Recordings sanity check:** list recent session recordings filtered for `rage_click`, `dead_click`, or sessions that landed on a page and bounced. Pick 1–3 representative ones, summarize what the user did, link the URL.
- **Errors:** check the error tracking endpoint for new or spiking error groups in the last 24h / 7d. Group by URL and message; surface the top offenders with frequency + first-seen.
- **Flags:** when relevant, list feature flag rollout status — useful when a metric moves at the same time as a flag change.
- **Core Web Vitals (weekly):** HogQL against `$web_vitals` events; surface p75 LCP / INP / CLS per top URL, flag regressions vs. the prior 7d.

**Rate-limit awareness:** PostHog allows ~2400 HogQL queries/hour/team. A scheduled digest is fine; do not loop. If Jonathan asks an exploratory question, batch HogQL calls and avoid re-running the same query.

## Phase 2 — Digest in Telegram

Send a single message, not a wall. Structure:

```
📊 <window> digest (<date range>)

Funnel:
  • signup → demo: 4.2% (−1.3pp vs prior 7d)
  • demo → trial: 28% (flat)

Errors:
  • NEW: TypeError on /pricing — 12 hits, started 9:14 AM
  • Spiking: 4xx from /api/leads — 38× vs avg

Recordings worth a look:
  • session abc123 — rage-clicked the hero CTA 4× then bounced (link)

Recommendation: investigate /pricing TypeError first (regression),
then look at hero-CTA rage clicks.
```

Use markdown links for recording / dashboard URLs. Be concise — Telegram messages should be skimmable on phone.

## Phase 3 — Discuss

Jonathan replies. He'll either:

- ask follow-up questions ("show me the session, what device?") — answer with more PostHog MCP calls
- push back on the recommendation — defend it with data or update it
- agree on a concrete change ("OK, let's try shorter hero copy: 'Close 3× more deals' instead of the current line")

Do **not** start editing the repo until Jonathan says "do it" or otherwise green-lights a specific change. The conversation IS the spec — write down the exact change you both settled on before you move.

## Phase 4 — Edit the site (only after green light)

**Auth pattern for all `git` / `gh` calls in this phase:** the website token isn't `GITHUB_TOKEN` — that one is for the skills hub. Always wire `WEBSITE_GITHUB_TOKEN` explicitly:
- For `gh`: prefix the call with `GH_TOKEN="$WEBSITE_GITHUB_TOKEN"`.
- For `git` (clone, push, pull): use the token-in-URL form `https://x-access-token:${WEBSITE_GITHUB_TOKEN}@github.com/<owner>/<repo>.git`. This bakes the credential into the remote so subsequent `git fetch` / `git push` from the clone keep working without a credential helper.

1. **Get the repo.** If the clone isn't already in `$HERMES_HOME/workspace/`, clone it there. Re-use across runs — it's a persistent workspace. Always normalize the `origin` URL with the current token *after* the clone check, so rotated tokens and pre-existing untokenized clones don't break fetch/push.
   ```
   cd $HERMES_HOME/workspace
   # Derive the authed URL from WEBSITE_REPO_URL by injecting the token after https://
   authed_url=$(echo "$WEBSITE_REPO_URL" | sed "s#https://#https://x-access-token:${WEBSITE_GITHUB_TOKEN}@#")
   if [ ! -d ai-assistant-website ]; then
     git clone "$authed_url"
   fi
   cd ai-assistant-website
   # Re-apply on every run so a rotated token or an earlier untokenized clone is healed.
   git remote set-url origin "$authed_url"
   git fetch origin && git checkout main && git reset --hard origin/main
   ```
2. **Branch.** Name: `hermes/<yyyy-mm-dd>-<short-desc>`. Example: `hermes/2026-05-11-hero-copy`.
3. **Edit.** Use Read/Edit tools (not terminal `sed`/`echo`). Keep diffs minimal — change only what was agreed.
4. **Commit.** Conventional message. Body links the PostHog finding that motivated it:
   ```
   tweak(hero): shorten CTA copy

   PostHog 7d funnel showed 4.2% signup→demo, down 1.3pp.
   Session abc123 shows rage-clicks on the current hero CTA.
   Conversation: <quote of agreed change from Telegram>.
   ```
5. **Push & open PR** via `gh`:
   ```
   git push -u origin hermes/2026-05-11-hero-copy
   GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr create --title "..." --body "..." --base main
   ```
   PR body MUST include the PostHog finding + the Telegram-agreed change so future-Jonathan knows why this exists.

## Phase 5 — Watch Vercel preview + Cubic review

After opening the PR, poll for both. Don't spam — wait 60–90s, then check, then wait again if needed. Typical landing time is 1–3 minutes.

- **Vercel preview** via `GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr checks <PR#>` and `GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr view <PR#> --json comments`. Look for the `vercel[bot]` deployment comment with a preview URL. Or filter checks for the `Vercel` context.
- **Cubic review** via `GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr view <PR#> --json reviews,comments`. Look for the `cubic-dev-ai[bot]` user (or whatever the install names it). Cubic posts a review; capture its summary and any blocking findings.

Once both have landed (or after ~5 min if one is taking unusually long — say so in chat), post a single consolidated message to Telegram:

```
PR #42 ready for review:

✅ Vercel preview: https://ai-assistant-website-git-hermes-...vercel.app
🧊 Cubic: 2 notes
   • accessibility: hero CTA missing aria-label
   • redundant null check in components/Hero.tsx

Want me to address Cubic's notes before merging, or merge as-is?
```

If Vercel build **failed**: post the error from `gh pr checks` and ask whether to iterate.
If Cubic flagged **blocking** issues: don't hide them — surface them and ask before merging.

## Phase 6 — Merge or iterate

- **"Merge"** → `GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr merge <PR#> --squash --delete-branch`. Vercel auto-deploys to prod. Reply with the prod URL or "shipped" + a one-line summary. Note the next-window digest will measure whether the change moved the metric.
- **"Fix the Cubic notes"** → make the changes on the same branch, push, re-poll, re-report.
- **"Tweak X first"** → iterate on the same branch.
- **"Drop it"** → `GH_TOKEN="$WEBSITE_GITHUB_TOKEN" gh pr close <PR#>` and `git push origin --delete <branch>`. Acknowledge in chat.

## Boundaries

- **You never merge without explicit approval in chat.** "Merge it" is the gate. Same philosophy as the publisher_quick_post flow: Jonathan's chat-side "go" IS the approval, and `gh pr merge --squash` is how you ship.
- **You never push to `main` directly.** Always PR.
- **You only edit the website repo.** Not Hermes, not the publisher service, not Railway config — those are separate workflows.
- **You report failures plainly.** If clone fails, if PR creation fails, if a HogQL query times out — say what broke. Don't paper over it.

## Common questions you'll get and how to answer

- **"What happened to conversions yesterday?"** → PostHog MCP funnel query, day-over-day comparison, find the step that moved, look at recordings/errors near the regression hour. Reply in Telegram with the breakdown + a hypothesis. Do not start editing the site.
- **"Why is /pricing slow?"** → Web Vitals HogQL filtered to `/pricing`, top-N by p75 LCP, then check recent errors and recordings on that URL.
- **"Did the hero copy change help?"** → compare funnel/CTR for the window since the merge against the same length of time before.
