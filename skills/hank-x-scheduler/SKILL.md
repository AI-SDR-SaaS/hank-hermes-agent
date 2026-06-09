---
name: hank-x-scheduler
description: |
  Schedules approved X drafts from the Airtable Drafts table to post in
  optimal engagement windows throughout the day. Sets the Scheduled For
  field on records, queueing them for the publisher to pick up at the
  right time. Goal: roughly 5 posts/day spaced across high-engagement
  windows, never bursting.

  Default windows for trades + founder X audience (Eastern Time): 8am,
  11am, 1pm, 4pm, 7pm. Adjustable. Skips weekends by default.

  Use this skill when the user says "schedule the queue", "spread out the
  posts", "schedule today's drafts", "queue the day", or similar
  scheduling commands. Also runs automatically via cron when enabled.

  Do not use for: drafting (use hank-x-drafter), publishing (use
  hank-x-publisher), or trend scanning (use hank-x-trend-watcher).

  IMPORTANT: This skill assigns post times to approved drafts. The
  publisher reads Scheduled For and posts when due. Cron is DISABLED by
  default.
---

# Hank X Scheduler

You assign optimal post times to approved X drafts. You do not post.
You do not draft. You queue.

## Operating principle

Trades + founder X audience peaks at predictable windows. Posting all 5
approved drafts at once = appearing spammy and burning audience attention.
Spreading them out = each post gets fair air time.

The 5 default windows (in user's local timezone, default Eastern):
- 8:00 AM (early morning, contractors checking phones before truck rolls)
- 11:00 AM (mid-morning break)
- 1:00 PM (lunch)
- 4:00 PM (end of day, post-job)
- 7:00 PM (evening, owner reflection time)

These are starting points. Adjust per Jonathan's pattern over time.

## Cron status

CRON IS DISABLED BY DEFAULT.

When ready, enable with:
hermes cron enable hank-x-scheduler

Schedule when enabled: once daily at 7:30 AM (30 min before first window).
30 7 * * 1-5 (weekdays only)

Disable with:
hermes cron disable hank-x-scheduler

## Configuration

Airtable:
- Base ID: appx83XNovzpsHlKe
- Drafts Table ID: tblqAlGW06vjyQWF3

Required field on Drafts table: "Scheduled For" (date with time enabled).
If this field doesn't exist yet, scheduler must alert and not run until
Jonathan adds it via update_field or manually.

## Workflow per scheduling cycle

1. Query Airtable Drafts for records where:
   - Platform = X
   - Status = Approved
   - Scheduled For is empty (not yet scheduled)
   - Posted At is empty (not yet posted)

   Filter formula:
   AND({Platform}='X', {Status}='Approved', {Scheduled For}=BLANK(),
   {Posted At}=BLANK())

2. Sort the queue by Date Drafted ascending (oldest first). FIFO scheduling.

3. Determine today's available slots:
   - Read current local time
   - Check the 5 default windows for today (8am, 11am, 1pm, 4pm, 7pm)
   - Skip windows already past current time + 30 min buffer
   - If today is Saturday or Sunday, skip entirely (return next weekday)

4. If any approved drafts have Scheduled For already set for today, count
   them as occupying slots. Don't double-book a window.

5. Assign each unscheduled draft (oldest first) to the next available
   window.

   - If 8am slot is open and current time < 7:30am: assign 8am
   - Then 11am, 1pm, 4pm, 7pm
   - If 5 slots fill and queue still has drafts, push to next weekday's
     8am, then 11am, etc.
   - Cap at 7 days forward. Anything beyond 7 days, leave Scheduled For
     blank and report "queue exceeds 7-day window, [N] drafts unscheduled."

6. Update each scheduled record:
   - Scheduled For: ISO timestamp for the assigned window in user's local
     timezone (e.g., 2026-04-28T13:00:00-04:00 for 1pm Eastern Daylight)
   - Status: stays Approved (publisher will flip to Published after posting)
   - Notes: append "Scheduled by hank-x-scheduler at [now]." (preserve
     existing Notes content)

7. Reply in Telegram (when manually invoked):
   - "Scheduled [N] drafts across [date range]:"
   - List each: V[N] of "[title]" → [day] [time]
   - Closer: "Publisher will post each at its scheduled time. Nothing
     posts before then."

## Window adjustment

User can override default windows in chat:
- "Change scheduling windows to 9am, noon, 3pm, 6pm" → updates internal
  windows for this and subsequent runs (persist via memory_save tool)
- "Schedule on weekends too" → flip weekend skip off
- "Only 3 posts a day" → use only first 3 windows

When user changes windows, confirm before applying:
"Updating windows to: [list]. Confirm? (yes/no)"
Save updated config to memory if confirmed.

## Conflict handling

If a draft already has Scheduled For set in the past (i.e., scheduled time
has passed but Posted At is still blank, meaning publisher missed it):
- This is the publisher's problem to handle, not scheduler's
- Leave the record alone, don't re-schedule
- Log in chat: "Note: [N] drafts have scheduled time in past. Publisher
  hasn't posted them. Investigate."

If a draft has Scheduled For set in the future and a new scheduler run
happens, leave it alone. Already scheduled = already handled.

## Manual invocation

When Jonathan says:
- "Schedule the queue"
- "Schedule today's drafts"
- "Queue the day"
- "Spread out the posts"

Execute one full cycle and report.

When he says "show schedule" or "what's queued":
LIST without rescheduling. Format:
- Today: 1pm V1 of "[title]", 4pm V2 of "[title]"
- Tomorrow: 8am V3 of "[title]"
- Wednesday: 11am V1 of "[title]"

## Defensive rules

- Never schedule a draft that's not Status=Approved
- Never post (this skill schedules; publisher posts)
- Never schedule for past times (always at least 30 min in future)
- Never schedule on weekends unless explicitly enabled
- Never schedule more than 5 in one day at default config
- Never overwrite an existing Scheduled For without flagging
- If Drafts table is missing the Scheduled For field, halt and alert.
  Do not silently fail.

## What this skill does NOT do

- Does NOT post (publisher does that, reads Scheduled For)
- Does NOT draft (drafter does that)
- Does NOT find trending content (trend-watcher does that)
- Does NOT analyze performance to optimize windows. That's a future skill.
  For now, windows are static based on best-practice trades + founder
  audience times.

## Future tuning notes

When you have 30+ days of post performance data:
- Pull engagement data per window from X analytics
- Identify which windows over-perform vs under-perform
- Suggest window adjustments to Jonathan ("Wed 7pm posts get 2x engagement
  vs Mon 7pm, recommend doubling Wed 7pm slot.")

For now: assume defaults work, iterate based on Jonathan's gut.

## Resources

- Airtable Drafts: appx83XNovzpsHlKe / tblqAlGW06vjyQWF3
- Required new field: Scheduled For (date with time)
- hank-x-publisher reads Scheduled For to know when to post
- AGENTS.md and hank-x-drafter for voice (not relevant to scheduler logic
  but referenced for completeness)
