# scraper

Python scripts for extracting polenet.org content from the Internet Archive
and generating the static site.

## Scripts (run in order)

| Script | Step | Purpose |
|--------|------|---------|
| `fetch_archive.py` | 1 | Download homepage HTML + images from Wayback Machine |
| `crawl_site.py` | 2 | Crawl all pages, blog posts, station pages, images |
| `audit.py` | 3 | Classify HTML files, produce audit reports, generate site_index.json |
| `build_site.py` | 4 | Generate all static HTML pages in `site/` from archived content |

## Setup

```
pip install -r requirements.txt
```

## Important: archive/ is gitignored

The `archive/` directory (raw Wayback downloads) is NOT committed to git.
It is large, reproducible, and excluded by `.gitignore`. Only `archive/audit/`
(JSON reports) is committed.

**If you clone this repo fresh**, you must re-download before running the builder:

```
python scraper/fetch_archive.py    # Step 1: homepage
python scraper/crawl_site.py       # Step 2: full site crawl (~15 min)
python scraper/audit.py            # Step 3: audit + regenerate site_index.json
python scraper/build_site.py       # Step 4: generate site/
```

Target snapshot: `20251207055143` (December 7, 2025 - last known-good state).

## Normal workflow (archive/ already exists locally)

```
python scraper/build_site.py       # regenerate site/
git add site/
git commit -m "description of change"
git push origin dev                # Netlify auto-deploys preview URL
```
