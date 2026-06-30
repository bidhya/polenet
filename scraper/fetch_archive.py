#!/usr/bin/env python3
"""
fetch_archive.py — Step 1: Extract polenet.org content from the Wayback Machine.

Workflow:
  1. Query the CDX API for the best snapshot of polenet.org in February 2026.
  2. Download the raw archived HTML of the homepage.
  3. Parse for image URLs (especially /wp-content/uploads/).
  4. Download each image via its Wayback Machine URL.
  5. Save HTML → archive/html/   |   images → archive/images/

Usage:
  python fetch_archive.py
"""

import os
import re
import time
import logging
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration — adjust these as needed
# ---------------------------------------------------------------------------

TARGET_URL    = "https://polenet.org"
DATE_FROM     = "20250901"   # YYYYMMDD — start of search window
DATE_TO       = "20251231"   # YYYYMMDD — end of search window
# NOTE: Feb 2026 snapshots are all 301 redirects (site already broken).
# Last known-good 200 snapshots: Sep, Nov, Dec 2025. We target Dec (most recent).

# Output directories (relative to the repo root, one level above this script)
BASE_DIR          = Path(__file__).resolve().parent.parent
ARCHIVE_HTML_DIR  = BASE_DIR / "archive" / "html"
ARCHIVE_IMAGE_DIR = BASE_DIR / "archive" / "images"

WB_BASE       = "https://web.archive.org"
REQUEST_DELAY = 1.5   # seconds between requests — be polite to archive.org

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "polenet-archive-research/1.0 "
        "(non-commercial site rebuild; contact via polenet.org)"
    )
})


def get(url: str, stream: bool = False) -> requests.Response:
    """GET with 3 retries on transient errors and a politeness delay."""
    for attempt in range(1, 4):
        try:
            resp = session.get(url, timeout=30, stream=stream)
            resp.raise_for_status()
            if not stream:
                time.sleep(REQUEST_DELAY)
            return resp
        except requests.RequestException as exc:
            log.warning("Attempt %d/3 failed for %s: %s", attempt, url, exc)
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"All 3 attempts failed for: {url}")


# ---------------------------------------------------------------------------
# Step 1 — Find the best snapshot via the CDX API
# ---------------------------------------------------------------------------

def find_snapshot() -> dict:
    """
    Query the Wayback CDX API for HTML snapshots of polenet.org within
    the configured date window.  Returns a dict with timestamp, original,
    statuscode keys from the first (earliest) match.
    """
    cdx_url = (
        "http://web.archive.org/cdx/search/cdx"
        f"?url={TARGET_URL}"
        "&output=json"
        "&limit=5"
        f"&from={DATE_FROM}"
        f"&to={DATE_TO}"
        "&fl=timestamp,original,statuscode,mimetype"
        "&filter=statuscode:200"
        "&filter=mimetype:text/html"
        "&collapse=timestamp:8"   # one result per day at most
    )
    log.info("Querying CDX API ...")
    log.debug("CDX URL: %s", cdx_url)

    resp = get(cdx_url)
    rows = resp.json()

    if len(rows) < 2:   # first row is the field-name header
        raise RuntimeError(
            "No snapshots found in the date range "
            f"{DATE_FROM}–{DATE_TO}. "
            "Try widening the window in the Configuration section."
        )

    header, *records = rows
    log.info("Found %d snapshot(s) in window. Using the most recent one.", len(records))
    for r in records:
        log.info("  Candidate: %s", dict(zip(header, r)))

    snapshot = dict(zip(header, records[-1]))  # most recent = last in ascending list
    log.info(
        "Selected snapshot: timestamp=%s  url=%s  status=%s",
        snapshot["timestamp"], snapshot["original"], snapshot["statuscode"]
    )
    return snapshot


# ---------------------------------------------------------------------------
# Step 2 — Download the archived homepage HTML
# ---------------------------------------------------------------------------

def download_homepage(snapshot: dict) -> tuple[str, str, str]:
    """
    Fetch the Wayback Machine version of the homepage.
    Returns (html_text, full_snapshot_url, timestamp_str).
    """
    ts       = snapshot["timestamp"]
    original = snapshot["original"]
    url      = f"{WB_BASE}/web/{ts}/{original}"

    log.info("Downloading homepage HTML from: %s", url)
    resp = get(url)
    log.info("  Response: %d bytes, encoding=%s", len(resp.content), resp.encoding)
    return resp.text, url, ts


# ---------------------------------------------------------------------------
# Step 3 — Parse & collect image URLs from the HTML
# ---------------------------------------------------------------------------

def extract_images(html: str, snapshot_url: str, timestamp: str) -> list[dict]:
    """
    Parse the downloaded HTML and return a list of images to download.
    Each entry is a dict:
        original_url  — the real polenet.org URL
        wayback_url   — the Wayback Machine URL to actually download from
        filename      — safe local filename

    The Wayback Machine rewrites src attributes to point back to itself,
    so we strip that wrapper to recover the original URL, then rebuild a
    clean Wayback download URL with the 'im_' modifier (raw binary).
    """
    soup   = BeautifulSoup(html, "html.parser")
    images = []
    seen   = set()

    # Pattern that matches a Wayback-wrapped URL:
    #   https://web.archive.org/web/20260201123456[optional_modifier]/ORIGINAL_URL
    wb_pattern = re.compile(
        r"https?://web\.archive\.org/web/(\d+)[^/]*/(.+)", re.IGNORECASE
    )

    for tag in soup.find_all("img"):
        src = (tag.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue

        # Normalise to an absolute URL
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/web/"):
            # Wayback-relative path  e.g.  /web/20260201.../https://polenet.org/...
            src = WB_BASE + src
        elif not src.startswith("http"):
            src = urljoin(snapshot_url, src)

        # Unwrap the Wayback layer to get the original URL
        m = wb_pattern.match(src)
        if m:
            original_url = m.group(2)
            if not original_url.startswith("http"):
                original_url = "https://" + original_url
        else:
            original_url = src

        if original_url in seen:
            continue
        seen.add(original_url)

        # Build a Wayback download URL using the 'im_' (raw image) modifier
        wayback_dl = f"{WB_BASE}/web/{timestamp}im_/{original_url}"

        # Derive a safe local filename from the URL path
        filename = Path(unquote(urlparse(original_url).path)).name
        if not filename or "." not in filename:
            filename = f"image_{len(images):04d}.bin"

        images.append({
            "original_url": original_url,
            "wayback_url":  wayback_dl,
            "filename":     filename,
        })
        log.debug("  IMG: %s", original_url)

    log.info("Found %d unique image(s) to download.", len(images))
    return images


# ---------------------------------------------------------------------------
# Step 4 — Download images
# ---------------------------------------------------------------------------

def download_images(images: list[dict], dest_dir: Path) -> None:
    """Stream each image from Wayback Machine into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok = skipped = failed = 0

    for img in images:
        dest = dest_dir / img["filename"]

        if dest.exists():
            log.info("  SKIP (already exists): %s", img["filename"])
            skipped += 1
            continue

        log.info("  ↓ %s", img["original_url"])
        try:
            resp = get(img["wayback_url"], stream=True)
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
            time.sleep(REQUEST_DELAY)
            ok += 1
        except Exception as exc:
            log.warning("  FAILED: %s — %s", img["filename"], exc)
            failed += 1

    log.info("Images: %d downloaded, %d skipped, %d failed.", ok, skipped, failed)


# ---------------------------------------------------------------------------
# Step 5 — Save HTML to disk
# ---------------------------------------------------------------------------

def save_html(html: str, timestamp: str, dest_dir: Path) -> Path:
    """Write the raw archived HTML to archive/html/."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"homepage_{timestamp}.html"
    out.write_text(html, encoding="utf-8")
    log.info("HTML saved → %s", out)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 55)
    log.info("  polenet.org Wayback Extractor  |  Step 1")
    log.info("=" * 55)

    snapshot                   = find_snapshot()
    html, snapshot_url, ts     = download_homepage(snapshot)
    save_html(html, ts, ARCHIVE_HTML_DIR)
    images                     = extract_images(html, snapshot_url, ts)
    download_images(images, ARCHIVE_IMAGE_DIR)

    log.info("=" * 55)
    log.info("Done.  Outputs:")
    log.info("  HTML   → %s", ARCHIVE_HTML_DIR)
    log.info("  Images → %s", ARCHIVE_IMAGE_DIR)
    log.info("=" * 55)


if __name__ == "__main__":
    main()
