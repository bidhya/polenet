# polenet.org Rebuild — TODO

Last updated: 2026-06-29
Snapshot in use: `20251207055143` (December 7, 2025)

---

## STEP 1 — Homepage extraction [DONE]
- [x] Write `scraper/fetch_archive.py`
- [x] Query CDX API — confirmed last good snapshot is Dec 7 2025 (Feb 2026 = 301 broken)
- [x] Download homepage HTML → `archive/html/homepage_20251207055143.html`
- [x] Download 7 homepage images → `archive/images/`
- [x] Confirm site structure: 7 nav pages + blog posts discovered

---

## STEP 2 — Full site crawl [DONE]
- [x] All 7 nav pages: home, about, sites, photos, publications, training-schools, blog
- [x] 51 individual monitoring site detail pages (home-page-id-*.html)
      e.g. "Backer Island" with station ID, coordinates, install date — REAL CONTENT
- [x] ~17 blog posts + training school detail pages
- [x] All 5 gallery pages captured (photos/nggallery/page/1–5)
- [x] 162 images (full-size; thumbnails failed but not needed — CSS will handle sizing)
- [x] 74 CSS/JS theme assets → archive/assets/
- [x] Noise also captured (harmless): date archives, wp-login, feed — can ignore

---

## STEP 3 — Audit [DONE]
- [x] Write `scraper/audit.py`
- [x] Classify all 101 HTML files: 7 nav, 50 site-detail, 18 blog, 6 training, 4 gallery, 16 noise
- [x] Generate site index with all 50 monitoring sites → `archive/audit/site_index.txt`
- [x] Site index also exported as `archive/audit/site_index.json` (for use in rebuild)
- [x] Image coverage report: 162 on disk, 170 "missing" (mostly thumbnails/avatars — not blocking)
- [x] Gap report produced → `archive/audit/gap_report.txt`

**Note:** 4 of the 50 "site-detail" pages appear to be photo gallery sub-albums
("Photos", "Photos- People", "Photos- in the Field", "Photos- Scenery") — ~46 are real monitoring sites.

---

## STEP 4 — Rebuild [NEXT]

### Decisions locked in
- **Hosting:** Netlify (free tier, custom domain polenet.org)
- **Site pages:** Individual pages for each monitoring station (~46), auto-generated from site_index.json
- **Blog posts:** 5 recent (2024 + 2016 GNET); 2014 Eric Kendrick posts flagged as optional
- **Gallery:** GLightbox CSS+JS lightbox grid, all images on one page
- **Layout:** Clean HTML/CSS from scratch — no WordPress, no frameworks

### 4a — Site structure to build
```
site/
├── index.html              (Home)
├── about.html
├── sites.html              (Sites and Data — table + links to individual site pages)
├── photos.html             (GLightbox image grid)
├── publications.html
├── training-schools.html   (index of training schools)
├── blog/
│   ├── index.html
│   └── [5 recent post pages]
├── sites/
│   └── [~46 station pages, auto-generated from site_index.json]
├── css/
│   └── style.css
└── images/                 (copied from archive/images/)
```

### 4b — Build tasks
- [x] Confirmed gould-knoll / lepley-nunatak etc. are real monitoring stations — merged into site_index.json (56 total, 51 with valid station IDs)
- [x] Write `site/css/style.css` — clean layout (navy/blue palette, responsive, CSS variables)
- [x] Write `scraper/build_site.py` — Python site generator
- [x] Generate all pages from archived HTML content
- [x] Copy 162 images → `site/images/`
- [x] Add GLightbox to photos page (77 images)
- [x] Deploy to Netlify — live at https://monumental-dieffenbachia-d72518.netlify.app/
- [x] Security audit — strip Akismet nonces, WordPress comment forms, gstatic avatars
- [x] URL cleanup — fix broken polenet.org/wp-content image refs, Wayback wrappers, srcset, video blocks
- [x] Fix image path depth bug in blog/training pages (../../images/ not ../../../images/)
- [x] Set up GitHub private repo (https://github.com/bidhya/polenet), main + dev branches
- [x] Configure Netlify CI/CD: dev branch auto-deploys; main branch paused until launch
- [x] Merge dev → main (branches synced)

## STEP 5 — Review & Launch [TODO]
- [ ] Colleague review of live site — flag content gaps or corrections
- [ ] Check publications page formatting
- [ ] Connect custom domain polenet.org in Netlify (DNS config)
- [ ] Unpause main branch deploy in Netlify to go live

### 4c — Build output (generated 2026-06-29)
```
site/
├── index.html              ✓
├── about.html              ✓
├── publications.html       ✓
├── sites.html              ✓ (51 stations)
├── photos.html             ✓ (77 images, GLightbox)
├── training-schools.html   ✓
├── blog/
│   ├── index.html          ✓
│   └── 11 post pages       ✓
├── sites/
│   └── 51 station pages    ✓
├── training/
│   └── 6 school pages      ✓
├── css/style.css           ✓
└── images/ (162 files)     ✓
```
Total: 75 HTML files, 239 files, 21 MB

---

## OPEN QUESTIONS
- **Site detail pages**: The 51 `home-page-id-*.html` files are individual monitoring site
  pages (e.g. Backer Island, station ID BACK, coordinates, install dates). Should all 51
  be rebuilt as individual pages, or just summarised in a table on the Sites page?
- Are there more blog posts on blog page 2? (need to check `page-2-page-id-81.html`)
- What hosting will the rebuilt static site use? (affects URL structure decisions)
