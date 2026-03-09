"""
poster.py — Content Ops Automation Script
==========================================
Reads content.csv, filters rows scheduled for today with status='pending',
posts to LinkedIn and/or Instagram, and updates the CSV status accordingly.

Usage:
    python poster.py              # normal run (posts to APIs, or mock if no tokens)
    python poster.py --dry-run    # log what WOULD be posted, skip all logic
"""

import csv
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────
CSV_PATH = Path(__file__).parent / "content.csv"
FIELDNAMES = [
    "scheduled_date",
    "platform",
    "post_type",
    "text_content",
    "image_urls",
    "status",
    "posted_at",
    "error_log",
]

# GitHub repo info for building raw image URLs
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

# ── API Credentials (from GitHub Secrets / env vars) ────────────────────────
LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")

DRY_RUN = "--dry-run" in sys.argv

# ── Lazy import: only load requests when we actually need it ────────────────
_requests = None


def _get_requests():
    """Lazy-import requests only when real API calls are needed."""
    global _requests
    if _requests is None:
        import requests as _req  # noqa: F811
        _requests = _req
    return _requests


# ═══════════════════════════════════════════════════════════════════════════
#  CSV HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def read_csv() -> list[dict]:
    """Read the content CSV and return a list of row dicts."""
    with open(CSV_PATH, mode="r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def write_csv(rows: list[dict]) -> None:
    """Overwrite the content CSV with the (potentially updated) rows."""
    with open(CSV_PATH, mode="w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def get_today_str() -> str:
    """Return today's date as YYYY-MM-DD in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_image_url(relative_path: str) -> str:
    """Convert a repo-relative image path to a GitHub raw URL."""
    if not relative_path:
        return ""
    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_REPO}/{GITHUB_BRANCH}/{relative_path.strip()}"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  MOCK HELPERS — used when API tokens are not configured
# ═══════════════════════════════════════════════════════════════════════════

def _mock_post(platform: str, text: str, image_urls: list[str] | None = None) -> dict:
    """Simulate a successful post when credentials are missing."""
    preview = text[:80].replace("\n", " ")
    logger.info("Mock: Posting to %s...", platform.upper())
    logger.info("  Text: %s", preview)
    if image_urls:
        logger.info("  Images: %s", image_urls)
    return {"id": f"mock-{platform}-id"}


# ═══════════════════════════════════════════════════════════════════════════
#  LINKEDIN POSTING
# ═══════════════════════════════════════════════════════════════════════════

def post_to_linkedin(text: str, image_urls: list[str] | None = None) -> dict:
    """
    Create a LinkedIn text post (UGC Post).
    Falls back to mock mode if credentials are not set.
    """
    if DRY_RUN:
        logger.info("[DRY-RUN] Would post to LinkedIn: %s", text[:80])
        return {"id": "dry-run-linkedin-id"}

    # ── Mock fallback ───────────────────────────────────────────────────
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_PERSON_URN:
        return _mock_post("linkedin", text, image_urls)

    # ── Real API call ───────────────────────────────────────────────────
    req = _get_requests()
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    resp = req.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
#  INSTAGRAM POSTING
# ═══════════════════════════════════════════════════════════════════════════

def post_to_instagram(text: str, image_urls: list[str] | None = None) -> dict:
    """
    Two-step Instagram publish via Meta Graph API.
    Falls back to mock mode if credentials are not set.
    """
    if DRY_RUN:
        logger.info("[DRY-RUN] Would post to Instagram: %s", text[:80])
        return {"id": "dry-run-instagram-id"}

    # ── Mock fallback ───────────────────────────────────────────────────
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        return _mock_post("instagram", text, image_urls)

    # ── Real API call ───────────────────────────────────────────────────
    req = _get_requests()
    base_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_USER_ID}"

    # Step 1: Create media container
    media_payload = {
        "caption": text,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    if image_urls and image_urls[0]:
        media_payload["image_url"] = image_urls[0]
    else:
        raise ValueError("Instagram posts require at least one image URL.")

    resp1 = req.post(f"{base_url}/media", data=media_payload, timeout=30)
    resp1.raise_for_status()
    creation_id = resp1.json().get("id")

    if not creation_id:
        raise ValueError(f"Instagram media creation failed: {resp1.text}")

    # Step 2: Publish the container
    publish_payload = {
        "creation_id": creation_id,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    resp2 = req.post(f"{base_url}/media_publish", data=publish_payload, timeout=30)
    resp2.raise_for_status()
    return resp2.json()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

PLATFORM_HANDLERS = {
    "linkedin": post_to_linkedin,
    "instagram": post_to_instagram,
}


def process_row(row: dict) -> dict:
    """
    Attempt to post a single row. Updates status, posted_at, and error_log.
    Returns the mutated row dict.
    """
    platform = row.get("platform", "").lower().strip()
    text = row.get("text_content", "")
    raw_images = row.get("image_urls", "")

    # Build full image URLs from repo-relative paths
    image_urls = (
        [build_image_url(p) for p in raw_images.split(";") if p.strip()]
        if raw_images
        else []
    )

    handler = PLATFORM_HANDLERS.get(platform)
    if not handler:
        row["status"] = "error"
        row["error_log"] = f"Unknown platform: {platform}"
        logger.error(
            "Unknown platform '%s' for row dated %s",
            platform,
            row.get("scheduled_date"),
        )
        return row

    try:
        result = handler(text, image_urls)
        row["status"] = "posted"
        row["posted_at"] = datetime.now(timezone.utc).isoformat()
        row["error_log"] = ""
        logger.info(
            "Posted to %s (id: %s)", platform, result.get("id", "n/a")
        )
    except Exception as exc:
        row["status"] = "error"
        row["error_log"] = str(exc)[:500]
        logger.error("Failed posting to %s: %s", platform, exc)

    return row


def main() -> None:
    """Main entry point: filter today's pending rows, post them, save CSV."""
    logger.info("=" * 60)
    logger.info("Content Ops Automation - Run started")
    logger.info("Dry-run mode: %s", DRY_RUN)
    logger.info("=" * 60)

    today = get_today_str()
    rows = read_csv()
    any_changes = False

    for row in rows:
        scheduled = row.get("scheduled_date", "").strip()
        status = row.get("status", "").strip().lower()

        if scheduled == today and status == "pending":
            logger.info(
                "Processing: [%s] %s - %s",
                scheduled,
                row.get("platform"),
                row.get("text_content", "")[:50],
            )
            process_row(row)
            any_changes = True

    if any_changes:
        write_csv(rows)
        logger.info("CSV updated and saved.")
    else:
        logger.info("No pending posts for today (%s). Nothing to do.", today)

    logger.info("Run complete.")


if __name__ == "__main__":
    main()
