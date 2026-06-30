#!/usr/bin/env python3
"""
audit.py — Step 3: Inventory and classify all captured archive content.

Reads archive/html/, classifies every file, checks image coverage,
and writes human-readable reports to archive/audit/.

Reports produced:
  page_inventory.txt   — every HTML file with its classification and title
  site_index.txt       — all 51 monitoring site pages (station ID, name, coords)
  image_report.txt     — images we have vs images referenced but missing
  gap_report.txt       — summary of what still needs attention before rebuild

Usage:
  python audit.py
"""

import re
import os
import json
import warnings
from pathlib import Path
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR   = Path(__file__).resolve().parent.parent
HTML_DIR   = BASE_DIR / "archive" / "html"
IMAGE_DIR  = BASE_DIR / "archive" / "images"
AUDIT_DIR  = BASE_DIR / "archive" / "audit"

AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------

# Exact slug → category for the 7 main nav pages
NAV_SLUGS = {
    "home", "about", "sites", "photos", "publications",
    "training-schools", "home-page-id-81",
}

# Patterns for noise (WordPress system pages we don't need)
NOISE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}\.html$"),        # date archives: 2010-10.html
    re.compile(r"^wp-login"),                    # wp-login-php.html
    re.compile(r"^feed\.html$"),                 # RSS feed
    re.compile(r"^comments-feed\.html$"),        # comments RSS
    re.compile(r"^category-"),                   # category pages
    re.compile(r"^homepage_\d+\.html$"),         # step-1 raw homepage (duplicate)
]

TRAINING_KEYWORDS = [
    "training-school", "workshop", "gia-training",
    "seismology", "glacial-isostatic"
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify(filename: str, soup: BeautifulSoup) -> str:
    """Return a category label for this HTML file."""
    stem = filename.replace(".html", "")

    # Noise first
    for pat in NOISE_PATTERNS:
        if pat.match(filename):
            return "noise"

    # Exact nav pages
    if stem in NAV_SLUGS:
        return "nav"

    # Blog page 2
    if stem == "page-2-page-id-81":
        return "blog"

    # Gallery pages
    if stem.startswith("photos-nggallery"):
        return "gallery"

    # Individual site detail pages (home-page-id-NNN where NNN != 81)
    if re.match(r"^home-page-id-\d+$", stem):
        return "site-detail"

    # Classify remaining by slug keywords
    slug_lower = stem.lower()
    if any(k in slug_lower for k in TRAINING_KEYWORDS):
        return "training"

    return "blog"


def extract_content(soup: BeautifulSoup) -> dict:
    """
    Pull key structured content from a page.
    Returns a dict with title, content_preview, images_referenced.
    """
    title = soup.title.text.strip() if soup.title else "(no title)"
    # Strip the site name suffix
    title = re.sub(r"\s*\|\s*POLENET.*$", "", title).strip()

    # Main content area
    content_el = soup.select_one(
        ".entry-content, .post-content, #content, .page-content, article"
    )
    content_text = ""
    if content_el:
        content_text = content_el.get_text(separator=" ", strip=True)

    # All referenced image paths (original URLs, not Wayback-wrapped)
    wb_re = re.compile(r"https?://web\.archive\.org/web/\d+[^/]*/(.+)")
    images_referenced = []
    for tag in soup.find_all("img"):
        src = (tag.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        m = wb_re.match(src)
        original = m.group(1) if m else src
        if not original.startswith("http"):
            original = "https://" + original
        images_referenced.append(original)

    return {
        "title":       title,
        "preview":     content_text[:300],
        "images":      images_referenced,
    }


def extract_site_detail(soup: BeautifulSoup) -> dict:
    """
    Extract structured fields from a monitoring site detail page.
    Returns a dict with station_id, coordinates, installed, etc.
    """
    content_el = soup.select_one(
        ".entry-content, .post-content, #content, .page-content, article"
    )
    text = content_el.get_text(separator="\n", strip=True) if content_el else ""

    def field(label):
        m = re.search(rf"{label}:\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    return {
        "station_id":  field("Station ID"),
        "coordinate":  field("Coordinate"),
        "installed":   field("Installed"),
        "former_projects": field("Former Projects"),
        "former_names":    field("Former Names"),
        "transport":       field("Transportation"),
        "hub":             field("Closest operations HUB"),
    }


def filename_from_url(url: str) -> str:
    """Get just the filename portion of a URL (for image lookup)."""
    path = unquote(urlparse(url).path)
    return Path(path).name.split("?")[0]


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def main():
    html_files = sorted(HTML_DIR.glob("*.html"))
    images_on_disk = {f.name for f in IMAGE_DIR.iterdir() if f.is_file()}

    pages = []
    site_details = []
    all_referenced_images = {}   # filename → set of pages that reference it

    print(f"Auditing {len(html_files)} HTML files ...")

    for html_path in html_files:
        html = html_path.read_text(encoding="utf-8", errors="replace")
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            print(f"  SKIP (parse error): {html_path.name}")
            continue
        category = classify(html_path.name, soup)
        info     = extract_content(soup)

        page_entry = {
            "file":     html_path.name,
            "category": category,
            "title":    info["title"],
            "preview":  info["preview"],
            "images":   info["images"],
        }

        # Track image references
        for img_url in info["images"]:
            fname = filename_from_url(img_url)
            if fname:
                all_referenced_images.setdefault(fname, []).append(html_path.name)

        pages.append(page_entry)

        # Extra extraction for site detail pages
        if category == "site-detail":
            detail = extract_site_detail(soup)
            detail["file"]  = html_path.name
            detail["title"] = info["title"]
            site_details.append(detail)

    # -------------------------------------------------------------------
    # Report 1: Page inventory
    # -------------------------------------------------------------------
    categories = ["nav", "gallery", "site-detail", "blog", "training", "noise"]
    with open(AUDIT_DIR / "page_inventory.txt", "w") as f:
        f.write("polenet.org ARCHIVE — PAGE INVENTORY\n")
        f.write("=" * 60 + "\n\n")
        counts = {}
        for cat in categories:
            group = [p for p in pages if p["category"] == cat]
            counts[cat] = len(group)
            f.write(f"{'─'*60}\n")
            f.write(f"  {cat.upper()}  ({len(group)} pages)\n")
            f.write(f"{'─'*60}\n")
            for p in group:
                f.write(f"  {p['file']}\n")
                f.write(f"    Title   : {p['title']}\n")
                if cat not in ("noise", "gallery"):
                    f.write(f"    Preview : {p['preview'][:180]}...\n")
                f.write(f"    Images  : {len(p['images'])}\n")
                f.write("\n")
        f.write("\n" + "=" * 60 + "\n")
        f.write("SUMMARY\n")
        for cat, n in counts.items():
            f.write(f"  {cat:<15} {n}\n")
        f.write(f"  {'TOTAL':<15} {len(pages)}\n")

    print(f"  → page_inventory.txt ({len(pages)} pages)")

    # -------------------------------------------------------------------
    # Report 2: Site index
    # -------------------------------------------------------------------
    site_details.sort(key=lambda x: x.get("station_id", ""))
    with open(AUDIT_DIR / "site_index.txt", "w") as f:
        f.write("polenet.org ARCHIVE — MONITORING SITE INDEX\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"{'Station':10}  {'Title':<35}  {'Coordinates':<28}  Installed\n")
        f.write(f"{'─'*10}  {'─'*35}  {'─'*28}  {'─'*20}\n")
        for s in site_details:
            f.write(
                f"{s.get('station_id','?'):<10}  "
                f"{s.get('title','?'):<35}  "
                f"{s.get('coordinate','?'):<28}  "
                f"{s.get('installed','?')}\n"
            )
        f.write(f"\nTotal monitoring sites: {len(site_details)}\n")

    print(f"  → site_index.txt ({len(site_details)} sites)")

    # -------------------------------------------------------------------
    # Report 3: Image coverage
    # -------------------------------------------------------------------
    missing_images = []
    for fname, referencing_pages in sorted(all_referenced_images.items()):
        if fname not in images_on_disk:
            # Skip known-unfetchable types
            if any(x in fname for x in ["gravatar", "fbcdn", "emoji", "?", "favicon"]):
                continue
            missing_images.append((fname, referencing_pages))

    with open(AUDIT_DIR / "image_report.txt", "w") as f:
        f.write("polenet.org ARCHIVE — IMAGE COVERAGE REPORT\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Images on disk      : {len(images_on_disk)}\n")
        f.write(f"Unique images ref'd : {len(all_referenced_images)}\n")
        f.write(f"Missing from disk   : {len(missing_images)}\n\n")

        if missing_images:
            f.write("MISSING IMAGES (referenced in HTML but not downloaded):\n")
            f.write("─" * 60 + "\n")
            for fname, ref_pages in missing_images:
                f.write(f"  {fname}\n")
                for pg in ref_pages[:3]:
                    f.write(f"    ← {pg}\n")
        else:
            f.write("No missing images found.\n")

        f.write(f"\nIMAGES ON DISK NOT REFERENCED IN ANY PAGE:\n")
        f.write("─" * 60 + "\n")
        all_ref_names = set(all_referenced_images.keys())
        unreferenced = sorted(images_on_disk - all_ref_names)
        for name in unreferenced[:30]:
            f.write(f"  {name}\n")
        if len(unreferenced) > 30:
            f.write(f"  ... and {len(unreferenced)-30} more\n")

    print(f"  → image_report.txt ({len(missing_images)} missing images)")

    # -------------------------------------------------------------------
    # Report 4: Gap / decision summary
    # -------------------------------------------------------------------
    nav_pages    = [p for p in pages if isinstance(p, dict) and p.get("category") == "nav"]
    blog_pages   = [p for p in pages if isinstance(p, dict) and p.get("category") == "blog"]
    training_pg  = [p for p in pages if isinstance(p, dict) and p.get("category") == "training"]
    gallery_pg   = [p for p in pages if isinstance(p, dict) and p.get("category") == "gallery"]
    noise_pages  = [p for p in pages if isinstance(p, dict) and p.get("category") == "noise"]
    sitedet_pgs  = [p for p in pages if isinstance(p, dict) and p.get("category") == "site-detail"]

    with open(AUDIT_DIR / "gap_report.txt", "w") as f:
        f.write("polenet.org ARCHIVE — GAP REPORT & DECISIONS NEEDED\n")
        f.write("=" * 60 + "\n\n")

        f.write("WHAT WE HAVE\n")
        f.write("─" * 40 + "\n")
        f.write(f"  Nav pages           : {len(nav_pages)}/7\n")
        f.write(f"  Monitoring sites    : {len(site_details)}\n")
        f.write(f"  Blog posts          : {len(blog_pages)}\n")
        f.write(f"  Training schools    : {len(training_pg)}\n")
        f.write(f"  Gallery pages       : {len(gallery_pg)}/5\n")
        f.write(f"  Images on disk      : {len(images_on_disk)}\n")
        f.write(f"  Missing images      : {len(missing_images)}\n\n")

        f.write("DECISIONS NEEDED BEFORE REBUILD\n")
        f.write("─" * 40 + "\n")
        f.write(f"  1. Individual site pages ({len(site_details)} pages) — rebuild as individual pages\n")
        f.write("     or consolidate into a table on the Sites and Data page?\n\n")
        f.write("  2. Blog posts — include all, or only recent (post-2020)?\n\n")
        f.write("  3. Photo gallery — CSS grid + lightbox (recommended)\n")
        f.write("     or match the original 5-page paginated layout?\n\n")
        f.write("  4. Hosting — affects URL structure and relative paths.\n\n")

        f.write("NOISE (will be excluded from rebuild)\n")
        f.write("─" * 40 + "\n")
        for p in noise_pages:
            f.write(f"  {p['file']}\n")

    print(f"  → gap_report.txt")

    # -------------------------------------------------------------------
    # Also dump site index as JSON for use in rebuild step
    # -------------------------------------------------------------------
    with open(AUDIT_DIR / "site_index.json", "w") as f:
        json.dump(site_details, f, indent=2)
    print(f"  → site_index.json ({len(site_details)} sites, for rebuild use)")

    # -------------------------------------------------------------------
    # Console summary
    # -------------------------------------------------------------------
    print()
    print("=" * 60)
    print("AUDIT COMPLETE")
    print(f"  Nav pages        : {len(nav_pages)}/7")
    print(f"  Site detail pages: {len(site_details)}")
    print(f"  Blog posts       : {len(blog_pages)}")
    print(f"  Training schools : {len(training_pg)}")
    print(f"  Gallery pages    : {len(gallery_pg)}/5")
    print(f"  Images on disk   : {len(images_on_disk)}")
    print(f"  Missing images   : {len(missing_images)}")
    print(f"  Noise (excluded) : {len(noise_pages)}")
    print("=" * 60)
    print(f"Reports → {AUDIT_DIR}")


if __name__ == "__main__":
    main()
