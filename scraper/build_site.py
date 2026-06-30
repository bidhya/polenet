#!/usr/bin/env python3
"""
build_site.py — Step 4: Generate the static polenet.org website.

Reads archived HTML from archive/html/, extracts content,
and writes clean static pages to site/.

Usage:
  python build_site.py

Output structure:
  site/
    index.html
    about.html
    sites.html
    photos.html
    publications.html
    training-schools.html
    blog/
      index.html
      [post-slug].html  × 5 recent posts
    sites/
      [STATION].html    × 56 monitoring site pages
    css/style.css       (already written separately)
    images/             (copied from archive/images/)
"""

import re
import json
import shutil
import warnings
from pathlib import Path
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR     = Path(__file__).resolve().parent.parent
ARCHIVE_HTML = BASE_DIR / "archive" / "html"
ARCHIVE_IMG  = BASE_DIR / "archive" / "images"
AUDIT_DIR    = BASE_DIR / "archive" / "audit"
SITE_DIR     = BASE_DIR / "site"
SITE_IMG     = SITE_DIR / "images"
SITE_CSS     = SITE_DIR / "css"

# ---------------------------------------------------------------------------
# Blog posts to include (recent + notable)
# ---------------------------------------------------------------------------
BLOG_POSTS = [
    "2024-2025-field-season-progress",
    "field-season-preparations-by-david-saddler",
    "field-season-training-by-david-saddler",
    "sharing-science-by-david-saddler",
    "greenland-gps-study-gnet-highlights-the-importance-of-a-dense-antarctic-gps-network",
    # 2014 Eric Kendrick field diaries — optional, included for now
    "heading-south-to-head-home-by-eric-kendrick",
    "howard-nunatak-vist-by-eric-kendrick",
    "wilson-nunatak-maintenance-vist-by-eric-kendrick",
    "visit-to-butcher-ridge-by-eric-kendrick",
    "installing-sites-in-northern-victoria-land-by-eric-kendrick",
    "iris-intern",
]

# ---------------------------------------------------------------------------
# HTML template helpers
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    ("Home",              "../index.html"),
    ("About",             "../about.html"),
    ("Sites and Data",    "../sites.html"),
    ("Photos",            "../photos.html"),
    ("Publications",      "../publications.html"),
    ("Training Schools",  "../training-schools.html"),
    ("Blog",              "../blog/index.html"),
]


def nav_html(active: str, depth: int = 0) -> str:
    prefix = "../" * depth
    items = []
    for label, href in NAV_ITEMS:
        adjusted = prefix + href.lstrip("../") if depth else href.lstrip("../")
        cls = ' class="active"' if label == active else ""
        items.append(f'<li{cls}><a href="{adjusted}">{label}</a></li>')
    return "<ul>\n      " + "\n      ".join(items) + "\n    </ul>"


def page(title: str, active: str, body: str, depth: int = 0) -> str:
    prefix   = "../" * depth
    css_path = f"{prefix}css/style.css"
    logo_src = f"{prefix}images/polenet2.jpg"
    fb_src   = f"{prefix}images/facebook.png"
    yt_src   = f"{prefix}images/youtube.png"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | POLENET: The Polar Earth Observing Network</title>
  <link rel="stylesheet" href="{css_path}">
</head>
<body>

<header id="site-header">
  <div id="header-inner">
    <div id="logo">
      <a href="{prefix}index.html">
        <img src="{logo_src}" alt="POLENET logo">
        <span class="site-name">POLENET
          <span class="site-tagline">The Polar Earth Observing Network</span>
        </span>
      </a>
    </div>
    <nav id="main-nav">
      {nav_html(active, depth)}
    </nav>
  </div>
</header>

<main id="page-content">
  <div class="container">
{body}
  </div>
</main>

<footer id="site-footer">
  <div class="footer-inner">
    <div>© POLENET — The Polar Earth Observing Network</div>
    <div class="footer-links">
      <a href="{prefix}about.html">About</a>
      <a href="{prefix}sites.html">Sites</a>
      <a href="{prefix}publications.html">Publications</a>
      <a href="{prefix}blog/index.html">Blog</a>
    </div>
    <div class="social-icons">
      <a href="https://www.facebook.com/polenet" target="_blank" rel="noopener">
        <img src="{fb_src}" alt="Facebook">
      </a>
      <a href="https://www.youtube.com/user/polenet" target="_blank" rel="noopener">
        <img src="{yt_src}" alt="YouTube">
      </a>
    </div>
  </div>
</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# Content extraction helpers
# ---------------------------------------------------------------------------

def load(slug: str) -> BeautifulSoup:
    path = ARCHIVE_HTML / f"{slug}.html"
    return BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")


def main_content(soup: BeautifulSoup) -> BeautifulSoup | None:
    return soup.select_one(".entry-content, .post-content, #content, .page-content, article")


def clean_html(el) -> str:
    """Strip Wayback Machine wrappers and WordPress cruft from content HTML."""
    if el is None:
        return "<p>Content not available.</p>"
    html = str(el)
    # Remove Wayback Machine URL prefix from href/src
    html = re.sub(
        r'https?://web\.archive\.org/web/\d+[^/]*/https?://',
        'https://',
        html
    )
    html = re.sub(
        r'https?://web\.archive\.org/web/\d+[^/]*/http://',
        'http://',
        html
    )
    # Remove Wayback banner scripts/styles
    html = re.sub(r'<script[^>]*web-static\.archive\.org[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    return html


def page_text(soup: BeautifulSoup, el) -> str:
    """Get clean inner HTML of a content element."""
    if el is None:
        return "<p>Content not available.</p>"
    # Remove known WP noise inside content
    for tag in el.find_all(class_=re.compile("sharedaddy|wpcnt|post-nav|post-footer|comments|wp-block-comment")):
        tag.decompose()
    # Remove WordPress comment form, Akismet fields, and respond section
    for tag in el.find_all(id=re.compile("respond|comments|akismet", re.I)):
        tag.decompose()
    for tag in el.find_all(class_=re.compile("comment|akismet", re.I)):
        tag.decompose()
    for tag in el.find_all("form"):
        tag.decompose()
    # Remove hidden inputs and akismet honeypot fields
    for tag in el.find_all(attrs={"name": re.compile("akismet|ak_", re.I)}):
        tag.decompose()
    for tag in el.find_all(attrs={"id": re.compile("akismet|ak_js", re.I)}):
        # Remove the parent <p> if it's the akismet container
        parent = tag.parent
        if parent and parent.name == "p" and parent.get("style","") and "display" in parent.get("style",""):
            parent.decompose()
        else:
            tag.decompose()
    # Fix image src attributes (strip Wayback wrapper, fix relative paths)
    for img in el.find_all("img"):
        src = img.get("src", "")
        m = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/https?://[^/]+(/wp-content/uploads/.+?)(?:\?|$)', src)
        if m:
            fname = Path(m.group(1)).name.split("?")[0]
            img["src"] = f"../images/{fname}"
            img["loading"] = "lazy"
        elif "wp-content" in src:
            fname = Path(src).name.split("?")[0]
            img["src"] = f"../images/{fname}"
            img["loading"] = "lazy"
    # Fix internal anchor hrefs
    for a in el.find_all("a", href=True):
        href = a["href"]
        # Strip Wayback wrapper
        m = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/https?://polenet\.org(/[^"]*)', href)
        if m:
            a["href"] = m.group(1)
    return el.decode_contents()


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_home():
    soup   = load("home")
    banner = soup.find("img", src=re.compile("home_page|group_photo"))
    banner_html = ""
    if banner:
        src = banner.get("src", "")
        m = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/https?://[^/]+(/wp-content/uploads/.+?)(?:\?|$)', src)
        fname = Path(m.group(1)).name if m else Path(src).name
        fname = fname.split("?")[0]
        banner_html = f"""
    <div class="hero">
      <img src="images/{fname}" alt="POLENET field team">
    </div>"""

    content_el = main_content(soup)
    # Extract homepage intro paragraph(s) before the blog posts
    intro_html = ""
    if content_el:
        paras = content_el.find_all("p", limit=3)
        intro_html = "".join(str(p) for p in paras if p.get_text(strip=True))
        intro_html = clean_html(intro_html)

    # Recent blog posts for homepage
    post_items = ""
    for slug in BLOG_POSTS[:4]:
        try:
            ps = load(slug)
            t  = ps.title.text if ps.title else slug
            t  = re.sub(r'\s*\|.*$', '', t).strip()
            date_el = ps.select_one('.entry-date, time, .post-date')
            date_str = date_el.text.strip() if date_el else ""
            excerpt_el = ps.select_one(".entry-content p, .post-content p")
            excerpt = excerpt_el.get_text(strip=True)[:180] + "…" if excerpt_el else ""
            post_items += f"""
        <li>
          <div class="post-title"><a href="blog/{slug}.html">{t}</a></div>
          <div class="post-meta">{date_str}</div>
          <div class="post-excerpt">{excerpt}</div>
        </li>"""
        except FileNotFoundError:
            continue

    body = f"""{banner_html}
    <div style="padding-top:2.5rem;">
      <h1 class="page-title">Investigating the polar regions from the inside out</h1>
      <div class="entry-body">
        {intro_html}
        <p><a href="about.html">Learn more about POLENET →</a></p>
      </div>

      <h2 class="page-title" style="margin-top:2.5rem;font-size:1.25rem;">Recent Updates</h2>
      <ul class="post-list">{post_items}
      </ul>
      <p style="margin-top:1rem;font-family:var(--font-ui);font-size:.875rem;">
        <a href="blog/index.html">View all blog posts →</a>
      </p>
    </div>"""

    out = SITE_DIR / "index.html"
    out.write_text(page("Home", "Home", body, depth=0), encoding="utf-8")
    print(f"  ✓ {out.relative_to(SITE_DIR)}")


def build_simple_page(slug: str, title: str, nav_label: str):
    soup  = load(slug)
    el    = main_content(soup)
    inner = page_text(soup, el)
    # Fix image paths (relative within same directory)
    inner = inner.replace("../images/", "images/")
    body  = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{inner}</div>"""
    out = SITE_DIR / f"{slug}.html"
    out.write_text(page(title, nav_label, body, depth=0), encoding="utf-8")
    print(f"  ✓ {out.relative_to(SITE_DIR)}")


def build_publications():
    soup = load("publications")
    el   = main_content(soup)
    if el:
        # Wrap year headings in our pub-year class
        for h in el.find_all(["h1","h2","h3","h4"]):
            t = h.get_text(strip=True)
            if re.match(r'^20\d{2}$', t):
                h.name = "h2"
                h["class"] = ["pub-year"]
        # Wrap paragraphs of citations into a pub-list
        inner = page_text(soup, el)
    else:
        inner = "<p>Publications list not available.</p>"
    inner = inner.replace("../images/", "images/")
    body  = f"""
    <h1 class="page-title">Publications</h1>
    <div class="entry-body">{inner}</div>"""
    out = SITE_DIR / "publications.html"
    out.write_text(page("Publications", "Publications", body, depth=0), encoding="utf-8")
    print(f"  ✓ publications.html")


def build_sites():
    """Sites and Data — overview table + links to individual site pages."""
    site_data = json.loads((AUDIT_DIR / "site_index.json").read_text())
    # Filter to real monitoring sites (have station_id)
    real_sites = [s for s in site_data if s.get("station_id") and len(s["station_id"]) <= 6]
    real_sites.sort(key=lambda x: x["station_id"])

    rows = ""
    for s in real_sites:
        sid   = s["station_id"]
        title = s.get("title", sid)
        coord = s.get("coordinate", "")
        inst  = s.get("installed", "")
        rows += f"""
      <tr>
        <td><a href="sites/{sid}.html">{sid}</a></td>
        <td><a href="sites/{sid}.html">{title}</a></td>
        <td>{coord}</td>
        <td>{inst}</td>
      </tr>"""

    # Also pull the intro text from the archived sites.html
    soup = load("sites")
    intro_el = main_content(soup)
    intro_paras = ""
    if intro_el:
        for p in intro_el.find_all("p", limit=2):
            t = p.get_text(strip=True)
            if t and len(t) > 40:
                intro_paras += f"<p>{t}</p>\n"

    body = f"""
    <h1 class="page-title">Sites and Data</h1>
    <div class="sites-intro">{intro_paras or '<p>POLENET operates a network of geophysical monitoring stations across Antarctica and Greenland.</p>'}</div>
    <div class="sites-table-wrap">
      <table class="sites-table">
        <thead>
          <tr>
            <th>Station ID</th>
            <th>Site Name</th>
            <th>Coordinates</th>
            <th>Installed</th>
          </tr>
        </thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div>"""

    out = SITE_DIR / "sites.html"
    out.write_text(page("Sites and Data", "Sites and Data", body, depth=0), encoding="utf-8")
    print(f"  ✓ sites.html  ({len(real_sites)} stations)")
    return real_sites


def build_site_detail_pages(real_sites):
    """Generate one HTML page per monitoring station."""
    sites_dir = SITE_DIR / "sites"
    sites_dir.mkdir(exist_ok=True)

    site_data = json.loads((AUDIT_DIR / "site_index.json").read_text())
    by_id = {s["station_id"]: s for s in site_data if s.get("station_id")}

    for s in real_sites:
        sid   = s["station_id"]
        title = s.get("title", sid)
        fname = s.get("file","")

        # Load the archived HTML for the description text
        desc_html = ""
        img_html  = ""
        try:
            src_path = ARCHIVE_HTML / fname
            if src_path.exists():
                psoup = BeautifulSoup(src_path.read_text(encoding="utf-8", errors="replace"), "lxml")
                el = main_content(psoup)
                if el:
                    # Remove the structured field table/spans — keep narrative text
                    paras = [p for p in el.find_all("p") if p.get_text(strip=True) and len(p.get_text(strip=True)) > 30]
                    desc_html = "".join(str(p) for p in paras)
                    desc_html = clean_html(desc_html)
                # Look for a photo matching station ID
                img_candidates = list(ARCHIVE_IMG.glob(f"{sid}-*.jpg")) + list(ARCHIVE_IMG.glob(f"{sid}_*.jpg"))
                if not img_candidates:
                    img_candidates = list(ARCHIVE_IMG.glob(f"{sid}*.jpg"))
                if img_candidates:
                    img_fname = img_candidates[0].name
                    img_html = f'<div class="site-photo"><img src="../../images/{img_fname}" alt="{title}" loading="lazy"></div>'
        except Exception:
            pass

        def row(label, val):
            if not val:
                return ""
            return f"<tr><th>{label}</th><td>{val}</td></tr>"

        meta_rows = (
            row("Station ID",     sid) +
            row("Coordinates",    s.get("coordinate","")) +
            row("Installed",      s.get("installed","")) +
            row("Former Projects",s.get("former_projects","")) +
            row("Former Names",   s.get("former_names","")) +
            row("Transportation", s.get("transport","")) +
            row("Nearest Hub",    s.get("hub",""))
        )

        grid_class = "site-detail-grid" if img_html else ""
        body = f"""
    <a class="back-link" href="../sites.html">Back to all sites</a>
    <h1 class="page-title">{title}</h1>
    <div class="{grid_class}">
      <div>
        <table class="site-meta-table">{meta_rows}</table>
      </div>
      {img_html}
      {'<div class="site-description">' + desc_html + '</div>' if desc_html else ''}
    </div>"""

        out = sites_dir / f"{sid}.html"
        out.write_text(page(title, "Sites and Data", body, depth=2), encoding="utf-8")

    print(f"  ✓ sites/{{}}.html  ({len(real_sites)} pages generated)".format("*"))


def build_photos():
    """Photo gallery with GLightbox."""
    # Collect gallery images: full-size images from gallery folder
    gallery_imgs = sorted(ARCHIVE_IMG.glob("*.jpg"))
    # Exclude known non-gallery images
    exclude = {"facebook.png","youtube.png","polenet2.jpg","touch-icon.png"}
    exclude_patterns = ["home_page","group_photo","photos.jpg","72.jpg"]
    gallery_imgs = [
        f for f in gallery_imgs
        if f.name not in exclude and not any(p in f.name for p in exclude_patterns)
        and not f.name.startswith("thumbs_")
    ]

    grid_items = ""
    for img in gallery_imgs:
        grid_items += f"""
      <a href="../images/{img.name}" class="glightbox" data-gallery="polenet">
        <img src="../images/{img.name}" alt="" loading="lazy">
      </a>"""

    body = f"""
    <h1 class="page-title">Photos</h1>
    <p class="gallery-intro">Field photos from POLENET monitoring station installations and operations across Antarctica and Greenland.</p>
    <div class="photo-grid">{grid_items}
    </div>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css">
    <script src="https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js"></script>
    <script>GLightbox({{ selector: '.glightbox' }});</script>"""

    out = SITE_DIR / "photos.html"
    out.write_text(page("Photos", "Photos", body, depth=0), encoding="utf-8")
    print(f"  ✓ photos.html  ({len(gallery_imgs)} images in gallery)")


def build_training_schools():
    """Training Schools index + individual school pages."""
    training_slugs = [
        ("2023-gia-training-school",  "2023 GIA Training School"),
        ("2019-gia-training-school",  "2019 GIA Training School"),
        ("2017-glacial-seismology-training-school", "2017 Glacial Seismology Training School"),
        ("2015-gia-training-school",  "2015 GIA Training School"),
        ("2025-gia-workshop",         "2025 GIA Workshop"),
        ("glacial-isostatic-adjustment-training-school-virtual-participation-is-now-open",
         "GIA Training School — Virtual Participation"),
    ]

    cards = ""
    for slug, label in training_slugs:
        try:
            ts = load(slug)
            t  = ts.title.text if ts.title else label
            t  = re.sub(r'\s*\|.*$', '', t).strip()
            excerpt_el = ts.select_one(".entry-content p, .post-content p")
            excerpt = excerpt_el.get_text(strip=True)[:180] + "…" if excerpt_el else ""
            cards += f"""
      <li class="training-card">
        <h3><a href="training/{slug}.html">{t}</a></h3>
        <div class="meta">{excerpt}</div>
      </li>"""
        except FileNotFoundError:
            continue

    body = f"""
    <h1 class="page-title">Training Schools</h1>
    <p class="sites-intro">POLENET hosts training schools and workshops focused on glacial isostatic adjustment, seismology, and polar geodesy.</p>
    <ul class="training-list">{cards}
    </ul>"""

    out = SITE_DIR / "training-schools.html"
    out.write_text(page("Training Schools", "Training Schools", body, depth=0), encoding="utf-8")
    print(f"  ✓ training-schools.html")

    # Individual training school pages
    training_dir = SITE_DIR / "training"
    training_dir.mkdir(exist_ok=True)
    for slug, label in training_slugs:
        try:
            ts    = load(slug)
            el    = main_content(ts)
            inner = page_text(ts, el)
            inner = re.sub(r'\.\./images/', '../../images/', inner)
            inner = inner.replace("../images/", "../../images/")
            t = ts.title.text if ts.title else label
            t = re.sub(r'\s*\|.*$', '', t).strip()
            bdy = f"""
    <a class="back-link" href="../training-schools.html">Back to Training Schools</a>
    <h1 class="page-title">{t}</h1>
    <div class="entry-body">{inner}</div>"""
            (training_dir / f"{slug}.html").write_text(
                page(t, "Training Schools", bdy, depth=2), encoding="utf-8"
            )
        except FileNotFoundError:
            continue
    print(f"  ✓ training/*.html  ({len(training_slugs)} pages)")


def build_blog():
    blog_dir = SITE_DIR / "blog"
    blog_dir.mkdir(exist_ok=True)

    index_items = ""
    built = 0
    for slug in BLOG_POSTS:
        try:
            bs   = load(slug)
            t    = bs.title.text if bs.title else slug
            t    = re.sub(r'\s*\|.*$', '', t).strip()
            date_el = bs.select_one(".entry-date, time, .post-date, .published")
            date_str = date_el.text.strip() if date_el else ""
            el   = main_content(bs)
            inner = page_text(bs, el)
            inner = re.sub(r'\.\./images/', '../../images/', inner)
            inner = inner.replace("../images/", "../../images/")
            excerpt_el = bs.select_one(".entry-content p, .post-content p")
            excerpt = excerpt_el.get_text(strip=True)[:200] + "…" if excerpt_el else ""

            bdy = f"""
    <a class="back-link" href="index.html">Back to Blog</a>
    <div class="post-header">
      <h1>{t}</h1>
      <div class="post-meta">{date_str}</div>
    </div>
    <div class="entry-body">{inner}</div>"""
            (blog_dir / f"{slug}.html").write_text(
                page(t, "Blog", bdy, depth=2), encoding="utf-8"
            )
            index_items += f"""
      <li>
        <div class="post-title"><a href="{slug}.html">{t}</a></div>
        <div class="post-meta">{date_str}</div>
        <div class="post-excerpt">{excerpt}</div>
      </li>"""
            built += 1
        except FileNotFoundError:
            continue

    index_body = f"""
    <h1 class="page-title">Blog</h1>
    <ul class="post-list">{index_items}
    </ul>"""
    (blog_dir / "index.html").write_text(
        page("Blog", "Blog", index_body, depth=2), encoding="utf-8"
    )
    print(f"  ✓ blog/index.html + {built} post pages")


def copy_images():
    SITE_IMG.mkdir(exist_ok=True)
    copied = 0
    for f in ARCHIVE_IMG.iterdir():
        dest = SITE_IMG / f.name
        if not dest.exists():
            shutil.copy2(f, dest)
            copied += 1
    print(f"  ✓ images/ — {copied} files copied ({len(list(SITE_IMG.iterdir()))} total)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  polenet.org Site Builder  |  Step 4")
    print("=" * 55)

    # Ensure output dirs exist
    SITE_DIR.mkdir(exist_ok=True)
    SITE_CSS.mkdir(exist_ok=True)

    # Copy images first (needed by all pages)
    print("\n[Images]")
    copy_images()

    # Build all pages
    print("\n[Pages]")
    build_home()
    build_simple_page("about",  "About", "About")
    build_publications()
    build_sites_result = build_sites()
    build_site_detail_pages(build_sites_result)
    build_photos()
    build_training_schools()
    build_blog()

    print("\n" + "=" * 55)
    print("Build complete.")
    print(f"Output → {SITE_DIR}")
    print("Open site/index.html in a browser to review.")
    print("=" * 55)


if __name__ == "__main__":
    main()
