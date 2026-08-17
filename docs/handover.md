# Handover — what a new developer needs

*Last verified 2026-08-17. Safe to share as-is: no credentials, no operational detail about the
legacy installation.*

---

## The short version

| Hand over | How |
|---|---|
| The repository | Public — just send the link: `https://github.com/bidhya/polenet` |
| The WordPress XML export (13 MB) | Any direct transfer. Not through the repo — see below |
| `docs/` (or at minimum `docs/project-report.md`) | Directly — it is gitignored, so not in the repo |

That is everything. No other accounts, credentials, or third-party access is required.

**Simplest option: send the whole project folder.** It contains all three of the above plus the
554 MB of original video files, and nothing in it is secret — no credentials, tokens or
passwords, by standing project rule. Skip `.venv/`; it is a throwaway Python environment that
`uv sync` recreates. Everything else travels.

The only thing to keep in mind is *where* the copy lives rather than who reads it: the export
carries a few third-party email and IP addresses from the original site's comments, so a direct
transfer or a private drive is right, and a public or indexable location is not.

---

## "Can they just clone the repo and rebuild the site?"

**Yes.** Verified 2026-08-12 by cloning from GitHub into a clean directory and building:

```bash
git clone https://github.com/bidhya/polenet.git && cd polenet
uv run python scraper/build_site.py
git status --short      # clean — the rebuild is byte-identical to what is deployed
```

115 pages, 160 gallery images, 43 station photos, 35 video embeds, zero differences.

To *host* the site rather than rebuild it, they need even less: `site/` is self-contained static
HTML. Point any static host at that folder. No Python, no database, no build step.

> This became true only on 2026-08-12. Before that, a fresh clone crashed — and in one case
> built a **silently broken** site. The full account is in `project-report.md` §6.

---

## "Do they still need the Wayback Machine?"

**No.** The material was scraped once, early in the project, and the results are committed.

The original site was recovered from the Internet Archive snapshot of **7 December 2025** — the
last capture before the site broke. `scraper/fetch_archive.py` and `scraper/crawl_site.py` did
that crawl and saved the pages to `archive/html/`, **which is now committed to the repository**
(100 files, 5.9 MB).

The builder reads those files directly — most importantly for the home page, which is generated
from the archived HTML rather than the WordPress export. So the Wayback dependency was resolved
at scrape time, not at build time. Those two scraper scripts are historical; nobody needs to run
them again, and the Internet Archive is never contacted during a build.

---

## "Do they still need access to the old WordPress site?"

**No.** Same reason: everything usable was pulled down and committed.

The archived crawl was missing most of the media — 303 of 386 referenced files, about 78%. Those
were recovered directly over public HTTPS by `scraper/fetch_live_uploads.py`, which read the
original site's public media index and downloaded each file. **268 of 268 recovered, zero
failures.** All of it now lives in `site/images/` — 539 images and PDFs, committed, with **zero
missing references** anywhere in the built site.

So the old site is not a live dependency. No login, no FTP, no hosting-provider involvement, and
nothing breaks if it goes away tomorrow. That script is also historical.

---

## "Then why hand over the XML export at all?"

Two reasons, and neither is required for a normal rebuild:

1. **Re-parsing the content.** `scraper/parse_xml.py` turns the export into
   `archive/xml/*.json`. That output is already committed, so this only matters if someone wants
   to regenerate it or change how content is parsed.
2. **Migrating to a CMS — this is the real reason.** The export is the authoritative original in
   standard **WXR** format, which Drupal and most other CMSs import natively. It is by far the
   most valuable artifact for that job.

**Why it is not in the repository:** a WordPress export contains more than the visible content.
This one holds 3 author email addresses, 3 WordPress usernames, 5 commenter email addresses,
5 commenter IP addresses, and 19 draft or private posts that were never published. That is other
people's data, so it stays out of a public repository — but handing the file directly to someone
working on the project is exactly what it is for, and needs no ceremony.

The line is *public versus not*, rather than who receives it. If it ever has to go somewhere open,
sanitize first: strip every `wp:author_email`, `wp:author_login`, `wp:comment_author_email` and
`wp:comment_author_IP` element, and drop any item whose `wp:status` is not `publish`.

---

## If they plan to move to Drupal or another CMS

Read `project-report.md` §10 first — the answer is counter-intuitive:

- **Do not import from `site/`.** It is rendered HTML; pulling structure back out of it repeats
  work already finished.
- **Do use** the XML export as the import source, plus `archive/xml/*.json` (parsed content) and
  `archive/audit/site_index.json` (the 51 monitoring stations as real fields, not prose).
- **The trap:** neither source is complete alone. `site/` is *corrected* but rendered — it
  carries every content fix made during this project. The raw export is *structured* but
  uncorrected. Importing purely from the export silently reintroduces every bug fixed here. Use
  the export as the source and `site/` as the reference for what correct output looks like.

---

## Dependencies that travel with the site

- **35 field videos are embedded from the project's YouTube channel**, POLENET Science
  (`youtube.com/@polenetscience`), Unlisted. Migrated there on 2026-08-17, so the site no longer
  depends on any individual's account. Replacing a video is a one-line change in
  `archive/xml/video_url_map.json` followed by a rebuild. **`docs/notes.md`, "Videos", is the
  reference to hand to whoever manages that channel** — it sets out what is safe to change
  (visibility, titles, descriptions) and what silently breaks these pages (deleting a video, or
  deleting and re-uploading it, which issues a new ID).
- **The photo gallery loads GLightbox from a CDN** — the only third-party *code* the site runs
  (the video iframes are the other external requests). It is **pinned to an exact version**,
  `glightbox@3.3.1`, deliberately: an unpinned CDN path resolves to whatever is latest, so a
  future major release could have broken the gallery with no change in this repository and nobody
  watching. Keep it pinned.
- **`SITE_BASE_URL` near the top of `build_site.py` is the only absolute URL the build emits.**
  It feeds `sitemap.xml` and `robots.txt`; every link in the pages themselves is relative. **If
  the site ever moves to another domain, change that one line and rebuild** — otherwise the
  sitemap keeps advertising the old addresses to search engines. `robots.txt` is inert while the
  site is served from a project subpath and becomes effective at a domain root.
- **`site/README.md` says "do not edit files here directly."** True while the generator is in
  use, wrong for anyone handed `site/` as their source. Update it if the generator is abandoned.
- **The site is generated, so hand-editing is a one-way door.** Navigation and footer are
  duplicated across all 115 pages, and re-running the builder overwrites manual edits. Pick one
  mode deliberately.

---

## Further reading (all in `docs/`, none of it in the repo)

| File | What it covers |
|---|---|
| `project-report.md` | Full technical report — how it was built, bugs found, architecture, §10 handover |
| `deployment.md` | Hosting, branch strategy, domain connection |
| — | The maintainer also keeps an internal running log and task tracker outside this repo; ask if you need the reasoning behind a specific decision. |
