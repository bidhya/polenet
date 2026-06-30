#!/usr/bin/env python3
"""
crawl_site.py — Step 2: Crawl all pages of polenet.org from the Wayback Machine.

Crawls all 7 nav pages + known blog posts, downloads:
  - HTML for each page        → archive/html/<slug>.html
  - Images from each page     → archive/images/
  - CSS / JS theme assets     → archive/assets/  (layout reference only)

Any new internal links discovered during crawl are added to the queue
(one level deep beyond the seed list — avoids runaway crawl).

Usage:
  python crawl_site.py
"""

import re
import time
import logging
import hashlib
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote, urlunparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TIMESTAMP     = "20251207055143"       # Wayback snapshot to use throughout
TARGET_ORIGIN = "https://polenet.org"
WB_BASE       = "https://web.archive.org"
REQUEST_DELAY = 2.0                    # seconds between requests

BASE_DIR          = Path(__file__).resolve().parent.parent
ARCHIVE_HTML_DIR  = BASE_DIR / "archive" / "html"
ARCHIVE_IMAGE_DIR = BASE_DIR / "archive" / "images"
ARCHIVE_ASSET_DIR = BASE_DIR / "archive" / "assets"   # CSS / JS

# Seed URLs — all known internal pages (original polenet.org paths)
SEED_PATHS = [
    "/about/",
    "/sites/",
    "/photos/",
    "/publications/",
    "/training-schools/",
    "/?page_id=81",                          # Blog index
    "/2024-2025-field-season-progress/",
    "/2025-gia-workshop/",
    "/sharing-science-by-david-saddler/",
    "/field-season-training-by-david-saddler/",
]

# Asset MIME types to save to archive/assets/
ASSET_MIMES = {"text/css", "application/javascript", "text/javascript"}

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


def get(url: str, stream: bool = False) -> requests.Response | None:
    """GET with 3 retries. Returns None on permanent failure."""
    for attempt in range(1, 4):
        try:
            resp = session.get(url, timeout=30, stream=stream)
            resp.raise_for_status()
            if not stream:
                time.sleep(REQUEST_DELAY)
            return resp
        except requests.RequestException as exc:
            log.warning("Attempt %d/3 failed (%s): %s", attempt, url, exc)
            if attempt < 3:
                time.sleep(5 * attempt)
    log.error("Giving up on: %s", url)
    return None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

# Matches Wayback-wrapped URLs and captures (timestamp_with_modifier, original_url)
WB_URL_RE = re.compile(
    r"https?://web\.archive\.org/web/(\d+[^/]*)/(.+)", re.IGNORECASE
)


def wayback_url(path: str, modifier: str = "") -> str:
    """Build a Wayback Machine URL for a polenet.org path."""
    origin = TARGET_ORIGIN.rstrip("/")
    path   = "/" + path.lstrip("/")
    return f"{WB_BASE}/web/{TIMESTAMP}{modifier}{origin}{path}"


def unwrap_wayback(url: str) -> str | None:
    """
    Extract the original URL from a Wayback-wrapped URL.
    Returns None if not a Wayback URL.
    """
    m = WB_URL_RE.match(url)
    if not m:
        return None
    original = m.group(2)
    if not original.startswith("http"):
        original = "https://" + original
    return original


def normalise_src(src: str, page_wb_url: str) -> str:
    """Turn any src/href value into an absolute URL."""
    src = src.strip()
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/web/"):
        return WB_BASE + src
    if not src.startswith("http"):
        return urljoin(page_wb_url, src)
    return src


def is_internal(url: str) -> bool:
    """True if the URL belongs to polenet.org (after unwrapping Wayback)."""
    original = unwrap_wayback(url) or url
    parsed   = urlparse(original)
    host     = parsed.netloc.lower().lstrip("www.")
    return host in ("polenet.org", "")


def path_slug(original_url: str) -> str:
    """
    Convert a polenet.org URL to a safe filesystem slug for naming HTML files.
    E.g.  https://polenet.org/about/  →  about
          https://polenet.org/?page_id=81  →  blog-index
    """
    parsed = urlparse(original_url)
    path   = parsed.path.strip("/") or "home"
    slug   = re.sub(r"[^a-z0-9\-]", "-", path.lower()).strip("-")
    if parsed.query:
        qslug = re.sub(r"[^a-z0-9]", "-", parsed.query.lower())
        slug  = (slug + "-" + qslug).strip("-") or "page"
    return slug or "home"


def safe_filename(url: str, fallback_prefix: str = "file") -> str:
    """Derive a safe local filename from a URL."""
    parsed   = urlparse(url)
    name     = Path(unquote(parsed.path)).name
    if name and "." in name:
        # handle query-string variants like 72.jpg?ver=1
        name = name.split("?")[0]
        return name
    # No useful name in path — use a hash of the URL
    return f"{fallback_prefix}_{hashlib.md5(url.encode()).hexdigest()[:8]}"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def save_html(html: str, slug: str) -> Path:
    ARCHIVE_HTML_DIR.mkdir(parents=True, exist_ok=True)
    out = ARCHIVE_HTML_DIR / f"{slug}.html"
    out.write_text(html, encoding="utf-8")
    return out


def download_binary(url: str, dest: Path) -> bool:
    """Download a binary file (image / CSS / JS). Returns True on success."""
    if dest.exists():
        log.debug("  SKIP (exists): %s", dest.name)
        return True
    resp = get(url, stream=True)
    if resp is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
    time.sleep(REQUEST_DELAY)
    return True


# ---------------------------------------------------------------------------
# Per-page scraping
# ---------------------------------------------------------------------------

def scrape_page(original_url: str) -> tuple[BeautifulSoup | None, list[str]]:
    """
    Download one page from Wayback, save its HTML, download its images and
    assets.  Returns (BeautifulSoup_object, list_of_discovered_internal_urls).
    """
    slug       = path_slug(original_url)
    html_dest  = ARCHIVE_HTML_DIR / f"{slug}.html"
    wb_page_url = f"{WB_BASE}/web/{TIMESTAMP}/{original_url}"

    log.info("── Page: %-40s  slug=%s", original_url, slug)

    # --- HTML ---------------------------------------------------------------
    if html_dest.exists():
        log.info("   HTML already cached, reading from disk.")
        html = html_dest.read_text(encoding="utf-8")
    else:
        resp = get(wb_page_url)
        if resp is None:
            log.error("   Could not download page — skipping.")
            return None, []
        html = resp.text
        save_html(html, slug)
        log.info("   HTML saved (%d bytes) → %s", len(html), html_dest.name)

    soup = BeautifulSoup(html, "lxml")

    # --- Images -------------------------------------------------------------
    img_ok = img_fail = 0
    for tag in soup.find_all("img"):
        src = (tag.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        abs_src      = normalise_src(src, wb_page_url)
        original_img = unwrap_wayback(abs_src) or abs_src
        wb_dl_url    = f"{WB_BASE}/web/{TIMESTAMP}im_/{original_img}"
        filename     = safe_filename(original_img, "img")
        dest         = ARCHIVE_IMAGE_DIR / filename
        if download_binary(wb_dl_url, dest):
            img_ok += 1
        else:
            img_fail += 1
    if img_ok or img_fail:
        log.info("   Images: %d ok, %d failed.", img_ok, img_fail)

    # --- CSS / JS assets ----------------------------------------------------
    asset_tags = (
        list(soup.find_all("link",   rel="stylesheet")) +
        list(soup.find_all("script", src=True))
    )
    for tag in asset_tags:
        href = (tag.get("href") or tag.get("src") or "").strip()
        if not href:
            continue
        abs_href = normalise_src(href, wb_page_url)
        # Only save Wayback-served assets that belong to polenet.org theme
        original_asset = unwrap_wayback(abs_href)
        if not original_asset:
            continue
        if "polenet.org" not in original_asset:
            continue
        filename = safe_filename(original_asset, "asset")
        dest     = ARCHIVE_ASSET_DIR / filename
        # Use cs_ modifier for CSS and js_ for JS
        modifier = "cs_" if "css" in filename else "js_"
        wb_dl    = f"{WB_BASE}/web/{TIMESTAMP}{modifier}/{original_asset}"
        download_binary(wb_dl, dest)

    # --- Discover new internal links ----------------------------------------
    discovered = []
    for tag in soup.find_all("a", href=True):
        href = normalise_src(tag["href"], wb_page_url)
        original_link = unwrap_wayback(href) or href
        parsed = urlparse(original_link)
        # Only follow polenet.org links that look like pages (not files)
        host = parsed.netloc.lower().lstrip("www.")
        if host not in ("polenet.org", ""):
            continue
        path = parsed.path
        if re.search(r"\.(jpg|jpeg|png|gif|pdf|zip|css|js|xml|ico)$", path, re.I):
            continue
        full_url = urlunparse(("https", "polenet.org", path, "", parsed.query, ""))
        discovered.append(full_url)

    return soup, list(set(discovered))


# ---------------------------------------------------------------------------
# Main crawl loop
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 60)
    log.info("  polenet.org Wayback Crawler  |  Step 2")
    log.info("  Snapshot: %s", TIMESTAMP)
    log.info("=" * 60)

    # Build work queue from seed paths
    seed_urls = [
        f"{TARGET_ORIGIN}{p}" if p.startswith("/") else p
        for p in SEED_PATHS
    ]

    crawled   = set()
    queue     = list(seed_urls)
    discovered_extra = []   # links found during crawl but not in seed list

    stats = {"pages_ok": 0, "pages_fail": 0}

    while queue:
        url = queue.pop(0)
        if url in crawled:
            continue
        crawled.add(url)

        soup, found_links = scrape_page(url)
        if soup is None:
            stats["pages_fail"] += 1
            continue
        stats["pages_ok"] += 1

        # Queue newly discovered internal links (one hop beyond seed)
        for link in found_links:
            if link not in crawled and link not in queue:
                if link not in seed_urls:
                    discovered_extra.append(link)
                    queue.append(link)

    log.info("=" * 60)
    log.info("Crawl complete.")
    log.info("  Pages downloaded : %d", stats["pages_ok"])
    log.info("  Pages failed     : %d", stats["pages_fail"])
    log.info("  Extra pages found: %d", len(set(discovered_extra)))
    if discovered_extra:
        log.info("  Extra pages:")
        for u in sorted(set(discovered_extra)):
            log.info("    %s", u)
    log.info("=" * 60)
    log.info("Outputs:")
    log.info("  HTML   → %s", ARCHIVE_HTML_DIR)
    log.info("  Images → %s", ARCHIVE_IMAGE_DIR)
    log.info("  Assets → %s", ARCHIVE_ASSET_DIR)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
