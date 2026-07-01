#!/usr/bin/env python3
"""
parse_xml.py — Step 6a: Parse the WordPress WXR export.

Reads:   Scratch/polenetthepolarearthobservingnetwork.WordPress.2026-07-01.xml
Outputs:
  archive/xml/pages.json       — all published pages
  archive/xml/posts.json       — all published posts (date-sorted)
  archive/xml/attachments.json — all media library files

Content storage:
  Image src and href attributes pointing to polenet.org/wp-content/uploads/ are
  rewritten to the placeholder prefix "images/" (root-relative).
  build_site.py adjusts this to "../../images/" for depth-2 pages.

Requires: lxml (NOT stdlib xml.etree — the WXR has invalid XML chars that crash it)

Usage:
  python scraper/parse_xml.py
"""

import json
import re
from pathlib import Path

from lxml import etree

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
XML_FILE = BASE_DIR / "Scratch" / "polenetthepolarearthobservingnetwork.WordPress.2026-07-01.xml"
XML_OUT  = BASE_DIR / "archive" / "xml"

# WordPress XML namespaces
NS = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'wp':      'http://wordpress.org/export/1.2/',
    'dc':      'http://purl.org/dc/elements/1.1/',
}

# ---------------------------------------------------------------------------
# Content cleaning
# ---------------------------------------------------------------------------

_GUTENBERG_COMMENT = re.compile(r'<!--\s*/?wp:[^\-]*?-->', re.DOTALL)
_WP_IMAGE_URL      = re.compile(
    r'(https?://(?:www\.)?polenet\.org/wp-content/uploads/)'
    r'(?:[0-9]{4}/[0-9]{2}/)?'
    r'([^"\'>\s\?]+)',
    re.IGNORECASE,
)
_WAYBACK_URL = re.compile(
    r'https?://web\.archive\.org/web/\d+[^/]*/https?://[^\s"\'<>]*'
)
_SRCSET_ATTR = re.compile(r'\s+(?:srcset|sizes)="[^"]*"')


def clean_content(html: str) -> str:
    """
    Clean WordPress HTML content for use in the static site.

    Steps:
    1. Strip Gutenberg block comments (<!-- wp:xxx --> / <!-- /wp:xxx -->)
    2. Rewrite polenet.org/wp-content/uploads/ image URLs → images/filename
    3. Strip srcset/sizes attributes (reference dead server URLs)
    4. Strip any Wayback Machine wrappers (shouldn't appear in WXR but be safe)
    5. Strip <a> wrappers around images that link to polenet.org uploads
    """
    if not html:
        return ''

    # 1. Strip Gutenberg block comments
    html = _GUTENBERG_COMMENT.sub('', html)

    # 2. Rewrite polenet.org image URLs → images/filename
    html = _WP_IMAGE_URL.sub(lambda m: f'images/{Path(m.group(2)).name}', html)

    # 3. Strip srcset/sizes attrs
    html = _SRCSET_ATTR.sub('', html)

    # 4. Strip Wayback wrappers
    html = _WAYBACK_URL.sub('', html)

    # 5. Unwrap <a href="images/..."> that wrap a single <img>
    #    These are Gutenberg "link to media" wrappers — clicking opens the image.
    #    On a static site they just link to a local file with no lightbox, so strip them.
    html = re.sub(
        r'<a\s+href="images/[^"]*"[^>]*>(\s*<img\s[^>]*>)\s*</a>',
        r'\1',
        html,
        flags=re.DOTALL,
    )

    # Clean up blank lines left by Gutenberg comment removal
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def field(el, tag: str) -> str:
    """Return stripped text of a child element, or ''."""
    return (el.findtext(tag, namespaces=NS) or '').strip()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_pages(channel) -> list[dict]:
    """Return all published pages."""
    records = []
    for item in channel.findall('item'):
        if field(item, 'wp:post_type') != 'page':
            continue
        status = field(item, 'wp:status')
        if status != 'publish':
            continue

        post_id   = _int(field(item, 'wp:post_id'))
        parent_id = _int(field(item, 'wp:post_parent'))
        content   = clean_content(field(item, 'content:encoded'))

        records.append({
            'id':          post_id,
            'title':       field(item, 'title'),
            'slug':        field(item, 'wp:post_name'),
            'status':      status,
            'date':        field(item, 'wp:post_date')[:10],
            'author':      field(item, 'dc:creator'),
            'parent_id':   parent_id,
            'content':     content,
            'has_content': bool(content.strip()),
        })

    # Second pass — resolve parent slugs
    id_to_slug = {r['id']: r['slug'] for r in records}
    for r in records:
        r['parent_slug'] = id_to_slug.get(r['parent_id'], '') if r['parent_id'] else ''

    records.sort(key=lambda x: x['title'].lower())
    return records


def parse_posts(channel) -> list[dict]:
    """Return all published posts, sorted by date ascending."""
    records = []
    for item in channel.findall('item'):
        if field(item, 'wp:post_type') != 'post':
            continue
        if field(item, 'wp:status') != 'publish':
            continue

        post_id = _int(field(item, 'wp:post_id'))
        content = clean_content(field(item, 'content:encoded'))

        records.append({
            'id':          post_id,
            'title':       field(item, 'title'),
            'slug':        field(item, 'wp:post_name'),
            'date':        field(item, 'wp:post_date')[:10],
            'author':      field(item, 'dc:creator'),
            'content':     content,
            'has_content': bool(content.strip()),
        })

    records.sort(key=lambda x: x['date'])
    return records


def parse_attachments(channel) -> list[dict]:
    """Return all attachment items (media library)."""
    records = []
    for item in channel.findall('item'):
        if field(item, 'wp:post_type') != 'attachment':
            continue
        url = field(item, 'wp:attachment_url')
        if not url:
            continue

        records.append({
            'id':        _int(field(item, 'wp:post_id')),
            'title':     field(item, 'title'),
            'slug':      field(item, 'wp:post_name'),
            'date':      field(item, 'wp:post_date')[:10],
            'parent_id': _int(field(item, 'wp:post_parent')),
            'url':       url,
            'filename':  Path(url.split('?')[0]).name,
        })

    return records


def _int(s: str) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=' * 55)
    print('  parse_xml.py — Step 6a: Parse WordPress WXR')
    print('=' * 55)

    if not XML_FILE.exists():
        print(f'\nERROR: XML file not found:\n  {XML_FILE}')
        return

    print(f'\nParsing {XML_FILE.name} ...')
    parser = etree.XMLParser(recover=True, encoding='utf-8')
    tree   = etree.parse(str(XML_FILE), parser)
    channel = tree.getroot().find('channel')

    pages       = parse_pages(channel)
    posts       = parse_posts(channel)
    attachments = parse_attachments(channel)

    XML_OUT.mkdir(parents=True, exist_ok=True)
    (XML_OUT / 'pages.json').write_text(
        json.dumps(pages, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    (XML_OUT / 'posts.json').write_text(
        json.dumps(posts, indent=2, ensure_ascii=False), encoding='utf-8'
    )
    (XML_OUT / 'attachments.json').write_text(
        json.dumps(attachments, indent=2, ensure_ascii=False), encoding='utf-8'
    )

    # Print summary
    print(f'\nResults:')
    print(f'  Published pages:  {len(pages):>4}  →  archive/xml/pages.json')
    print(f'  Published posts:  {len(posts):>4}  →  archive/xml/posts.json')
    print(f'  Attachments:      {len(attachments):>4}  →  archive/xml/attachments.json')

    with_content = sum(1 for p in pages if p['has_content'])
    print(f'\n  Pages with content: {with_content}/{len(pages)}')

    print(f'\n  All {len(posts)} posts (chronological):')
    for p in posts:
        flag = '✓' if p['has_content'] else '○'
        print(f'    {flag} {p["date"]}  {p["title"][:65]}')

    img_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.tif', '.tiff'}
    img_atts = [a for a in attachments if Path(a['url']).suffix.lower() in img_exts]
    print(f'\n  Image attachments: {len(img_atts)} of {len(attachments)} total')
    print(f'\n  Sample attachment URLs:')
    for a in attachments[:5]:
        print(f'    {a["url"]}')

    print(f'\nDone. Output → archive/xml/')


if __name__ == '__main__':
    main()
