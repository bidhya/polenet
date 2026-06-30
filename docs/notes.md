# polenet.org Rebuild — Project Notes

## Status
In progress — Step 1 complete. Planning Step 2: full site crawl.

## Root Cause of Site Failure
- **Theme:** Aries WordPress Theme by United Themes (Marcel Moerkens & Matthew Nettekoven)
- **Cause:** Incompatibility between the Aries theme and WordPress core updates broke the site
- The site returned 200 OK through December 2025, then started returning 301 redirects from
  February 2026 onward — the site was effectively dead by then
- No database backup exists; server is compromised

## Rebuild Strategy
- Extract all content from the last known-good Wayback snapshot (December 7, 2025)
- Rebuild as a clean static HTML/CSS/JS site — zero WordPress, zero PHP, zero database
- The Aries theme is being discarded; we write clean HTML/CSS from scratch

## Key Decisions
- Master folder (`polenet/`) has no git; subfolders (`scraper/`, `site/`) have their own repos
- `archive/` holds raw extracted content — not version controlled
- Step-by-step approach: extract → audit → rebuild

---

## Site Structure (from December 2025 snapshot)

**Title:** POLENET: The Polar Earth Observing Network | Investigating the polar regions from the inside out

### Navigation Pages (7)
| Label           | Path                  |
|-----------------|-----------------------|
| Home            | `/`                   |
| About           | `/about/`             |
| Sites and Data  | `/sites/`             |
| Photos          | `/photos/`            |
| Publications    | `/publications/`      |
| Training Schools| `/training-schools/`  |
| Blog            | `/?page_id=81`        |

### Blog Posts found on homepage
- `/2024-2025-field-season-progress`
- `/2025-gia-workshop`
- `/sharing-science-by-david-saddler`
- `/field-season-training-by-david-saddler`

---

## Wayback Machine Snapshots

| Timestamp       | Status | Notes                        |
|-----------------|--------|------------------------------|
| 20250906215317  | 200    | Good — September 2025        |
| 20251119045508  | 200    | Good — November 2025         |
| 20251207055143  | 200    | **Best — December 7, 2025**  |
| 20260203074229  | 301    | Broken — site already down   |
| 20260302021541  | 301    | Broken                       |

**Active snapshot in use:** `20251207055143`
Wayback URL: https://web.archive.org/web/20251207055143/https://polenet.org/

---

## Extraction Progress

### Step 1 — Homepage (DONE)
- HTML saved: `archive/html/homepage_20251207055143.html`
- Images downloaded (7): facebook.png, youtube.png, polenet2.jpg, home_page-copy.jpg,
  group_photo_home_page.jpg, group_photo_hompage-scaled.jpg, 72.jpg

### Step 2 — Full site crawl (TODO)
Pages to crawl: `/about/`, `/sites/`, `/photos/`, `/publications/`, `/training-schools/`,
`/?page_id=81` (Blog), plus all blog post URLs discovered

### Step 3 — CSS / JS / Theme assets (TODO)
- Aries theme CSS files identified in HTML head — need to archive them
- Goal: understand the layout/design so we can replicate it in clean CSS (not copy it)

### Step 4 — Audit (TODO)
- Compare what was captured vs. what's linked
- Identify missing images, broken links, pages with no snapshot

### Step 5 — Rebuild (TODO)
- Design clean static HTML/CSS layout based on the archived content
- No WordPress dependencies

---

## Known Issues / Gaps
- Only 7 `<img>` tag images captured from homepage; `/photos/` page likely has many more
- CSS/JS theme assets not yet downloaded
- Blog page URL uses `?page_id=81` — need to verify this resolves correctly in Wayback

---

## References
- Wayback Machine CDX API: http://web.archive.org/cdx/search/cdx
- Wayback Availability API: https://archive.org/wayback/available
- Aries Theme (reference only): https://www.unitedthemes.com
