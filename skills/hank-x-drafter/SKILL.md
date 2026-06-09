---
name: hank-x-drafter
description: Draft tight X (Twitter) posts for Hank the Pro. Enforce 220-char hard limit, lowercase fragments, stripped narration. Use structural templates, verify char counts, batch-update to Airtable Drafts table.
version: 1.1.0
author: Ace (CMO, Hank the Pro)
trigger: |
  When asked to draft X posts (especially for Hank marketing, founder voice, or industry observations), or when Jonathan asks to "write for X" / "tweet this" / "draft 3 X variations."
---

## CRITICAL: Length and structure rules (overrides earlier sections if conflict)

X posts are NOT short LinkedIn posts. They are different format entirely.

### Hard length limits (must enforce)

Single post target: 100 to 220 characters. Hard ceiling: 270 characters. If you hit 270, you've failed the format. Cut.

Thread tweets: each piece 100 to 240 characters. Don't pack one piece. Spread the idea.

### Character math (do this before writing)

Before drafting a single post, decide: this is one post (under 220 char) or a thread (multiple under-240 pieces). Don't write a single post that should have been a thread.

Test: read your draft. Can you cut a sentence and lose nothing? You're over.

### Structural templates (use one, don't invent)

Template 1: Observation + Twist
"watched [scene]. [implication]."
Example: "watched a CSR field 47 calls in 4 hours yesterday. she's not a bottleneck, she's performing miracles."
Char count: 117. Posts clean.

Template 2: Stat + Reframe
"[number]. [reframe of what that means]."
Example: "78% of homeowners hire whoever calls back first. trades software still treats phone calls as a backwater feature."
Char count: 138.

Template 3: Setup + Punchline
"[short setup]. [twist that lands]."
Example: "6-truck plumbing shop just told 3 customers 'maybe wednesday.' that's $30k of follow-up work guessed away in 90 seconds."
Char count: 152.

Template 4: Hot Take
"[contrarian opinion stated flat]."
Example: "ServiceTitan is right that the trades need software. wrong that it has to cost $50k and 6 months."
Char count: 119.

Template 5: Question / Frame
"[question that flips assumption]."
Example: "why does dispatch software treat the phone call as the backwater? it's the entire game."
Char count: 105.

### Forbidden patterns (you keep doing these, stop)

DON'T explain the implication of your numbers. "47 calls in 4 hours yesterday. that's one call every 5 minutes. no break. no system." The reader did the math. Cut the math.

DON'T stack 4 short sentences when 2 would work. Pick the strongest 2.

DON'T put the punchline on the last line of a long setup. Lead with it or split into a thread.

DON'T use lowercase headings like "DRAFT 1 (Volume shock)" — reader doesn't see your scaffolding. Just write the post.

DON'T over-narrate. "heres what actually happens:" — show, don't say "here's what happens."

DON'T use ≠, ≈, or other symbols. Use plain words.

### When to thread instead of single

If you have:
- More than one beat (setup + escalation + punchline)
- A list of 3+ items
- A story with arc
- A take that needs evidence

Use a thread. Each beat = its own tweet. 3 to 5 tweets ideal. 7+ is showing off.

### Forced cut step (do this every time)

After drafting, cut 30 to 50 percent of words. Specifically:
- Cut every "actually," "really," "just," "kind of"
- Cut explanatory clauses ("which means...", "in other words...")
- Cut ratio comparisons unless mathematically necessary
- Cut the SECOND example when one example does the job

If your draft was 280 chars, target 180 after cuts. If 480 chars, you needed a thread.

### Character verification and Airtable workflow (before updating records)

**Always follow this checklist when saving X drafts:**

1. **Count each variation programmatically.** Use Python: `len("your text here")` — paste each post and verify the count displays under 220 chars. If any exceed, flag it and don't save.
2. **When updating Airtable Drafts table:** Use MCP `mcp_airtable_update_records` or terminal curl to batch-update existing record IDs. Do not create duplicate records. Populate: Body (multilineText), Variant (single select: V1/V2/V3), Platform (single select), and Title (tracing label).
3. **Never publish or post live.** All drafts stay in Airtable with Status: "Todo" until Jonathan approves via Telegram. Post URL and Posted At fields remain empty until he gives the go-ahead.
4. **Batch updates matter.** When you have 3 record IDs ready, update all three in a single API call. It saves quota and prevents partial saves.

Example Airtable update payload:
```json
{
  "records": [
    {"id": "recXXX", "fields": {"Body": "your post text here (168 chars verified)", "Variant": "V1", "Platform": "LinkedIn", "Title": "CSR 47 calls - V1"}},
    {"id": "recYYY", "fields": {"Body": "second post (174 chars verified)", "Variant": "V2", "Platform": "LinkedIn", "Title": "CSR 47 calls - V2"}}
  ]
}
```

### Voice fingerprint check (per draft, before saving)

Read your final draft. Ask: does this sound like:
1. Alex Finn (fast, present-tense, lowercase fragments) ✓
2. Tommy Mello (operator-grounded, dollar specific) ✓
3. ChatGPT trying to sound human ✗
4. LinkedIn post copied to X ✗

If it reads like 3 or 4, redraft.

### When variations should differ

When generating 3 variations, vary by:
- LENGTH (one short ~120 char, one mid ~180, one approaching limit ~240)
- STRUCTURE (one observation+twist, one stat+reframe, one hot take)
- ANGLE (each surfaces a different beat from the same input)

NOT all 3 variations of the same beat in different lengths. That's lazy.

## Humor calibration (add wry observations, sparingly)

Sterile drafts get ignored. But humor every post reads as trying too hard. Aim for: roughly 1 in 5 drafts has a humor beat. Not 1 in 5 are jokes. Just a slight wink.

### What works in this lane

Dry observations:
"watched a CSR put a customer on hold to take a call from her own husband asking what's for dinner. small business is mostly dinner logistics."

Self-deprecation that reveals something real:
"shipped a feature today that broke 30% of our integrations. the support tickets are educational."

Industry inside jokes (only if you'd know it from being on the floor):
"every plumber knows what 'i'm 5 minutes out' actually means and it's not 5 minutes."

Absurd specificity:
"a $4M roofer just told me his best lead source last quarter was the homeowners next door to a job that went well. that's it. that's the system."

The pattern: humor comes from a TRUE observation that's slightly absurd, not from punchlines you wrote.

### What doesn't work (avoid)

Don't write any of these flavors:

- Pun jokes or dad jokes ("AI: artificially incompetent")
- Twitter-bro snark ("ratio'd," "skill issue," "based," "anon")
- Self-aggrandizing humor ("just shipped at 3am, who else gets it?")
- Generic AI-takes-your-job jokes
- "If you know, you know" / "iykyk"
- Forced wordplay
- Comparing trades to silicon valley as a lazy contrast joke

### Humor placement rules

- Never put humor in the hook (first 100 chars). Hook earns the read. Humor is the close or middle beat.
- Never explain the humor. If you wrote "i'm 5 minutes out," don't add "you know what i mean."
- Humor lives in ONE post per batch of 3, not all 3. If you write 3 humor drafts, you've drifted. Pick 1.

### When to add humor

Skip humor entirely on:
- Hank product reality posts (these need to feel honest, not winking)
- Hot takes on competitors (humor reads as catty, not confident)
- Stat-led posts where the number is the punch
- Anything about customer money problems (their losses aren't funny)

Use humor on:
- Founder lessons (self-deprecation lands)
- Industry observations (dry noting works)
- Behind-the-scenes building moments (everyone screws up, humanize)

### Variation rule update

When generating 3 variations on a topic:
- Variant A: straight observation, no humor
- Variant B: tighter / different angle, no humor
- Variant C: optional wry tone (pick this one only if topic supports humor per the rules above)

If the topic shouldn't have humor at all, all 3 variants stay straight. Don't force a wry version onto a serious topic.
