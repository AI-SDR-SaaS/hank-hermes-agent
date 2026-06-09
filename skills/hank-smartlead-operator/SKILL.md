---
name: hank-smartlead-operator
description: |
  Operates Smartlead campaigns from Telegram. Pauses and resumes
  campaigns via the Smartlead REST API. Future expansion will add
  reading campaign analytics for Optimizer mode and pushing approved
  drafts from the Cold Email Drafts Airtable table directly into
  Smartlead campaigns.

  Tonight's scope: pause and resume only. Other actions are stubbed and
  will be added in future skill updates.

  Campaign matching: Jonathan refers to campaigns by vertical or
  partial name (e.g., "the HVAC campaign", "the roofer campaign", "the
  electrician one"). The skill calls GET /campaigns/ to list all
  campaigns, fuzzy matches against name, shows the match for
  confirmation before any destructive action.

  Pause action ALWAYS requires explicit confirmation in chat. Skill
  shows campaign details (name, status, sent count if available) and
  waits for Jonathan's "yes" or "confirmed" before firing the PATCH.

  Resume action confirms once and fires.

  Use this skill when Jonathan says "pause the [vertical] campaign",
  "resume the [vertical] campaign", "stop the [vertical] campaign",
  "start the [vertical] campaign", "pause Smartlead", "resume
  Smartlead", or any campaign control phrasing.

  Do not use for: drafting cold emails (use hank-cold-email-drafter),
  pushing drafts to Smartlead (not yet built), or reading campaign
  analytics (not yet built).

  IMPORTANT: This skill makes destructive changes to live email
  campaigns. Pausing or resuming the wrong campaign affects real
  prospects. Always confirm before pause.
---

# Hank Smartlead Operator

You operate Smartlead campaigns on Jonathan's behalf. You pause
campaigns, resume campaigns, and confirm actions before firing
destructive API calls. You do not draft, push leads, or read analytics
in this version of the skill. Those are future capabilities.

## Configuration

Smartlead API:
- Base URL: https://server.smartlead.ai/api/v1
- Auth: api_key query parameter on every request
- API key env var: SMARTLEAD_API_KEY (set in Railway)
- Rate limit: 10 requests per 2 seconds. On 429, wait 2 seconds and
  retry once. If second 429, abort and tell Jonathan.

Campaign status values per Smartlead API:
- ACTIVE: campaign is running
- PAUSED: campaign is temporarily halted
- STOPPED: campaign is permanently stopped
- ARCHIVED: campaign is archived
- DRAFTED: campaign is in draft, never launched

For pause/resume operations:
- To pause an ACTIVE campaign: PATCH /campaigns/{id}/status with body
  {"status": "PAUSED"}
- To resume a PAUSED campaign: PATCH /campaigns/{id}/status with body
  {"status": "START"}
- The body status value for resume is "START" not "ACTIVE" or "RESUME".
  This is per Smartlead's API spec.

## Required env var check

At the start of every action, verify SMARTLEAD_API_KEY is set:

if not os.environ.get("SMARTLEAD_API_KEY"):
    fail with: "SMARTLEAD_API_KEY not set in Railway env vars. Cannot
    proceed. Add the key in Railway dashboard and redeploy."

Do not proceed with any API call if the key is missing.

## Workflow: pause a campaign

When Jonathan says "pause the [vertical] campaign" or similar:

STEP 1: List campaigns

GET https://server.smartlead.ai/api/v1/campaigns/?api_key={KEY}&include_tags=true

Response is an array of campaign objects with id, name, status, and
other fields.

STEP 2: Fuzzy match the vertical to a campaign name

Lowercase both the user's vertical word and each campaign name. Search
for the vertical word as a substring of the campaign name.

Examples:
- User says "HVAC" -> match any campaign with "hvac" in name (case
  insensitive)
- User says "roofer" or "roofing" -> match "roofer" OR "roofing" in
  name
- User says "plumber" or "plumbing" -> match "plumb" prefix in name
- User says "electrician" or "electrical" -> match "electric" prefix
- User says "landscaper" or "landscaping" -> match "landscap" prefix

If multiple campaigns match (e.g., user says "the campaign" with no
vertical specified), do NOT guess. Ask Jonathan to specify which
vertical.

If zero campaigns match, tell Jonathan: "No campaign found matching
'[user's word]'. Available campaigns are: [list all campaign names
and their current statuses]. Which one?"

If exactly one campaign matches, proceed to STEP 3.

STEP 3: Show match and request confirmation

Reply to Jonathan in Telegram with:

"Found match: '[campaign name]'
Status: [current status]
Created: [created_at]
Daily lead limit: [max_leads_per_day]

Confirm pause? Reply 'yes' or 'confirmed' to proceed. Reply anything
else to cancel."

Wait for Jonathan's response. Do NOT fire the PATCH yet.

If Jonathan replies "yes", "confirmed", "go", "do it", or similar
explicit confirmation, proceed to STEP 4.

If Jonathan replies anything ambiguous or negative, do NOT pause.
Tell him: "Cancelled. No changes made."

STEP 4: Execute the pause

PATCH https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status?api_key={KEY}

Body: {"status": "PAUSED"}

Headers: Content-Type: application/json

Capture the response. If 200, success. If non-200, capture the error
message.

STEP 5: Confirm to Jonathan

If success:
"Paused '[campaign name]' at [timestamp]. Status now PAUSED. No
further sends until you resume."

If failure:
"Pause failed for '[campaign name]'. API returned [status code]: [error
message]. Campaign status unchanged. Try again or check Smartlead
directly."

## Workflow: resume a campaign

When Jonathan says "resume the [vertical] campaign" or similar:

STEP 1: List campaigns (same as pause workflow)

STEP 2: Fuzzy match (same as pause workflow)

STEP 3: Show match and request confirmation

"Found match: '[campaign name]'
Status: [current status]

Confirm resume? Reply 'yes' or 'confirmed' to proceed."

Wait for confirmation. Same logic as pause.

STEP 4: Execute the resume

PATCH https://server.smartlead.ai/api/v1/campaigns/{campaign_id}/status?api_key={KEY}

Body: {"status": "START"}

Note: Smartlead expects "START" not "ACTIVE" or "RESUME" in the body
to resume a paused campaign.

STEP 5: Confirm to Jonathan

If success:
"Resumed '[campaign name]' at [timestamp]. Status now ACTIVE. Sending
will resume per the campaign schedule."

If failure: same error pattern as pause.

## Workflow: list campaigns

When Jonathan says "list campaigns", "show campaigns", "what
campaigns are running", or similar:

GET /campaigns/?api_key={KEY}&include_tags=true

Reply with a clean summary:

"5 campaigns in Smartlead:
1. [name] - [status]
2. [name] - [status]
3. [name] - [status]
..."

No confirmation needed for list since it is a read action.

## Workflow: campaign details

When Jonathan says "show details for [vertical] campaign", "what's the
status of [vertical]", or similar:

STEP 1: List campaigns and fuzzy match (same as pause/resume)

STEP 2: GET /campaigns/{id}/?api_key={KEY} for full details

Reply with:
"[campaign name]
Status: [status]
Created: [created_at]
Last updated: [updated_at]
Daily lead limit: [max_leads_per_day]
Min time between emails: [min_time_btwn_emails] minutes
Stop on: [stop_lead_settings]
Schedule: [days] [startHour]-[endHour] [tz]"

No confirmation needed since it is a read action.

## Future actions (NOT YET IMPLEMENTED)

These actions are described here so future skill versions can add them
without restructuring. Do NOT attempt these yet. If Jonathan asks for
any of them, reply: "Not built yet. Coming in a future skill update."

### Read campaign analytics
GET /campaigns/{id}/analytics?api_key={KEY}

Returns: sent, opened, clicked, replied, bounced, unsubscribed counts.
Useful for the Optimizer mode of hank-cold-email-drafter.

### Read sequence content
GET /campaigns/{id}/sequences?api_key={KEY}

Returns: full sequence content with subjects, bodies, and variants.
Useful for the Optimizer mode of hank-cold-email-drafter.

### Push approved drafts to Smartlead
POST /campaigns/{id}/sequences?api_key={KEY}
Body: array of sequence objects from Airtable Cold Email Drafts table
where Status=Approved.

This is the highest stakes action because it modifies live campaign
content. Future implementation MUST require explicit confirmation
showing the diff between current sequence and proposed new sequence
before firing.

### Get analytics by date range
GET /campaigns/{id}/analytics-by-date?api_key={KEY}&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD

Max 30 day range. Useful for weekly performance reports.

## Error handling

API rate limit (429):
- Wait 2 seconds
- Retry once
- If second 429, abort and tell Jonathan: "Smartlead rate limit hit.
  Wait a minute and try again."

API auth failure (401):
- Abort immediately
- Tell Jonathan: "Smartlead API key invalid or expired. Check
  SMARTLEAD_API_KEY in Railway env vars."
- Do not retry

API not found (404):
- The campaign ID doesn't exist
- Tell Jonathan: "Campaign ID [id] not found in Smartlead. The campaign
  may have been deleted or the API key is for a different account."

API validation error (422):
- Body shape was wrong
- Tell Jonathan: "Smartlead rejected the request. [error message from
  response]. This is a skill bug, please report."

API server error (500, 503):
- Wait 5 seconds, retry once
- If second failure, abort and tell Jonathan: "Smartlead is having
  issues. Try again in a few minutes."

Network failure:
- Wait 5 seconds, retry once
- If second failure, abort and tell Jonathan

Empty campaign list response:
- API returned 200 but empty array
- Tell Jonathan: "No campaigns found in this Smartlead account. Check
  the API key is for the right workspace."

## Defensive rules (NEVER violate)

- Never pause a campaign without explicit confirmation in chat from
  Jonathan. "Yes", "confirmed", "go", "do it" are valid confirmations.
  Anything else means cancel.
- Never pause more than one campaign per request. If Jonathan says
  "pause all campaigns", do them ONE AT A TIME with separate
  confirmations. This prevents accidental mass pause.
- Never resume a campaign that was STOPPED (only resume PAUSED).
  Resuming STOPPED is a separate intentional action that requires
  explicit "yes I want to start a stopped campaign" from Jonathan.
- Never modify a campaign's content (sequences, schedule, settings)
  with this skill. Only status changes.
- Never delete a campaign. Smartlead supports DELETE but this skill
  does not. Deletion is a manual UI action.
- Never push leads to a campaign with this skill (future capability).
- Never log the API key or include it in Telegram replies.
- If the campaign list call returns campaigns from a workspace
  Jonathan does not recognize (e.g., he expected Hank campaigns and
  sees Lumix campaigns), DO NOT proceed. Tell him: "The campaign list
  shows '[name]' style names which look like a different workspace.
  Confirm this is the correct API key before any action."

## Manual invocation phrases

When Jonathan says any of these in Telegram, run the appropriate
workflow:

Pause:
- "pause the [vertical] campaign"
- "stop the [vertical] one for now"
- "halt [vertical]"
- "pause Smartlead [vertical]"

Resume:
- "resume the [vertical] campaign"
- "start [vertical] back up"
- "unpause [vertical]"
- "turn [vertical] back on"

List:
- "list campaigns"
- "show campaigns"
- "what's running in Smartlead"
- "what campaigns do I have"

Details:
- "show details for [vertical]"
- "what's the status of [vertical]"
- "stats on [vertical] campaign" (note: this is just status info, NOT
  analytics, since analytics is not yet built)

## Self check before any pause or resume

1. Did I list campaigns first to find the right ID? (Required, do not
   guess campaign IDs)
2. Did I fuzzy match correctly to a single campaign? (If multiple
   matches, ask Jonathan, do not guess)
3. Did I show the match details to Jonathan?
4. Did I get explicit confirmation in chat?
5. Am I about to PATCH the right URL with the right body?
6. Pause body: {"status": "PAUSED"}. Resume body: {"status": "START"}.
   Confirm before firing.

If any check fails, abort and report to Jonathan.

## Resources

- Smartlead API docs: https://helpcenter.smartlead.ai/en/articles/125-full-api-documentation
- Smartlead workspace: app.smartlead.ai (manual UI for verification)
- AGENTS.md for brand voice (not directly used here, all output is
  operational not creative)
- Cold Email Drafts table: appx83XNovzpsHlKe / tblmXTzZ4TJ1h0pTN (for
  future push action)
- USER.md for Jonathan's communication preferences

## Known scope limits

This skill version 1 does ONLY:
- List campaigns
- Show campaign details
- Pause a campaign (with confirmation)
- Resume a campaign (with confirmation)

It does NOT:
- Read campaign analytics (future)
- Read sequence content (future)
- Push approved drafts to Smartlead (future, highest priority next)
- Update campaign schedule
- Update campaign settings
- Add or remove email accounts from campaigns
- Manage individual leads (pause, resume, unsubscribe)
- Configure warmup
- Manage webhooks
- Stop or archive campaigns (separate intentional action)
- Delete campaigns
- Create new campaigns

If Jonathan asks for any of these, tell him: "Not in this version of
the skill. Available: list, details, pause, resume. The action you
asked for needs a future skill update."
