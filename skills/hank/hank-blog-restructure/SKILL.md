---
name: hank-blog-restructure
description: |
  Audit and restructure existing blog post drafts in Airtable to match 2026 MDX format.
  Fixes format violations (markdown headers, missing components, wrong MDX names, hyphens).
  Bulk reformat 1-18+ posts at a time. Validates with publisher's validation function.
  Always read exemplars first. Batch update via Airtable API with rate-limiting.
author: Ace
created: 2026-05-07
tags:
  - blog
  - audit
  - format-fix
  - bulk-restructure
---

# Hank Blog Restructure

**When to use:** Jonathan says "fix these blog posts", "audit the drafts", "reformat posts X-Y", or you discover posts with format violations (wrong MDX components, markdown headers in body, hyphens, missing Callout, etc.).

**When NOT to use:** Drafting new posts from scratch (use hank-blog-drafter). Publishing approved posts (use blog-publisher-cron).

**Scope:** Fix 1 to 18+ existing draft records in one workflow. Validate against publisher rules. Never publish; leave Status as Draft.

## Quick Start (first time)

1. **Read exemplars** — non-negotiable. These are the source of truth for structure.
   - `/opt/data/skills/hank-blog-drafter/examples/servicetitan-comparison.mdx` (Comparison format)
   - `/opt/data/skills/hank-blog-drafter/examples/pricing-models.mdx` (Pricing/cost format)
   - Spend 3 minutes scanning both. Notice: Callout at top → prose → mid-body Quote/KeyStat → FAQ as **bold?** → CtaPair close.

2. **Fetch records** — Get all 8 (or 1-18) records from Airtable base appx83XNovzpsHlKe, table tblPpkyoAP5dROgh8.

3. **Audit each** — Check for CRITICAL violations:
   - Markdown headers (# ## ###) in body → must replace with **bold**
   - Wrong component names (<CTA>, <Stat>, <PricingCard>) → must fix to exact case (<Cta>, <KeyStat>, <PricingTeaser>)
   - Hyphens in phrases (after-hours, $500-$1,500) → must convert to after hours, $500 to $1,500
   - Invalid Pillar/Format fields → must be exact enum values
   - Missing <Callout> or </CtaPair> → must add

4. **Restructure** — Rewrite body to match exemplar: Callout → BLUF → bold sections → mid-body component → FAQ (bold) → CtaPair.

5. **Validate** — Run the publisher's validate_post() function on each record to confirm CLEAN status.

6. **Batch update** — Push all corrected records to Airtable in one or a few batch calls (rate-limit: 5 req/sec, wait 20s between batches).

## Violation Hierarchy

### CRITICAL (page crashes if not fixed)
- Markdown headers: `## Section` in body → Replace with `**Section**`
- Wrong component names: `<Stat>`, `<CTA>`, `<PricingCard>`, `<CTAGroup>` → Fix to `<KeyStat>`, `<Cta>`, `<PricingTeaser>`, `<CtaPair>`
- Forbidden CTA URLs: `/demo`, `/calculator`, `/vs/*` (wrong endpoints) → Use `/pricing#plans`, `/contact`, `/how-it-works`
- Invalid field values: Pillar = "BOOK" (not one of 6 valid values) → Set to valid: Setup, Strategy, Industry, Comparison, Pricing, Product
- Invalid Format: Format = "Comparison Post" (typo or extra words) → Must be exact: Comparison, Real-Data, Operator-Voice

### HIGH (violates brand rules, Jonathan will reject)
- Hyphens: "after-hours" → "after hours"; "$500-$1,500" → "$500 to $1,500"
- Byline in body: "By Jonathan S" or author bio as first line → Remove entirely (goes in frontmatter only)
- Section titles not bold: "The Real Cost" (plain text) → "**The Real Cost**"
- No <Callout title="Key Takeaways"> block → Must add after lede
- No closing <Cta> or <CtaPair> → Must add before end

### MEDIUM (quality degrade, not a blocker)
- FAQ questions not bold: `### Question` → `**Question?**`
- No mid-body components: 1,500 words with zero <KeyStat>, <Quote>, or <Callout> → Add 1-2 spaced 400 words apart
- Missing last-updated date: No "Last updated: May 2026" line near end → Add it
- Invalid component shape: `<KeyStat>43%</KeyStat>` (text content) → Fix to `<KeyStat value="43%" label="..." source="..." />`

## Exemplar Structure (read before drafting)

Both exemplars at `/opt/data/skills/hank-blog-drafter/examples/` follow this pattern:

```
[Lede paragraph intro]

<Callout title="Key takeaways">
- Bullet 1
- Bullet 2
...
</Callout>

[BLUF paragraph: direct answer in 2 sentences]

**Section Title (bold, NOT markdown header)**

[Prose content]

<Quote attribution="Name, role, location">
Quote text
</Quote>

**Another Section**

[More prose]

<KeyStat value="X" label="Y" source="Z" />

[Continue prose sections]

**FAQ**

**Q: First question?**

Answer paragraph.

**Q: Second question?**

Answer paragraph.

---

<CtaPair
  primaryHref="/url"
  primaryLabel="Primary button text"
  secondaryHref="/url"
  secondaryLabel="Secondary button text"
/>
```

**Key patterns:**
- NO `#`, `##`, or `###` headers in body (all replaced with `**bold**`)
- Callout near top with 4-6 bullets
- Mid-body components (Quote, KeyStat, or second Callout variant="success")
- FAQ questions as `**Q: text?**` (bold paragraphs, not headers)
- Closing with CtaPair (or single Cta if only one obvious action)
- NO markdown tables (`| col |` — doesn't render, use bullet lists with `/` separators instead)
- NO hyphens or em-dashes

## Validation Checklist (13-point)

Use this BEFORE and AFTER to catch issues. Load the blog-publisher script and call validate_post(record) to verify CLEAN status.

**Pre-restructure (identify violations):**
1. Any `#`, `##`, or `###` in body? (CRITICAL)
2. Any `<CTA>`, `<Stat>`, `<PricingCard>`, `<CTAGroup>`? (CRITICAL)
3. Any forbidden CTA hrefs: /demo, /calculator, /vs/*, /team/*? (CRITICAL)
4. Invalid Pillar field? Must be one of: Setup, Strategy, Industry, Comparison, Pricing, Product (CRITICAL)
5. Invalid Format field? Must be one of: Comparison, Real-Data, Operator-Voice (CRITICAL)
6. Hyphens in compound words or ranges? (HIGH)
7. Byline or author bio in first line of body? (HIGH)
8. Section titles not bold? (HIGH)
9. No <Callout> component? (HIGH)
10. No <Cta> or <CtaPair> at end? (HIGH)
11. FAQ questions not **bold** (or using ###)? (MEDIUM)
12. No mid-body <KeyStat>, <Quote>, or variant Callout? (MEDIUM)
13. Any markdown tables (`| col |`)? (HIGH — use bullet lists with `/` instead)

**Post-restructure (run validator):**
```python
import importlib.util
spec = importlib.util.spec_from_file_location('bp', '/opt/data/cron/blog-publisher.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)
result = bp.validate_post(record)  # Returns error string or None (CLEAN)
```

If result is None, record is CLEAN.

## Workflow: Single Post Audit (No Changes)

**Trigger:** Jonathan says "Audit this post rec_..." or you're spot-checking a draft to confirm compliance.

**When this applies:** The post may already be compliant (zero violations). Do not assume you need to fix it.

1. **Fetch record** from Airtable (get full Body, Name, Pillar, Format)
2. **Audit** against 13-point checklist (scan for violations)
3. **Run validator** to confirm CLEAN status
4. **Return audit report:**
   - If CLEAN: list all checks passed, note "No update needed"
   - If violations: identify severity (CRITICAL / HIGH / MEDIUM) and proceed to "Workflow: Single Post Fix"

**Report format (CLEAN case):**
```
Record ID: rec6jCPeidSQZrmiM
Name: [Title]
Status: Draft

✓ VALIDATION RESULT: CLEAN

Violations found: 0
Violations fixed: 0
Action: No update needed.

All structural requirements met:
  ✓ Has <Callout> component
  ✓ Has <KeyStat> component
  ✓ Has closing <Cta> component
  ✓ No markdown headers (#, ##, ###)
  ✓ No invalid MDX components
  ✓ Valid CTA hrefs
  ✓ No markdown tables
```

## Workflow: Single Post Fix (Direct Airtable Update)

1. **Fetch record** from Airtable (get full Body)
2. **Audit** against 13-point checklist
3. **Identify violations** and severity (CRITICAL / HIGH / MEDIUM)
4. **Rewrite body** to fix all violations
5. **Run validator** to confirm CLEAN
6. **Update Airtable** with corrected Body field
7. **Verify post-update** by fetching and validating again

## Workflow: Single Post Fix with File Output (Session/Batch Pattern)

**When to use:** AIRTABLE_API_KEY is unavailable or uncertain in session (Telegram, delegated tasks). Jonathan approves fixes before batch update, or fixes are staged for later batch processing.

**Trigger:** `Fix blog post rec2bkPwluMDwFrIS (Hank vs. Goodcall). Fetch, audit, fix hyphens + rename Hank AI to Hank the Pro, validate, and return results. Do NOT update Airtable yet (batch update later).`

**Pattern:**

1. **Fetch record** from Airtable via HTTP (Python urllib, not terminal curl)
2. **Audit via local script** (do not call publisher via import; write standalone audit validators in Python)
3. **Fix violations** inline in Python script (string replace, regex sub for hyphens, etc.)
4. **Validate via standalone validator** (re-implement validation logic locally or import blog-publisher.py via exec() if available)
5. **Save outputs:**
   - Fixed Body text to `/tmp/fixed_body_<RECORD_ID>.txt`
   - Audit JSON report to `/tmp/audit_result_<RECORD_ID>.json`
6. **Return to user:**
   - Summary in Telegram with JSON report
   - File paths for fixed body and report
   - Clear "READY_FOR_UPDATE" status
   - Do NOT attempt Airtable PATCH (wait for Jonathan's batch update approval)

**Example execution (code pattern):**

```python
import json
import re
import urllib.request

# Constants
BASE_ID = "appx83XNovzpsHlKe"
TABLE_ID = "tblPpkyoAP5dROgh8"
RECORD_ID = "rec2bkPwluMDwFrIS"
api_key = os.getenv("AIRTABLE_API_KEY")

# 1. Fetch record via HTTP
url = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}/{RECORD_ID}"
headers = {"Authorization": f"Bearer {api_key}"}
req = urllib.request.Request(url, headers=headers, method="GET")
with urllib.request.urlopen(req) as response:
    record = json.loads(response.read().decode("utf-8"))
    body = record["fields"]["Body"]

# 2. Audit: run local validators (copy logic from blog-publisher.py or exec the file)
def has_hyphens(text):
    return re.findall(r'\$?\d+-\$?\d+|\bafter-hours\b|\breal-time\b', text)

violations = has_hyphens(body)

# 3. Fix violations inline
fixed_body = body.replace("after-hours", "after hours")
fixed_body = fixed_body.replace("Hank AI", "Hank the Pro")

# 4. Validate fixed version (re-run local validators or import blog-publisher)
exec(open('/opt/data/cron/blog-publisher.py').read(), globals())
errors = validate_post({"fields": {"Name": name, "Body": fixed_body}})

# 5. Save outputs
with open(f'/tmp/fixed_body_{RECORD_ID}.txt', 'w') as f:
    f.write(fixed_body)

result = {
    "record_id": RECORD_ID,
    "violations_found": violations,
    "violations_fixed": list(set(violations)),
    "validation_result": "CLEAN" if not errors else "NEEDS_FIXING"
}

with open(f'/tmp/audit_result_{RECORD_ID}.json', 'w') as f:
    json.dump(result, f, indent=2)

# 6. Return summary and file paths
```

**Advantages of this pattern:**

- Works in Telegram and delegated task contexts where API is uncertain
- Audit is reproducible via script (not interactive shell commands)
- Fixes are staged for approval before batch update
- File outputs provide clear handoff to Jonathan or batch update queue
- Validator logic can be re-imported if blog-publisher.py is available, or re-implemented locally

**Fallback if exec() fails:**

If `exec(open('/opt/data/cron/blog-publisher.py'))` fails (syntax issues, main() call, etc.), re-implement validation locally:

```python
def validate_post_local(record):
    body = record.get("fields", {}).get("Body", "")
    errors = []
    if re.search(r"^#{1,3}\s", body, re.MULTILINE):
        errors.append("Markdown headers found")
    if re.findall(r"<([A-Z][a-zA-Z0-9]*)", body):
        invalid = [c for c in list(set(...)) if c not in ALLOWED_MDX_COMPONENTS]
        if invalid:
            errors.append(f"Invalid MDX: {invalid}")
    # ... (add more checks as needed)
    return errors if errors else None
```

This ensures validation can always run even if blog-publisher.py is unavailable.

## Workflow: Bulk Restructure (5-18+ posts)

**Trigger:** "Fix posts 2-18" or "Reformat all 8 drafts" or "Audit and fix violations"

**Rate-limiting:** Airtable enforces 5 req/sec per base. Strategy:
- Fetch full list once (1 call)
- Wait 20s
- For each post needing fix, dispatch with delegate_task (batch 3 at a time)
- Wait 20s between batches
- Each task: fetch, audit, rewrite, validate, update

**Execution (pseudocode):**

```
1. Fetch all records from tblPpkyoAP5dROgh8 (paginate if 100+)
2. Wait 20s
3. Identify which need fixes (scan Body for violations)
4. Organize into batches of 3
5. For each batch:
   - delegate_task with 3 fix jobs (parallel)
   - Each job: audit, rewrite, validate, update 1 post
   - Wait for all 3 to complete
   - Wait 20s before next batch
6. Collect results and summarize

Example for posts 2-18 (17 total):
  Batch 1: posts [2, 3, 4] — delegate
  Wait 20s
  Batch 2: posts [5, 6, 7] — delegate
  Wait 20s
  Batch 3: posts [8, 9, 10] — delegate
  Wait 20s
  ...
  Batch 6: posts [17, 18] — delegate
  Wait 20s
  Done
```

**Return summary:**
```
Blog Restructure Complete: Posts 2-18 (17 total)

Posts already compliant (skipped): 1, 7, 12
Posts fixed: 2, 3, 4, 5, 6, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18 (14 total)

Violations fixed:
- Markdown headers (## → **bold**): 12 posts
- Wrong component names (<Stat> → <KeyStat>, etc.): 8 posts
- Hyphens (after-hours → after hours): 14 posts
- Missing <Callout>: 3 posts
- Missing <CtaPair>: 5 posts
- Invalid Pillar values: 2 posts
- Invalid Format values: 1 post

All 14 posts updated and CLEAN. Ready for review.
Airtable links: rec2..., rec3..., rec4..., ...
```

## Common Fixes (Reference Table)

| Violation | Before | After | Severity |
|-----------|--------|-------|----------|
| Markdown header in body | `## Why This Matters` | `**Why This Matters**` | CRITICAL |
| Wrong component (case) | `<CTA href="/pricing">` | `<Cta href="/pricing">` | CRITICAL |
| Wrong component (name) | `<Stat value="43%">` | `<KeyStat value="43%" label="..." source="..." />` | CRITICAL |
| Hyphens in ranges | `$500-$1,500` | `$500 to $1,500` | HIGH |
| Hyphens in phrases | `after-hours` | `after hours` | HIGH |
| Forbidden CTA URL | `href="/demo"` | `href="/how-it-works"` | CRITICAL |
| Byline in body | `By Jonathan S\nFounder of Hank AI...` (first line) | (Remove. Byline in frontmatter only.) | HIGH |
| Section not bold | `The Real Cost` (plain) | `**The Real Cost**` | HIGH |
| Invalid Pillar | `Pillar = "BOOK"` | `Pillar = "Setup"` (or Comparison, Strategy, etc.) | CRITICAL |
| Invalid Format | `Format = "Tech Post"` | `Format = "Operator-Voice"` | CRITICAL |
| Bullets not in Callout | `- Takeaway 1\n- Takeaway 2` (bare) | `<Callout title="Key Takeaways">- Takeaway 1\n- Takeaway 2\n</Callout>` | HIGH |
| FAQ header | `### Can we use both?` | `**Can we use both?**` | MEDIUM |
| No mid-body component | 1,500 words prose | Add `<Quote>` or `<KeyStat>` at ~700 words | MEDIUM |

## Key Rules

1. **Always read exemplars first.** Do not rely on rules alone. Structure is learned from examples, not documentation.

2. **Validate with the publisher function.** Do not trust your own checklist. Load `/opt/data/cron/blog-publisher.py` and call `validate_post(record)`. If it returns None, record is CLEAN.

3. **No markdown tables.** The site's MDX renderer does not parse `| col | col |` syntax. Use bullet lists with `/` separators:
   - GOOD: `- Per minute at $2.40: $960 / $2,880 / $5,760 (for 50/150/300 calls)`
   - BAD: `| Model | 50 calls | 150 calls | 300 calls |`

4. **No hyphens or em-dashes anywhere.** Replace with commas, periods, or new sentences.
   - "after-hours" → "after hours"
   - "30-day" → "30 day"
   - "4-5x" → "4 to 5x"
   - "long — clause" → "long. Clause." or "long, clause."

5. **Component names are case-sensitive.** Exact matches required:
   - Valid: `<Cta>`, `<CtaPair>`, `<Callout>`, `<KeyStat>`, `<Quote>`, `<PricingTeaser>`
   - Invalid: `<CTA>`, `<CTAGroup>`, `<Stat>`, `<PricingCard>`, `<PricingCard>`, `<CTA>` (wrong case or name)

6. **Pillar and Format are enums.** No typos. Must be exact:
   - Pillar: Setup, Strategy, Industry, Comparison, Pricing, Product
   - Format: Comparison, Real-Data, Operator-Voice

7. **Never invent content.** If a Callout, Quote, or KeyStat is missing, you ADD the STRUCTURE, but preserve existing prose content. Do not rewrite facts or invent stats. Restructure only.

8. **Status stays Draft.** Never flip to Approved or Published. Jonathan approves after review.

## Environment

- **AIRTABLE_API_KEY** required (read/write on base appx83XNovzpsHlKe)
- **BLOG_API_KEY** optional (only needed if you plan to publish after fixing)

**In Telegram/delegated task contexts:** AIRTABLE_API_KEY may not be available. Use "Workflow: Single Post Fix with File Output" (fetch via Python HTTP, audit locally, save to files). This preserves audit reproducibility while deferring Airtable writes.

**Delegated task pattern note (bulk restructure with parallel execution):**
- Max concurrent children: 3 (Hermes limit). For 10+ posts, split into batches of 3.
- Each child task receives record ID, goal, and context (no direct env var injection guaranteed).
- Task timeout: if a child doesn't complete within expected time (~5 min per post), it will be interrupted (status: interrupted, no summary).
- On child interrupt: Treat as "fix not attempted yet" — post remains unchanged in Airtable. Can retry in next batch or escalate to Jonathan.
- Always collect results from all children before summarizing. Do NOT assume all 3 children completed if 1-2 return results.

If AIRTABLE_API_KEY is not available, use file output fallback, or fetch/patch manually via UI, or request key be set in environment.

## Example: Fix 8 Posts

**Scenario:** Jonathan has 8 drafts with format violations. Audit and fix all 8, validate, and batch update.

1. Read exemplars (3 min)
2. Fetch all 8 records from Airtable (1 call, wait 20s)
3. Audit each against 13-point checklist (identify violations per post)
4. For each post with violations:
   - Rewrite body to match exemplar structure
   - Run validator to confirm CLEAN
   - Batch into groups of 3
5. Delegate 3 posts at a time (parallel execution)
6. Wait 20s between batches
7. Collect results, summarize violations fixed, return Airtable links

Expected time: 15-20 minutes for 8 posts (5 min exemplars + 3 min audit + 8 min restructure + 2 min validate + 2 min batch update).

## Troubleshooting

**Delegated task interrupted (status: interrupted)**
- Happens when a child task doesn't complete within expected time (5+ min per post)
- Symptoms: 3 tasks delegated, only 1-2 return results, 1+ shows status: interrupted
- Action: Treat interrupted task as fix not attempted — post stays unchanged in Airtable
- Next steps: (a) Retry in new batch, (b) Fix inline directly, or (c) Flag to Jonathan
- Prevention: Large posts (2000+ words) are best fixed inline. Delegation best for 5-15 typical posts.
- Monitoring: Always log task status per batch. If any child interrupted, note in final report so Jonathan knows what needs retry.

**AIRTABLE_API_KEY not set**
- Env var missing. Set it in Railway or request access.
- Fallback: Use "Workflow: Single Post Fix with File Output" pattern (fetch via HTTP in Python, audit locally, save to files, no PATCH attempt)
- Fetch manually via UI, fix locally, paste corrected Body back into Airtable UI if script also fails.

**"Validator returns error, not CLEAN"**
- Run validator again with full error output
- Common: still has `##` header somewhere, or component name is wrong
- Scan body for `#` character, fix all matches
- Check all `<` tags for exact case match

**"Too many Airtable requests, rate-limited"**
- Wait 30 seconds, try again
- For bulk updates, increase delay between batches from 20s to 30s
- Batch into groups of 2 instead of 3 if needed

**"Markdown table renders as raw text"**
- Expected. Site's MDX doesn't enable remark-gfm.
- Replace with bullet list: `- Model A / Cost / Result`
- Or write raw HTML `<table>` if tabular layout is critical (rare)

**"exec(blog-publisher.py) fails or hangs"**
- Script may have a main() call at the end that tries to run argparse
- Fallback: Extract only the validator functions (has_header_violations, check_invalid_mdx_components, check_required_components, etc.) into a local dict and re-implement
- Or: Use Python's `importlib.util.spec_from_file_location` to load functions without triggering main()
- Pattern: `spec = importlib.util.spec_from_file_location('bp', '/opt/data/cron/blog-publisher.py'); bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp); errors = bp.validate_post(record)`

## Files & References

- **Exemplar 1 (Comparison format):** `/opt/data/skills/hank-blog-drafter/examples/servicetitan-comparison.mdx`
- **Exemplar 2 (Pricing format):** `/opt/data/skills/hank-blog-drafter/examples/pricing-models.mdx`
- **Publisher script (validation function):** `/opt/data/cron/blog-publisher.py` — load and call `validate_post(record)`
- **Airtable base:** appx83XNovzpsHlKe
- **Airtable table:** tblPpkyoAP5dROgh8 (Blog Posts)
- **Voice rules reference:** `/opt/data/AGENTS.md` — defines hyphens, buzzwords, tone

## Success Criteria

- All CRITICAL violations fixed (no markdown headers, no wrong component names, all valid field values)
- All posts validate as CLEAN via publisher function
- All posts updated to Airtable
- Summary report with record IDs and violations fixed
- Status remains Draft (Jonathan reviews before approval)
