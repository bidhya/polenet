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
  embedded via YouTube iframe instead (personal-account interim, Unlisted; official-channel
  migration still owed — see the playbook at the end of this file).

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

## Video migration playbook — the one substantial pending task
Not blocking anything. Do this whenever the project confirms access to its official channel.

> **First establish what that channel actually is.** The legacy `youtube.com/user/polenet`
> address returns 404 — YouTube retired the `/user/` URL format, which is *not* the same as the
> channel being gone. Nobody has confirmed the current address, so treat it as an open question
> for the project team rather than guessing a replacement URL.

Once the destination is known this can be executed end-to-end —
it's the exact same pattern as the original personal-account upload, just pointed at a
different channel. That original run is described in `docs/project-report.md` (Phase 7b–7c);
the operational detail you actually need is in the steps below.

**Backup, already done (2026-07-26):** `archive/xml/video_url_map.personal-backup.json` is a
frozen copy of the working, verified personal-account URL map (all 35 filled). **Before
overwriting `video_url_map.json` with official-channel URLs, confirm this backup file still
exists and is current** — if `video_url_map.json` has since changed for any other reason,
re-copy it to the backup path first so the fallback is never stale.

**Why a backup file instead of automatic runtime fallback:** `build_site.py` does not (and
should not) verify video URLs are actually live at build time — that would mean hitting
YouTube on every build, and we already know repeated automated requests to YouTube get
rate-limited (see the steps below). A static backup file that can be manually
restore from is simpler and doesn't add a network dependency to the build.

**Upload steps** (same as the original run):
1. Download the 35 files from `archive/images/videos/*.mov`/`*.mp4` (if not still present locally)
   or re-fetch via `uv run python scraper/fetch_live_uploads.py` if needed — though at
   this point the currently-live personal-account YouTube copies could also serve as the
   source video files if the local originals are gone; either works.
2. Upload all 35 to the official channel via YouTube Studio, same as before: bulk-upload,
   leave titles matching original filenames (critical — that's how matching works), set each
   to Unlisted, publish. Check both the "Videos" and "Shorts" tabs afterward — short clips
   (under ~60s) get auto-routed to Shorts, this tripped us up once already.
3. Send the new links back in batches, bare URLs, any order — no need to label with filenames.

**Once the new links arrive:**
1. Confirm/refresh `video_url_map.personal-backup.json` per the backup note above.
2. For each new URL: fetch the video's page individually (`curl -sk` on
   `https://www.youtube.com/watch?v={id}`, ~2s delay between requests — do NOT repeatedly hit
   the playlist listing page, it rate-limits after 2-3 requests), extract the real `<title>`
   from the page and the `playabilityStatus`/`isPrivate` fields from the embedded
   `ytInitialPlayerResponse` JSON, and match the title to the right filename key in
   `video_url_map.json`. Cross-check for duplicate video IDs (within the batch and against
   ones already mapped) before writing anything.
3. Overwrite each matched entry in `video_url_map.json` with the new official-channel URL.
4. Rebuild (`uv run python scraper/build_site.py`), verify all 35 embeds still render (grep
   for `wp-block-embed-youtube` count across the 3 field-season pages — should total 35: 5 in
   2023-2024, 8 in 2024-2025, 22 in 2025-2026), confirm 0 missing images / 0 dead links (same
   regression checks used throughout this project).
5. Commit + push to `dev`, confirm live on the Netlify preview before merging to `main`.

**If the official-channel URLs turn out broken/restricted for some reason:** restore
`video_url_map.json` from `video_url_map.personal-backup.json`, rebuild, commit, push. This
puts the site back on the known-working personal-account videos while the issue gets sorted.
