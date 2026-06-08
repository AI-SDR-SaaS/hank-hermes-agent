# Agent split — live inventory (2026-06-08)

Read-only enumeration of the current `hank-hermes-agent` (KG) for classifying into
**Social** vs **Web/Analytics/Ads** per the spec. `S` = Social, `W` = Web/Analytics/Ads,
`?` = needs a human decision, `drop` = disable on both (bloat).

> Note: all 5 crons show `Last run … ok` (Jun 7–8), consistent with the box having
> stabilized after the 2026-06-06 redeploy. The earlier cron failures were pre-06-06.

## Crons (5)

| ID | Name | Schedule | Deliver / Skill | Target |
|---|---|---|---|---|
| `4f1adb9d7423` | blog-publisher-production | `0 8 * * 2,4` (Tue/Thu 8am) | origin | **W** |
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
| airtable | content calendar **or** CRM/leads | **?** |
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
| hank-blog-drafter | **W** |
| hank-blog-restructure | **W** |
| blog-publisher-cron | **W** |
| hank-cold-email-drafter | **W** (ads/SDR) |
| hank-smartlead-operator | **W** (ads/SDR) |
| hank-where-they-live | **W** (lead/audience research) |
| hank-hormozi-copywriter | **?** (ad copy vs social captions — leans W) |
| airtable-schema-creation | **shared/infra** |

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

## Decisions needed from operator

1. **airtable** (MCP + skills) — is it the social **content calendar**, the **CRM/leads** store, or both? Determines S / W / duplicate.
2. **hank-hormozi-copywriter** — ad copy (W) or also social captions (both)?
3. Confirm **blog** work (drafter/restructure/publisher-cron) belongs with **Web** (it's website content), not Social.
