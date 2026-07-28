# polenet.org — Static Site Rebuild

A clean static HTML/CSS rebuild of [polenet.org](https://polenet.org) (The Polar Earth Observing Network). The original WordPress site's Aries theme broke and stopped rendering; the underlying WordPress database and media library are still intact and reachable, but the goal is to migrate off WordPress/Aries entirely rather than just fix the theme. Built from a WordPress XML export plus the Internet Archive as a fallback/design reference.

**Live preview (Netlify, `dev` branch):** https://monumental-dieffenbachia-d72518.netlify.app/
**GitHub Pages (testing on `pages` branch):** https://bidhya.github.io/polenet/

---

## What's here

| Directory | Contents |
|-----------|----------|
| `site/` | The deployable website (104 HTML pages, CSS, 429 images/PDFs) |
| `scraper/` | Python scripts to crawl the archive and build the site |
| `archive/audit/` | Station index JSON + audit reports (source data) |
| `docs/` | Project notes, decisions, deployment plan |

> `archive/html/` and `archive/images/` are gitignored — too large to commit.
> See **Rebuild from scratch** below if you need them.
>
> 35 videos referenced in the original content are embedded via YouTube (currently the
> project owner's personal account, Unlisted, as an interim solution) rather than committed
> as files. Migrating to the official POLENET channel once access is confirmed is still owed —
> see `docs/questions.md` Q12 if you're picking this up.

---

## Quickstart

### View or deploy the site
The `site/` directory is self-contained static HTML — open `site/index.html` in a browser or point any static host at it.

Netlify is configured via `netlify.toml` to publish from `site/`.

### Make a content change
```bash
# Edit scraper/build_site.py, then:
mamba run python scraper/build_site.py   # regenerate site/
git add site/
git commit -m "your change"
git push origin dev            # Netlify auto-deploys
```

### Rebuild from scratch (fresh clone)
```bash
pip install -r scraper/requirements.txt
mamba run python scraper/fetch_archive.py   # Step 1 — Wayback homepage/images (historical)
mamba run python scraper/crawl_site.py      # Step 2 — full Wayback crawl (historical, ~15 min)
mamba run python scraper/audit.py           # Step 3 — classify pages (historical)
mamba run python scraper/parse_xml.py       # Step 6 — WordPress XML export → archive/xml/*.json
                                             #   (needs Scratch/*.xml — gitignored, ask for a copy)
mamba run python scraper/build_site.py      # Step 4/6 → generates site/
mamba run python scraper/fetch_live_uploads.py  # Step 7 — pull missing images/PDFs from the
                                                 #   live polenet.org server, then re-run build_site.py
```

---

## Branches

| Branch | Purpose |
|--------|---------|
| `dev` | Active development — auto-deploys to Netlify preview |
| `main` | Production — deploy paused until polenet.org is ready to go live; also drives GitHub Pages via `.github/workflows/pages.yml` |
| `pages` | GitHub Pages testing/iteration — branched off `main`, kept separate so `dev` stays untouched while working out Pages-specific issues |

---

## Further reading

- `docs/todo.md` — current status and next steps
- `docs/deployment.md` — Netlify setup, branch strategy, domain connection
- `AGENTS.md` — full project context for AI-assisted development
