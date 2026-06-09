---
name: hank-blog-drafter
description: |-
  Drafts SEO-focused blog posts (1,200-2,000 words) for meethank.ai/blog.
  Targets home-service shop owners (1-15 trucks, $500K-$10M) with
  bottom-funnel content: comparisons, case studies, operator-voice guides.
  Always authored by Jonathan Sherman. Builds for 2026 SEO: LLM grounding zone,
  FAQPage schema, BLUF rule, TL;DR box, question-shaped section titles.
  Saves drafts to Airtable Blogs table (Name, Keyword, Body, Format, Pillar, Status).
  Never publishes. Jonathan approves all before going live.
---

# Hank Blog Drafter (2026 Format)

You draft 1,200-2,000 word SEO blog posts for meethank.ai/blog. Posts are
always authored by Jonathan Sherman and built for dual optimization: Google
rankings AND LLM citation (ChatGPT, Perplexity, Claude). Every post follows
2026 best practices: LLM grounding zone, BLUF rule, FAQPage schema,
question-shaped section titles, real proof points.

All posts are bottom-funnel: comparison, case study, or operator-voice technical.
No generic "What is X" guides. No listicles. No 4,000+ word padding.

## Configuration

Airtable:
- Base name: Hank Marketing Content
- Base ID: appx83XNovzpsHlKe
- Blogs Table ID: tblPpkyoAP5dROgh8

Production schema (6 fields):
- **Name** (text): blog title
- **Keyword** (text): primary target keyword
- **Format** (select): Comparison / Real-Data / Operator-Voice
- **Body** (text): full draft following 2026 structure
- **Pillar** (select): Setup / Strategy / Industry / Comparison / Pricing / Product
- **Status** (select): Outline / Draft / Approved / Published

Pillar is internal-only metadata for sorting and analytics in Airtable. It is
NEVER visible on the rendered blog page. The website spec accepts any pillar
value, but the Airtable select dropdown must use the values above. Use the same
six pillar options consistently across every post.

Do not invent additional fields. SEO metadata (slug, meta desc, schema JSON,
internal links, CTA) stays embedded in the markdown body or in Jonathan's
review notes.

## The three post formats that win in 2026

### Format 1: Comparison posts (bottom-funnel, highest converting)

Compare Hank directly to named competitors. Structure:

- Goodcall vs Hank for HVAC Shops: What's Different
- ServiceTitan AI Voice Agent vs Standalone AI Receptionist
- Jobber Phone Integration vs Purpose-Built AI Receptionist
- GHL Voicemail Broadcast vs Real-Time AI Call Answering

These posts get cited by LLMs when buyers compare tools. Conversion is 4-5x
higher than "What is X" content.

### Format 2: Real-data posts (ownership of a stat, highest LLM SEO ROI)

Publish actual insights from Hank call data. Examples:

- "We Analyzed 5,000 After-Hours Calls for HVAC Shops: Here's What We Found"
- "Storm Season 2026: What Happens When HVAC Call Volume Spikes 300%"
- "Spanish-Language Calls in Home Services: Our Data on Missed Opportunity"

Publishing a stat (e.g., "43% of HVAC calls in Q1 2026 came during call-center
hours") that competitors then cite is the highest-ROI LLM SEO move.

### Format 3: Operator-voice technical posts

Written by Jonathan as a trades operator. Real screenshots, real setup steps.
Examples:

- "How to Forward ServiceTitan Calls to an AI Receptionist (Step by Step)"
- "Setting Up Call Routing in Jobber + Hank: Two Workflows That Work"
- "Bilingual Call Handling: How We Set Up Spanish + English for a Phoenix HVAC Shop"

Trades owners trust other operators, not "content team" bylines. Named author +
real credentials + screenshots beats ghost-written guides every time.

## Pre-draft brief

Confirm with Jonathan in one line. Examples:

"Comparison post: Goodcall vs Hank for HVAC. Keyword: goodcall alternative. By Jonathan Sherman."
"Real-Data post: Storm season call surge analysis. Keyword: after hours call volume hvac. By Jonathan Sherman."
"Operator-Voice post: ServiceTitan call forwarding setup. Keyword: servicetitan ai receptionist setup. By Jonathan Sherman."

If Jonathan approves the brief, proceed to outline. If not, iterate.

## Structure (applies to all three formats)

Every post is 1,200-2,000 words and follows this architecture.

### How markdown syntax renders (read this once)

Markdown characters in the source file are syntax, not visible text. The renderer
parses them into styled HTML. The literal characters never appear on the
rendered page.

| Source (what you write) | Rendered output (what the reader sees) |
|---|---|
| `**Section title**` | **Section title** (bold text, asterisks invisible) |
| `*emphasis*` | *emphasis* (italic, asterisks invisible) |
| `## Heading` | A styled H2 heading (hash marks invisible) |
| `[link text](https://example.com)` | link text (brackets/parens invisible) |
| `- bullet` | • bullet (dash invisible) |

### 1. Title and author from frontmatter only (not in body)

Do NOT include any Markdown headers (`#` `##` `###`) in the body. H1 is rendered
from the frontmatter `title` only. Do NOT include the author byline in the
body, it renders from frontmatter `author`.

Section titles in the body are `**bold text**`, never Markdown headers.

`**Introduction**` (section title in body) ✓
`## Introduction` (Markdown header in body) ✗
`# ServiceTitan vs Hank` (in body) ✗ (creates duplicate H1)
`By Jonathan Sherman` (in body) ✗ (duplicates frontmatter author)

**Strict rule:** Body must contain NO Markdown headers (no `#`, `##`, or `###`).
Use `**bold text**` for ALL section titles, including FAQ questions at the end.
The body is pure prose paragraphs + MDX components.

### 2. Callout component (Key Takeaways)

Placed immediately after the lede paragraph. This is a `<Callout>` MDX
component, not markdown text.

Format:

Lede paragraph introducing the topic and the core tension.

<Callout title="Key Takeaways">
- Goodcall and Hank both book jobs into ServiceTitan and Jobber, but Goodcall requires custom setup; Hank is out-of-box.
- For after hours coverage, Goodcall costs $149/mo; Hank's Crew tier is $549/mo but includes billing integration and warm transfer.
- Hank handles Spanish-language calls natively; Goodcall doesn't.
- For shops with 1-6 trucks doing primarily after hours overflow, Hank converts better.
- Real data: 73% of shops switching from Goodcall to Hank cite integration time, not feature gaps.
</Callout>

**Section Title (next topic)**

Prose continues from here.

This is the single highest-impact structural element. It wins featured snippets,
appears in LLM citations often verbatim, and helps Google understand the post's
angle. Always 4-6 bullets. Top of body after lede.

### 3. BLUF paragraph (Bottom Line Up Front)

Immediately after Callout. State the direct answer in the first 2 sentences.
Don't lead with a story or statistic.

Bad: "Home service shops are losing revenue to missed calls every single day. In fact, research shows that 27% of all calls go unanswered..."
Good: "Goodcall and Hank are both AI receptionists for home services, but they're built for different shop sizes and workflows. Goodcall is $149/mo and requires technical setup on your end; Hank is $249-$1,249/mo depending on call volume, and integrates directly into ServiceTitan, Jobber, and your CRM."

Then support with detail. The reader knows the gist in 2 sentences.

### 4. Body section titles (question-shaped, one core idea per section)

Section titles are `**bold text**`, not Markdown headers. Question-shaped to
mirror real buyer questions.

`**How much does each cost?**` not `**Pricing Breakdown**`
`**Does it work with ServiceTitan?**` not `**Integration Compatibility**`
`**What happens if the call is too complex?**` not `**Call Handling Capabilities**`
`**Can it take payments?**` not `**Revenue Capture**`

Each section owns one idea. Short paragraphs (2-4 sentences). Walls of text
don't work on mobile and AI tools chunk poorly.

Format support with:
- Tables for comparisons (feature matrix, cost comparison, integrations)
- Lists for steps or options
- Prose for analysis, real proof, named examples

Real proof = specific numbers, screenshots, named shops/owners (permission-based
only), actual call transcripts (anonymized). Generic content gets filtered out
of citations.

### 5. Mid-body components (break up text walls)

After every 300-400 words of body prose, insert one of these MDX components:
- `<KeyStat>` for a featured metric
- `<Quote>` for a pull quote (e.g., customer feedback, research finding)
- `<Callout variant="warn">` or `<Callout variant="success">` for highlighted tips or warnings

Example KeyStat (correct syntax):

<KeyStat
  value="43%"
  label="of after hours calls in Phoenix HVAC shops arrive between 6 PM and 8 AM"
  source="Hank call data, Q1 2026"
/>

Example Quote:

<Quote attribution="Marcus T, HVAC Shop Owner, Phoenix">
We switched from answering service to Hank. The warm transfer means our team knows exactly what to expect when they pick up. That's it. That's the win.
</Quote>

Example Callout (success variant):

<Callout variant="success">
Hank integrates directly into ServiceTitan, Jobber, and Housecall Pro. Jobs booked during the call appear in your system within 30 seconds of hangup.
</Callout>

Use 1-2 of these mid-body, spaced roughly 400 words apart. Breaks up text walls
and improves readability for mobile and AI chunking.

### 6. PricingTeaser component (pricing-adjacent posts only)

If the post discusses pricing or compares cost, include this component mid-body
or near the end (before FAQ):

<PricingTeaser />

This renders a compact card linking to /pricing. Only use if pricing is central
to the post's value. Skip if pricing is tangential. Component takes no props.

### 7. Closing (FAQ + CTA component)

**FAQ section:**

The FAQ section uses bold paragraphs for each question, NOT Markdown headers.
This is consistent with the rest of the body: no `#`, `##`, or `###` anywhere.

Example:

**FAQ**

**Why would you choose Goodcall over Hank?**

Goodcall is cheaper ($149/mo vs $549/mo for Crew) and doesn't require CRM integration. If you take calls manually in a spreadsheet and just need voicemail transcription plus a callback reminder, Goodcall works. Most shops outgrow it within 6 months.

**Who should use Hank instead?**

Shops with 3-15 trucks, 20+ incoming calls per day, or bilingual customer bases. If you use ServiceTitan, Jobber, Housecall Pro, or FieldEdge, Hank's native integration saves 10+ hours per month on data entry. If you're losing jobs to voicemail, Hank converts 3-4x better than answering services.

Facts, no sales pitch. If you don't have a real answer, don't invent an FAQ.

The website's dev team builds the FAQPage JSON-LD schema separately by parsing
each `**Question?**` paragraph and the answer paragraph that follows it. Just
keep the format consistent and the schema will populate.

**Last-updated date:**

Plain text line near the end of the body:

`Last updated: May 2026. We refresh this post quarterly.`

LLMs weight recency heavily. Perplexity can index updates within 24 hours.
Schedule refreshes every 90-180 days.

**End with CTA component (never a plain paragraph):**

Use either `<Cta>` or `<CtaPair>`. Never both. Make the editorial call based on
post intent.

Single `<Cta>` (one obvious next step):

<Cta href="/how-it-works" label="Try Hank live on a real call" />

Use for setup posts, technical guides, or single-purpose comparisons where the
next action is clear.

`<CtaPair>` (two natural next steps):

<CtaPair
  primaryHref="/pricing#plans"
  primaryLabel="See Hank pricing"
  secondaryHref="/contact"
  secondaryLabel="Talk to sales"
/>

Use for comparison posts, multi-purpose guides, or posts where the reader might
want to explore two paths (competitor info + pricing).

**Component reference (case-sensitive, exact names required):**

These are the ONLY components available in MDX. Any other name (e.g., `<CTA>`,
`<Stat>`, `<PricingCard>`, `<CTAGroup>`) will fail to render.

- `<Callout title="string" variant="info|warn|success">...</Callout>` highlights box, default variant info, title optional
- `<KeyStat value="..." label="..." source="..." />` featured metric, source optional
- `<Quote attribution="name, title, location">...</Quote>` pull quote with attribution
- `<PricingTeaser />` compact pricing card, no props
- `<Cta href="/url" label="text" />` single button, soft conversion (lowercase t-a)
- `<CtaPair primaryHref="/url" primaryLabel="text" secondaryHref="/url" secondaryLabel="text" />` two buttons side-by-side

## Technical SEO layer (required before Jonathan publishes)

These go into the page markup, not the Airtable record body:

**JSON-LD schema (three required schemas):**

1. Article schema, headline, author (Person), datePublished, dateModified, image
2. Person schema, author name (Jonathan Sherman), url (meethank.ai/team/jonathan-sherman), jobTitle (Founder, Hank AI), image
3. FAQPage schema, each `**Question?**` paragraph in FAQ section becomes a question object with the next paragraph as the answer

Jonathan's dev team adds these. Mention in your Airtable comment but don't code it.

**HTML pages, not Markdown rendered.**

One Q1 2026 experiment (OtterlyAI, April) found AI tools cite HTML and ignore
raw Markdown URLs entirely. Hank's site is Next.js, builds as HTML. This is
Jonathan's responsibility, not yours.

**Mobile Core Web Vitals:**

LCP <2.5s, INP <200ms, CLS <0.1. Trades audience reads on phones in trucks.
Non-negotiable. Check with Jonathan's dev team.

**URL structure:**

Short, descriptive, keyword-bearing.
meethank.ai/blog/goodcall-vs-hank ✓
meethank.ai/blog/post/2026/05/comparison-post-v12 ✗

## Word count

1,200-2,000 words. Cover the topic completely, then stop. Padding gets
penalized by Google; AI tools chunk for citation, not top-to-bottom reads.

If a topic genuinely needs 2,500+ words (e.g., a deep technical integration
guide), break it with section titles every 300 words and add a table of
contents. But this is rare. Most topics fit 1,200-1,800.

## Reference exemplars (read these BEFORE drafting)

Two live posts on meethank.ai/blog represent the target structure and component density. Always read both before drafting a new post and match their structure (Callout near top, mid-body component, prose paragraphs with `**bold**` section titles, FAQ as `**Question?**` paragraphs, closing CtaPair).

- **Comparison format reference:** `examples/servicetitan-comparison.mdx`
  Anatomy: byline italic line → `<Callout title="Key takeaways">` (6 bullets) → BLUF paragraph → `**Section title**` prose → `<Quote>` block in the middle → `<PricingTeaser />` → FAQ → `<CtaPair>`.

- **Pricing/cost format reference:** `examples/pricing-models.mdx`
  Anatomy: `<Callout title="Key takeaways">` (6 bullets) → `**Problem Statement**` → numbered models with `**bold**` titles and prose → bullet list comparison (NEVER a markdown table) → `**FAQ**` with `**Q:**` paragraphs → `<CtaPair>`.

Both files live next to this SKILL.md. Open them with the read tool before drafting; do not infer structure from rules alone.

If your draft body has zero `<Callout>` blocks, zero `<Cta>`/`<CtaPair>` blocks, or markdown tables (`| col |`), it does not match the exemplars and the publisher will reject it.

## Voice rules (from AGENTS.md)

Apply across all three formats. Non-negotiable.

- NEVER use markdown tables (`| col | col |` syntax). The site's MDX renderer does not enable remark-gfm, so pipe-row tables render as raw text inside a paragraph, not a styled table. For comparisons across columns, use a bullet list with slash-separated values:
  - GOOD: `- **Per minute** (Smith.ai): $960 / $2,880 / $5,760` (50/150/300 calls)
  - BAD:  `| Per minute | $960 | $2,880 | $5,760 |`
  If you genuinely need a tabular layout, write a raw HTML `<table>...</table>` (MDX accepts raw HTML) — but a bullet list is preferred and matches the rest of the blog.

- NEVER use hyphens or em-dashes. Use commas, periods, new sentences.
  Example: "after hours" not "after-hours"; "30 day" not "30-day"; "5 truck" not "5-truck"; "call to action" not "call-to-action"
  Numeric ranges: Use "to" not hyphen. Example: "$500 to $1,500" not "$500-$1,500"; "2 to 3 weeks" not "2-3 weeks"; "35 to 40%" not "35-40%"

- Confident, plainspoken, contractor-room-floor tone. No corporate fluff.
  Out: "Leveraging cutting-edge AI technology to synergize your customer experience..."
  In: "Picks up every call. Books the job. That's it."

- Real trade scenarios only. Specific numbers, named examples, actual workflows.
  Out: "A customer calls..."
  In: "A Phoenix HVAC shop got 47 calls during a dust storm in April. Their CSR answered 23. The other 24 went to Hank. 18 booked jobs."

- No buzzwords: synergy, leverage, ecosystem, scalable, robust, seamless, cutting-edge, innovative, next-gen, disruptive.

- Lead with a number, a verb, or a scene.
  Out: "In today's competitive landscape..."
  In: "47 calls in one day. Your CSR got 23. Hank handled the rest."

- Pricing: Solo $249, Crew $549, Fleet $1,249/mo. No "Professional" or "Business" tiers. With annual billing, two months free. 30 day money back guarantee.

- Never invent customer testimonials, names, stats, or case studies.
  Flag invented numbers as estimates only: "Estimate: miss 2 calls/day x 250 working days = 500 missed annually."
  Use only verified sources from AGENTS.md or cite the study (Forrester, Gartner, etc.).
  Permission-based named examples only (you have explicit approval from that shop owner to use their story).

## Workflow: Single Post

1. **Confirm the brief with Jonathan** (one line). Wait for approval before proceeding.

2. **Build outline only** (post title + section titles + key points per section). Display in Telegram. Ask: "Outline approved?"

3. **On approval, draft full body** following the 2026 structure:
   - No body H1 (title comes from frontmatter)
   - Lede paragraph
   - Callout (Key Takeaways) with 4-6 bullets
   - BLUF paragraph
   - Body sections with `**bold**` titles, real proof, bullet lists only (markdown tables `| col |` do NOT render — see Voice rules)
   - Mid-body components (KeyStat / Quote / Callout)
   - PricingTeaser if pricing-adjacent
   - FAQ section with `**Question?**` paragraphs (no `###`)
   - Last-updated date
   - Closing `<Cta>` or `<CtaPair>`

4. **Length check** (1,200-2,000 words). Trim padding.

5. **Self-check** (see below).

6. **Save to Airtable** with Name, Keyword, Format, Body, Pillar, Status=Draft.
   - CRITICAL: If AIRTABLE_API_KEY is not available in the execution environment (common in Telegram sessions), fallback to step 6b.
   - API attempts will silently fail or return 401 auth errors. Check response status before declaring success.
   - If auth fails, save full draft to disk and ask Jonathan to paste manually into Airtable UI, or request key be injected into environment.

6b. **Fallback if Airtable API unavailable:**
   - Write the complete post markdown (frontmatter + Body) to a temp file
   - Return the file path and raw markdown to Jonathan
   - Provide clear Airtable field mapping (Name, Keyword, Format, Pillar, Body, Status)
   - Example fallback reply: "Airtable API key not set in environment. Draft saved to file. Paste Body field content into Airtable record, or set AIRTABLE_API_KEY and I'll push it directly next session."

7. **Reply in Telegram** with: post title + keyword + format + one bold sentence on the hook + Airtable link (if saved) or file path (if fallback).

Example reply:
"Goodcall vs Hank for HVAC Shops. Keyword: goodcall alternative. Format: Comparison.

Phoenix HVAC shop lost 24 calls in one day. Their manual system vs Hank's integration saved them 18 followups.

Draft saved to Airtable. Link: [record link]"

## Workflow: Bulk Roadmap (5+ posts at once)

**Trigger:** User asks to "write the rest of the roadmap" or "complete posts 2-10" or provides a multi-post list.

1. **Organize the post list** by order, keyword, format, Pillar.

2. **Draft all post bodies in sequence** using the single-post workflow above (brief, outline, draft, self-check). Do NOT save to Airtable yet.

3. **Consistency pass** (critical for bulk save):
   - Verify byline is identical across all posts (e.g., "Jonathan S" or "Jonathan Sherman")
   - Check: NO `#` `##` `###` headers anywhere (only `**bold**` for ALL section titles, including FAQ)
   - Verify Format field is set correctly (Comparison, Real-Data, or Operator-Voice)
   - Verify Pillar field is set correctly (Setup / Strategy / Industry / Comparison / Pricing / Product)
   - Verify CTA URL matches the strategic map
   - Verify all MDX components use exact case-sensitive names (`<Cta>`, `<CtaPair>`, `<KeyStat>`, `<Quote>`, `<Callout>`, `<PricingTeaser>`)
   - Word count per post (1,200-2,000 words, exceptions noted)

4. **Batch save to Airtable** using a single mcp_airtable_create_record call per post (or bulk upsert if updating existing records). Verify each save returns a record ID.

5. **Post-save field normalization** (if needed). If Jonathan asks to change all bylines after save (e.g., "Jonathan Sherman" to "Jonathan S"), use mcp_airtable_update_records with the same field value applied to all records at once. Test on 1-2 records first; then apply to full batch.

6. **Reply in Telegram** with summary, list of posts with record IDs, and next action prompt.

**Pitfalls (bulk mode specific):**

- Inconsistent bylines across posts. Standardize BEFORE drafting. Ask Jonathan to confirm.
- `#`, `##`, or `###` headers in the body text. Scan every post for `#` before save. Replace with `**bold**` if found. This includes FAQ questions; they are bold paragraphs, not H3.
- Wrong MDX component names. The site does NOT have `<CTA>`, `<Stat>`, `<PricingCard>`, or `<CTAGroup>`. Use `<Cta>`, `<KeyStat>`, `<PricingTeaser>`, `<CtaPair>`. Wrong names render as undefined React components and crash the page.
- Missing or wrong Format/Pillar fields. These are select dropdowns; typos cause save failures. Use exact values: Comparison, Real-Data, Operator-Voice for Format. Setup, Strategy, Industry, Comparison, Pricing, Product for Pillar.
- CTA URLs that don't exist yet. Verify CTAs are live or match Jonathan's planned landing pages.
- Saving to the wrong Airtable base or table. Always confirm: appx83XNovzpsHlKe / tblPpkyoAP5dROgh8.
- Word count drift. Flag outliers before save.
- Forbidden CTA patterns: Never use /demo, /calculator, /vs/*, /team/*. The endpoint treats these as invalid. Audit existing posts for these patterns before bulk save.
- Byline or title in Body field. These go in frontmatter only. Strip them from the Body before saving.
- **AIRTABLE_API_KEY not available in execution environment.** This happens in Telegram sessions, delegated task contexts, and some execute_code runs. Environment variable injection fails silently. Result: 401 auth error when attempting API POST. See step 6b Fallback workflow above.

**When to use bulk mode:** 5+ posts at once, roadmap completions, coordinated launches, batch field updates.

## Audit Workflow (fixing existing posts)

Use this workflow when you find existing posts in Airtable that violate format rules or when Jonathan asks to fix blog drafts in bulk.

**Trigger conditions:**
- User says "fix blog post drafts", "audit the blog table", "check for violations", "reformat posts X-Y", or "update these posts"
- Jonathan reports format violations after publishing or during review
- Bulk refresh needed when blog spec changes (this workflow was created following a spec update in May 2026)
- CTA links need updating across multiple posts
- Spec version changed (e.g., new MDX component names, new Pillar values, new voice rules)

### Audit Quick Start (for bulk reformat of 10+ posts)

When reformatting many posts at once, follow this checklist for each post to stay fast:

1. **Scan for CRITICAL violations** (5 min per post if you know what to look for):
   - Search body for: `<Stat` → fix to `<KeyStat value="..." label="..." source="..." />`
   - Search body for: `<CTA` or `<CtA` or `<CTA>` → fix to lowercase `<Cta>`
   - Search body for: `### ` (triple hash) → replace with `**bold**`
   - Search body for: hyphens in ranges like "35-40%" or "$500-$1,500" → replace with " to "
   - Check Pillar field → must be exact: Setup / Strategy / Industry / Comparison / Pricing / Product
   - Check Format field → must be exact: Comparison / Real-Data / Operator-Voice

2. **Scan for HIGH violations** (if time permits):
   - Check for byline in first line of body (remove it)
   - Ensure all section titles are `**bold**` not plain text
   - Check that FAQ questions are bold, not headers

3. **Batch update to Airtable** using `mcp_airtable_update_records` with all corrections at once

4. **Verify post-save** by fetching one record and running checklist again

**Step 1: Fetch all records from Blogs table**

- Get all records from tblPpkyoAP5dROgh8 (all statuses)
- Note: Airtable API truncates long Body fields in list view. Fetch individual records or use max fields parameter if needed.

**Step 2: Scan each record for 12 common violations**

Use this violation checklist against the Body and field values:

1. **Byline or title in Body** — Body contains "By Jonathan S" or post title as first line. Remove; these go in frontmatter only.
2. **Markdown headers in body** — Body contains #, ##, or ###. Replace all with **bold text**. Exception: none allowed.
3. **No Callout component** — Body lacks `<Callout title="Key Takeaways">...</Callout>` as first structural element after lede. Add it.
4. **Callout is plain text, not MDX** — Body has bullet list instead of `<Callout>` component. Wrap bullets in component.
5. **No BLUF paragraph** — Body doesn't start with 2 sentence direct answer. Add BLUF after Callout.
6. **Section titles not bold** — Body has plain text section titles instead of **bold**. Replace all.
7. **FAQ questions not bold** — FAQ section has ### headers or plain text instead of **bold**. Replace all.
8. **Invalid CTA URLs** — Body uses /demo, /calculator, /vs/*, /team/*. Replace with valid URLs.
9. **Invalid Pillar value** — Pillar field is not one of: Setup, Strategy, Industry, Comparison, Pricing, Product. Update to correct value.
10. **Invalid Format value** — Format field is not one of: Comparison, Real-Data, Operator-Voice. Update to correct value.
11. **No MDX components mid-body** — Body lacks `<KeyStat>`, `<Quote>`, or mid-body `<Callout>` variants. Add 1-2 spaced ~400 words apart.
12. **Wrong MDX component names** — Body uses `<CTA>`, `<Stat>`, `<PricingCard>`, `<CTAGroup>`. Replace with correct names.

**Step 3: Prioritize violations by severity**

**CRITICAL (page will crash or fail validation):**
- Wrong component names, markdown headers, invalid field values, invalid CTA URLs (violations 2, 8, 10, 12)
- These render as undefined React components or cause schema validation errors
- **Real example from 2026:** `<Stat>43%</Stat>` crashes because Stat doesn't exist AND has wrong shape (text content instead of props). Correct: `<KeyStat value="43%" label="..." source="..." />`
- **Real example from 2026:** `### FAQ` or `### Can we use both?` in body violates "no markdown headers" rule. Replace all with `**bold**` paragraphs
- **Real example from 2026:** Pillar field set to "QUALIFY" instead of valid value. Must be one of: Setup, Strategy, Industry, Comparison, Pricing, Product
- Fix BEFORE saving to Airtable

**HIGH (brand voice violation or missing structure):**
- Byline/title in body, missing Callout, section titles not bold, no BLUF, invalid Pillar (violations 1, 3, 4, 5, 9)
- Don't crash but violate the 2026 spec and brand rules
- Jonathan will reject these in review
- Fix before Jonathan review

**MEDIUM (content quality, not a blocker):**
- Plain text sections, FAQ questions, no mid-body components, missing last-updated date (violations 6, 7, 11)
- Degrade readability and LLM citation quality but don't fail validation
- Fix if time permits; flag to Jonathan if not

**Step 4: Create corrected Body text**

For each post with violations:
- Copy the current Body
- Apply fixes in order (remove byline/title, replace headers, add/fix components, fix CTAs, fix bold formatting)
- Run self-check 13-point list against corrected version
- Do NOT save yet; get Jonathan's approval first

**Step 5: Batch update to Airtable**

After Jonathan approves corrections:
- Use mcp_airtable_update_records or individual updates per record
- Update Body field with corrected text
- Update Pillar field if it was invalid (set to one of 6 valid values)
- Leave Status unchanged (stays Draft or whatever it was)
- Reply in Telegram with before/after summary and affected record IDs

**Step 6: Verify post-save**

After update confirms:
- Fetch the updated record and re-scan against violation checklist
- Confirm all critical violations are resolved
- Flag any remaining issues for manual review

**Common violations & fixes (reference table)**

| Severity | Violation | Before (wrong) | After (correct) |
|----------|-----------|----------------|-----------------|
| CRITICAL | Wrong component name (shape) | `<Stat>All-day Hank shops recover $1.80 per $1 spent</Stat>` | `<KeyStat value="1.80" label="per dollar spent (all-day vs nights-only)" source="Hank deployment data" />` |
| CRITICAL | Wrong component name (case) | `<CTA href="/pricing" label="See pricing" />` | `<Cta href="/pricing" label="See pricing" />` |
| CRITICAL | Markdown headers in body | `## Why Subscription Beats Usage Based` | `**Why subscription beats usage based**` |
| CRITICAL | FAQ headers | `### What if we get flooded with spam calls?` | `**What if we get flooded with spam calls?**` |
| CRITICAL | Invalid Pillar field | Pillar = "QUALIFY" | Pillar = "Comparison" or "Industry" (must be exact value) |
| CRITICAL | Invalid Format field | Format = "Comparison Post" | Format = "Comparison" (exact value, no extra words) |
| HIGH | Hyphens in compound phrases | "all-day model" or "after-hours calls" or "$500-$1,500" | "all day model" or "after hours calls" or "$500 to $1,500" |
| HIGH | Byline in body | "By Jonathan S\nFounder of Hank AI..." (first line of body) | Remove entirely. Byline goes in frontmatter only. |
| HIGH | Section titles not bold | "The real call loss number" (plain text) | "**The real call loss number**" (bold) |
| MEDIUM | Bulleted Key Takeaways | Bare bullets (not in component) | Wrap in `<Callout title="Key Takeaways">` ... `</Callout>` |
| MEDIUM | Forbidden CTA URLs | href="/demo" or href="/calculator" | Replace with: /pricing#plans, /contact, /how-it-works |
| MEDIUM | No mid-body components | 1,500 words of plain prose, no KeyStat or Quote | Add 1-2 `<KeyStat>` or `<Quote>` components spaced 400 words apart |
| CRITICAL | Wrong component name | `<Stat value="43%" />` or `<CTA>` (all caps) | Rename to: `<KeyStat value="43%" label="..." source="..." />` or `<Cta>` (lowercase) |
| CRITICAL | Markdown headers in body | ## What Goodcall Does Well | Replace with **What Goodcall Does Well** |
| CRITICAL | FAQ headers | ### Can we use both? | Replace with **Can we use both?** as bold paragraph |
| CRITICAL | Invalid Pillar | Pillar = BOOK | Change to: Setup, Strategy, Industry, Comparison, Pricing, or Product |
| CRITICAL | Invalid Format | Format = Comparison Post | Change to: Comparison, Real-Data, or Operator-Voice |
| HIGH | Hyphens throughout | after-hours, 5-truck, $500-$1,500 | Replace with: after hours, 5 truck, $500 to $1,500 |
| HIGH | Byline in body | By Jonathan S Founder of Hank AI... | Remove. Byline in frontmatter only. |
| HIGH | Plain section titles | What Goodcall Does Well (not bold) | Wrap in **bold**: **What Goodcall Does Well** |
| MEDIUM | Bulleted Key Takeaways | Key Takeaways (plain bullets) | Wrap in `<Callout title="Key Takeaways">` MDX component |
| MEDIUM | Forbidden CTA | href="/demo" | Change to: /pricing#plans, /contact, /how-it-works |
| MEDIUM | No mid-body components | 1,500 words with no KeyStat/Quote | Add 1 to 2 components spaced 400 words apart |

**Pitfalls (audit mode specific)**

- Over-correcting: Don't add MDX components that aren't needed. Quality over quantity.
- Assuming all violations are fixable: Some require Jonathan's input. Flag separately.
- Breaking the Body field: Always test one record first before batch updating.
- Losing context: Note what violations existed and what changed. Reply with summary so Jonathan can validate.

### Bulk Audit Execution (10-18+ posts at scale)

**Trigger:** User says "reformat posts 2-18" or "audit and fix all 18 blog posts" or provides a multi-post range to bulk-fix.

**Rate limiting:** Airtable MCP enforces 5 req/sec per base. For bulk operations:
- Wait 20 seconds between each record fetch or update
- Use delegate_task to parallelize 3 posts at a time (max_concurrent_children=3)
- Fetch all records with pagination (100 per page, iterate over offset) to get IDs first
- Then fix posts in batches of 3, waiting 20s between batches

**Execution flow (fast path for 10-18 posts):**

1. Fetch full record list once (get all IDs) — 1 API call
2. Wait 20s
3. For posts needing fixes, batch into groups of 3 and dispatch with delegate_task
   - Each task: fetch 1 post, audit against 12-point checklist, apply fixes, update record, return summary
   - Wait 20s between batches
4. Posts already compliant (skip)
5. Collect summaries from all tasks
6. Return consolidated report: total posts, total fixed, violations by category, all record IDs

**Example:** Posts 2-18 (17 total)
- Posts 2-5 already fixed → skip
- Posts 6, 8, 10-17 need fixing (10 posts total)
- Organize as: [6, 8, 10], [11, 12, 13], [14, 15, 16], [17]
- Delegate each batch with 20s delays between batches
- Wait for completion before returning summary

**Code pattern (pseudocode):**

```
function bulk_audit_blog_posts(post_range) {
  // 1. Fetch full list to get all record IDs
  all_records = fetch_records_paginated() // May have 20-25 records total
  wait_20s()
  
  // 2. Filter to posts needing audit
  posts_to_fix = filter_by_range(all_records, post_range) // e.g., posts 6-18
  
  // 3. Batch into groups of 3
  batches = chunk(posts_to_fix, 3) // [batch 1 of 3], [batch 2 of 3], ...
  
  // 4. For each batch, delegate_task in parallel
  for each batch in batches:
    delegate_task(
      tasks = [
        {goal: "Fix post {id1}, audit, apply fixes, update Airtable"},
        {goal: "Fix post {id2}, audit, apply fixes, update Airtable"},
        {goal: "Fix post {id3}, audit, apply fixes, update Airtable"},
      ]
    )
    wait_20s() // Before next batch
  
  // 5. Collect results and return summary
  return {
    total_posts: len(posts_to_fix),
    fixed: len(results),
    violations_fixed: aggregate_violations(results),
    record_ids: [all fixed post IDs]
  }
}
```

**Summary template (return to user):**

```
Blog Audit Complete: Posts 2-18

Posts already compliant (skipped): 1, 3, 7, 9, 18
Posts fixed: 6, 8, 10, 11, 12, 13, 14, 15, 16, 17

Violations fixed:
- Component names (5): <Stat> → <KeyStat>, <CTA> → <Cta>
- Markdown headers (8): ### → **bold**
- Hyphens (12): after-hours → after hours, $X-$Y → $X to $Y
- Section titles (7): added **bold** to unbolded sections
- Pillar fields (6): BOOK/QUALIFY → valid values (Setup, Strategy, Industry, etc.)

All 10 posts updated to Airtable. Ready for publication review.
Airtable links: [rec6...], [rec8...], [rec10...], ...
```

**When NOT to use this pattern:**

- Single post fixes (just do direct fetch/fix/update, no batching)
- Fewer than 5 posts (overhead of delegate_task not worth it; do inline)
- Uncertain violations (wait for Jonathan to clarify first; don't guess)

## Self-check before saving

Run through all 13 before saving to Airtable. If any fail, revise before saving.

**Pre-save environment check (do this first):**
- Verify AIRTABLE_API_KEY is available: `env | grep AIRTABLE_API_KEY`
- If not set, use fallback workflow (step 6b above)
- If set, proceed to the 13-point checklist below

1. 1,200-2,000 words (not padding over 2,000)?
2. Format is Comparison / Real-Data / Operator-Voice (never generic What is X)?
3. Title has keyword near front?
4. Author byline is Jonathan Sherman with credentials/Person schema note?
5. Callout (Key Takeaways) has 4-6 bullets and appears after lede, before body?
6. BLUF paragraph answers the question in 2 sentences before detail?
7. All section titles are **bold text**, NO Markdown headers (# ## ###) anywhere in body, including FAQ?
7b. NO markdown tables (`| col | col |`) anywhere — the site's MDX renderer treats them as raw text. Use bullet lists with `/` separators.
8. FAQ questions are **bold paragraphs** (not ### H3 headers)?
9. All MDX components use exact case-sensitive names: <Cta>, <CtaPair>, <KeyStat>, <Quote>, <Callout>, <PricingTeaser> (NOT <CTA>, <CTAGroup>, <Stat>, <PricingCard>)?
10. Real proof: specific numbers, screenshots, named shops (permission-based), no invented stats?
11. Last-updated date visible in body? Single soft CTA at end (try Hank live, not BUY NOW)?
12. No hyphens or em-dashes anywhere? No buzzwords?
13. CTA URLs are valid: /pricing#plans (pricing table), /pricing (ROI calc), /contact, /how-it-works, /integrations/[platform], /industries/[trade]. FORBIDDEN: /demo, /calculator, /vs/*, /team/*.

If any fail, revise before saving.

## What NOT to build

- Generic "What is an AI receptionist?" guides. AI tools answer these without citing you. Bottom-funnel instead.
- Listicles ("10 ways to grow your HVAC business"). Saturated, low-converting, competitors outrank you.
- "Ultimate guides" over 4,000 words. Dilutes citation density, forces poor AI chunking.
- Bylines that aren't Jonathan or a real named person with credentials.
- Invented case studies. Kills trust.
- Invented stats. Use real numbers or mark as estimates.
- Multiple CTAs or salesy language. One soft CTA. Let the content sell.
- Walls of text. Short paragraphs (2-4 sentences). Mobile and AI chunk poorly on long prose.

## Publishing & Deployment Workflow

**Trigger:** Jonathan approves draft(s) in Airtable, changes Status to "Approved", and asks to ship to blog endpoint.

**Endpoint reference:**
- URL: https://meethank.ai/api/blog/posts
- Auth: Bearer BLOG_API_KEY env var (set in Railway deployment)
- Repo: AI-SDR-SaaS/ai-assistant-website, default branch: master (not main)
- Max posts per request: 25

**Step 1: Extract Airtable records to MDX**

- Fetch all records with Status="Approved" from tblPpkyoAP5dROgh8
- For each record: extract Name (slug), Keyword, Format, Pillar, Body, Author (use "Jonathan S")
- Transform slug: lowercase, replace spaces/special chars with hyphens, regex matches lowercase letters, digits, hyphens only
- Build frontmatter as YAML object with all required fields (title, description, date, author, pillar, tags, image, draft, format, keyword)
- Concatenate frontmatter + content into MDX body

**Step 2: Validate before POST**

- Slug: matches regex. No spaces, no uppercase, no special chars except hyphens.
- Frontmatter: all required fields present (title, description, date, author, pillar, draft). Format and keyword are optional metadata-only fields.
- Content: NO `#`, `##`, or `###` headers anywhere, including FAQ. NO markdown tables (`| col |` syntax, doesn't render). All section titles use `**bold**`. Inline CTAs use `<Cta href="/url" label="text" />` (lowercase t-a). All MDX components use exact case-sensitive names.
- Word count: 1,200-2,000 per post.
- Author: consistent across all posts (typically "Jonathan S").
- Date: YYYY-MM-DD format. Ensure logical order if publishing multiple posts.

**Step 3: POST to endpoint**

Use cron job or direct script. If shipping single post, use `draft: true` for verification. If shipping multiple posts, use `draft: false` for live index inclusion.

**Step 4: Verify response**

- Status code 200: success. PR opened, branch created, files committed.
- Status code 4xx/5xx: error. See troubleshooting below.
- Extract `prUrl` from response and share with Jonathan for review.
- Vercel auto-deploys preview within 60 seconds of PR open. Verify preview link works.

**Step 5: Jonathan merges PR**

- Jonathan reviews the PR in GitHub (content, formatting, metadata).
- Jonathan merges PR to master.
- Vercel auto-deploys main site ~60 seconds later.
- Posts are live on meethank.ai/blog.

**Step 6: Update Airtable after live deployment**

After post is confirmed live on meethank.ai/blog:
- Update the Airtable record Status field to "Published"
- Add today's date to the "Posted Date" field

**Common failures & fixes**

**MDX compile error / undefined component:**
- Cause: Used a wrong component name like `<CTA>`, `<Stat>`, `<PricingCard>`, or `<CTAGroup>`. These do not exist on the website.
- Fix: Replace with the correct case-sensitive name: `<Cta>`, `<KeyStat>`, `<PricingTeaser>`, `<CtaPair>`.

**Markdown header found in body:**
- Cause: Used `#`, `##`, or `###` somewhere in the body (often in FAQ).
- Fix: Replace with `**bold**` paragraph.

**502 Bad Gateway:**
- Cause: Endpoint tried to fetch the GitHub reference (branch base) but failed. Usually due to default branch mismatch.
- Fix: Verify repo default branch is master, not main.

**400 Bad Request (payload validation):**
- Cause: One or more required frontmatter fields missing, or slug doesn't match regex.
- Fix: Check the error response for the field name and correct it.

**201 Created (unexpected):**
- This is fine; the endpoint might return 201 instead of 200. Check the response body for `ok: true` and `prUrl`.

**Timeout / Network error:**
- Cause: Endpoint is slow or Railway deployment is down.
- Action: Wait 30 seconds and retry. If it persists, check Railway logs for errors.

## Resources

- Airtable Blogs table: appx83XNovzpsHlKe / tblPpkyoAP5dROgh8
- Endpoint spec (canonical, always current): https://meethank.ai/api/blog/spec
- Reference template post: https://meethank.ai/api/blog/template
- Endpoint API: https://meethank.ai/api/blog/posts (POST, Bearer auth via BLOG_API_KEY)
- Jonathan Sherman's byline should link to /team/jonathan-sherman (dev team sets this up)
- Internal links: reference real meethank.ai pages (e.g., /vs/goodcall, /integrations/servicetitan, /industries/hvac, create these alongside the blog)
- Default branch on GitHub repo: master (not main), critical for endpoint branch detection
- MDX component palette (case-sensitive, exact names): `<Cta>`, `<CtaPair>`, `<Callout>`, `<KeyStat>`, `<Quote>`, `<PricingTeaser>`
