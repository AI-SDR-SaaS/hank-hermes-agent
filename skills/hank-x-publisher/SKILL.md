---
name: hank-x-publisher
description: |
  Posts approved X drafts from Airtable to Jonathan Sherman's personal X
  account (@jonathan_sherm) via the X API. Polls the Airtable Drafts table
  for records with Platform=X and Status=Approved, posts them to X using
  OAuth 1.0a, then updates the record with Posted At timestamp, Post URL,
  and Status=Published.

  Handles single posts and threads (drafts split on --- separator become
  threaded reply chains).

  Use this skill when the user explicitly says "publish approved X drafts",
  "run the X publisher", "post the approved drafts now", "check the queue",
  or similar publishing commands. Also runs automatically via cron when
  cron is enabled.

  Do not use for: drafting (use hank-x-drafter), trend discovery (use
  hank-x-trend-watcher), or any non-X publishing.

  IMPORTANT: This skill writes to a real X account. Cron is DISABLED by
  default. Posting only happens on explicit Jonathan invocation OR when
  cron is explicitly enabled by Jonathan.
---

# Hank X Publisher

You publish approved X drafts to Jonathan Sherman's personal X account
(@jonathan_sherm). You do not draft. You do not curate. You execute.

## Operating principle

The Airtable Drafts table is the queue. Anything with Platform=X AND
Status=Approved is your work. You post it, then mark it Published.

You do NOT post:
- Status=Draft (Jonathan hasn't approved)
- Status=Killed (rejected, leave alone)
- Status=Published (already posted, don't double-post)
- Platform != X (different platform, not your job)

If a record's data is incomplete or malformed, mark it with a Post Error
and DO NOT post a partial or guessed version.

## Configuration (use these exact IDs and env vars)

Airtable:
- Base ID: appx83XNovzpsHlKe
- Drafts Table ID: tblqAlGW06vjyQWF3

X API credentials (from Railway env):
- X_API_KEY (consumer key)
- X_API_SECRET (consumer secret)
- X_ACCESS_TOKEN (access token, scoped Read+Write)
- X_ACCESS_TOKEN_SECRET (access token secret)

X API endpoint for creating posts: https://api.x.com/2/tweets

Auth: OAuth 1.0a HMAC-SHA1 signed requests. Use a standard library
(tweepy in Python, oauth-1.0a libraries in Node) rather than hand-rolling
the signature. Hand-rolled OAuth is the most common publisher failure mode.

## Linear task tracking

Each publisher run creates a Linear issue (team MEE) to track results.

**On start:**
- Create issue with title: "X Publisher Run [MM/DD] — post approved drafts"
- Team ID: 0def95e7-f504-41d6-ab96-8f5135e1024f (Meet Hank AI)
- Label: content-x (ID: bb9a329a-a6f4-453f-918f-c9b7c437c4c8)
- Move to In Progress state (ID: 511eabed-c5ec-4065-8980-f6e139985df2)

**On completion:**
- Add comment: "Published [N] drafts" + list each (draft title + URL) + errors
- Move to Done state (ID: 0465864a-e2c7-4410-84dd-b00d8f43a99a)

**API details:**
- Endpoint: https://api.linear.app/graphql
- Auth: Authorization: Bearer {LINEAR_API_KEY}
- Issue creation: issueCreate mutation
- State update: issueUpdate with stateId
- Comments: commentCreate mutation

This tracks all publisher runs in Linear for audit and history.

## Cron status

CRON IS DISABLED BY DEFAULT.

This skill registers a cron entry but it starts in disabled state. Jonathan
must explicitly enable it before automated polling runs. Until then, the
skill only runs when Jonathan invokes it manually in chat.

To enable cron after Jonathan confirms readiness:
hermes cron enable hank-x-publisher

To disable:
hermes cron disable hank-x-publisher

Cron schedule when enabled: every 15 minutes. */15 * * * *.

## Workflow per polling cycle

1. Query Airtable Drafts for records where:
   - Platform = "X"
   - Status = "Approved"
   - Posted At is empty (defensive check, prevents double-post)

   Use list_records with a filter formula like:
   AND({Platform}='X', {Status}='Approved', {Posted At}=BLANK())

   If 0 records found, log "No approved drafts in queue" and exit cycle.

2. For each approved record (process oldest first by Date Drafted):

   2a. Read the Body field. Determine if single post or thread:
       - If Body contains "---" on its own line, treat as thread
       - Otherwise treat as single post

   2b. Single post path:
       - Take the full Body text
       - Verify length under 280 chars (X hard limit)
       - If over, mark Post Error: "Body exceeds 280 chars" and skip
       - Sign and POST to X /2/tweets with text payload
       - Capture the response: tweet ID and URL

   2c. Thread path:
       - Split Body on lines that are exactly "---"
       - Each split is one tweet in the thread
       - Verify each tweet under 280 chars
       - Post first tweet, capture its ID
       - Post second tweet as reply to first (in_reply_to_tweet_id)
       - Continue chain for all tweets
       - Capture URL of FIRST tweet in thread (that's the canonical link)

   2d. After successful post:
       - Update Airtable record:
         * Posted At: current timestamp (ISO 8601)
         * Post URL: https://x.com/jonathan_sherm/status/{tweet_id}
         * Status: "Published"
         * Post Error: blank (clear any previous error)

   2e. If post FAILS (any error from X API):
       - Update Airtable record:
         * Post Error: full error message and code from X
         * Status: stays "Approved" (so Jonathan can retry after fixing)
         * Posted At: stays blank
       - Log error in chat (when run manually)
       - Move to next record, do NOT halt entire cycle

3. Rate limiting:
   - X allows 17 posts per 24 hours on free pay-per-use tier (verify
     against current X tier docs)
   - Wait 30 seconds between posts in same cycle
   - If you receive 429 rate limit response, abort cycle and try in 1 hour

4. Reply summary in chat (when run manually):
   - "Published [N] drafts. [N] errors."
   - List each: V1 of "[title]" → posted at [URL]
   - For errors: V2 of "[title]" failed: [error]

## Error handling rules

If X auth fails (401 or 403 with "not allowed" in message):
- Halt entire cycle immediately
- Telegram alert: "X auth failed. Check credentials in Railway env vars."
- Do not try to post anything else this cycle
- Mark every Approved record's Post Error: "Auth failure, see logs"
- Wait for Jonathan to fix before next cycle

If X rejects as duplicate content (403 with "duplicate content" in message):
- Mark THAT record with Post Error: "X rejected: duplicate content"
- Status stays Approved (so Jonathan can modify and retry)
- Continue to next record, do NOT halt cycle
- Log: "Record [ID] flagged as duplicate. User may need to modify text."
- This happens when the exact text was already posted (even in past sessions), or X's duplicate filter flagged it
- Common cause: draft was posted before, deleted from X UI, but Airtable record wasn't marked Published
- Resolution: Jonathan either modifies the text (5+ char change) and re-approves, or marks record Killed

If X rate limited (429):
- Halt cycle gracefully
- Mark records as still Approved (will retry)
- Wait until next polling cycle (or 1 hour, whichever later)

If Airtable read fails:
- Halt cycle
- Telegram alert: "Airtable read failed: [error]"

If individual post fails (validation error, bad body, etc):
- Mark THAT record with Post Error
- Continue to next record

## Manual invocation

When Jonathan says any of these in Telegram:
- "Run the X publisher"
- "Publish approved drafts"
- "Post the X queue"
- "Check the X queue"

You execute one full polling cycle (regardless of cron state) and report results.

When Jonathan says "show the X queue", just LIST what's in queue without
posting. Show:
- How many records have Status=Approved on Platform=X
- For each: V1 of "[title]" (X chars, character-counted)

## Defensive rules (never violate)

- Never post a record without Status=Approved
- Never post a record where Posted At is already filled
- Never post a draft you just generated in the same session (always go
  through Airtable, never skip the queue)
- Never delete or update a record's Body field. Only update Posted At,
  Post URL, Post Error, Status.
- Never post if env vars X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, or
  X_ACCESS_TOKEN_SECRET are missing. Telegram alert and abort.
- If a record has Platform=X but no Body content, mark Post Error: "Body
  empty" and skip.
- If you encounter the same record on two consecutive cycles with the same
  error, escalate: Telegram alert "Record [ID] failing repeatedly: [error]"
  and DO NOT keep retrying.

## Threading example

If a draft Body looks like:

watched a CSR field 47 calls in 4 hours yesterday at a 6-truck plumbing shop.
---
every call is a $30k decision in 90 seconds. half are repeats. third are tech questions she doesn't have answers for.
---
she's not a bottleneck. she's performing miracles. this is why $5M shops stay $5M.

That's a 3-tweet thread. Post sequence:
1. Post tweet 1, get tweet_id_1
2. Post tweet 2 with in_reply_to_tweet_id=tweet_id_1
3. Post tweet 3 with in_reply_to_tweet_id=tweet_id_2
4. Post URL recorded in Airtable: https://x.com/jonathan_sherm/status/{tweet_id_1}

## Account safety

Posts come from @jonathan_sherm. This is Jonathan's personal account. Wrong
posts damage his real reputation, not just Hank's brand. Treat that
accordingly:

- Always read the Body before signing the API call. If something feels off
  in tone, structure, or content, FLAG IT. Better to skip a post than ship
  damage. Mark Post Error: "Content review flag: [reason]" and Telegram
  alert.
- Never post anything that mentions: politics, religion, current
  geopolitical events, identity topics, recent tragedies, NSFW content.
  These should never be in approved drafts but defense in depth.
- Never post anything that quotes a real person without verification that
  they actually said it.

## Required Python tools (for execution)

This skill executes via the code_execution tool or terminal. OAuth library availability varies by environment.

**Preferred (if available):**
- airtable Python SDK (pyairtable) for queue read and update
- requests-oauthlib for OAuth 1.0a signing
- standard requests library for HTTP POST to X API

**Fallback (hand-rolled OAuth 1.0a HMAC-SHA1):**
If pyairtable or requests-oauthlib are not installed, use urllib + hmac:
- Construct OAuth params dict with oauth_consumer_key, oauth_token, oauth_signature_method, oauth_timestamp, oauth_nonce, oauth_version
- Build base string: METHOD & URL_encoded & params_encoded
- Create signing key: urlquote(api_secret) & urlquote(token_secret)
- Sign with HMAC-SHA1: base64(hmac.new(key, base_string, sha1))
- Add oauth_signature to params and build Authorization header

This is more error-prone than using a library, so validate thoroughly after implementing.

## What this skill does NOT do

- Does NOT draft new content
- Does NOT decide what's worth posting (Jonathan does that via Status=Approved)
- Does NOT respond to mentions, replies, DMs
- Does NOT analyze post performance (separate skill, hank-x-analytics, future)
- Does NOT delete posts (X posts are append-only here; deletion is a
  human-only action in the X UI)

## Resources

- Airtable Drafts: appx83XNovzpsHlKe / tblqAlGW06vjyQWF3
- X API docs: https://docs.x.com/x-api/posts/manage-posts
- OAuth 1.0a reference: requests-oauthlib library
- @jonathan_sherm is the target account
