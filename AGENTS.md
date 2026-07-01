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
| `docs/deployment.md` | Deployment decisions, branch strategy, Netlify setup | Internal |

---

### SITE STRUCTURE (discovered)
- 7 nav pages: Home, About, Sites and Data, Photos, Publications, Training Schools, Blog
- 51 individual monitoring site detail pages (station ID, coordinates, install dates)
- 11 blog posts (5 recent 2024 + 6 Eric Kendrick 2014 field diaries)
- 6 training school pages (GIA 2015, 2017, 2019, 2023, 2025 workshop + 1 more)
- 77-image photo gallery with GLightbox lightbox

### MY TECHNICAL STACK
- IDE: VS Code
- AI Assistant: GitHub Copilot
- Language: Python 3
- Output: Static site (HTML, CSS, JavaScript) — zero databases, zero PHP
- Hosting: Netlify (free tier), GitHub private repo

### YOUR ROLE AS MY AI ARCHITECT
You will act as a senior Python automation engineer and web developer. Continue guiding me through improvements, content review, and eventual launch.

---

### STEP 1: ARCHIVE DATA EXTRACTION — COMPLETE
- Script: `scraper/fetch_archive.py`
- Queries Wayback CDX API, targets snapshot `20251207055143` (Dec 7, 2025)
- Downloads homepage HTML → `archive/html/`
- Downloads images → `archive/images/`

### STEP 2: FULL SITE CRAWL — COMPLETE
- Script: `scraper/crawl_site.py`
- Crawled all 7 nav pages, 51 site detail pages, ~17 blog/training posts, 5 gallery pages
- 162 images and 74 CSS/JS assets downloaded
- See `docs/discovery-log.md` for full findings

### STEP 3: AUDIT — COMPLETE
- Script: `scraper/audit.py`
- Classified 101 HTML files; produced page_inventory, image_report, gap_report
- Generated `archive/audit/site_index.json` — 56 entries, 51 with valid station IDs
- Reports in `archive/audit/`

### STEP 4: REBUILD — COMPLETE
- CSS: `site/css/style.css` — navy/blue palette, CSS variables, responsive
- Builder: `scraper/build_site.py` — generates all pages from archived HTML
- Output: 75 HTML files, 162 images, 21 MB total in `site/`
- Security audit applied: stripped Akismet nonces, comment forms, broken image refs
- URL cleanup: all Wayback wrappers removed, local image paths corrected

### STEP 5: DEPLOYMENT — COMPLETE
- GitHub: https://github.com/bidhya/polenet (private repo, `main` + `dev` branches)
- Netlify: https://monumental-dieffenbachia-d72518.netlify.app/
- CI/CD: push to `dev` → Netlify auto-deploys to preview URL
- `main` branch: paused in Netlify until ready to connect polenet.org
- See `docs/deployment.md` for full setup details

### STEP 6: REVIEW & LAUNCH — NEXT
- Colleague content review of live site
- Fix any content gaps or corrections identified
- Connect custom domain polenet.org in Netlify (DNS config)
- Unpause `main` branch deploy to go live

### GIT / DEPLOYMENT DISCIPLINE
- Do NOT push every minor change to `dev` — batch related edits into one commit/push
- Do NOT merge `dev` → `main` for small/incremental updates — only merge meaningful, reviewed milestones
- Netlify free tier build credits are limited; frequent pushes/merges trigger unnecessary deploys
- `netlify.toml` already skips deploys unless `site/` changed, but this is a safety net, not a substitute for batching pushes

