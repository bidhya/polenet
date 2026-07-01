# polenet.org — Static Site Rebuild

A clean static HTML/CSS rebuild of [polenet.org](https://polenet.org) (The Polar Earth Observing Network), reverse-engineered from the Internet Archive after the original WordPress site became unrecoverable.

**Live preview:** https://monumental-dieffenbachia-d72518.netlify.app/

---

## What's here

| Directory | Contents |
|-----------|----------|
| `site/` | The deployable website (75 HTML pages, CSS, 162 images) |
| `scraper/` | Python scripts to crawl the archive and build the site |
| `archive/audit/` | Station index JSON + audit reports (source data) |
| `docs/` | Project notes, decisions, deployment plan |

> `archive/html/` and `archive/images/` are gitignored — too large to commit.
> See **Rebuild from scratch** below if you need them.

---

## Quickstart

### View or deploy the site
The `site/` directory is self-contained static HTML — open `site/index.html` in a browser or point any static host at it.

Netlify is configured via `netlify.toml` to publish from `site/`.

### Make a content change
```bash
# Edit scraper/build_site.py, then:
python scraper/build_site.py   # regenerate site/
git add site/
git commit -m "your change"
git push origin dev            # Netlify auto-deploys
```

### Rebuild from scratch (fresh clone)
```bash
pip install -r scraper/requirements.txt
python scraper/fetch_archive.py   # Step 1
python scraper/crawl_site.py      # Step 2 (~15 min)
python scraper/audit.py           # Step 3
python scraper/build_site.py      # Step 4 → generates site/
```

---

## Branches

| Branch | Purpose |
|--------|---------|
| `dev` | Active development — auto-deploys to Netlify preview |
| `main` | Production — deploy paused until polenet.org is ready to go live |

---

## Further reading

- `docs/todo.md` — current status and next steps
- `docs/deployment.md` — Netlify setup, branch strategy, domain connection
- `AGENTS.md` — full project context for AI-assisted development
