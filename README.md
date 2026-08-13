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
| `scraper/` | Python scripts that build the site |
| `archive/html/` | Archived source pages the builder reads |
| `archive/xml/` | Parsed WordPress export — the primary content source |
| `archive/audit/` | Station index JSON + audit reports |
| `pyproject.toml`, `uv.lock` | The three dependencies, and their pinned versions |

> **Everything needed to rebuild the site is committed.** Clone and run
> `uv run python scraper/build_site.py` — see **Rebuild** below.
>
> `archive/images/` is gitignored, but the build does not need it: `site/images/` holds the
> same files and is committed.
>
> 35 videos referenced in the original content are embedded via YouTube (currently the
> project owner's personal account, Unlisted, as an interim solution) rather than committed
> as files. Migrating to the official POLENET channel once access is confirmed is still owed.

---

## How this works

`site/` is generated **locally** and committed as finished HTML — git stores the output, not a
recipe. Neither host builds anything: the GitHub Actions workflow and Netlify both just serve the
committed `site/` folder verbatim (no build command, no Python in CI).

```
build locally  →  commit site/  →  push  →  host serves it
```

**Consequence worth knowing:** editing `scraper/build_site.py` alone changes nothing live. You have
to re-run the build and commit the resulting `site/` diff. Push the Python by itself and Netlify
skips the deploy outright — its `ignore` rule sees `site/` unchanged.

This is also why `site/` works as a standalone handover: it's the finished artifact, not an
intermediate. Point any static host at it and you're done.

---

## Quickstart

### View or deploy the site
The `site/` directory is self-contained static HTML — open `site/index.html` in a browser or point any static host at it.

Netlify is configured via `netlify.toml` to publish from `site/`.

### Make a content change
```bash
# Edit scraper/build_site.py, then:
uv run python scraper/build_site.py      # regenerate site/
git add site/
git commit -m "your change"
git push origin dev             # Netlify auto-deploys the preview
```
Once it looks good there, promote it:
```bash
git checkout main && git merge dev --ff-only && git push origin main
# GitHub Actions auto-deploys to bidhya.github.io/polenet
```
See **Branches** below for the full promotion workflow.

### Rebuild (fresh clone)
Everything the builder reads is committed, so this is the whole rebuild:
```bash
uv run python scraper/build_site.py         # regenerates all 115 pages in site/
```
Dependencies are three ordinary libraries — `requests`, `beautifulsoup4`, `lxml` — declared in
`pyproject.toml`. The commands here use [uv](https://docs.astral.sh/uv/) because it handles the
interpreter and the dependencies in one step, but any Python tooling works; substitute your own
and drop the `uv run` prefix.
This reproduces `site/` byte-for-byte — `git status` should come back clean afterwards. If it
doesn't, something genuinely changed. Sanity check: `grep -c 'class="glightbox' site/photos.html`
returns **160**. The build refuses to run rather than emit an empty gallery, so a missing-asset
failure stops loudly instead of shipping a broken site.

<details>
<summary>Historical / one-off scripts (not needed for a normal rebuild)</summary>

```bash
uv run python scraper/parse_xml.py          # WordPress export → archive/xml/*.json
                                            #   output is already committed; needs Scratch/*.xml
uv run python scraper/fetch_archive.py      # original Wayback capture
uv run python scraper/crawl_site.py         # original full Wayback crawl (~15 min)
uv run python scraper/audit.py              # page classification → archive/audit/
uv run python scraper/fetch_live_uploads.py # one-off media recovery from the original server
```
</details>

---

## Branches

Two-tier model — work flows one direction: `dev` → `main`.

| Branch | Purpose |
|--------|---------|
| `dev` | Active development — push here, auto-deploys to Netlify preview |
| `main` | Merge from `dev` once it looks stable — auto-deploys to GitHub Pages, production track |

---

## Further reading

Everything needed to build, host and understand the site is in this repo. The project's
working notes — the full rebuild narrative, deployment detail, and a handover guide — are kept
outside it by the maintainer; ask if you need them.

- `site/README.md` — note on the generated output
- `pyproject.toml` — the three dependencies
