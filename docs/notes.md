# Technical Reference — polenet.org

Lookup detail for working on the build. **Not a status document** — for how any of this came
about, and what a successor needs, see `docs/project-report.md` and `docs/handover.md`.

## Content Sources
| Source | What it provides |
|--------|-----------------|
| `archive/xml/pages.json` | 135 published WP pages with cleaned HTML content |
| `archive/xml/posts.json` | 29 published posts, chronological 2010–2024 |
| `archive/xml/attachments.json` | 928 media library entries with original upload URLs |
| `archive/xml/video_placements.json` | 35 stripped-video records: page, filename, caption (regenerated every build) |
| `archive/xml/video_url_map.json` | filename → hosting URL for each video |
| `archive/html/` | Wayback-crawled HTML — **committed since 2026-08-12** so a clone can rebuild (the captured wp-login page stays ignored) |
| `archive/images/` | Downloaded photos, flat (gitignored) — **the build no longer needs this**; `site/images/` supersedes it |
| `archive/images/videos/` | The 35 field videos (organized 2026-07-28) |
| `archive/images/pdfs/` | 6 linked PDFs (organized 2026-07-28) |

## Site Structure — detail

**Title:** POLENET: The Polar Earth Observing Network

| Section | Count | Location |
|---------|-------|----------|
| Nav pages (home, about, sites, photos, publications, training, blog-index) | 7 | `site/*.html` |
| Monitoring station detail pages | 51 | `site/sites/` |
| Blog posts + index | 30 | `site/blog/` |
| Training school pages | 6 | `site/training/` |
| Extra content pages | 22 | `site/*.html` |

**Extra pages grew 11 → 22 on 2026-07-28**: added 11 real published training-school
sub-pages (course content, agendas, photo pages, homework prep, code of conduct, poster
gallery) that were in the XML export but never built — found by a full-site link regression;
see `docs/project-report.md` §6.

**Extra pages** (all reachable from the nav/footer since 2026-07-26, `5de936e` — "In the News"
is a top-level nav item, Meet the Researchers/Quick Facts link from About, Data from Sites and
Data, Links from the footer, and the 3 field-season pages are pinned atop the Blog index):
`in-the-news.html`, `data.html`, `meet-the-researchers.html`, `quick-facts.html`, `links.html`,
`2023-2024-field-season-progress.html`, `2024-2025-field-season-progress.html`, `2025-2026-field-season-progress-page.html`,
`researchers-brave-antarcticas-wind-chill-to-track-climate-change-at-the-bottom-of-the-world.html`,
`plane-crash-wont-keep-osu-scientist-off-the-ice.html`, `scientists-explore-ice-caps.html`
(last 3 added 2026-07-26 — press reprints linked from `in-the-news.html`)

## Images
- **Present:** 539 images/PDFs in `site/images/`, 0 missing refs (429 → 539 on 2026-07-28,
  recovering the 110 files newly referenced by the 11 training sub-pages added that day)
- **Recovery method:** `scraper/fetch_live_uploads.py` pulls directly from the live
  `polenet.org` WordPress REST API media index over HTTPS — no FTP/SFTP/cPanel needed
  (that was the original plan; turned out unnecessary once we confirmed the site is live,
  not offline — see Root Cause section above)
- 268 files recovered in this pass, 0 failures
- `archive/xml/images_to_fetch.json` (134 entries) is now stale/historical — it predates
  the 2026-07-26 recount and recovery; not the current source of truth for anything
- **Videos are separate:** 35 files (554 MB on disk) never copied to `site/images/` — they're
  embedded via YouTube iframe instead, from the project's own channel and Unlisted. See the
  **"Videos"** section at the end of this file.

## Build Pipeline Scripts
| Script | Purpose | Run order |
|--------|---------|-----------|
| `scraper/build_site.py` | JSON + archived HTML → `site/` (115 pages) | **the only script a normal rebuild needs** |
| `scraper/parse_xml.py` | WXR XML → `archive/xml/*.json` | only to regenerate the JSON (already committed); needs the gitignored export |
| `scraper/fetch_live_uploads.py` | Original server's media index → download missing images/PDFs over HTTPS | historical — one-off recovery, 2026-07-26 |
| `scraper/fetch_missing_images.py` | Wayback CDX → download anything the server lacked | historical fallback |
| `scraper/fetch_archive.py` | CDX API → Wayback HTML snapshots | historical |
| `scraper/crawl_site.py` | Full Wayback site crawl | historical |
| `scraper/audit.py` | Classify pages, generate site_index.json | historical |

## Key Technical Notes
- **lxml required** for XML parsing (`recover=True`) — stdlib `xml.etree.ElementTree` crashes on WXR
- `xml_to_html(content, depth, page_slug)` in `build_site.py` handles image path depth for subdirectory pages
- Internal WP links (`?page_id=NNN`) resolved via `ID_TO_PATH` (built by `build_id_to_path()`) to the
  real local page where known; unresolved ones are unwrapped to plain text — **not** rewritten to
  `href="#"` anymore (fixed 2026-07-26; that was leaving dead-looking links)
- Video blocks are stripped from content (see `_WP_VIDEO_BLOCK`/`_VIDEO_TAG`) and recorded into
  `archive/xml/video_placements.json` before removal, so they can be re-inserted as embeds
- `build_blog()` clears all `blog/*.html` before regenerating (prevents stale files)
- Home page built from Wayback HTML — XML version is heavy Gutenberg layout blocks

---

## Videos — how they are hosted, and what is safe to change

**Status: complete.** All 35 videos were migrated to the project's official YouTube channel on
2026-08-17. Nothing about the videos is outstanding.

### Where they live

| | |
|---|---|
| Channel | **POLENET Science** — `https://www.youtube.com/@polenetscience` |
| Channel ID | `UC_rZ7us194LIZ4PF3GaiiJQ` |
| Count | 35 |
| Visibility | **Unlisted** (5 of them are Shorts, being under ~60s) |
| Appear on | 3 pages only — the 2023-2024, 2024-2025 and 2025-2026 field-season progress pages |

The video files themselves are **not** in this repository — they are large, and the site embeds
them from YouTube rather than serving them. The originals live outside the repo in
`archive/images/videos/` on the maintainer's machine.

### How they were uploaded

Briefly, for the record:

1. Uploaded to the channel through YouTube Studio in four batches over one session.
2. Titles were left as the original filenames. YouTube tidies these automatically — it strips
   the extension and turns `_`, `-` and `.` into spaces — so `Digging-out-MCRG-seismic.mov`
   became `Digging out MCRG seismic`. That transformation is reversible and produced no
   ambiguity across all 35 names, which is how each video was matched back to the right page.
3. Each upload was finished through the wizard (an unfinished upload sits as a **Draft** and has
   no visibility and no shareable link), and set to **Unlisted** on the last step.
4. The resulting links were fed into `archive/xml/video_url_map.json`, and the site rebuilt.

### Why Unlisted rather than Public

Public and Unlisted behave **identically** when embedded on the website. The only difference is
discoverability on YouTube itself: Unlisted videos do not appear on the channel's Videos tab, in
YouTube search, in recommendations, or in subscriber notifications.

These 35 are raw field clips — a few seconds of blowing snow, someone digging out a sensor. The
channel also carries a curated, produced series. Publishing 35 unedited clips would bury that
series under raw footage, and the five that became Shorts would be pushed into YouTube's Shorts
feed for algorithmic distribution, stripped of the captions that give them meaning.

**Unlisted is not privacy.** Anyone with the link can watch without signing in, and the links are
in the public HTML of three pages. It is a presentation choice about the channel, nothing more.

### For the team — what is safe to change

**Safe. Changes nothing on the website:**

- Switching any or all videos from Unlisted to **Public**, or back. No rebuild, no developer
  involvement, no change to the site at all. If the team would rather this footage were
  discoverable on YouTube, that is a bulk edit in Studio and nothing else.
- **Renaming** videos, adding descriptions, thumbnails, chapters, captions. The website
  references videos by ID, not by title, so titles can be tidied up freely — and several would
  benefit (`lucas marathion` is misspelled; `IMG 6226` was never named).
- Adding them to playlists.

**Breaks the website. Avoid, or tell the developer:**

- Setting a video to **Private** — the page shows "Video unavailable" instead of playing. This is
  the dangerous one, because Private sits directly next to Unlisted in the same dropdown.
- **Deleting** a video.
- **Deleting and re-uploading** a video, even the identical file with the identical name. A
  re-upload gets a **new ID**, and the old one stored by the site is now dead. This is the
  subtle one — it looks like nothing happened, and the broken page would not be noticed unless
  someone looked at it.
- A **copyright block** escalating. `film festival mod17` already carries a partial block, so it
  cannot be played in some countries.

The rule of thumb: **changing a video's visibility or details is safe; changing whether it exists
is not.**

### For a developer — the mechanism

`archive/xml/video_url_map.json` maps **original filename → video URL**. During the build,
`build_site.py` looks the filename up, extracts the 11-character YouTube ID from whatever URL
form it finds (`youtu.be/`, `watch?v=`, `embed/` and `shorts/` are all accepted, query strings
ignored), and emits an `<iframe>` pointing at `youtube.com/embed/<id>`.

Consequences worth knowing:

- **The build has no concept of an account.** The 35 could come from 35 different channels and
  nothing would behave differently. A partial migration is therefore always a valid state.
- **It must be YouTube.** The ID extractor only understands YouTube URL shapes and the output
  template hardcodes `youtube.com/embed/`. A Vimeo or university-hosted URL would be **silently
  ignored** and the video would simply vanish from the page — no error. Relevant if the site
  ever moves to hosting that prefers its own video platform.
- **The build never checks that a URL still works.** That is deliberate — it would put a
  rate-limited network dependency into every build. Breakage is therefore silent, which is why
  the "safe to change" list above matters.

**To replace a video:** put the new URL against the right filename key in `video_url_map.json`,
run `uv run python scraper/build_site.py`, and commit the map plus the three regenerated pages.

### Verification after any video change

```bash
uv run python scraper/build_site.py
for p in 2023-2024-field-season-progress 2024-2025-field-season-progress \
         2025-2026-field-season-progress-page; do
  printf "%s %s\n" "$(grep -c wp-block-embed-youtube site/$p.html)" "$p"
done            # must read 5, 8, 22
```
