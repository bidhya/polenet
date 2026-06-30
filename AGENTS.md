### PROJECT CONTEXT & GOAL
I am helping a colleague rebuild a broken website (https://polenet.org). The site was originally built on WordPress using the **Aries theme by United Themes**. The site broke due to an incompatibility between the Aries theme and WordPress core updates. The database and server are now compromised, and there is no backup.

My goal is to completely reverse-engineer this site into a clean, modern, static HTML/CSS website — entirely removing our reliance on WordPress and the Aries theme.

Because we do not have a backup of the original site files, we must extract all content, media, and structural context from the Internet Archive (Wayback Machine). The last known-good snapshots are from **September, November, and December 2025**. We are targeting the **December 7, 2025** snapshot as it is the most recent good state.

---

### DOCUMENTATION INDEX

All project documentation lives in `docs/`. Key files:

| File | Purpose | Audience |
|------|---------|----------|
| `docs/todo.md` | Live task tracker — current step and what's next | Internal |
| `docs/notes.md` | Technical notes, snapshot details, site structure | Internal |
| `docs/questions.md` | Open questions needing input — pick what to share | Colleague / Internal |
| `docs/discovery-log.md` | Running log of findings and decisions, newest first | Colleague / Internal |
| `docs/archive-analysis.md` | Why we chose Dec 2025 snapshot — clean explanation | Shareable with colleague |

---

### SITE STRUCTURE (discovered)
- 7 nav pages: Home, About, Sites and Data, Photos, Publications, Training Schools, Blog
- ~51 individual monitoring site detail pages (station ID, coordinates, install dates)
- ~17 blog posts and training school pages
- 5-page photo gallery (NextGEN Gallery plugin — being replaced with clean HTML/CSS)
- WordPress Aries theme (reference only — being discarded in rebuild)

### MY TECHNICAL STACK
- IDE: VS Code
- AI Assistant: GitHub Copilot
- Language: Python 3
- Output Target: Static site (HTML, CSS, JavaScript) with zero databases or PHP.

### YOUR ROLE AS MY AI ARCHITECT
You will act as a senior Python automation engineer and web scraper. You must guide me through this process sequentially, step-by-step.

---

### STEP 1: ARCHIVE DATA EXTRACTION SCRIPT — COMPLETE
- Script: `scraper/fetch_archive.py`
- Queries the Wayback CDX API for the best snapshot in the Sept–Dec 2025 window
- Downloads homepage HTML → `archive/html/`
- Downloads images from `<img>` tags → `archive/images/`
- Result: 7 images + homepage HTML captured from snapshot `20251207055143`

### STEP 2: FULL SITE CRAWL — COMPLETE
- Script: `scraper/crawl_site.py`
- Crawled all 7 nav pages, 51 site detail pages, ~17 blog/training posts, 5 gallery pages
- 162 images and 74 CSS/JS assets downloaded
- See `docs/discovery-log.md` for full findings

### STEP 3: AUDIT — IN PROGRESS
- Script: `scraper/audit.py` (to be written)
- Inventory and classify all captured HTML files
- Identify content gaps and missing images
- Produce `archive/audit/gap_report.txt`
- Key decisions needed: see `docs/questions.md`

### STEP 4: REBUILD — TODO
- Design clean static HTML/CSS layout based on archived content
- No WordPress, no PHP, no database dependencies
