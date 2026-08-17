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

**Destination confirmed 2026-08-14:** the project's official channel is
**POLENET Science** — `https://www.youtube.com/@polenetscience` (channel ID
`UC_rZ7us194LIZ4PF3GaiiJQ`). It is live and already hosts a curated video series. This
replaces the long-standing open question about the channel address; the legacy
`youtube.com/user/polenet` form returns 404 only because YouTube retired the `/user/` URL
format.

Nothing is blocked on this. The site works today. What follows is a plan that can be picked up,
put down, and resumed weeks later without losing state.

### The property that makes this resumable

`video_url_map.json` maps **original filename → video URL**, and the build injects an embed
wherever `video_placements.json` says one belongs. The build does not care *which* channel a URL
points at, and it never validates URLs at build time.

**So a half-migrated map is a completely valid map.** Batches can be migrated, committed and
deployed independently — there is no flag day, no all-or-nothing cutover, and no state held
anywhere except that one JSON file. Stopping halfway leaves a working site.

### Batches

They group naturally by the page they appear on, which also makes each batch independently
verifiable:

| Batch | Page | Videos | Size |
|---|---|---|---|
| A | `2023-2024-field-season-progress` | 5 | 48.5 MB |
| B | `2024-2025-field-season-progress` | 8 | 144.4 MB |
| C | `2025-2026-field-season-progress-page` | 22 | 387.0 MB |
| | **Total** | **35** | **~580 MB** |

Start with A. It is the smallest, and it exercises every step of the process end to end before
any real time goes into uploading.

Largest single files, worth knowing for upload time: `polenet_UG_film_4k.mp4` (89.5 MB),
`New-Year-Arrives_Eric_125.mp4` (80.8 MB), `film_festival_mod17.mp4` (72.8 MB).

### The loop, per batch

**Yours:**
1. Bulk-upload the batch from `archive/images/videos/` via YouTube Studio.
2. **Leave each title exactly the original filename, extension included.** Title text is the
   only thing matching keys on. See "renaming" below — this is temporary.
3. Set visibility **Unlisted**.
4. **Check the Shorts tab afterwards.** Clips under ~60s are auto-routed there and will not
   appear under Videos. This caught the project out once already.
5. Send the links back — bare URLs, any order, no labels needed.

**Mine:**
6. Confirm `video_url_map.personal-backup.json` is still current before touching anything.
7. Fetch each video page individually — `https://www.youtube.com/watch?v={id}`, ~2s apart. **Do
   not** poll the channel or playlist listing; it rate-limits after 2–3 requests.
8. Read the real `<title>` and the `playabilityStatus`/`isPrivate` fields from the embedded
   `ytInitialPlayerResponse` JSON. Match title → filename key. Cross-check for duplicate video
   IDs, both within the batch and against entries already mapped.
9. Overwrite only that batch's entries in `video_url_map.json`.
10. Rebuild and verify the per-page embed counts still read 5 / 8 / 22 (total 35), with 0
    missing images and 0 dead internal links.
11. Commit, push to `dev`, check the preview, then merge to `main`.

### Visibility: Unlisted, deliberately

The channel's existing videos are Public, but these 35 should not be. They are raw field clips
that exist to be embedded in three pages — publishing them would push 35 unedited files onto the
channel's Videos tab and bury the curated series already there. Unlisted affects only browsing
and search; embedded playback is identical.

### Renaming, after the fact

Filenames-as-titles is required only at the moment the links are captured. The map stores URLs,
not titles, so **renaming the videos to human-readable titles afterwards breaks nothing.** Do the
whole migration first, then rename at leisure.

### Rollback

If official-channel URLs turn out to be broken or restricted, restore `video_url_map.json` from
`video_url_map.personal-backup.json`, rebuild, commit, push. That returns the site to the
previously verified, known-working URLs while the problem is sorted out.

**Why a backup file rather than runtime fallback:** `build_site.py` does not verify video URLs at
build time and should not — that would put a network dependency, and a rate-limited one, into
every build. A static file that can be restored by hand is simpler and cannot fail silently.

### When all three batches are done

- Rename titles on the channel if wanted (see above).
- Decide what happens to the previous copies. Leaving them costs nothing; removing them is
  cleaner. Either way, do it only after all 35 are verified live from the new source.
- Update the STATUS block in `AGENTS.md` and `docs/todo.md` to close the item.

### Verification commands

```bash
uv run python scraper/build_site.py
for p in 2023-2024-field-season-progress 2024-2025-field-season-progress \
         2025-2026-field-season-progress-page; do
  printf "%s %s\n" "$(grep -c wp-block-embed-youtube site/$p.html)" "$p"
done            # must read 5, 8, 22
python3 -c "import json; m=json.load(open('archive/xml/video_url_map.json')); \
  print(sum(1 for v in m.values() if v), 'of', len(m), 'mapped')"
```
