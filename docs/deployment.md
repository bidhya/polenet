# Deployment Plan — polenet.org

Last updated: 2026-11-11

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Hosting | GitHub Pages | Free for public repos; tied to the repository, so it travels with it |
| Repo | GitHub, single monorepo, public since 2026-07-28 | scraper + site in one place |
| Branches | `dev` (development) → `main` (GitHub Pages, production) | Two-tier model, see below (simplified from three tiers on 2026-08-12) |
| Build | Pre-built static HTML, no build command | site/ is already generated output |

---

## Repo layout

```
polenet/                   ← repo root
├── docs/                   ← published docs (handover, report, deployment, notes)
├── Scratch/                ← gitignored, local-only (WordPress XML export)
├── scraper/                ← Python scripts — committed
├── site/                   ← the deployable site — committed, published as-is
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
| `dev` | No | — | Active development — push freely |
| `main` | Yes (GitHub Pages) | `bidhya.github.io/polenet` (GitHub Pages, via `.github/workflows/pages.yml`) and `polenet.org` (future) | Merge from `dev` once it looks stable — production track |

**Promotion checklist**, run before merging `dev` → `main` (this is what's actually been
checked before every promotion so far, not just aspirational): 0 missing images/PDFs (verified
against a real server response, not just file existence on disk), 0 dead links, all 35 video
embeds intact, and a visual check on the actual live deploy — not just local, and not just an
HTTP 200 on the page's own URL, since that alone doesn't confirm *that page's* asset links
(CSS/images/nav) resolved correctly. That exact gap is how the GitHub Pages depth bugs (see
"GitHub Pages setup" below) went unnoticed until manually checking rendered pages.

Workflow:
1. Make changes on `dev`, push freely
2. Review locally — open `site/index.html` in a browser
3. When `dev` looks stable: `git checkout main && git merge dev --ff-only && git push origin main`
4. GitHub Actions auto-deploys `main` → `https://bidhya.github.io/polenet/` — but only when the
   merge changed something under `site/`. To redeploy by hand, use "Run workflow" on the
   "Deploy site/ to GitHub Pages" action

---

## Key config files

### netlify.toml
Optional — only relevant to anyone who hosts the site on Netlify. It publishes `site/` and skips
a deploy when `site/` is unchanged. It has no effect on GitHub Pages.

### GitHub Pages setup

Live at https://bidhya.github.io/polenet/. Set up 2026-07-28, re-pointed at `main` when the
branch model went two-tier on 2026-08-12. Non-default for one reason: the site output lives in
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

### .gitignore — two entries worth knowing

Read the file itself rather than a copy here, but two lines are non-obvious:

- **`docs/*` plus `!docs/<name>.md` negations.** Four docs are published and the rest are the
  maintainer's working notes. Publishing a fifth means adding another negation line.
- **`archive/html/` is tracked** so the build works from a fresh clone — *except* the captured
  `wp-login-php.html`, which is excluded deliberately. It is unreferenced by the build.

---

## Still open — not scheduled

- [ ] **Connect the polenet.org custom domain.** *Which host* is settled: **GitHub Pages**,
      decided 2026-08-14, on handover grounds rather than technical merit — Pages is tied to the
      repository and travels with it, whereas a host on someone's personal account does
      not.

      Three things to know if it ever happens. The DNS change is **not self-service for this
      domain** — it goes through the organisation that administers it, on their timescale, so
      every record belongs in a single request. GitHub's `_github-pages-challenge-*` TXT token is
      **web-UI only and must be fetched before that request goes out**. And on the repo side it
      is `site/CNAME` (committed — not generated, but it survives rebuilds) plus `SITE_BASE_URL`
      in `build_site.py`, which is the only absolute URL the build emits.

      Verified: the site needs **no changes** to serve from a domain root — 0 root-relative
      links. The step-by-step plan and the request itself are in the project's internal notes.

> Nobody has asked for it, and nothing depends on it: the site is live and working at
> `bidhya.github.io/polenet/` regardless. Recorded so the reasoning is not lost, not because
> it is queued.

## Future reference — how to update the site

1. Run `uv run python scraper/build_site.py` if content changes
2. `git add site/` and commit on `dev` (not `main` directly — see Branch strategy above)
3. Push `dev`; review locally
4. When `dev` looks stable: `git checkout main && git merge dev --ff-only && git push origin main`
   → GitHub Actions auto-deploys `main` to `bidhya.github.io/polenet`; review there

**Git push auth note (found 2026-07-26):** no `credential.helper` is configured for
this repo/machine, so a bare `git push` fails with "could not read Username". `gh` is
authenticated (`gh auth status` — account `bidhya`, `repo` scope). Push using gh's
credential helper scoped to just that command (does not touch git config):
```bash
git -c credential.helper='!gh auth git-credential' push origin dev
```
