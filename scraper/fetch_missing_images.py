#!/usr/bin/env python3
"""
fetch_missing_images.py — Download missing images from the Wayback Machine.

Run AFTER parse_xml.py and build_site.py. This script:
1. Scans site/ HTML for image references not in archive/images/
2. Cross-references with archive/xml/attachments.json for original URLs
3. Queries the Wayback CDX API for each URL
4. Downloads found images to archive/images/

Because Wayback CDX can be slow/throttled, this script is intentionally
conservative with rate limits and can be run multiple times (it skips
already-downloaded files).

After downloading images, re-run build_site.py to copy them to site/images/.

Usage:
  python scraper/fetch_missing_images.py [--dry-run]
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR     = Path(__file__).resolve().parent.parent
SITE_DIR     = BASE_DIR / "site"
ARCHIVE_IMG  = BASE_DIR / "archive" / "images"
XML_DIR      = BASE_DIR / "archive" / "xml"

DRY_RUN = "--dry-run" in sys.argv

# Wayback rate limiting (seconds between requests)
CDX_DELAY     = 1.0   # between CDX API calls
DOWNLOAD_DELAY = 1.5  # between image downloads


def find_missing_images() -> set[str]:
    """Find all image filenames referenced in site/ HTML that aren't in archive/images/."""
    archive_imgs = {f.name for f in ARCHIVE_IMG.iterdir() if f.is_file()}
    missing = set()
    for hp in SITE_DIR.rglob("*.html"):
        c = hp.read_text(encoding="utf-8")
        for img in re.findall(r'src="images/([^"]+)"', c):
            if img not in archive_imgs:
                missing.add(img)
        for img in re.findall(r'src="\.\./\.\./images/([^"]+)"', c):
            if img not in archive_imgs:
                missing.add(img)
    return missing


def build_url_map() -> dict[str, str]:
    """
    Build mapping from image filename → original polenet.org URL.
    Uses attachments.json, matching by exact filename and by base name
    (stripping WordPress size suffixes like -1024x768).
    """
    atts_file = XML_DIR / "attachments.json"
    if not atts_file.exists():
        print("WARNING: archive/xml/attachments.json not found. Run parse_xml.py first.")
        return {}

    atts = json.loads(atts_file.read_text(encoding="utf-8"))
    url_map = {}

    # Exact filename match
    for a in atts:
        url_map[a["filename"]] = a["url"]

    # Base name match (strip -WxH size suffix)
    att_by_base = {}
    for a in atts:
        base = re.sub(r"-\d+x\d+", "", a["filename"])
        att_by_base[base] = a["url"]

    return url_map, att_by_base


def resolve_wayback_url(original_url: str) -> str | None:
    """
    Query Wayback CDX API for the most recent archived copy of a URL.
    Returns the Wayback URL if found, None if not archived.
    """
    # CDX API: find most recent 200 snapshot
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={urllib.parse.quote(original_url)}"
        "&output=json&limit=1&fl=timestamp,statuscode"
        "&filter=statuscode:200&sort=timestamp&order=desc"
    )
    try:
        resp = urllib.request.urlopen(cdx_url, timeout=10)
        data = json.loads(resp.read())
        if len(data) > 1:
            ts = data[1][0]
            # Use "if_" to get raw image without Wayback toolbar injection
            return f"https://web.archive.org/web/{ts}if_/{original_url}"
        return None
    except Exception:
        return None


def download_image(wayback_url: str, dest: Path) -> bool:
    """Download image from Wayback and save. Returns True on success."""
    try:
        resp = urllib.request.urlopen(wayback_url, timeout=20)
        data = resp.read()
        if len(data) < 5_000:
            # Too small — probably an error page
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def main():
    print("=" * 55)
    print("  fetch_missing_images.py — Wayback image recovery")
    print("=" * 55)
    if DRY_RUN:
        print("  [DRY RUN — no files will be downloaded]")

    # Step 1: find missing
    print("\nScanning site/ for missing images...")
    missing = find_missing_images()
    print(f"  {len(missing)} missing image references")

    # Step 2: build URL map
    url_map, att_by_base = build_url_map()

    # Step 3: match each missing image to an original URL
    to_download = []  # [(filename, original_url)]
    no_url = []

    for fname in sorted(missing):
        # Skip video files — not useful as images
        if Path(fname).suffix.lower() in {".mov", ".mp4", ".avi", ".wmv"}:
            continue
        if fname in url_map:
            to_download.append((fname, url_map[fname]))
        else:
            base = re.sub(r"-\d+x\d+", "", fname)
            if base in att_by_base:
                to_download.append((fname, att_by_base[base]))
            else:
                no_url.append(fname)

    print(f"  {len(to_download)} have a known URL to try")
    print(f"  {len(no_url)} have no known URL (cannot recover automatically)")

    if no_url:
        print(f"\n  Images with no known URL (first 10):")
        for f in no_url[:10]:
            print(f"    {f}")

    # Step 4: CDX query + download
    downloaded = 0
    not_archived = 0
    errors = 0

    print(f"\nQuerying Wayback CDX and downloading ({len(to_download)} images)...")
    for i, (fname, original_url) in enumerate(to_download):
        dest = ARCHIVE_IMG / fname
        if dest.exists():
            print(f"  [skip] {fname} — already exists")
            continue

        # CDX query
        time.sleep(CDX_DELAY)
        wayback_url = resolve_wayback_url(original_url)
        if not wayback_url:
            not_archived += 1
            print(f"  ○ {fname} — not in Wayback")
            continue

        if DRY_RUN:
            print(f"  [dry] {fname} — would download from {wayback_url}")
            downloaded += 1
            continue

        # Download
        time.sleep(DOWNLOAD_DELAY)
        ok = download_image(wayback_url, dest)
        if ok:
            size_kb = dest.stat().st_size // 1024
            print(f"  ✓ {fname} ({size_kb}KB)")
            downloaded += 1
        else:
            errors += 1
            print(f"  ✗ {fname} — download failed")

        # Progress
        if (i + 1) % 20 == 0:
            print(f"\n  Progress: {i+1}/{len(to_download)} processed\n")

    # Summary
    print(f"\n{'='*55}")
    print(f"  Downloaded: {downloaded}")
    print(f"  Not in Wayback: {not_archived}")
    print(f"  Errors: {errors}")
    print(f"  No URL known: {len(no_url)}")
    if downloaded > 0 and not DRY_RUN:
        print(f"\n  ✓ Re-run build_site.py to copy new images to site/")
    print("=" * 55)


if __name__ == "__main__":
    main()
