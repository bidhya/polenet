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
from html import escape
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, XMLParsedAsHTMLWarning

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

# Absolute base URL of the deployed site, used only for sitemap.xml and robots.txt — the pages
# themselves stay entirely relative, so nothing else depends on this being right. Must end in a
# slash. Change this ONE line if the site ever moves to its own domain, then rebuild.
SITE_BASE_URL = "https://bidhya.github.io/polenet/"

# ---------------------------------------------------------------------------
# XML data (populated in main)
# ---------------------------------------------------------------------------
XML_PAGES: dict = {}  # slug → page dict
XML_POSTS: list = []  # all published posts, chronological

# Extra pages to build from XML (not in the main nav)
# Each entry: (slug, title, nav_label_for_active_highlight)
EXTRA_PAGES = [
    ("in-the-news",                      "In the News",               "In the News"),
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
     "Researchers brave Antarctica's wind, chill, to track climate change at the bottom of the world", "In the News"),
    ("plane-crash-wont-keep-osu-scientist-off-the-ice",
     "Plane crash won't keep OSU scientist off the ice", "In the News"),
    ("scientists-explore-ice-caps",
     "Scientists explore ice caps", "In the News"),
    # Training-school sub-pages — real published children of the top-level training
    # school pages (course content, agendas, photo pages, etc.) that the parent pages
    # already link to, but that were never built. Built at site root (not under
    # training/) because the existing links to them (rewritten by _POLENET_LINK from
    # raw polenet.org/slug/ hrefs) already resolve to "../{slug}.html" — flat, same as
    # the press reprints above.
    ("2019-gia-training-school-course-work-preparation",
     "2019 GIA Training School - Course Content", "Training Schools"),
    ("2019-gia-training-school-virtual-participation",
     "2019 GIA Training School - Recorded Lectures", "Training Schools"),
    ("2019-gia-training-school-photos",
     "2019 GIA Training School Photos", "Training Schools"),
    ("2023-gia-training-school-course-content",
     "2023 GIA Training School Course Content", "Training Schools"),
    ("2023-gia-training-school-photos",
     "2023 GIA Training School Photos", "Training Schools"),
    ("2025-gia-workshop-code-of-conduct",
     "2025 GIA Workshop Code of Conduct", "Training Schools"),
    ("2025-gia-workshop-photos",
     "2025 GIA Workshop Photos", "Training Schools"),
    ("2025-gia-workshop-virtual-poster-gallery",
     "2025 GIA Workshop Virtual Poster Gallery", "Training Schools"),
    ("glacial-seismology-school-presentations",
     "Glacial Seismology School Presentations", "Training Schools"),
    ("glacial-seismology-training-school-agenda",
     "Glacial Seismology Training School Agenda", "Training Schools"),
    ("training-school-homework-exercises-and-preparation-materials",
     "Training School Homework Exercises and Preparation Materials", "Training Schools"),
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
# WordPress video blocks (e.g. <figure class="wp-block-video"><video controls src="images/x.mov"></video></figure>)
# Videos are intentionally excluded from the static rebuild (large files — see docs/discovery-log.md
# 2026-07-26 for the video-hosting strategy discussion); strip the whole block rather than leave a
# dangling reference to a file that copy_images() also deliberately skips.
_WP_VIDEO_BLOCK = re.compile(r'<figure[^>]*class="[^"]*wp-block-video[^"]*"[^>]*>.*?</figure>', re.DOTALL)
_VIDEO_TAG = re.compile(r'<video\b.*?</video>', re.DOTALL)

# Matches a YouTube video ID out of youtu.be/, youtube.com/watch?v=, /embed/, or /shorts/ URLs
_YOUTUBE_ID_RE = re.compile(r'(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})')


def _extract_youtube_id(url: str) -> str | None:
    """Pull an 11-char YouTube video ID out of any common paste format, or a bare ID."""
    if not url:
        return None
    url = url.strip()
    m = _YOUTUBE_ID_RE.search(url)
    if m:
        return m.group(1)
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', url):
        return url
    return None

# wp:post_id -> site-relative output path (e.g. "blog/foo.html"), for resolving
# internal "?page_id=N" links. Populated by build_id_to_path() before any page is built.
ID_TO_PATH: dict = {}

# slug -> site-relative output path, same coverage as ID_TO_PATH but keyed by slug —
# used by page_text() (the Wayback-fallback content path) to resolve internal
# polenet.org/{slug}/ links, since Wayback-archived content carries the permalink
# slug directly rather than a "?page_id=N" query string. Populated alongside ID_TO_PATH.
SLUG_TO_PATH: dict = {}

# Registry of every stripped video placement (page, filename, surrounding caption) —
# written to archive/xml/video_placements.json at the end of the build. Once video
# hosting is decided (docs/questions.md Q12), this is what makes swapping the strip-out
# for a real embed a fast, data-driven change instead of re-deriving from raw XML.
VIDEO_PLACEMENTS: list = []

# filename -> hosting URL (see docs/questions.md Q12). Loaded from archive/xml/video_url_map.json
# by load_video_url_map(). Blank/missing entries just keep stripping as before — safe to run
# with a partially-filled map, since uploads trickle in.
VIDEO_URL_MAP: dict = {}


def load_video_url_map():
    global VIDEO_URL_MAP
    map_file = XML_DIR / 'video_url_map.json'
    if map_file.exists():
        VIDEO_URL_MAP = json.loads(map_file.read_text(encoding='utf-8'))
    else:
        VIDEO_URL_MAP = {}
    filled = sum(1 for v in VIDEO_URL_MAP.values() if v)
    print(f"  Video URL map: {filled}/{len(VIDEO_URL_MAP)} filled in")


def build_id_to_path():
    """Map WordPress post/page IDs (and slugs) to the relative path we actually build them at."""
    global ID_TO_PATH, SLUG_TO_PATH
    ID_TO_PATH = {}
    SLUG_TO_PATH = {}
    for post in XML_POSTS:
        pid = post.get('id')
        target = f"blog/{post['slug']}.html"
        if pid:
            ID_TO_PATH[pid] = target
        SLUG_TO_PATH[post['slug']] = target
    for slug, _label in TRAINING_SLUGS:
        target = f"training/{slug}.html"
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = target
        SLUG_TO_PATH[slug] = target
    for slug, _title, _nav in EXTRA_PAGES:
        target = f"{slug}.html"
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = target
        SLUG_TO_PATH[slug] = target
    for slug in ("about", "publications"):
        target = f"{slug}.html"
        page_data = XML_PAGES.get(slug)
        if page_data and page_data.get('id'):
            ID_TO_PATH[page_data['id']] = target
        SLUG_TO_PATH[slug] = target
    # Other top-level nav pages, in case raw content ever links to them by slug
    SLUG_TO_PATH["sites"] = "sites.html"
    SLUG_TO_PATH["photos"] = "photos.html"
    SLUG_TO_PATH["training-schools"] = "training-schools.html"
    SLUG_TO_PATH["blog"] = "blog/index.html"
    # 6 monitoring stations that happened to get human-readable WordPress slugs
    # instead of the "home-page-id-XXXX" pattern (see docs/questions.md Q8) — they're
    # real built pages, just under their station ID, not their original slug.
    for slug, station_id in (
        ("gould-knoll", "GLDK"), ("lepley-nunatak", "LPLY"),
        ("martin-peninsula", "MRTP"), ("miller-crag", "MCRG"),
        ("mt-takahe", "MTAK"), ("slater-rocks-2", "SLTR"),
    ):
        SLUG_TO_PATH[slug] = f"sites/{station_id}.html"


def xml_to_html(content: str, depth: int = 0, page_slug: str = "") -> str:
    """
    Prepare XML-parsed page/post content for use at a given site depth.

    - depth=0: root pages (index.html, about.html, ...)
    - depth=1: subdirectory pages (blog/x.html, sites/x.html, ...)

    Actions:
    - Rewrite src="images/..." and href="images/..." for the correct depth
    - Strip WordPress shortcodes (e.g. [two_thirds], [/one_half])
    - Rewrite internal polenet.org links to local relative paths
    - Resolve "?page_id=N" links to the real local page where we know it (ID_TO_PATH);
      unwrap (keep text, drop the link) anything we can't resolve rather than
      leaving a fake href="#"
    - Strip video blocks, recording each one (page, filename, caption) into
      VIDEO_PLACEMENTS before removing it — see that global for why. If VIDEO_URL_MAP
      has a hosting URL for the file, emit a real embed instead of stripping to nothing.
    """
    if not content:
        return ''

    prefix = '../' * depth

    # Strip video blocks — videos are excluded from the static rebuild by default (see
    # _WP_VIDEO_BLOCK above). Record what's being removed and from where before it's gone;
    # if a hosting URL is already known for this file (VIDEO_URL_MAP, see docs/questions.md
    # Q12), emit a real embed instead of removing it.
    def _record_and_strip_video(m):
        block = m.group(0)
        fname_m = re.search(r'src="images/([^"]+)"', block)
        fname = fname_m.group(1) if fname_m else None
        after = content[m.end():m.end() + 300]
        cap_m = re.match(r'\s*<p>(.*?)</p>', after, re.DOTALL)
        caption = re.sub(r'<[^>]+>', '', cap_m.group(1)).strip() if cap_m else None
        VIDEO_PLACEMENTS.append({
            "page": page_slug,
            "video_file": fname,
            "archive_path": f"archive/images/videos/{fname}" if fname else None,
            "caption_after": caption or None,
        })
        url = VIDEO_URL_MAP.get(fname) if fname else None
        if url:
            yt_id = _extract_youtube_id(url)
            if yt_id:
                return (
                    '<figure class="wp-block-embed-youtube">'
                    f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{yt_id}" '
                    f'title="{fname}" frameborder="0" allowfullscreen loading="lazy"></iframe>'
                    '</figure>'
                )
            # URL present but not a recognizable YouTube link — fall back to a direct video tag
            return f'<figure class="wp-block-video"><video src="{url}" controls></video></figure>'
        return ''
    content = _WP_VIDEO_BLOCK.sub(_record_and_strip_video, content)
    content = _VIDEO_TAG.sub('', content)

    # Adjust image paths
    if depth > 0:
        content = content.replace('src="images/', f'src="{prefix}images/')
        content = content.replace('href="images/', f'href="{prefix}images/')

    # Strip WordPress shortcodes
    content = _WP_SHORTCODE.sub('', content)

    # Rewrite internal polenet.org links (slug/page-name form) against known built
    # pages. A slug we don't recognize is left untouched here rather than guessed at
    # (e.g. assumed to be a flat root page) — _POLENET_UNRESOLVED below will unwrap it
    # to plain text instead of leaving a link to a page that doesn't exist.
    def rewrite_polenet_link(m):
        raw_slug = m.group(1).rstrip('/')
        target = SLUG_TO_PATH.get(raw_slug)
        if target:
            return f'href="{prefix}{target}"'
        return m.group(0)
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
    ("In the News",       "../in-the-news.html"),
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


_DEFAULT_DESC = ("POLENET — The Polar Earth Observing Network: GPS and seismic observation of "
                 "the polar regions of Antarctica and Greenland.")


def meta_description(body: str) -> str:
    """Derive a search-result snippet from a page's own body content.

    Taken from the body rather than written by hand because there are 115 pages. Three things are
    dropped before the text is read: the <h1>, which repeats the <title> and would waste the
    snippet; <script>/<style>, so JavaScript never leaks in (the photo gallery's inline GLightbox
    call lives in the body); and a.back-link, the "Back to …" navigation that opens the body on 86
    pages and would otherwise begin every one of their snippets. Falls back to a site-level
    description when a page has too little prose to summarise.
    """
    soup = BeautifulSoup(body, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    for tag in soup.select("h1, a.back-link"):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    if len(text) < 40:
        text = _DEFAULT_DESC
    if len(text) > 155:
        text = text[:155].rsplit(" ", 1)[0].rstrip(" ,;:.—–-") + "…"
    return escape(text, quote=True)


# Footer social icons: intentionally absent — do not add them back.
#
# The previously linked social profiles are not maintained as part of this site, and the old
# URLs no longer resolve to anything the project publishes. Linking to them would send visitors
# somewhere unintended, so they were removed rather than updated. Any future social links should
# be written fresh, from destinations confirmed by the project team at that time.
#
# Deleted outright rather than commented out. An earlier pass kept the markup in a comment, and
# the stale URLs then shipped inside every generated page — where a later review mistook them
# for live links. Dead markup left "just in case" costs more confusion than it saves.
#
# site/images/facebook.png and youtube.png are deliberately left in place but unreferenced:
# removing them would change the committed asset count for no benefit. They stay in the gallery
# exclude list in build_photos() so they never surface in the photo grid.
def page(title: str, active: str, body: str, depth: int = 0) -> str:
    prefix   = "../" * depth
    css_path = f"{prefix}css/style.css"
    logo_src = f"{prefix}images/polenet2.jpg"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{meta_description(body)}">
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
      <a href="{prefix}links.html">Links</a>
      <span class="site-credit"><a href="https://bidhya.github.io/" target="_blank" rel="noopener">Webmaster</a></span>
    </div>
    <!-- No social icons here by design. See the note in build_site.py above this footer. -->
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


def page_text(soup: BeautifulSoup, el, depth: int = 1) -> str:
    """Get clean inner HTML of a content element.

    depth follows the same convention as xml_to_html(): 0 for root pages,
    1 for one-level-deep subdirectory pages (e.g. training/x.html).
    """
    if el is None:
        return "<p>Content not available.</p>"
    prefix = "../" * depth
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
            img["src"] = f"{prefix}images/{fname}"
            img["loading"] = "lazy"
        elif "wp-content" in src:
            fname = Path(src).name.split("?")[0]
            img["src"] = f"{prefix}images/{fname}"
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
                continue
            # Resolve against known built pages by slug (mirrors xml_to_html()'s
            # ?page_id=N resolution, but Wayback content carries the permalink slug
            # directly rather than a page-id query string).
            slug = internal_path.strip('/').split('/')[0] if internal_path.strip('/') else ''
            if not slug:
                a["href"] = f"{prefix}index.html"
            elif slug in SLUG_TO_PATH:
                a["href"] = f"{prefix}{SLUG_TO_PATH[slug]}"
            else:
                # Unresolved — unwrap rather than leave a dead absolute path
                a.unwrap()
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
        inner = xml_to_html(page_data['content'], depth=0, page_slug=slug)
        body  = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{inner}</div>"""
    else:
        soup  = load(slug)
        el    = main_content(soup)
        inner = page_text(soup, el, depth=0)
        body  = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{inner}</div>"""
    if slug == "about":
        # These two pages exist in the XML export but have no nav entry of their
        # own — link them from About instead of adding more top-level nav items.
        body += """
    <p style="margin-top:1.5rem;font-family:var(--font-ui);font-size:.875rem;">
      Learn more: <a href="meet-the-researchers.html">Meet the Researchers</a> ·
      <a href="quick-facts.html">Quick Facts</a>
    </p>"""
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
            elif h.name == "h1" and t.lower() == "publications":
                # Redundant with our own page-title <h1> above — the source content
                # repeats the page title inline; drop it rather than show it twice.
                h.decompose()
            elif h.name == "h1":
                # A stray <h1> for a category label (e.g. "JOURNAL PUBLICATIONS BY
                # PROJECT TEAM:") — every other occurrence of the same label is a
                # bold+underlined <p>, not a heading. Normalize to match instead of
                # rendering one oversized heading in the middle of the citation list.
                h.name = "p"
        # Wrap paragraphs of citations into a pub-list
        inner = page_text(soup, el, depth=0)
    else:
        inner = "<p>Publications list not available.</p>"
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
    <p style="font-family:var(--font-ui);font-size:.875rem;">
      <a href="data.html">Access GPS, seismic &amp; gravity data archives →</a>
    </p>
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
                    # clean_html() always emits root-relative "images/..." paths;
                    # this page is depth=1 (site/sites/{sid}.html), so correct for it.
                    desc_html = desc_html.replace('src="images/', 'src="../images/')
                # Look for a photo matching station ID.
                # Reads SITE_IMG (committed) rather than ARCHIVE_IMG (gitignored) so the build
                # works from a fresh clone — copy_images() runs first, so both hold the same
                # files. See docs/BUILD-REPRODUCIBILITY-WARNING.md.
                img_candidates = list(SITE_IMG.glob(f"{sid}-*.jpg")) + list(SITE_IMG.glob(f"{sid}_*.jpg"))
                if not img_candidates:
                    img_candidates = list(SITE_IMG.glob(f"{sid}*.jpg"))
                if img_candidates:
                    img_fname = img_candidates[0].name
                    img_html = f'<div class="site-photo"><img src="../images/{img_fname}" alt="{title}" loading="lazy"></div>'
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
        out.write_text(page(title, "Sites and Data", body, depth=1), encoding="utf-8")

    print(f"  ✓ sites/{{}}.html  ({len(real_sites)} pages generated)".format("*"))


def build_photos():
    """Photo gallery with GLightbox."""
    # Collect gallery images from SITE_IMG (committed) rather than ARCHIVE_IMG (gitignored),
    # so a fresh clone can rebuild. copy_images() runs before this, so when archive/images/
    # IS present its contents are already mirrored here.
    gallery_imgs = sorted(SITE_IMG.glob("*.jpg"))
    # Exclude known non-gallery images
    exclude = {"facebook.png","youtube.png","polenet2.jpg","touch-icon.png"}
    exclude_patterns = ["home_page","group_photo","photos.jpg","72.jpg"]
    gallery_imgs = [
        f for f in gallery_imgs
        if f.name not in exclude and not any(p in f.name for p in exclude_patterns)
        and not f.name.startswith("thumbs_")
    ]

    # Fail loudly rather than silently shipping an empty gallery. Before this guard, a missing
    # image source produced a successful build with 0 gallery images and 43 station pages
    # stripped of photos, with no warning. See docs/BUILD-REPRODUCIBILITY-WARNING.md.
    if not gallery_imgs:
        raise SystemExit(
            "\nFATAL: photo gallery would be empty — 0 images found in "
            f"{SITE_IMG}.\n"
            "Expected ~160. This usually means site/images/ is missing or empty.\n"
            "Refusing to build a silently-broken site. Nothing was written."
        )

    grid_items = ""
    for img in gallery_imgs:
        grid_items += f"""
      <a href="images/{img.name}" class="glightbox" data-gallery="polenet">
        <img src="images/{img.name}" alt="" loading="lazy">
      </a>"""

    # GLightbox is pinned to an exact version on purpose — an unpinned jsdelivr path resolves to
    # whatever is latest, so a future major release could break this gallery with no change here.
    body = f"""
    <h1 class="page-title">Photos</h1>
    <p class="gallery-intro">Field photos from POLENET monitoring station installations and operations across Antarctica and Greenland.</p>
    <div class="photo-grid">{grid_items}
    </div>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/glightbox@3.3.1/dist/css/glightbox.min.css">
    <script src="https://cdn.jsdelivr.net/npm/glightbox@3.3.1/dist/js/glightbox.min.js"></script>
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
            inner = xml_to_html(page_data['content'], depth=1, page_slug=slug)
            if slug == "2015-gia-training-school":
                # Stray literal "test" in the original WordPress content, right after
                # the last lecture link — an editing leftover, not real content (Q11).
                inner = re.sub(r'(</ul>)\s*test\s*$', r'\1', inner)
            title_text = label
        else:
            try:
                ts    = load(slug)
                el    = main_content(ts)
                inner = page_text(ts, el, depth=1)
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
            page(t, "Training Schools", bdy, depth=1), encoding="utf-8"
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

    # Pin the 3 field-season progress pages at the top — they're the most current,
    # actively-updated content on the site, but live at site root (built by
    # build_extra_pages(), not here) so they'd otherwise never appear on the Blog
    # index at all, only reachable by direct URL. Link to the root page instead of
    # duplicating it into blog/; extract the excerpt from raw content directly
    # rather than via xml_to_html(), which would double-record these pages'
    # videos into VIDEO_PLACEMENTS as a side effect since build_extra_pages()
    # already ran xml_to_html() on them once.
    field_season_slugs = [
        "2025-2026-field-season-progress-page",
        "2024-2025-field-season-progress",
        "2023-2024-field-season-progress",
    ]
    index_items = ""
    for slug in field_season_slugs:
        page_data = XML_PAGES.get(slug)
        if not page_data or not page_data['has_content']:
            continue
        title = page_data['title']
        date_str = page_data.get('date', '')
        soup_ex = BeautifulSoup(page_data['content'], 'lxml')
        first_p = soup_ex.find('p')
        excerpt = (first_p.get_text(strip=True)[:200] + '…') if first_p else ''
        index_items += f"""
      <li>
        <div class="post-title"><a href="../{slug}.html">{title}</a></div>
        <div class="post-meta">{date_str}</div>
        <div class="post-excerpt">{excerpt}</div>
      </li>"""

    built = 0
    for post in posts_desc:
        slug     = post['slug']
        title    = post['title']
        date_str = post.get('date', '')
        content  = xml_to_html(post.get('content', ''), depth=1, page_slug=slug)

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
            page(title, "Blog", bdy, depth=1), encoding="utf-8"
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
        page("Blog", "Blog", index_body, depth=1), encoding="utf-8"
    )
    print(f"  ✓ blog/index.html + {built} post pages")


def _fix_in_the_news_links(html: str) -> str:
    """Normalize inconsistent external-link styling on the "In the News" page.

    Older entries print the raw URL as the link text and stay in the same tab;
    newer entries use a short label ("Read more »" / "Listen now »") and open in
    a new tab. Standardize every external link on the newer, preferred style —
    internal links (to our own built pages) are left untouched, since same-tab
    is correct for those. See docs/wishlist.md item 3.
    """
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith(("http://", "https://")):
            continue  # internal link — leave text and same-tab behavior as-is
        text = a.get_text(strip=True)
        if text.rstrip("/") == href.rstrip("/"):
            # Raw URL used as the link text — swap in a clean label, and drop
            # the now-redundant "Read more at:" that precedes it, if present.
            prev = a.previous_sibling
            if isinstance(prev, NavigableString):
                cleaned = re.sub(r"Read more at:\s*$", "", str(prev), flags=re.IGNORECASE)
                if cleaned != str(prev):
                    prev.replace_with(cleaned)
            a.string = "Read more »"
        rel = a.get("rel", [])
        if isinstance(rel, str):
            rel = rel.split()
        if "noopener" not in rel:
            rel.append("noopener")
        a["rel"] = rel
        a["target"] = "_blank"
    return soup.body.decode_contents()


def build_extra_pages():
    """Build extra pages from XML that don't appear in the main nav."""
    built = 0
    for slug, title, nav_label in EXTRA_PAGES:
        page_data = XML_PAGES.get(slug)
        if not page_data:
            print(f"  ○ skipped (not in XML): {slug}")
            continue
        content = xml_to_html(page_data['content'], depth=0, page_slug=slug)
        if slug == "in-the-news":
            content = _fix_in_the_news_links(content)
        body = f"""
    <h1 class="page-title">{title}</h1>
    <div class="entry-body">{content}</div>"""
        out = SITE_DIR / f"{slug}.html"
        out.write_text(page(title, nav_label, body, depth=0), encoding="utf-8")
        print(f"  ✓ {slug}.html")
        built += 1
    print(f"  ({built} extra pages built)")


# Videos are excluded from the static rebuild — large files, not part of the site design
# (see docs/discovery-log.md 2026-07-26). Kept in archive/images/videos/ for reference; just
# not copied into site/images/ or committed.
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".wmv"}


def copy_images():
    """Copy every non-video file from archive/images/ (including its videos/ and pdfs/
    subfolders — organized 2026-07-28, see docs/discovery-log.md) into site/images/,
    flattened, since every built page's image/PDF links assume a flat images/ path."""
    SITE_IMG.mkdir(exist_ok=True)
    # archive/images/ is gitignored, so it is absent on a fresh clone. That is fine: site/images/
    # is committed and already holds every non-video file. Skip rather than crash.
    if not ARCHIVE_IMG.is_dir():
        print(f"  ○ archive/images/ not present — using the {len(list(SITE_IMG.iterdir()))} "
              "committed files in site/images/ as-is")
        return
    copied = 0
    skipped_videos = 0
    for f in ARCHIVE_IMG.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in _VIDEO_EXTS:
            skipped_videos += 1
            continue
        dest = SITE_IMG / f.name
        if not dest.exists():
            shutil.copy2(f, dest)
            copied += 1
    print(f"  ✓ images/ — {copied} files copied ({len(list(SITE_IMG.iterdir()))} total, {skipped_videos} videos skipped)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_sitemap():
    """Write sitemap.xml and robots.txt. Must run after every page exists — it walks the output.

    No <lastmod>: it would have to come from file mtimes, which change on every build and would
    break the byte-identical-rebuild guarantee for no real benefit. Search engines re-crawl on
    their own schedule regardless.

    Note that robots.txt is only honoured at a domain root. While the site is served from a
    project subpath it is inert — harmless, and correct the moment the site moves to its own
    domain. sitemap.xml works either way and can be submitted directly to a search console.
    """
    pages = sorted(p.relative_to(SITE_DIR).as_posix() for p in SITE_DIR.rglob("*.html"))

    urls = []
    for rel in pages:
        loc = SITE_BASE_URL if rel == "index.html" else SITE_BASE_URL + rel
        urls.append(f"  <url><loc>{escape(loc, quote=False)}</loc></url>")

    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(urls) + "\n</urlset>\n")
    (SITE_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    robots = ("User-agent: *\n"
              "Allow: /\n\n"
              f"Sitemap: {SITE_BASE_URL}sitemap.xml\n")
    (SITE_DIR / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"  ✓ sitemap.xml  ({len(urls)} URLs)")
    print(f"  ✓ robots.txt   (points at {SITE_BASE_URL}sitemap.xml)")


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
    load_video_url_map()

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

    # Video placement registry (see docs/questions.md Q12) — every video stripped
    # during the build above, recorded for a fast data-driven swap-in once hosting
    # is decided
    print("\n[Video placements]")
    video_out = XML_DIR / "video_placements.json"
    video_out.write_text(json.dumps(VIDEO_PLACEMENTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {len(VIDEO_PLACEMENTS)} video placements → {video_out.relative_to(BASE_DIR)}")

    # Must come last — it walks site/ for the pages the steps above just wrote
    print("\n[Search discoverability]")
    build_sitemap()

    print("\n" + "=" * 55)
    print("Build complete.")
    print(f"Output → {SITE_DIR}")
    print("Open site/index.html in a browser to review.")
    print("=" * 55)


if __name__ == "__main__":
    main()
