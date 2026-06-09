#!/usr/bin/env python3
"""
Blog Post Auto-Publisher for Hank AI
Publishes approved posts from Airtable to meethank.ai/api/blog/posts
Schedule: Tuesday and Thursday 8:00 AM ET
Uses only stdlib (urllib, json, etc.).
"""

import os
import json
import sys
import re
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Configuration
AIRTABLE_BASE_ID = "appx83XNovzpsHlKe"
AIRTABLE_TABLE_ID = "tblPpkyoAP5dROgh8"
BLOG_API_URL = "https://meethank.ai/api/blog/posts"

ALLOWED_CTA_HREFS = [
    r"^/$",
    r"^/how-it-works$",
    r"^/pricing$",
    r"^/pricing#plans$",
    r"^/contact$",
    r"^/blog$",
    r"^/industries/.*",
    r"^/integrations/.*",
    r"^/vs/.*",
    r"^/best-ai-receptionist-for-hvac$",
    r"^/privacy$",
    r"^/terms$",
]

ALLOWED_MDX_COMPONENTS = {"Cta", "CtaPair", "Callout", "KeyStat", "Quote", "PricingTeaser"}


def http_request(
    method: str, url: str, headers: Dict[str, str], data: Optional[bytes] = None
) -> Tuple[int, str]:
    """Execute HTTP request. Returns (status_code, response_body)."""
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        raise Exception(f"HTTP request failed: {e}")


def slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def validate_slug(slug: str) -> bool:
    """Check slug matches regex ^[a-z0-9]+(?:-[a-z0-9]+)*$"""
    return bool(re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug))


def has_header_violations(content: str) -> bool:
    """Check if content has #, ##, or ### markdown headers."""
    return bool(re.search(r"^#{1,3}\s", content, re.MULTILINE))


def check_invalid_mdx_components(content: str) -> List[str]:
    """Extract MDX components and check if any are invalid."""
    components = re.findall(r"<([A-Z][a-zA-Z0-9]*)", content)
    components = list(set(components))
    invalid = [c for c in components if c not in ALLOWED_MDX_COMPONENTS]
    return invalid


def validate_cta_href(href: str) -> bool:
    """Check if href matches allowed patterns."""
    return any(re.match(pattern, href) for pattern in ALLOWED_CTA_HREFS)


def check_invalid_cta_hrefs(content: str) -> List[str]:
    """Extract all CTA hrefs and identify invalid ones."""
    hrefs = re.findall(r'<Cta[^>]*href="([^"]*)"', content)
    hrefs += re.findall(r'<CtaPair[^>]*href="([^"]*)"', content)
    hrefs = list(set(hrefs))
    invalid = [h for h in hrefs if not validate_cta_href(h)]
    return invalid


def has_markdown_table(content: str) -> bool:
    """Detect GFM markdown table syntax. Site MDX does not enable remark-gfm, so
    pipe-row syntax renders as raw text in a paragraph (not a styled table)."""
    lines = content.split("\n")
    for i, line in enumerate(lines[:-1]):
        if re.match(r"^\s*\|.*\|\s*$", line) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i + 1]):
            return True
    return False


def check_required_components(content: str) -> List[str]:
    """Reject posts that visibly lack the structural components every Hank blog post uses.

    Backstops the drafter skill: even if the LLM forgets to include a Callout or a closing
    CtaPair, the publisher refuses to ship the post with a clear error message.
    """
    errors: List[str] = []

    callouts = len(re.findall(r"<Callout\b", content))
    if callouts == 0:
        errors.append(
            "Body has no <Callout> block. Every post must open with "
            "<Callout title=\"Key takeaways\">...</Callout> right after the lede."
        )

    if not re.search(r"<Cta\b|<CtaPair\b", content):
        errors.append(
            "Body has no closing <Cta> or <CtaPair>. Every post must end with one of these "
            "components, never a plain paragraph."
        )

    mid_body = len(re.findall(r"<KeyStat\b|<Quote\b|<PricingTeaser\b", content))
    if callouts < 2 and mid_body == 0:
        errors.append(
            "Body has no mid-body component (<KeyStat>, <Quote>, <PricingTeaser>, or a "
            "second <Callout>). Add at least one to break up text walls."
        )

    return errors


def validate_post(record: Dict) -> Optional[List[str]]:
    """Validate a post record. Return list of errors, or None if valid."""
    errors = []

    # Extract fields
    name = record.get("fields", {}).get("Name", "").strip()
    body = record.get("fields", {}).get("Body", "").strip()

    if not name:
        errors.append("Missing Name")
    if not body:
        errors.append("Missing Body")

    if not name or not body:
        return errors

    # Validate slug
    slug = slugify(name)
    if not validate_slug(slug):
        errors.append(f"Invalid slug format: '{slug}'")

    # Check for header violations
    if has_header_violations(body):
        errors.append("Body contains markdown headers (#, ##, or ###)")

    # Check for markdown tables (site MDX doesn't render them)
    if has_markdown_table(body):
        errors.append("Body contains markdown table syntax (| col |) — site MDX renders pipes as raw text. Use a bullet list instead.")

    # Check for required structural components
    errors.extend(check_required_components(body))

    # Check MDX components
    invalid_components = check_invalid_mdx_components(body)
    if invalid_components:
        errors.append(f"Invalid MDX components: {', '.join(invalid_components)}")

    # Check CTA hrefs
    invalid_hrefs = check_invalid_cta_hrefs(body)
    if invalid_hrefs:
        errors.append(f"Invalid CTA hrefs: {', '.join(invalid_hrefs)}")

    return errors if errors else None


def escape_mdx_unsafe(body: str) -> str:
    """Escape '<' followed by a digit (MDX would otherwise try to parse '<5' as a JSX tag)."""
    return re.sub(r"<(?=\d)", r"\\<", body)


def strip_title_meta_block(name: str, body: str) -> str:
    """Remove a duplicated title line and **Author**/**Expertise**/**Last Updated** meta from the top of the body."""
    lines = body.split("\n")
    title_re = re.compile(r"^\s*#{0,3}\s*" + re.escape(name) + r"\s*$", re.IGNORECASE)
    meta_re = re.compile(r"^\s*\*\*(?:Author|Expertise|Last Updated)\b", re.IGNORECASE)
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or title_re.match(line) or meta_re.match(line):
            i += 1
            continue
        break
    rest = lines[i:]
    while rest and not rest[0].strip():
        rest.pop(0)
    return "\n".join(rest)


def extract_description(body: str, max_len: int = 180) -> str:
    """First prose paragraph (markdown stripped), word-boundary truncated.

    Skips heading-only paragraphs and bullet/numbered lists. Recognizes
    **Bold Heading** style pseudo-headings the way ATX headings are skipped.
    """

    bold_heading_re = re.compile(r"^\s*\*\*[^*]+\*\*\s*$")
    bullet_re = re.compile(r"^\s*(?:[-*]|\d+\.)\s")

    def _strip_md(t: str) -> str:
        t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
        t = re.sub(r"\*([^*]+)\*", r"\1", t)
        return re.sub(r"\s+", " ", t).strip()

    prose_text = None
    list_text = None

    for para in body.split("\n\n"):
        if para.lstrip().startswith("#"):
            continue
        lines = [ln for ln in para.split("\n") if ln.strip()]
        while lines and bold_heading_re.match(lines[0]):
            lines.pop(0)
        if not lines:
            continue
        text = _strip_md("\n".join(lines))
        if not text:
            continue
        if all(bullet_re.match(ln) for ln in lines):
            if list_text is None:
                list_text = text
        else:
            prose_text = text
            break

    text = prose_text or list_text or body[:max_len]
    if len(text) <= max_len:
        return text
    cut = text.rfind(" ", 0, max_len - 1)
    if cut == -1:
        cut = max_len - 1
    return text[:cut].rstrip(",;:.!? -") + "\u2026"


def build_post_object(record: Dict) -> Dict:
    """Build post object for API."""
    fields = record.get("fields", {})
    name = fields.get("Name", "").strip()
    body = fields.get("Body", "").strip()
    description = fields.get("Description", "").strip()

    body = strip_title_meta_block(name, body)
    body = escape_mdx_unsafe(body)

    if not description:
        description = extract_description(body)

    slug = slugify(name)
    today = datetime.now().strftime("%Y-%m-%d")

    return {
        "slug": slug,
        "frontmatter": {
            "title": name,
            "description": description,
            "date": today,
            "author": "Jonathan S",
            "pillar": fields.get("pillar", ""),
            "format": fields.get("format", ""),
            "keyword": fields.get("keyword", ""),
            "draft": False,
            "tags": [],
            "image": None,
        },
        "content": body,
    }


def query_airtable(limit: int = 25) -> List[Dict]:
    """Query Airtable for approved posts."""
    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise Exception("AIRTABLE_API_KEY not set")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"

    params = {
        "filterByFormula": "{Status} = 'Approved'",
        "maxRecords": str(limit),
    }

    query_str = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_str}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    status, body = http_request("GET", full_url, headers)

    if status != 200:
        raise Exception(f"Airtable query failed: {status} {body[:200]}")

    try:
        data = json.loads(body)
        return data.get("records", [])
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Airtable response: {e}")


def publish_posts(
    posts: List[Dict], dry_run: bool = False
) -> Optional[Dict]:
    """POST posts to blog API. Returns response data or None on failure."""
    if dry_run:
        print("[DRY-RUN] Would POST to blog API")
        return {
            "prUrl": "https://github.com/example/meethank/pull/123",
            "branch": f"blog/{datetime.now().strftime('%Y%m%d')}",
            "files": ["content/blog/sample-post.mdx"],
        }

    blog_api_key = os.getenv("BLOG_API_KEY")
    if not blog_api_key:
        raise Exception("BLOG_API_KEY not set")

    today = datetime.now().strftime("%Y%m%d")

    payload = {
        "posts": posts,
        "branchSuffix": today,
    }

    headers = {
        "Authorization": f"Bearer {blog_api_key}",
        "Content-Type": "application/json",
    }

    payload_json = json.dumps(payload).encode("utf-8")

    status, body = http_request("POST", BLOG_API_URL, headers, payload_json)

    if status != 200:
        raise Exception(f"Blog API returned {status}: {body[:500]}")

    try:
        result = json.loads(body)
        print(f"\n[API RESPONSE]\n{json.dumps(result, indent=2)}\n")
        return result
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse blog API response: {e}")


def update_airtable_status(record_id: str, dry_run: bool = False) -> None:
    """Update record status to Published."""
    if dry_run:
        print(f"[DRY-RUN] Would update Airtable record {record_id} to Published")
        return

    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise Exception("AIRTABLE_API_KEY not set")

    today = datetime.now().strftime("%Y-%m-%d")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}/{record_id}"

    payload = {
        "fields": {
            "Status": "Published",
        }
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload_json = json.dumps(payload).encode("utf-8")

    status, body = http_request("PATCH", url, headers, payload_json)

    if status != 200:
        raise Exception(f"Airtable update failed: {status} {body[:200]}")


def send_telegram(message: str) -> None:
    """Send message to Telegram. Bot token must be set in Railway env."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise Exception(
            "TELEGRAM_BOT_TOKEN not set in Railway environment. "
            "Add it to the blog-publisher service environment variables."
        )
    
    if not chat_id:
        raise Exception(
            "TELEGRAM_CHAT_ID not set. "
            "Add TELEGRAM_CHAT_ID to the blog-publisher environment."
        )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    payload_json = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    status, body = http_request("POST", url, headers, payload_json)

    if status != 200:
        raise Exception(f"Telegram API failed: {status} {body[:200]}")


def send_telegram_safe(message: str) -> None:
    """Send Telegram message, but fail gracefully if tokens aren't set."""
    try:
        send_telegram(message)
    except Exception as e:
        if "not set" in str(e):
            print(f"[WARN] {e}")
            raise  # Re-raise so cron exits 1
        else:
            raise  # Network/API errors should still fail


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Publish approved blog posts from Airtable to meethank.ai"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without making changes"
    )
    parser.add_argument(
        "--limit", type=int, default=25, help="Maximum posts per run (default: 25)"
    )

    args = parser.parse_args()

    try:
        print(f"[{datetime.now().isoformat()}] Starting blog publisher (dry_run={args.dry_run})")

        # Query Airtable
        records = query_airtable(limit=args.limit)
        print(f"Found {len(records)} approved posts")

        if not records:
            send_telegram_safe("No approved posts to publish today.")
            sys.exit(0)

        # Validate and filter
        validated_posts: List[Tuple[Dict, Dict]] = []
        failed_posts: List[Tuple[str, List[str]]] = []

        for record in records:
            errors = validate_post(record)
            if errors:
                name = record.get("fields", {}).get("Name", "Unknown")
                failed_posts.append((name, errors))
                print(f"✗ {name}: {', '.join(errors)}")
                continue

            validated_posts.append((record, build_post_object(record)))
            print(f"✓ {record.get('fields', {}).get('Name', 'Unknown')}")

        # If all failed, report and exit
        if not validated_posts:
            msg = "⚠️ All posts failed validation:\n\n"
            for name, errors in failed_posts:
                msg += f"<b>{name}</b>\n"
                for err in errors:
                    msg += f"• {err}\n"
            send_telegram_safe(msg)
            print("[FAILED] All posts failed validation")
            sys.exit(1)

        # Notify of skipped posts if any
        if failed_posts:
            msg = "⚠️ Skipped posts due to validation errors:\n\n"
            for name, errors in failed_posts:
                msg += f"<b>{name}</b>\n"
                for err in errors:
                    msg += f"• {err}\n"
            send_telegram_safe(msg)

        # Build posts list for API
        posts_for_api = [post for _, post in validated_posts]

        print(f"\nPublishing {len(posts_for_api)} valid posts...")

        # Publish
        result = publish_posts(posts_for_api, dry_run=args.dry_run)

        # Update Airtable
        for record, _ in validated_posts:
            update_airtable_status(record["id"], dry_run=args.dry_run)

        # Send success Telegram
        files_str = "\n".join(
            f"  • {f}" for f in result.get("files", [])
        )
        msg = f"""📝 Blog publish run — {len(validated_posts)} posts shipped

PR: {result.get('prUrl')}
Branch: {result.get('branch')}
Files:
{files_str}

Vercel will deploy a preview in ~60s. Review and merge when ready."""

        send_telegram_safe(msg)

        status = "[DRY-RUN OK]" if args.dry_run else "[SUCCESS]"
        print(f"{status} Published {len(validated_posts)} posts")
        sys.exit(0)

    except Exception as e:
        error_msg = f"❌ Publish failed: {str(e)}"
        try:
            send_telegram_safe(error_msg)
        except:
            pass  # If Telegram also fails, just log to stderr
        print(f"[ERROR] {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
