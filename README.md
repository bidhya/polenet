# polenet.org — Static Site Rebuild

A clean static HTML/CSS rebuild of [polenet.org](https://polenet.org) (The Polar Earth Observing Network). The original WordPress site's theme broke in early 2026 with no easy recourse; this rebuild — done with heavy use of AI-assisted tooling — moves the site off WordPress entirely rather than patch the old theme. Built from a WordPress XML export plus the Internet Archive (Wayback Machine).

**Live previews:**
- GitHub Pages (`main` branch): https://bidhya.github.io/polenet/
- Netlify (`dev` branch): https://monumental-dieffenbachia-d72518.netlify.app/

---

## What's here

| Directory | Contents |
|-----------|----------|
| `site/` | The deployable website (115 HTML pages, CSS, 539 images/PDFs) |
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
git push origin dev             # Netlify auto-deploys the preview
```
Once it looks good there, promote it:
```bash
git checkout main && git merge dev --ff-only && git push origin main
# GitHub Actions auto-deploys to bidhya.github.io/polenet
```
See **Branches** below and `docs/deployment.md` for the full promotion workflow.

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

Two-tier model — work flows one direction: `dev` → `main`.

| Branch | Purpose |
|--------|---------|
| `dev` | Active development — push here, auto-deploys to Netlify preview |
| `main` | Merge from `dev` once it looks stable — auto-deploys to GitHub Pages, production track |

---

## Further reading

- `docs/todo.md` — current status and next steps
- `docs/deployment.md` — Netlify setup, branch strategy, domain connection
- `AGENTS.md` — full project context for AI-assisted development
