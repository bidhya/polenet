# Open Questions — polenet.org Rebuild

Questions that need input from the team or colleague before decisions can be made.
Items are marked with their status. Add new questions as they arise.

---

## For Colleague

### Q1 — Individual site detail pages [DECIDED]
**Decision:** Build individual pages for each monitoring station.

The data is already structured (station ID, coordinates, install date, description) and
stored in `archive/audit/site_index.json`. Python will auto-generate all ~46 pages from
a single template — no manual work per page. This preserves the richness of the original
site and matches what the team expects.

If the colleague prefers a table-only view later, we can always add a table to the
Sites and Data page that links to the individual pages.

---

### Q2 — Blog posts [DECIDED]
**Decision:** Keep recent posts (2020 onwards) + the 2016 GNET scientific post.

**Keep (5 posts):**
- 2024-2025 ANET-POLENET Field Season Progress
- Field Season Preparations by David Saddler (Oct 2024)
- Field Season Training by David Saddler (Nov 2024)
- Sharing Science by David Saddler (Nov 2024)
- Greenland GPS study (GNET) highlights a dense Antarctic GPS network (Sep 2016) ← scientific finding

**Flag for colleague — optional (5 old field diary posts from 2014):**
- Heading South to Head Home by Eric Kendrick
- Howard Nunatak Visit by Eric Kendrick
- Wilson Nunatak Maintenance Visit by Eric Kendrick
- Visit to Butcher Ridge by Eric Kendrick
- Installing Sites in Northern Victoria Land by Eric Kendrick
- IRIS Intern

**Excluded:** Pre-2014 date-archive pages (just WordPress monthly index pages, no unique content)

---

### Q3 — Photo gallery [DECIDED]
**Decision:** CSS image grid with a lightbox (GLightbox — free, no jQuery, modern).

Users click a thumbnail → full-size image opens in an overlay.
All gallery images are on one page (no WordPress pagination needed).
This is simpler and better than the original NextGEN Gallery plugin.

---

### Q4 — Hosting [DECIDED]
**Decision:** Netlify (free tier)

Netlify hosts static sites for free, supports custom domains, and has simple drag-and-drop
or Git-based deployment. No server configuration required.
- Custom domain: polenet.org will point to the Netlify deployment
- No subfolder needed — all files served from site root

---

## For Us (Internal / Technical)

### Q5 — Site detail page content format [DECIDED]
**Decision:** Generate individual pages from `archive/audit/site_index.json` using Python.
One template file → 46 HTML pages auto-generated. Easy to update in the future.

---

### Q6 — Photos page approach [DECIDED]
**Decision:** GLightbox CSS+JS lightbox grid. Single page, all gallery images.
GLightbox CDN link — no install needed.

---

### Q7 — Publications page format [OPEN — review content]
**Status:** Need to review `archive/html/publications.html` before deciding format.
Content appears to be a list of journal citations by year. Will likely be a styled
reference list in HTML (no database needed).

---

### Q8 — Slug-named site pages [OPEN — need content check]
**Status:** 6 pages exist with monitoring site names as slugs:
`gould-knoll`, `lepley-nunatak`, `martin-peninsula`, `miller-crag`, `mt-takahe`, `slater-rocks-2`

These may be: (a) blog posts about field visits to those sites, or (b) duplicate site
detail pages discovered via slug URLs rather than page_id URLs.
Need to check their content before deciding whether to include them as blog posts or
merge them into the site detail pages.
