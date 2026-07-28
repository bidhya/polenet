#!/usr/bin/env python3
"""
fetch_live_uploads.py — Download missing images/files directly from the live
polenet.org WordPress site.

Background (see docs/discovery-log.md 2026-07-26): polenet.org is not offline —
its Aries theme broke, but the database and media library are intact and the
site is reachable. wp-content/uploads/ files are public, no login needed.

This is the primary Step 7 recovery path, ahead of fetch_missing_images.py
(Wayback CDX), because it pulls from the live source of truth: the WordPress
REST API media endpoint (which reflects every generated image size variant),
not the stale 2026-07-01 XML export's attachments list.

Run AFTER parse_xml.py and build_site.py. This script:
1. Scans site/ HTML for image/file references not in archive/images/
2. Pulls the full live media index from https://polenet.org/wp-json/wp/v2/media
   (paginated, ~928 items) and maps every filename (including size variants
   like -1024x768.jpg) to its live source_url
3. Downloads each resolved file to archive/images/

Usage:
  mamba run python scraper/fetch_live_uploads.py --dry-run       # report only
  mamba run python scraper/fetch_live_uploads.py --limit 10      # test batch
  mamba run python scraper/fetch_live_uploads.py                 # full run
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning

BASE_DIR    = Path(__file__).resolve().parent.parent
SITE_DIR    = BASE_DIR / "site"
ARCHIVE_IMG = BASE_DIR / "archive" / "images"
XML_DIR     = BASE_DIR / "archive" / "xml"

MEDIA_API     = "https://polenet.org/wp-json/wp/v2/media"
DOWNLOAD_DELAY = 0.5  # be polite to the live server

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get(url: str, timeout: int = 20) -> requests.Response:
    """
    GET with TLS verification, falling back to unverified only on an SSL
    error. This machine's local CA bundle is missing an intermediate
    certificate for polenet.org's chain; the certificate itself was verified
    legitimate out-of-band with `openssl s_client` (real Sectigo cert, valid
    Oct 2025-Oct 2026) — see docs/discovery-log.md 2026-07-26. On a machine
    with a complete CA bundle, the verified request just succeeds and this
    fallback never triggers.
    """
    try:
        return requests.get(url, timeout=timeout, verify=True)
    except requests.exceptions.SSLError:
        return requests.get(url, timeout=timeout, verify=False)


_PDF_EXT = ".pdf"
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv"}


def _archive_dest(fname: str) -> Path:
    """Route by file type: archive/images/ is organized into videos/ and pdfs/
    subfolders (2026-07-28, see docs/discovery-log.md) — photos stay flat in the root."""
    suffix = Path(fname).suffix.lower()
    if suffix == _PDF_EXT:
        return ARCHIVE_IMG / "pdfs" / fname
    if suffix in _VIDEO_EXTS:
        return ARCHIVE_IMG / "videos" / fname
    return ARCHIVE_IMG / fname


def find_missing_files() -> set[str]:
    """Find all files referenced under images/ in site/ HTML that aren't in archive/images/
    (including its videos/ and pdfs/ subfolders)."""
    archive_files = {f.name for f in ARCHIVE_IMG.rglob("*") if f.is_file()}
    missing = set()
    for hp in SITE_DIR.rglob("*.html"):
        c = hp.read_text(encoding="utf-8", errors="replace")
        for f in re.findall(r'(?:src|href)="(?:\.\./)*images/([^"]+)"', c):
            if f not in archive_files:
                missing.add(f)
    return missing


def fetch_live_media_index() -> dict[str, str]:
    """
    Pull the full WP REST API media listing from the live site. Returns a
    filename -> source_url map covering every generated size variant (not
    just the original upload), since site/ HTML references those size-suffixed
    filenames directly (e.g. foo-1024x768.jpg).
    """
    url_map: dict[str, str] = {}
    page = 1
    total_pages = None
    while True:
        resp = get(f"{MEDIA_API}?per_page=100&page={page}")
        if resp.status_code != 200:
            break
        if total_pages is None:
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        items = resp.json()
        if not items:
            break
        for item in items:
            details = item.get("media_details") or {}
            src = item.get("source_url")
            if src:
                url_map[Path(src).name] = src
            for size in (details.get("sizes") or {}).values():
                su = size.get("source_url")
                if su:
                    url_map[Path(su).name] = su
        print(f"  media index: page {page}/{total_pages} ({len(items)} items)")
        page += 1
        if total_pages and page > total_pages:
            break
        time.sleep(0.3)
    return url_map


def download(url: str, dest: Path) -> bool:
    try:
        resp = get(url, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 500:
            dest.write_bytes(resp.content)
            return True
        return False
    except requests.exceptions.RequestException:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report matches, download nothing")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N files (test batch)")
    args = ap.parse_args()

    print("=" * 55)
    print("  fetch_live_uploads.py — live-server image recovery")
    print("=" * 55)

    print("\nScanning site/ for missing files...")
    missing = sorted(find_missing_files())
    print(f"  {len(missing)} missing file references")

    print("\nPulling live media index from polenet.org REST API...")
    url_map = fetch_live_media_index()
    print(f"  {len(url_map)} unique filenames indexed (incl. size variants)")

    resolved, unresolved = [], []
    for fname in missing:
        if fname in url_map:
            resolved.append((fname, url_map[fname]))
        else:
            unresolved.append(fname)

    print(f"\nResolved: {len(resolved)}   Unresolved: {len(unresolved)}")
    if unresolved:
        print("  Unresolved (no match in live media index):")
        for f in unresolved[:20]:
            print("   -", f)

    if args.limit:
        resolved = resolved[: args.limit]
        print(f"\n  --limit {args.limit}: processing first {len(resolved)} only")

    if args.dry_run:
        print("\n[DRY RUN] would download:")
        for fname, url in resolved:
            print(f"   {fname}  <-  {url}")
        return

    ok = fail = skipped = 0
    for fname, url in resolved:
        dest = _archive_dest(fname)
        if dest.exists():
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if download(url, dest):
            print(f"  OK   {fname} ({dest.stat().st_size // 1024} KB)")
            ok += 1
        else:
            print(f"  FAIL {fname}  <-  {url}")
            fail += 1
        time.sleep(DOWNLOAD_DELAY)

    print(f"\n{'=' * 55}")
    print(f"  Downloaded: {ok}   Failed: {fail}   Already present: {skipped}")
    if ok > 0:
        print("  Re-run scraper/build_site.py to copy new files into site/")
    print("=" * 55)


if __name__ == "__main__":
    main()
