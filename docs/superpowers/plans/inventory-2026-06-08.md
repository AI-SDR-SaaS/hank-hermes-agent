# Agent split — live inventory (2026-06-08)

Read-only enumeration of the current `hank-hermes-agent` (KG) for classifying into
**Social** vs **Web/Analytics/Ads** per the spec. `S` = Social, `W` = Web/Analytics/Ads,
`?` = needs a human decision, `drop` = disable on both (bloat).

> Note: all 5 crons show `Last run … ok` (Jun 7–8), consistent with the box having
> stabilized after the 2026-06-06 redeploy. The earlier cron failures were pre-06-06.

## Crons (5)

| ID | Name | Schedule | Deliver / Skill | Target |
|---|---|---|---|---|
| `4f1adb9d7423` | blog-publisher-production | `0 8 * * 2,4` (Tue/Thu 8am) | origin | **S** (blog = content motion, per operator) |
| `7edd7f070f34` | PostHog Daily Digest | `0 9 * * *` | posthog-monitor | **W** |
| `c37c1876332e` | Fastlane publish slot A (11:30 ET) | `30 15 * * *` | telegram | **S** |
| `f26f82154413` | Fastlane publish slot B (18:00 ET) | `0 22 * * *` | telegram | **S** |
| `169b9d4ece6d` | Fastlane daily plan | `0 12 * * *` | fastlane-daily-plan | **S** |

## MCP servers (5)

| Name | Purpose | Target |
|---|---|---|
| posthog | product analytics | **W** |
| smartlead | cold-email / SDR outreach | **W** (ads/SDR) |
| higgsfield | image/video generation | **S** (content) — also the headless-OAuth noise loop; fix or API-key it on Social, remove from Web. See `project_higgsfield_mcp_headless_oauth_loop`. |
| airtable | marketing approval hub (blog posts, reddit threads) | **S** (per operator) |
| tavily | web search | **shared** (enable on both) |

## Local (Hank-specific) skills — 15

| Skill | Target |
|---|---|
| hank-x-drafter | **S** |
| hank-x-publisher | **S** |
| hank-x-scheduler | **S** |
| hank-x-trend-watcher | **S** |
| hank-ig-tiktok-drafter | **S** |
| fastlane-publish-slot | **S** |
| hank-reddit-engagement | **S** |
| hank-blog-drafter | **S** (blog = content motion, per operator) |
| hank-blog-restructure | **S** |
| blog-publisher-cron | **S** |
| hank-hormozi-copywriter | **S** (per operator) |
| hank-cold-email-drafter | **W** (ads/SDR) |
| hank-smartlead-operator | **W** (ads/SDR) |
| hank-where-they-live | **W** (lead/audience research) |
| airtable-schema-creation | **S** (paired with airtable approval hub) |

## Relevant builtin skills

- **S:** `fastlane-daily-plan`, `ad-hoc-post`, `xurl` (social-media category)
- **W:** `posthog-monitor`
- **shared:** `airtable`, github-* (PR workflow for website), `notion`, `google-workspace`

## Bloat to trim (YAGNI — disable on BOTH focused agents)

~80 builtins are enabled but irrelevant to either agent and inflate context every run:
`mlops/*` (axolotl, unsloth, vllm, dspy, trl, w&b, llama-cpp, sam, …), `gaming/*`
(pokemon-player, minecraft), `smart-home/*` (openhue), `red-teaming/godmode`,
`polymarket`, `pokemon`, etc. Disabling these per agent is a direct fix for the
"loaded it up too much" overload, independent of the split itself.

## Decisions resolved (operator, 2026-06-08)

1. **airtable** → **Social** — it's the marketing approval hub (blog posts, reddit threads).
2. **hank-hormozi-copywriter** → **Social**.
3. **blog** (drafter/restructure/publisher-cron + Tue/Thu cron) → **Social** — blog is part of the content motion, not the Web agent.

### Resulting split

- **Social / Content agent:** all platform content — X (drafter/publisher/scheduler/trend-watcher), IG/TikTok + Fastlane (daily-plan, slots A/B), Reddit, **blog** (drafter/restructure/publisher), Hormozi copywriting, ad-hoc-post, higgsfield (image/video), airtable approval hub. Drives the publisher.
- **Web / Analytics / Ads agent:** PostHog analytics (monitor skill + daily digest cron + posthog MCP), the `ai-assistant-website` code-edit loop (GitHub PR/Vercel/Cubic), and cold outbound/SDR (cold-email-drafter, smartlead-operator + smartlead MCP, where-they-live). Keeps the Ace bot.

### Dependency to verify before cutover

**blog → website publishing:** blog content is authored on the **Social** agent, but the blog likely lives on the website owned by the **Web** agent (`ai-assistant-website`). Check where `blog-publisher-cron` / `blog-publisher-production` actually publishes (cron `Deliver: origin`). If it pushes to the website repo, the Social agent needs `WEBSITE_GITHUB_TOKEN` (or a clean handoff to the Web agent). Resolve in the plan before wiring blog crons onto Social.
