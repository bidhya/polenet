#!/usr/bin/env python3
"""
build_site.py — Step 4/6: Generate the static polenet.org website.

Reads from:
  archive/html/     — Wayback Machine archived pages (fallback for some content)
  archive/xml/      — WordPress WXR export JSON (primary source for posts, pages)
  archive/audit/    — site_index.json (station metadata)

Outputs:
  site/             — full static site ready for Netlify

Usage:
  python build_site.py
  (run scraper/parse_xml.py first to generate archive/xml/)
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
XML_DIR      = BASE_DIR / "archive" / "xml"
SITE_DIR     = BASE_DIR / "site"
SITE_IMG     = SITE_DIR / "images"
SITE_CSS     = SITE_DIR / "css"

# ---------------------------------------------------------------------------
# XML data (populated in main)
# ---------------------------------------------------------------------------
XML_PAGES: dict = {}  # slug → page dict
XML_POSTS: list = []  # all published posts, chronological

# Extra pages to build from XML (not in the main nav)
# Each entry: (slug, title, nav_label_for_active_highlight)
EXTRA_PAGES = [
    ("in-the-news",                      "In the News",               "About"),
    ("data",                             "Data",                      "Sites and Data"),
    ("meet-the-researchers",             "Meet the Researchers",      "About"),
    ("quick-facts",                      "Quick Facts",               "About"),
    ("links",                            "Links",                     "About"),
    ("2025-2026-field-season-progress-page", "2025-2026 Field Season Progress", "Blog"),
    ("2024-2025-field-season-progress",  "2024-2025 Field Season Progress", "Blog"),
    ("2023-2024-field-season-progress",  "2023-2024 Field Season Progress", "Blog"),
    # Full-text press reprints — linked from in-the-news.html "Read more »" links,
    # which pointed at these page_ids but the pages themselves were never built.
    ("researchers-brave-antarcticas-wind-chill-to-track-climate-change-at-the-bottom-of-the-world",
     "Researchers brave Antarctica's wind, chill, to track climate change at the bottom of the world", "About"),
    ("plane-crash-wont-keep-osu-scientist-off-the-ice",
     "Plane crash won't keep OSU scientist off the ice", "About"),
    ("scientists-explore-ice-caps",
     "Scientists explore ice caps", "About"),
]

# Training school pages — module level so the page_id link resolver (below) can see them.
TRAINING_SLUGS = [
    ("2023-gia-training-school",  "2023 GIA Training School"),
    ("2019-gia-training-school",  "2019 GIA Training School"),
    ("2017-glacial-seismology-training-school", "2017 Glacial Seismology Training School"),
    ("2015-gia-training-school",  "2015 GIA Training School"),
    ("2025-gia-workshop",         "2025 GIA Workshop"),
    ("glacial-isostatic-adjustment-training-school-virtual-participation-is-now-open",
     "GIA Training School — Virtual Participation"),
]

# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

# WordPress shortcodes (theme-specific) — strip on output
_WP_SHORTCODE = re.compile(r'\[/?[a-zA-Z_][a-zA-Z0-9_-]*[^\]]*\]')
# Internal polenet.org links that we know how to rewrite
_POLENET_LINK = re.compile(
    r'href="https?://(?:www\.)?polenet\.org/([^"/?#][^"/?#]*?)/?"'
)
_POLENET_HOME = re.compile(
    r'href="https?://(?:www\.)?polenet\.org/?"'
)
# WordPress "?page_id=N" links — resolved against ID_TO_PATH (built in build_id_to_path())
_PAGE_ID_LINK = re.compile(
    r'<a([^>]*?)\shref="https?://(?:www\.)?polenet\.org/\?page_id=(\d+)"([^>]*)>(.*?)</a>',
    re.DOTALL
)
# Any other internal polenet.org link we couldn't resolve to a built page
_POLENET_UNRESOLVED = re.compile(
    r'<a[^>]*\shref="https?://(?:www\.)?polenet\.org/[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL
)

# wp:post_id -> site-relative output path (e.g. "blog/foo.html"), for resolving
# internal "?page_id=N" links. Populated by build_id_to_path() before any page is built.
ID_TO_PATH: dict = {}


def build_id_to_path():
    """Map WordPress post/page IDs to the relative path we actually build them at."""
    global ID_TO_PATH
    ID_TO_PATH = {}
    for post in XML_POSTS:
        pid = post.get('id')
        if pid:
            ID_TO_PATH[pid] = f"blog/{post['slug']}.html"
    for slug, _label in TRAINING_SLUGS:
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = f"training/{slug}.html"
    for slug, _title, _nav in EXTRA_PAGES:
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = f"{slug}.html"
    for slug in ("about", "publications"):
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = f"{slug}.html"


def xml_to_html(content: str, depth: int = 0) -> str:
    """
    Prepare XML-parsed page/post content for use at a given site depth.

    - depth=0: root pages (index.html, about.html, ...)
    - depth=2: subdirectory pages (blog/x.html, sites/x.html, ...)

    Actions:
    - Rewrite src="images/..." and href="images/..." for the correct depth
    - Strip WordPress shortcodes (e.g. [two_thirds], [/one_half])
    - Rewrite internal polenet.org links to local relative paths
    - Resolve "?page_id=N" links to the real local page where we know it (ID_TO_PATH);
      unwrap (keep text, drop the link) anything we can't resolve rather than
      leaving a fake href="#"
    """
    if not content:
        return ''

    prefix = '../' * depth

    # Adjust image paths
    if depth > 0:
        content = content.replace('src="images/', f'src="{prefix}images/')
        content = content.replace('href="images/', f'href="{prefix}images/')

    # Strip WordPress shortcodes
    content = _WP_SHORTCODE.sub('', content)

    # Rewrite internal polenet.org links (slug/page-name form)
    def rewrite_polenet_link(m):
        raw_slug = m.group(1).rstrip('/')
        return f'href="{prefix}{raw_slug}.html"'
    content = _POLENET_LINK.sub(rewrite_polenet_link, content)
    content = _POLENET_HOME.sub(f'href="{prefix}index.html"', content)

    # Resolve "?page_id=N" links against known built pages
    def resolve_page_id(m):
        pre, pid, post, text = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        target = ID_TO_PATH.get(pid)
        if target:
            return f'<a{pre} href="{prefix}{target}"{post}>{text}</a>'
        return text  # unresolved — unwrap rather than link to nowhere
    content = _PAGE_ID_LINK.sub(resolve_page_id, content)

    # Any other unresolved internal polenet.org link — unwrap rather than leave a dead '#'
    content = _POLENET_UNRESOLVED.sub(lambda m: m.group(1), content)

    return content


def load_xml_data():
    """Load XML-parsed JSON data into module globals."""
    global XML_PAGES, XML_POSTS
    pages_file = XML_DIR / 'pages.json'
    posts_file = XML_DIR / 'posts.json'
    if pages_file.exists():
        data = json.loads(pages_file.read_text(encoding='utf-8'))
        XML_PAGES = {p['slug']: p for p in data}
    if posts_file.exists():
        XML_POSTS = json.loads(posts_file.read_text(encoding='utf-8'))
    print(f"  XML: {len(XML_PAGES)} pages, {len(XML_POSTS)} posts loaded")


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
    # Rewrite polenet.org/wp-content/uploads/ image srcs to local images/
    # Use [^"]+ to match any number of subdirectory levels (e.g. 2024/12/filename.jpg)
    html = re.sub(
        r'src="https?://(?:www\.)?polenet\.org/wp-content/uploads/(?:[^"]+/)*([^/"]+\.[a-zA-Z]{3,4})(?:\?[^"]*?)?"',
        lambda m: f'src="images/{m.group(1)}"',
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
    # Remove video blocks — videos were not archived and won't load
    for tag in el.find_all(class_=re.compile("wp-block-video", re.I)):
        tag.decompose()
    for tag in el.find_all("video"):
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
    # Also strip srcset — we use single images, not responsive sets
    for img in el.find_all("img"):
        img.attrs.pop("srcset", None)
        img.attrs.pop("sizes", None)
        src = img.get("src", "")
        # Remove useless external images (comment avatars, mail embeds)
        if any(x in src for x in ["gstatic.com", "gravatar.com", "mail.google.com", "wp-includes/images/smilies"]):
            img.decompose()
            continue
        m = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/https?://[^/]+(/wp-content/uploads/.+?)(?:\?|$)', src)
        if m:
            fname = Path(m.group(1)).name.split("?")[0]
            img["src"] = f"../images/{fname}"
            img["loading"] = "lazy"
        elif "wp-content" in src:
            fname = Path(src).name.split("?")[0]
            img["src"] = f"../images/{fname}"
            img["loading"] = "lazy"
    # Fix anchor hrefs — strip Wayback wrapper from all links
    for a in el.find_all("a", href=True):
        href = a["href"]
        # Internal polenet.org links → relative path
        m = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/https?://(?:www\.)?polenet\.org(/[^"]*)', href)
        if m:
            internal_path = m.group(1)
            # If this <a> wraps only an <img> and links to a wp-content image, unwrap it
            children = [c for c in a.children if str(c).strip()]
            if len(children) == 1 and getattr(children[0], 'name', None) == 'img' and '/wp-content/' in internal_path:
                a.unwrap()
            else:
                a["href"] = internal_path
            continue
        # External links still wrapped in Wayback → unwrap to real URL
        m2 = re.search(r'https?://web\.archive\.org/web/\d+[^/]*/(https?://.*)', href)
        if m2:
            a["href"] = m2.group(1)
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

    # Recent blog posts for homepage — use XML posts (newest first)
    post_items = ""
    recent_posts = list(reversed(XML_POSTS))[:4]  # 4 most recent
    for post in recent_posts:
        slug = post['slug']
        t    = post['title']
        date_str = post.get('date', '')
        # Extract first paragraph as excerpt (strip HTML tags)
        soup_ex = BeautifulSoup(post.get('content', ''), 'lxml')
        first_p = soup_ex.find('p')
        excerpt = (first_p.get_text(strip=True)[:200] + '…') if first_p else ''
        post_items += f"""
        <li>
          <div class="post-title"><a href="blog/{slug}.html">{t}</a></div>
          <div class="post-meta">{date_str}</div>
          <div class="post-excerpt">{excerpt}</div>
        </li>"""

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
    # Prefer XML content over Wayback HTML
    page_data = XML_PAGES.get(slug)
    if page_data and page_data['has_content']:
        inner = xml_to_html(page_data['content'], depth=0)
        body  = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{inner}</div>"""
    else:
        soup  = load(slug)
        el    = main_content(soup)
        inner = page_text(soup, el)
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
    training_slugs = TRAINING_SLUGS

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
        title_text = None
        inner = None
        # Prefer XML content
        page_data = XML_PAGES.get(slug)
        if page_data and page_data['has_content']:
            inner = xml_to_html(page_data['content'], depth=2)
            title_text = label
        else:
            try:
                ts    = load(slug)
                el    = main_content(ts)
                inner = page_text(ts, el)
                inner = re.sub(r'\.\./images/', '../../images/', inner)
                t = ts.title.text if ts.title else label
                title_text = re.sub(r'\s*\|.*$', '', t).strip()
            except FileNotFoundError:
                continue
        if inner is None:
            continue
        t = title_text or label
        bdy = f"""
    <a class="back-link" href="../training-schools.html">Back to Training Schools</a>
    <h1 class="page-title">{t}</h1>
    <div class="entry-body">{inner}</div>"""
        (training_dir / f"{slug}.html").write_text(
            page(t, "Training Schools", bdy, depth=2), encoding="utf-8"
        )
    print(f"  ✓ training/*.html  ({len(training_slugs)} pages)")


def build_blog():
    blog_dir = SITE_DIR / "blog"
    # Clear stale HTML files before regenerating
    if blog_dir.exists():
        for old in blog_dir.glob("*.html"):
            old.unlink()
    blog_dir.mkdir(exist_ok=True)

    # Use all XML posts (newest first for index)
    posts_desc = list(reversed(XML_POSTS))

    index_items = ""
    built = 0
    for post in posts_desc:
        slug     = post['slug']
        title    = post['title']
        date_str = post.get('date', '')
        content  = xml_to_html(post.get('content', ''), depth=2)

        # Excerpt from first non-empty paragraph
        soup_ex   = BeautifulSoup(content, 'lxml')
        first_p   = soup_ex.find('p')
        excerpt   = (first_p.get_text(strip=True)[:200] + '…') if first_p else ''

        bdy = f"""
    <a class="back-link" href="index.html">Back to Blog</a>
    <div class="post-header">
      <h1>{title}</h1>
      <div class="post-meta">{date_str}</div>
    </div>
    <div class="entry-body">{content}</div>"""
        (blog_dir / f"{slug}.html").write_text(
            page(title, "Blog", bdy, depth=2), encoding="utf-8"
        )
        index_items += f"""
      <li>
        <div class="post-title"><a href="{slug}.html">{title}</a></div>
        <div class="post-meta">{date_str}</div>
        <div class="post-excerpt">{excerpt}</div>
      </li>"""
        built += 1

    index_body = f"""
    <h1 class="page-title">Blog</h1>
    <ul class="post-list">{index_items}
    </ul>"""
    (blog_dir / "index.html").write_text(
        page("Blog", "Blog", index_body, depth=2), encoding="utf-8"
    )
    print(f"  ✓ blog/index.html + {built} post pages")


def build_extra_pages():
    """Build extra pages from XML that don't appear in the main nav."""
    built = 0
    for slug, title, nav_label in EXTRA_PAGES:
        page_data = XML_PAGES.get(slug)
        if not page_data:
            print(f"  ○ skipped (not in XML): {slug}")
            continue
        content = xml_to_html(page_data['content'], depth=0)
        body = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{content}</div>"""
        out = SITE_DIR / f"{slug}.html"
        out.write_text(page(title, nav_label, body, depth=0), encoding="utf-8")
        print(f"  ✓ {slug}.html")
        built += 1
    print(f"  ({built} extra pages built)")


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
    print("  polenet.org Site Builder  |  Step 4/6")
    print("=" * 55)

    # Ensure output dirs exist
    SITE_DIR.mkdir(exist_ok=True)
    SITE_CSS.mkdir(exist_ok=True)

    # Load XML data first
    print("\n[XML data]")
    load_xml_data()
    build_id_to_path()

    # Copy images
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

    # Extra pages from XML (field season, in-the-news, data, etc.)
    print("\n[Extra pages from XML]")
    build_extra_pages()

    print("\n" + "=" * 55)
    print("Build complete.")
    print(f"Output → {SITE_DIR}")
    print("Open site/index.html in a browser to review.")
    print("=" * 55)


if __name__ == "__main__":
    main()
