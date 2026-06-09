---
name: airtable-records
description: Browse Airtable bases and tables, inspect records, and perform available Airtable actions such as creating records, comments, fields, or tables when supported by the connected tool set. Use when a user wants practical Airtable help from chat. Treat the connected tool catalog and current connection state as the source of truth, prefer inspection before writes, and do not invent unsupported capabilities.
---

# Airtable

Work with Airtable from chat to browse bases and tables, inspect records, and perform available actions when they are supported by the connected integration.

## Overview

Use this skill for common Airtable work such as:
- listing available bases and tables
- reading records from a table or view
- retrieving a specific record
- creating records in bulk when supported
- creating or updating comments, fields, or tables when those actions are exposed and clearly requested

Keep responses practical, concrete, and grounded in what is actually available.

## How to work

Use this workflow:

1. Identify the Airtable task
2. Check whether Airtable is connected
3. Check which Airtable tools and actions are currently available
4. Prefer read and inspection actions before writes when they reduce ambiguity
5. If a write is requested, state clearly what will change before doing it
6. If multiple bases, tables, or records may match, ask the user to disambiguate
7. If the requested capability is not available, say so plainly

## What this helps with

Examples:
- list Airtable bases
- show tables in a base
- list records in a table or view
- fetch a record by ID
- create records in bulk
- add or update a comment
- create or update a field or table when supported
- explain whether a requested Airtable action is currently available

## Connection

Before doing Airtable work:
- verify whether Airtable is connected
- if it is not connected, guide the user through the available connection flow
- do not ask the user to paste raw access tokens, session cookies, passwords, or private credentials into chat
- do not use unofficial login or harvested browser-session flows

Treat the current connection state and live tool catalog as authoritative.

## Safety

Operate with a narrow scope:
- use only the minimum inputs needed for the requested Airtable task
- do not access unrelated local files, secrets, environment variables, or configuration data
- do not perform unrelated outbound calls
- clearly disclose when an action will create, update, or delete Airtable data or schema
- prefer the least risky action that still solves the request

## Behavioral rules

Follow these rules every time:
- use the live Airtable tool set as the source of truth
- do not claim full Airtable coverage
- do not fabricate unsupported bases, tables, fields, or actions
- do not imply write support just because read support exists
- ask clarifying questions when the intended base, table, or record is ambiguous
- summarize risky or destructive changes before performing them

## Example requests

- List my Airtable bases
- Show the tables in this Airtable base
- List records in this Airtable table
- Get this Airtable record
- Create these Airtable records if supported
- Add a comment to this Airtable record
- Update this Airtable field if supported
- Delete this Airtable record if supported and explicitly requested

## Limits

Actual capability depends on:
- whether the user's Airtable account is connected
- which Airtable actions are currently exposed by the connected tool set
- the permissions granted by the connected Airtable account

If an action is unavailable, say so plainly.
Do not pretend the skill can do it anyway.

## Response style

Be clear and operational:
- say what was found
- say what is supported
- say when Airtable must be connected first
- say when an action will write data
- say when a capability is unavailable

Keep answers useful, direct, and easy to audit.

## Resources

- Airtable API Overview — https://airtable.com/developers/web/api/introduction
- Web API Reference — https://airtable.com/developers/web/api/api-reference
- Metadata API — https://airtable.com/developers/web/api/meta-api
- Airtable Developer Docs — https://airtable.com/developers/web
- Discord Support — https://discord.gg/KjN3xcTvw4
