---
name: airtable-schema-creation
description: Create and configure Airtable table schemas (fields, select options) via MCP tools. Handle typed fields, select options, and server resilience.
version: 1.1.0
author: Ace
license: MIT
prerequisites:
  env_vars: []
  commands: []
metadata:
  hermes:
    tags: [Airtable, Schema, MCP, Database]
---

# Airtable Schema Creation via MCP Tools

Create and configure Airtable table schemas programmatically using MCP field tools. This skill covers field creation with proper type handling, select option configuration, and recovery from partial failures.

## When to Use

- Creating multiple fields in an Airtable table with specific types and select options.
- Configuring single-select or multi-select fields with predefined choice lists.
- Building a structured table schema from scratch or enhancing an existing table.
- Troubleshooting server errors during schema mutations and recovering from partial failures.

## Prerequisites

- Access to Airtable via MCP tools (tools like `mcp_airtable_create_field` must be available).
- Base ID (`app...`) and Table ID (`tbl...`) identified before starting.
- User must have create permissions on the base.

## Workflow

### 1. Identify base and table IDs

```bash
# List bases
mcp_airtable_list_bases()

# List tables in a base
mcp_airtable_list_tables(baseId=..., detailLevel="tableIdentifiersOnly")
```

Both return IDs needed for field creation.

### 2. Create fields with correct nested structure

All field creation uses `mcp_airtable_create_field` with a `nested` parameter containing the field definition.

**Single line text (primary):**
```json
{
  "nested": {
    "field": {
      "isPrimary": true,
      "name": "Title",
      "type": "singleLineText"
    }
  }
}
```

**Long text:**
```json
{
  "nested": {
    "field": {
      "name": "Notes",
      "type": "multilineText"
    }
  }
}
```

**URL field:**
```json
{
  "nested": {
    "field": {
      "name": "Post URL",
      "type": "url"
    }
  }
}
```

**Single select with options:**
```json
{
  "nested": {
    "field": {
      "name": "Status",
      "type": "singleSelect",
      "options": {
        "choices": [
          {"name": "Draft"},
          {"name": "Approved"},
          {"name": "Published"},
          {"name": "Killed"}
        ]
      }
    }
  }
}
```

**Number field (integer):**
```json
{
  "nested": {
    "field": {
      "name": "Audience Size",
      "type": "number",
      "options": {"precision": 0}
    }
  }
}
```

Note: Number fields REQUIRE `precision` in options. Precision 0 = integers, 1+ = decimal places.

**Date field:**
```json
{
  "nested": {
    "field": {
      "name": "Date Drafted",
      "type": "date",
      "options": {"dateFormat": {"name": "local"}}
    }
  }
}
```

Note: Date fields REQUIRE `dateFormat` in options with a dateFormat object. Use `{"name": "local"}` for locale-based formatting.

**DateTime field (date + time):**
```json
{
  "nested": {
    "field": {
      "name": "Posted At",
      "type": "dateTime",
      "options": {
        "dateFormat": {"format": "l", "name": "local"},
        "timeFormat": {"format": "HH:mm", "name": "24hour"},
        "timeZone": "utc"
      }
    }
  }
}
```

Note: DateTime fields REQUIRE all three options keys: `dateFormat`, `timeFormat`, and `timeZone`. For dateFormat, include BOTH `format` and `name` keys. For timeFormat, include `name` ONLY (no `format` key; Airtable rejects it). Use `{"name": "24hour"}` for 24-hour time or `{"name": "12hour"}` for 12-hour. Common timeZones: `"utc"`, `"America/New_York"`, `"America/Los_Angeles"`. Match your backend timezone.

**Multiple-select field:**
```json
{
  "nested": {
    "field": {
      "name": "Trade Focus",
      "type": "multipleSelects",
      "options": {
        "choices": [
          {"name": "Roofing"},
          {"name": "HVAC"},
          {"name": "Plumbing"}
        ]
      }
    }
  }
}
```

Note: The correct field type is `multipleSelects` (plural with 's'), not `multipleSelect`. Structure mirrors single-select.

**Checkbox field:**
```json
{
  "nested": {
    "field": {
      "name": "Pushed To Smartlead",
      "type": "checkbox",
      "options": {
        "color": "greenLight2",
        "icon": "check"
      }
    }
  }
}
```

Note: Checkbox fields REQUIRE both `color` and `icon` in options. Color validation is strict; valid Airtable colors like `redLight2`, `yellowLight2`, `greenLight2`, `blueLight2`, `grayLight2` work here. Not all standard Airtable colors are accepted (e.g., `redLight1`, `greenLight1` will fail). Always use a `Light2` variant or test the exact color name.

**Percent field:**
```json
{
  "nested": {
    "field": {
      "name": "Reply Rate",
      "type": "percent",
      "options": {"precision": 1}
    }
  }
}
```

Note: Percent fields REQUIRE `precision` in options. Precision 0 = whole percent (25%), 1+ = decimal places (25.5%).

### 3. Batch strategically; use pacing for high-volume

For 5-10 fields, parallel batch calls work. For 10+ fields, especially with complex select options, introduce 2-second pacing to avoid rate limiting:

```bash
# Small batch (OK to parallelize)
mcp_airtable_create_field(..., nested={field: {...}})  # parallel 1
mcp_airtable_create_field(..., nested={field: {...}})  # parallel 2

# Wait 2 seconds
sleep 2

# Next batch
mcp_airtable_create_field(..., nested={field: {...}})  # parallel 3
mcp_airtable_create_field(..., nested={field: {...}})  # parallel 4
```

Or, for 13+ fields with complex options (multi-select, single-select), pace individually:

```bash
mcp_airtable_create_field(...) → success
sleep 2
mcp_airtable_create_field(...) → success
sleep 2
mcp_airtable_create_field(...) → success
```

Pacing reduces transient `INVALID_REQUEST_UNKNOWN` errors and MCP server timeouts. If one fails and others succeed, retry only the failed ones after 30+ seconds.

### 3.5 Update Existing Field Select Options (without API schema endpoint)

In MCP-only environments (no curl/terminal), you cannot PATCH field select options directly via the metadata endpoint. Workaround: use `mcp_airtable_update_records` with `typecast: true` to force Airtable to auto-create missing select options on write.

**Pattern (recommended: use temp records):**
```bash
# 1. List existing records to confirm at least one exists
mcp_airtable_list_records(baseId, tableId, maxRecords=1)

# If no records exist, create a temporary one:
mcp_airtable_create_record(baseId, tableId, fields={"Name": "temp"})

# 2. For each new select option, create a temp record with that value
mcp_airtable_create_record(baseId, tableId, fields={"Status": "Draft"})
mcp_airtable_create_record(baseId, tableId, fields={"Status": "Approved"})
mcp_airtable_create_record(baseId, tableId, fields={"Status": "Sent"})

# 3. Verify the schema now includes the new options
mcp_airtable_describe_table(baseId, tableId, detailLevel="full")
# Inspect field's options.choices to confirm new options are present

# 4. Delete the temp records (optional, but cleans up the table)
mcp_airtable_delete_records(baseId, tableId, recordIds=["rec...", "rec...", "rec..."])
```

**Why temp records?** Creating separate records ensures each new option value is written atomically. Attempting multiple updates to a single record fails (Airtable rejects duplicate record IDs in one request). Temp records are the safest pattern.

**Limitations:**
- Airtable assigns colors automatically (you don't choose them).
- Works for single-select and multi-select fields.
- Use this only when schema endpoints are unavailable; prefer explicit field creation/patching when curl access exists.
- Do NOT update the same record ID multiple times in a single `mcp_airtable_update_records` call. Create separate records for each option instead.

**Verification:**
After creation, describe the table:
```bash
mcp_airtable_describe_table(baseId, tableId, detailLevel="full")
```
Inspect the field's `options.choices` to confirm new options and their auto-assigned IDs.

### 4. Handle server resilience

**Transient errors:** `INVALID_REQUEST_UNKNOWN` or `Unprocessable Entity` followed by server timeout typically indicate temporary issues. Wait 30-60 seconds and retry.

**Persistent errors:**
- `DUPLICATE_OR_EMPTY_FIELD_NAME` — field with that name already exists. Either update it or choose a new name.
- `INVALID_MULTIPLE_CHOICE_OPTIONS` — select option doesn't exist or is malformed. Verify option names match exactly (case-sensitive).
- `INVALID_FIELD_TYPE_OPTIONS_FOR_CREATE` — field type missing required options object. Date fields must have `"options": {}`, DateTime must have all three keys (dateFormat, timeFormat, timeZone).

**MCP server unreachable:** After 3 consecutive failures, the MCP tool returns "unreachable after 3 consecutive failures. Auto-retry available in ~Xs." Do NOT retry immediately. Wait at least the suggested duration before retrying.

### 5. Verify and audit

After creation, list fields to confirm:

```bash
mcp_airtable_list_tables(baseId=..., detailLevel="full")
```

Response includes field objects with all configuration applied. Confirm:
- All field names match request.
- Select options have correct choice names and auto-assigned IDs.
- Date/DateTime fields are marked with correct type.
- Primary field has expected type.

## Examples

### Creating a marketing content drafts table schema

Objective: 9 fields (Title primary, Variant select, Pillar select, Platform select, Body text, CTA text, Status select, Date Drafted, Notes).

```bash
# Create fields in parallel
mcp_airtable_create_field(baseId, tableId, nested={field: {isPrimary: true, name: "Title", type: "singleLineText"}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Variant", type: "singleSelect", options: {choices: [{name: "V1"}, {name: "V2"}, {name: "V3"}]}}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Pillar", type: "singleSelect", options: {choices: [{name: "ANSWER"}, {name: "BOOK"}, {name: "QUALIFY"}, {name: "FOLLOW UP"}, {name: "MONITOR"}]}}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Platform", type: "singleSelect", options: {choices: [{name: "LinkedIn"}, {name: "Reels"}, {name: "TikTok"}, {name: "Blog"}, {name: "Meta Ad"}, {name: "Email"}, {name: "Other"}]}}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Body", type: "multilineText"}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "CTA", type: "singleLineText"}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Status", type: "singleSelect", options: {choices: [{name: "Draft"}, {name: "Approved"}, {name: "Published"}, {name: "Killed"}]}}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Date Drafted", type: "date", options: {}}})
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Notes", type: "multilineText"}})
```

If some fail and others succeed, retry only the failed ones after 30+ seconds.

### Creating three fields with pacing (small batch)

Objective: Add Posted At (dateTime), Post URL (url), and Post Error (multilineText) to an existing table.

```bash
# First field
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Posted At", type: "dateTime", options: {dateFormat: {format: "l", name: "local"}, timeFormat: {format: "HH:mm", name: "24hour"}, timeZone: "utc"}}})

# Wait 10 seconds
sleep 10

# Second field
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Post URL", type: "url"}})

# Wait 10 seconds
sleep 10

# Third field
mcp_airtable_create_field(baseId, tableId, nested={field: {name: "Post Error", type: "multilineText"}})
```

If rate limit is hit (MCP server unreachable), wait 60 seconds and retry failed fields individually at 10-second intervals.

## Pitfalls

- **Missing required options on typed fields.** Number fields MUST have `"options": {"precision": 0}`. Date fields MUST have `"options": {"dateFormat": {"format": "l", "name": "local"}}` (both keys required). DateTime fields MUST have all three: `dateFormat` (with both format AND name), `timeFormat` (name only, no format key), `timeZone`. Without these, `INVALID_FIELD_TYPE_OPTIONS_FOR_CREATE` error. Empty `{}` is NOT sufficient.
- **DateTime requires all three option keys AND correct key structure.** If `dateTime` is missing any of `dateFormat`, `timeFormat`, or `timeZone`, the API rejects it. Additionally, do NOT include `format` key in `timeFormat`; only include `name`. Airtable rejects `timeFormat: {"format": "HH:mm", "name": "24hour"}` — use `timeFormat: {"name": "24hour"}` instead. The `dateFormat` object MUST have both `format` and `name` keys, but `timeFormat` must have `name` only.
- **Incorrect multi-select type name.** Use `multipleSelects` (plural 's'), not `multipleSelect`. Single-select and multi-select share the same options structure `{choices: [{name: "..."}, ...]}`.
- **Select option structure.** Single-select and multi-select require `"options": {"choices": [{"name": "..."}, ...]}`, NOT `"options": [...]`. The wrapper object `{choices: [...]}` is mandatory.
- **Duplicate field names.** If a field with the same name already exists, the API returns `DUPLICATE_OR_EMPTY_FIELD_NAME`. Check the table schema first or use a unique name.
- **Case-sensitive option names.** Airtable select options are case-sensitive. `"Todo"` and `"todo"` are different. Match exactly in writes and reads.
- **Rate limiting on batch ops.** For 10+ fields, especially with multi-select/single-select options, introduce 2-second pacing between groups of calls. Parallel requests without pacing trigger `INVALID_REQUEST_UNKNOWN` and MCP server timeouts. Pace individually for 13+ fields or when hitting rate limits.
- **Server flakiness recovery.** After 3 failures, MCP returns "unreachable... Auto-retry available in ~Xs." Do NOT retry immediately. Wait at least the FULL duration suggested by the error message (usually 50-60 seconds), then retry only the failed mutations at slower intervals (10s between calls). Retrying before the auto-recovery window closes will fail again.
- **Primary field must be unique.** Only one field can have `isPrimary: true`. If the table already has a primary, either update it (not covered here) or omit `isPrimary`.
- **URL fields have no options.** URL field type requires no `options` object, unlike number/date/dateTime. Pass the type and name only.
- **Typecast auto-creates select options.** When updating records with `mcp_airtable_update_records` and the field value doesn't exist in the select choices, Airtable auto-creates it (in MCP-only environments where schema PATCH is unavailable). This is a workaround, not the primary method. Airtable assigns colors automatically; you cannot control them. Always verify the options after updates with `describe_table`.
- **Checkbox and percent field schema requirements.** Checkbox REQUIRES both `color` (e.g., `greenLight2`) and `icon` (e.g., `check`) in options. Percent REQUIRES `precision` (integer, 0 or higher). Without these, `INVALID_FIELD_TYPE_OPTIONS_FOR_CREATE` error. Test checkbox color names; not all Airtable color names are valid in checkbox context (e.g., `greenLight1` fails, but `greenLight2` works).
- **Cannot update the same record multiple times in one request.** When auto-creating select options via `mcp_airtable_update_records`, use separate record IDs for each option. Do not reuse the same record ID; Airtable rejects it as a duplicate.

## Related Skills

- `airtable` (REST API via curl) — for record CRUD, filtering, pagination. Schema operations are separate.
- `airtable-records` (MCP browsing) — generic Airtable guidance. Does not document MCP schema tools.

## Resources

- Airtable API — https://airtable.com/developers/web/api/introduction
- Web API Reference — https://airtable.com/developers/web/api/api-reference
- Airtable MCP Tool Docs — tool documentation for `mcp_airtable_create_field` and related schema tools.
