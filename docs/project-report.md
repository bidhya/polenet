# Rebuilding polenet.org — Project Report

**Project:** migrating polenet.org (POLENET — The Polar Earth Observing Network) from a broken
WordPress installation to a static HTML/CSS site.
**Duration:** 2026-06-30 → 2026-08-12 (52 commits)
**Outcome:** 115-page static site, content-complete, live on two hosts, pending content review.

> **Scope note.** This is the end-to-end technical record: what was done, why, what went wrong,
> and what a successor needs to know. It deliberately omits operational detail about the legacy
> installation; the maintainer keeps a fuller internal log covering that.

---

## 1. At a glance

| | |
|---|---|
| Pages built | 115 |
| Monitoring station pages | 51 (station ID, coordinates, install dates) |
| Blog posts | 29, spanning 2010–2024, plus index |
| Training school pages | 6 top-level + 11 supporting |
| Images & PDFs | 539, zero missing references |
| Photo gallery | 160 images, lightbox viewer |
| Field videos | 35, embedded |
| Dead links | 0 |
| Automation written | ~2,860 lines of Python across 7 scripts |
| Runtime dependencies | None (no database, no PHP, no build step) |

---

## 2. Background — what broke

polenet.org ran on WordPress with a third-party commercial theme. Sometime between December
2025 and February 2026 the site stopped rendering: the theme had fallen out of compatibility
with its hosting environment, most likely following a routine server-side software upgrade the
theme was never updated to accommodate.

The Internet Archive corroborates the timing precisely. Wayback Machine captures return HTTP
200 through **December 7, 2025**, then HTTP 301 redirects from **February 3, 2026** onward.
That gap bounds the failure window and, usefully, identified the last known-good capture of the
site — snapshot `20251207055143` — which became the project's reference point.

### Choosing the reference snapshot

Querying the Internet Archive's CDX API for every capture from 2025 onward gave a clear picture:

| Captured | Status | Reading |
|---|---|---|
| Jan–Aug 2025 | 301 | Redirect — see the false signal below |
| 6 Sep 2025 | **200** | Working |
| 19 Nov 2025 | **200** | Working |
| **7 Dec 2025** | **200** | **Working — most recent good capture; the one used** |
| 3 Feb 2026 | 301 | Already broken |
| Mar–Apr 2026 | 301 | Still broken |

`20251207055143` was selected as the last known-good capture. It was verified rather than
assumed: correct page title, all 7 navigation items present and linked, images resolving
through the archive, blog posts rendering, and the original theme markup intact as a layout
reference.

**One false signal worth recording.** The 301s through early-to-mid 2025 look alarming but are
unrelated to the failure: the site redirected the bare domain to its `www` form during that
period, and the archive was capturing the non-`www` URL. A redirect is not evidence of an
outage, and reading it as one would have pushed the reference point back by months for no
reason.

The project's original assumption had been that the site worked until roughly February 2026.
The archive disproved that — the February capture was already a redirect — which is how
December 2025 became the reference point.

### The decision that followed

**Migrate off WordPress permanently rather than repair the theme.** Made early and never
revisited. Repairing it would have restored the site to the same fragile footing — a stack whose
failure mode had just been demonstrated.

---

## 3. A wrong premise, corrected

The project began on a false assumption worth recording, because it shaped a month of work.

Initial notes stated the database and server were lost with no backup. Every early decision
followed from that: the Wayback Machine was treated as the *only* content source, and the plan
for recovering missing media assumed FTP or hosting-provider intervention would eventually be
required.

**On 2026-07-26 this was found to be wrong.** The original content was still present and
retrievable. The consequences were immediate and large:

- The WordPress XML export became available as a **primary** content source, far richer and
  cleaner than scraped HTML.
- Missing media could be retrieved directly over public HTTPS — no third-party access request,
  no credentials, no waiting.
- A drafted request to the hosting team was never sent; it had been built on the wrong premise.

A secondary lesson came bundled with this. An earlier automated session had concluded the site
was entirely offline based on `curl` failures. That reading was false — the failures came from
a certificate-trust gap in that sandbox, not from the server. Verifying independently
(`openssl s_client`) showed a valid certificate the whole time. **A tool failing is not the
same as the thing it points at being broken**, and the distinction cost real time here.

---

## 4. Approach

Two content sources, used in priority order:

1. **WordPress XML export (WXR)** — primary. 135 published pages, 29 posts, 928 media
   attachments. Structured, complete, authoritative.
2. **Wayback Machine, snapshot `20251207055143`** — fallback, and the layout reference. Used
   where the XML content was unusable (notably the home page, whose XML is dense layout-builder
   markup rather than prose).

Output target: plain HTML, one stylesheet, no framework, no database, no build step at serve
time.

---

## 5. How it was built, phase by phase

### Phase 1–2: Archive extraction and crawl (2026-06-30)
`fetch_archive.py` queried the Wayback CDX API to identify and pull the last good snapshot.
`crawl_site.py` then walked the archived site in full — 7 navigation pages, 51 station detail
pages, blog and training posts, gallery pages — capturing 162 images and 74 theme assets.

### Phase 3: Audit (2026-06-30)
`audit.py` classified all 101 captured HTML files by type and produced a machine-readable
station index. This step is what made the station pages tractable: it extracted 51 stations
into structured records (`station_id`, `coordinate`, `installed`, `transport`, `hub`) rather
than leaving them as prose to be hand-transcribed.

### Phase 4: First rebuild (2026-06-30)
`build_site.py` generated the initial 101-page site from a single template, with a hand-written
stylesheet. WordPress residue was stripped in the process: comment forms, tracking nonces,
external avatar calls, archive-wrapper URLs.

### Phase 5: Deployment (2026-07-01)
Netlify, publishing `site/` directly with no build command. A `dev` branch drove a preview
deploy; `main` was deliberately left paused so nothing went public prematurely.

### Phase 6: WordPress XML import (2026-07-01) — the turning point
`parse_xml.py` parsed the WXR export into JSON, and `build_site.py` was restructured to treat
the XML as primary with Wayback HTML as fallback. This single change was the largest quality
jump in the project:

- Blog coverage went from 11 posts to **29** — the complete history back to 2010.
- The site grew from 75 to **101** pages.
- Content came through as authored, rather than as theme-rendered HTML needing reverse
  engineering.

Two format hazards had to be handled: the WXR file contains characters that crash Python's
standard XML parser (requiring `lxml` with `recover=True`), and newer content is wrapped in
layout-block comments and legacy shortcodes, both of which needed stripping.

### Phase 7: Media recovery (2026-07-26)
A direct scan of the built HTML found the real gap was far worse than estimated: **303 of 386
referenced files were missing — 78%.** The Wayback Machine had never archived most of the
media library.

`fetch_live_uploads.py` resolved this by reading the original site's public media index and
mapping 6,323 filename→URL variants, then downloading over HTTPS. **Result: 268 of 268
recoverable files retrieved, zero failures.** The photo gallery went from 77 images to 135.

### Phase 7b–7c: Video handling (2026-07-26)
35 genuine embedded videos (554 MB — 29 `.mov` totalling 297 MB and 6 `.mp4` totalling 256 MB;
earlier notes said ~298 MB, having counted only the `.mov` files) were discovered in the
original content — real media the
Wayback Machine had never captured. Committing them would have permanently bloated the
repository, so they were excluded from the build and handled separately.

They were uploaded to YouTube as unlisted videos and embedded via a flat filename→URL map
(`video_url_map.json`), keeping the substitution trivially reversible. Matching returned URLs
back to source files required care: upload titles were preserved as filenames, each video's
page was fetched individually to read its real title, and each was checked for embeddability
before being trusted. All 35 IDs were verified unique before commit.

**Completed 2026-08-17.** The videos initially sat on an interim account while the project's own
channel was being identified. All 35 were then re-uploaded to **POLENET Science**
(`youtube.com/@polenetscience`) and the map swapped over in four batches.

Two things made that migration cheap, and both were design decisions taken earlier rather than
luck. The map is keyed by filename and the build extracts the video ID from whatever URL form it
finds, so **a half-migrated map is a valid map** — the batches could be verified and deployed
independently, with no cutover moment. And because the build never validates URLs, nothing had to
be coordinated with YouTube at build time. The previous URL set was kept intact as
`video_url_map.personal-backup.json`, making the whole change reversible with one file copy and a
rebuild.

One wrinkle worth recording: YouTube rewrites uploaded titles, stripping extensions and turning
`_`, `-` and `.` into spaces. Matching returned links back to source files therefore normalises
both sides before comparing. That transformation was checked against all 35 filenames first and
produced no collisions, so every video could be matched unambiguously.

### Phase 8: Second host and hardening (2026-07-28 → 2026-08-12)
GitHub Pages was added as an independent second host once the repository was made public
(after a security audit — see §7). Adding it exposed two genuine latent bugs, covered below.

---

## 6. Bugs worth recording

### Relative-path depth errors, hidden by a coincidence
Subdirectory pages emitted one `../` too many, and the gallery page emitted one it didn't need.
**Netlify never revealed this**: it serves at a domain root, where an excess `../` simply clamps
back to root under standard URL resolution. GitHub Pages serves a project site under an extra
path segment, where the same paths overshoot past the site root and break.

~87 pages had broken CSS, navigation, and images under the subpath — from a defect that had
been latent and invisible for a month.

**The deeper lesson concerns verification.** Earlier checks had confirmed pages returned HTTP
200. That says nothing about whether *that page's own asset links* resolved. A page can return
200 while its stylesheet, navigation, and images all 404. Every check since resolves assets,
not just page URLs.

A proactive audit of every other hardcoded path found a third instance of the same defect class
before it could surface.

### Fifteen dead links, eleven of them real missing pages
A full-site link regression — every `href` and `src` on every page, resolved and requested
against a running server — found 15 broken links. Eleven were **published pages that existed in
the export but had never been built**: training-school agendas, course content, homework
preparation, poster galleries. They were added, along with 110 further images they referenced
(429 → 539 files).

The previous "0 dead links" claim had simply gone stale; it predated the content that broke it.
Point-in-time verification expires, and dated claims in documentation need re-running rather
than trusting.

### A repository that could not rebuild itself

Found near the end of the project, and the most consequential of the three. The build read two
gitignored directories that existed only on the original workstation. A fresh clone therefore
crashed on the home page — and if only the image directory was missing, it did something worse:
**exited successfully while producing a broken site**, with the photo gallery silently reduced
from 160 images to 0 and 43 station pages stripped of photos. A successful exit code, no
warning, and output that looked plausible enough to commit.

The obvious remedy was to commit the 624 MB image directory. That turned out to be unnecessary:
`site/images/` was *already committed* and held a filename-for-filename identical set. The build
had simply been reading the wrong copy of data the repository already contained. Repointing two
globs fixed the entire image half at zero storage cost; only the 5.9 MB of archived HTML
genuinely needed committing.

**Two lessons, both general.** First, an expensive-looking fix deserves a few minutes of
measurement before being accepted — the assumed 624 MB cost was off by two orders of magnitude.
Second, a build that can fail silently will eventually do so unobserved, so the guard added here
makes an empty gallery a hard error rather than a quiet regression.

Verified by cloning from the public repository into a clean directory and rebuilding —
byte-identical output. Anyone can repeat it:

```bash
git clone https://github.com/bidhya/polenet.git /tmp/clonetest && cd /tmp/clonetest
uv run python scraper/build_site.py
git status --short                            # expect 0 — byte-identical rebuild
grep -c 'class="glightbox' site/photos.html   # expect 160
```

If that gallery count is ever wrong, the build should have refused to run; if it did not, the
guard in `build_photos()` has been removed or bypassed.

---

## 7. Security review before going public

The repository was made public on 2026-07-28 for free-tier hosting continuity. Two distinct
passes preceded that, and the difference between them is the point:

1. **A credential audit** scanned every blob across all commits for keys, tokens, passwords,
   and private keys. Clean.
2. **A separate operational-disclosure review** caught what the first one structurally could
   not: two *currently tracked* files described the legacy backend's state in terms that
   shouldn't be broadcast. Not credentials — nothing a secret-scanner would flag — but exactly
   the sort of detail that makes a system a more attractive target. Both were reworded before
   the visibility flip.

**A clean secret scan is not a clean security review.** They answer different questions, and
only running the first would have shipped the problem.

One low-severity historical item was knowingly left alone: two early commits name the broken
theme. Rewriting history to remove a vendor name was judged disproportionate to the benefit.

A third audit, run at handover time, checked the WordPress export and the committed artifacts
for personal data. The export itself holds author and commenter email addresses, commenter IP
addresses, WordPress usernames, and 19 unpublished draft/private posts — which is why it is
excluded from the repository and passed on privately instead. The committed parsed JSON carries
none of it, and the handful of addresses that do appear in the built site are training-school
organiser contacts that were public on the original site. **Exporting a CMS produces more than
the content you can see** — publishing an export wholesale is a straightforward way to leak
personal data without noticing.

---

## 8. How the finished system works

The architecture is deliberately unglamorous:

```
build locally  →  commit site/  →  push  →  host serves it
```

`site/` is generated on a workstation and **committed as finished HTML**. Git stores output,
not a recipe. Neither host builds anything — the GitHub Actions workflow uploads the committed
folder as an artifact, and Netlify publishes it with no build command. There is no Python in
CI anywhere.

The practical consequence: **changing the generator alone changes nothing live.** The build has
to be re-run and its output committed. Netlify will in fact skip the deploy entirely if `site/`
is unchanged.

The tradeoff is a large repository — roughly 600 MB, almost entirely committed media — in
exchange for a deployment with no moving parts, reproducible by pointing any static host at a
folder. For a site whose predecessor died of moving parts, that was the right trade.

**Branching:** `dev` (Netlify preview) → `main` (GitHub Pages, production track). A third
branch was used temporarily during host setup and retired once the site stabilized.

---

## 9. Current state

Content-complete and live on two independent free hosts. Verified as of 2026-08-12: a clone of
the public repository rebuilds the site byte-for-byte, both deploys return 200, 0 missing
assets, 0 dead links, all 35 video embeds intact, photo gallery serving 160 images on the live
page.

**Outstanding:**

| Item | Blocked on |
|---|---|
| Content review | Colleague |
| Video migration to the institutional channel | Channel access confirmation |
| Custom domain cutover | Decision on destination host, and on who owns that decision |

---

## 10. Notes for whoever takes this over

> For the practical checklist — what to send, what a clone already contains, and why no external
> source is required — see **`docs/handover.md`**. This section covers the reasoning behind it.

> ### Rebuilding: just clone and run it
>
> ```bash
> git clone https://github.com/bidhya/polenet.git && cd polenet
> > uv run python scraper/build_site.py
> git status --short          # expect 0 — the rebuild is byte-identical
> ```
>
> Everything the builder reads is committed. This was **not** true until 2026-08-12: the build
> depended on two gitignored directories, so a clean checkout either crashed or — worse —
> succeeded while silently dropping the photo gallery. Both are fixed, and the build now refuses
> to run rather than emit an empty gallery. See §6.

**If the goal is to keep the static site:** `site/` alone is sufficient. It is fully
self-contained — one stylesheet, plain HTML, and a single CDN reference for the gallery
lightbox. Any static host serves it. The Python is not needed to run the site.

**If the goal is to migrate to a CMS:** do not use `site/` as the import source. It is rendered
HTML; extracting structure from it would repeat work already done. Use instead:

- `archive/xml/*.json` — parsed, cleaned page/post/attachment content (committed)
- `archive/audit/site_index.json` — the 51 stations as structured fields, not prose (committed)
- **The original WordPress XML export** — standard WXR format, directly supported by common
  migration tooling. This is the single most valuable artifact for a CMS migration, and it is
  **deliberately not in the repository**: it contains author and commenter email addresses,
  commenter IP addresses, WordPress usernames, and 19 draft/private posts that were never
  published. Request it from the project owner directly. If it must be shared more widely,
  sanitize it first: strip every `wp:author_email`, `wp:author_login`, `wp:comment_author_email`
  and `wp:comment_author_IP` element, and drop any item whose `wp:status` is not `publish`.

**The critical caveat:** neither source is complete alone. `site/` is *corrected* but rendered —
it carries every content fix made during this project. The raw export is *structured* but
uncorrected. Migrating purely from the export would silently reintroduce every bug fixed here.
Use the export as the import source and `site/` as the reference for correct output.

**Three things that will bite:**

1. **Videos are embedded from a YouTube channel the site does not control.** Since 2026-08-17
   that is the project's own channel rather than an individual's, which removed the sharpest
   handover risk — but the dependency itself remains. The failure mode is silent: the build never
   checks that a video still resolves, so deleting one, or deleting and re-uploading it (which
   issues a new ID), breaks a page with no error anywhere. `docs/notes.md`, "Videos", is written
   to be handed to whoever manages that channel.
2. **`site/README.md` says "do not edit files here directly."** True while the generator is in
   use; wrong for anyone handed `site/` as their source. Update it at handover.
3. **The site is generated, so hand-editing is a one-way door.** Navigation and footer are
   duplicated across all 115 pages — a site-wide change is a 115-file edit by hand, and
   re-running the generator would overwrite manual changes. Pick one mode deliberately.

---

## 11. What this project taught

- **Verify the premise before building on it.** A month of work proceeded from "the data is
  gone." It wasn't. The correction improved the output substantially and eliminated an entire
  planned workstream.
- **A failing tool is not a failing system.** A certificate gap in one sandbox was read as a
  server outage and recorded as fact.
- **HTTP 200 is a weak assertion.** It says a page exists, not that it works. Asset resolution
  is the check that matters.
- **Verification expires.** "0 dead links" was true when written and false a month later.
  Undated claims in documentation are liabilities.
- **Secret scanning and security review are different activities.** The second one caught what
  the first could not see.
- **Convenient scaffolding should be retired deliberately.** A temporary branch was useful, then
  became overhead once its rationale expired.
- **Measure before accepting an expensive fix.** The reproducibility gap looked like it needed a
  624 MB commit; measurement showed the data was already in the repository and the real cost was
  5.9 MB. The first estimate was wrong by two orders of magnitude.
- **A silent failure is worse than a crash.** The build that exited 0 while dropping the photo
  gallery was far more dangerous than the one that refused to start. Failures should be loud by
  construction, not by luck.
- **Timestamps are not facts.** The workstation clock drifted two days and resynced mid-session;
  git recorded the drifted values, and dates derived from `git log` were wrong in the docs until
  cross-checked against the system clock.

---

*Report compiled 2026-08-12 from the project's internal log, the git history (52 commits), and
verification run at the time of writing — including a clean clone of the public repository,
rebuilt to confirm byte-identical output.*
