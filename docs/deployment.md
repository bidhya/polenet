# Deployment Plan — polenet.org

Last updated: 2026-08-12

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Hosting | Netlify (free tier) **and** GitHub Pages | Two independent free hosts — see "Two hosts" below |
| Repo | GitHub, single monorepo, public since 2026-07-28 | scraper + site in one place |
| Privacy during prototype | Option B — main branch Netlify deploy paused | Hard separation; flip to live only when ready |
| Branches | `dev` (Netlify preview) → `main` (GitHub Pages + production) | Two-tier model, see below (simplified from three tiers on 2026-08-12) |
| Build | Pre-built static HTML, no build command | site/ is already generated output |

### Two hosts, deliberately

Netlify and GitHub Pages serve the same `site/` output independently. Established 2026-07-28,
because GitHub Pages became viable once the repo went public (free for any public repo) — a
genuine second free host, not just a backup. GitHub Actions minutes are free/unlimited for
public repos, so there's no cost concern on that side; Netlify's are metered, which is the
whole reason the branch model below routes GitHub Pages traffic through `main` and keeps
`dev` as the one branch that pushes freely.

---

## Repo layout

```
polenet/                   ← repo root
├── docs/                   ← published docs (handover, report, deployment, notes)
├── Scratch/                ← gitignored, local-only (WordPress XML export)
├── scraper/                ← Python scripts — committed
├── site/                   ← the deployable site — committed, Netlify publishes this
│   ├── index.html
│   ├── css/style.css
│   ├── images/             ← 539 images/PDFs (videos hosted on YouTube, not committed as files)
│   ├── blog/
│   ├── sites/
│   └── training/
├── archive/
│   ├── audit/              ← site_index.json + audit reports — committed
│   ├── xml/                ← parsed WXR JSON + video registries — committed
│   ├── html/                ← archived source pages — COMMITTED since 2026-08-12 (build needs it)
│   ├── images/               ← raw photos (flat) — gitignored; build no longer needs it
│   │   ├── videos/            ← the 35 field videos (organized 2026-07-28)
│   │   └── pdfs/               ← 6 linked PDFs (organized 2026-07-28)
│   └── assets/              ← WordPress JS/CSS — gitignored, irrelevant
├── .gitignore
└── netlify.toml
```

---

## Branch strategy

**Two-tier model, since 2026-08-12: `dev` → `main`.** Never commit new work directly to
`main` — it should always arrive there via a merge from `dev`.

| Branch | Auto-deploys? | Where | Notes |
|---|---|---|---|
| `dev` | Yes | `monumental-dieffenbachia-d72518.netlify.app` (Netlify) | Active development — push freely |
| `main` | Yes (GitHub Pages) / Paused (Netlify) | `bidhya.github.io/polenet` (GitHub Pages, via `.github/workflows/pages.yml`) and `polenet.org` (future) | Merge from `dev` once it looks stable — production track |

**Promotion checklist**, run before merging `dev` → `main` (this is what's actually been
checked before every promotion so far, not just aspirational): 0 missing images/PDFs (verified
against a real server response, not just file existence on disk), 0 dead links, all 35 video
embeds intact, and a visual check on the actual live deploy — not just local, and not just an
HTTP 200 on the page's own URL, since that alone doesn't confirm *that page's* asset links
(CSS/images/nav) resolved correctly. That exact gap is how the GitHub Pages depth bugs (see
"GitHub Pages setup" below) went unnoticed until manually checking rendered pages.

Workflow:
1. Make changes on `dev`, push freely — Netlify auto-deploys the preview
2. Review at `https://monumental-dieffenbachia-d72518.netlify.app/`
3. When `dev` looks stable: `git checkout main && git merge dev --ff-only && git push origin main`
4. GitHub Actions auto-deploys `main` → `https://bidhya.github.io/polenet/` (Netlify's `main`
   context stays paused — not connected to a live domain yet)

### History: how this got simplified from three branches

A temporary third branch, `pages`, was used 2026-07-28–2026-08-12 for setup convenience
(constant GitHub Pages pushes without touching Netlify's metered build credits). Retired
2026-08-12 once the site stabilized.

---

## Key config files

### netlify.toml
```toml
[build]
  publish = "site"
  ignore = "git diff --quiet $CACHED_COMMIT_REF $COMMIT_REF -- site/"

[context.dev]
  publish = "site"
```
The `ignore` line skips a deploy entirely if `site/` didn't change in the pushed commits —
a safety net against wasting build minutes on doc-only or scraper-only commits, but not a
substitute for batching pushes — related commits are best pushed together.

### GitHub Pages setup

Live at https://bidhya.github.io/polenet/. Set up 2026-07-28, since re-pointed at `main`
(2026-08-12, see "History" above). Non-default for one reason: the site output lives in
`site/` rather than the repo root or a `/docs` folder (GitHub Pages' two built-in branch-deploy
options — and `/docs` is already taken by this project's internal notes anyway).

**1. `.github/workflows/pages.yml`** — a GitHub Actions–based Pages deploy instead of the
simple branch-based one, since only the Actions-based option can publish an arbitrary folder:
```yaml
on:
  push:
    branches: ["main"]
    paths: ["site/**"]
  workflow_dispatch:
# ...
      - uses: actions/upload-pages-artifact@v3
        with:
          path: "./site"
      - uses: actions/deploy-pages@v4
```
Manual trigger any time: `gh workflow run pages.yml --ref main`.

**2. Repo settings, one-time:**
- Settings → Pages → Build and deployment → Source → **"GitHub Actions"** (not the default
  branch-based option). Set via `gh api -X POST repos/{owner}/{repo}/pages -f build_type=workflow`.
- Enabling Pages this way auto-creates a `github-pages` deployment **environment** with a
  branch-protection rule that, by default, only allows the repo's default branch (`main`) to
  deploy to it — which happens to be exactly the branch this project uses now, so no extra
  setup is needed today. (If a non-`main` branch ever needs to deploy: `gh api -X POST
  repos/{owner}/{repo}/environments/github-pages/deployment-branch-policies -f name=<branch>`.)

**Two real bugs found while verifying this** (not GitHub-Pages-only quirks — genuine
pre-existing defects in `build_site.py` that Netlify's root-serving happened to mask): blog/
sites/training pages used one `../` too many (`depth=2` instead of `depth=1`), and
`build_photos()` hardcoded a `../` on a page that needed none. Full writeup in
`docs/project-report.md` §6.

### .gitignore
```
# Raw Wayback Machine downloads — large, re-creatable, not needed in git
archive/images/
archive/assets/

# Project docs: four are published, the rest are the maintainer's working notes
docs/*
!docs/handover.md
!docs/project-report.md
!docs/deployment.md
!docs/notes.md
AGENTS.md
CLAUDE.md
Scratch/

# Python — uv manages the environment; the lockfile IS committed, the venv is not
.venv/
__pycache__/
*.pyc
*.pyo
.env

# OS
.DS_Store
Thumbs.db

# archive/html/ is tracked so the build works from a fresh clone, EXCEPT:
# the captured wp-login page — unreferenced by the build, and not something to
# publish in a public repo.
archive/html/wp-login-php.html
```

---

## Setup history

All of it is done — the full narrative lives in `docs/project-report.md`. The short version:

- Repo created, `dev`/`main` established, Netlify connected to `dev` (publish dir `site`, no
  build command), `main`'s Netlify context left paused.
- GitHub Pages added 2026-07-28 via GitHub Actions once the repo went public — see "GitHub Pages
  setup" above, including the two genuine path-depth bugs it surfaced.
- Repo flipped to **public** 2026-07-28 after two security passes (a credential scan, then a
  separate operational-disclosure review that caught something the first could not).
- Branch model simplified to two tiers 2026-08-12 — see "History" above.
- Build made reproducible from a clean clone 2026-08-12 (`bd3a021`).

## Still open

- [ ] **Connect the polenet.org custom domain.** *Which host* is now settled — **GitHub Pages**,
      decided 2026-08-14. The deciding factor is handover rather than technical merit: Pages is
      tied to the repository and travels with it, whereas the Netlify deployment is tied to an
      individual's personal account. Pages is also free and unmetered for public repos, already
      configured (`.github/workflows/pages.yml`), and already serving `main`.
      - Repo side, once the DNS side is agreed: `echo "polenet.org" > site/CNAME` (committed —
        it is not generated, but it does survive rebuilds), then set the custom domain via
        Settings → Pages or `gh api -X PUT repos/bidhya/polenet/pages -f cname=polenet.org`.
        Wait for the Let's Encrypt certificate, then confirm HTTPS enforcement.
      - Verification: request GitHub's `_github-pages-challenge-*` TXT record at the same time as
        the address records. The token is available only through the GitHub web UI, so fetch it
        *before* raising the DNS change.
      - **What is still unresolved is the DNS change itself, which is not self-service for this
        domain** — it goes through the organisation that administers the domain's DNS, on their
        timescale. Treat it as lead-time work and put every record in a single request; a second
        round trip costs another full turnaround. Details are held in the project's internal
        notes rather than here.
      - Verified: the site needs **no changes** to serve from a domain root — 0 root-relative
        links, and `build_site.py` never wipes `site/`, so a committed `CNAME` file survives.
- [ ] **Unpause Netlify's `main` context** — moot now that GitHub Pages is the chosen host for
      the domain. Left open only as a fallback.

## Future reference — how to update the site

1. Run `uv run python scraper/build_site.py` if content changes
2. `git add site/` and commit on `dev` (not `main` directly — see Branch strategy above)
3. Push `dev` → Netlify auto-deploys the preview; review there
4. When `dev` looks stable: `git checkout main && git merge dev --ff-only && git push origin main`
   → GitHub Actions auto-deploys `main` to `bidhya.github.io/polenet`; review there

**Git push auth note (found 2026-07-26):** no `credential.helper` is configured for
this repo/machine, so a bare `git push` fails with "could not read Username". `gh` is
authenticated (`gh auth status` — account `bidhya`, `repo` scope). Push using gh's
credential helper scoped to just that command (does not touch git config):
```bash
git -c credential.helper='!gh auth git-credential' push origin dev
```
