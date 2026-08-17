# scraper

Python scripts that recovered the original polenet.org content and generate the static site in
`site/`.

## You almost certainly only need one of these

```
uv run python scraper/build_site.py
```

That regenerates all 115 pages in `site/`. **It works from a fresh clone** — everything it reads
is committed. Afterwards `git status` should be clean, because the rebuild is byte-identical to
what is deployed.

Use `uv run python`, not bare `python`: the three dependencies (`requests`, `beautifulsoup4`,
`lxml`) are declared in `pyproject.toml` and pinned in `uv.lock`. Any Python tooling works if you
prefer something else — uv is simply what is set up here. There is no `requirements.txt`.

## The other scripts are historical

They were used once, during recovery, and **should not be re-run**. They are kept because they
document how the content was obtained.

| Script | What it did |
|---|---|
| `fetch_archive.py` | Downloaded the home page from the Internet Archive |
| `crawl_site.py` | Crawled the archived site — pages, posts, station pages, images |
| `fetch_live_uploads.py` | Recovered media over public HTTPS that the archive had missed |
| `fetch_missing_images.py` | Fallback image recovery via the Wayback CDX API |
| `audit.py` | Classified the crawled HTML and produced `archive/audit/site_index.json` |
| `parse_xml.py` | Parsed the WordPress export into `archive/xml/*.json` |

Archive snapshot used: `20251207055143` (7 December 2025 — the last capture before the original
site broke).

**Re-running the crawlers is not just unnecessary, it is a step backwards.** Their output is
already committed, and the committed copies carry content corrections that a fresh crawl would
discard.

`parse_xml.py` is the one exception worth knowing about: it regenerates `archive/xml/*.json` from
the WordPress XML export. That output is committed too, so it is not part of a normal rebuild —
you would only run it to change how content is parsed. The export itself is not in this
repository; it contains personal data and is handed over privately.

## What is committed under archive/

Contrary to what this file used to say, most of it is:

| Path | Committed? | Why |
|---|---|---|
| `archive/html/` | **Yes** | The builder reads it — the home page is generated from archived HTML |
| `archive/xml/` | **Yes** | Parsed content, plus the video URL map and placement registry |
| `archive/audit/` | **Yes** | Audit reports and the 51 stations as structured fields |
| `archive/images/` | No | Large, and no longer needed — `site/images/` is committed and supersedes it |

If `archive/images/` is absent, the builder says so and carries on using the committed files in
`site/images/`. That is the expected state on a fresh clone.

## Normal workflow

```
uv run python scraper/build_site.py     # regenerate site/
git add site/ && git commit
git push origin dev                     # Netlify deploys the preview
```

Promotion from `dev` to `main` — which is what GitHub Pages serves — is a separate, deliberate
step. See `docs/deployment.md`.
