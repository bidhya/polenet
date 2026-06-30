# Deployment Plan — polenet.org

Last updated: 2026-06-30

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Hosting | Netlify (free tier) | CI/CD built in, custom domain, deploy previews |
| Repo | GitHub private, single monorepo | scraper + site in one place |
| Privacy during prototype | Option B — main branch deploy paused | Hard separation; flip to live only when ready |
| Branches | `main` (production), `dev` (testing) | Simple two-branch model |
| Build | Pre-built static HTML, no build command | site/ is already generated output |

---

## Repo layout

```
polenet/                   ← repo root
├── AGENTS.md
├── docs/                  ← project notes
├── scraper/               ← Python scripts (may be used in future)
├── site/                  ← the deployable site  ← Netlify publishes this
│   ├── index.html
│   ├── css/style.css
│   ├── images/
│   ├── blog/
│   ├── sites/
│   └── training/
├── archive/
│   └── audit/             ← site_index.json + audit reports (committed — useful artifacts)
│   └── html/              ← raw Wayback HTML (gitignored — large, re-creatable)
│   └── images/            ← raw images (gitignored — duplicate of site/images/, 21 MB)
│   └── assets/            ← WordPress JS/CSS (gitignored — irrelevant)
├── .gitignore
└── netlify.toml
```

---

## Branch strategy

| Branch | Auto-deploys? | URL | Notes |
|---|---|---|---|
| `dev` | Yes | `dev--polenet-XXXX.netlify.app` | Working preview, share with colleague |
| `main` | Paused | `polenet.org` (future) | Enable in Netlify only when ready to launch |

Workflow:
1. Make changes locally on `dev`
2. Push → Netlify auto-deploys to preview URL
3. Review at preview URL
4. Merge `dev` → `main` when satisfied
5. Netlify deploys `main` to polenet.org (once main deploy is unpaused)

---

## Key config files

### netlify.toml
```toml
[build]
  publish = "site"

[context.dev]
  publish = "site"
```

### .gitignore
```
archive/html/
archive/images/
archive/assets/
__pycache__/
*.pyc
*.DS_Store
```

---

## Setup steps (one-time)

- [x] Write deployment plan (this file)
- [x] Create `.gitignore` locally
- [x] Create `netlify.toml` locally
- [x] Confirm repo created at github.com — https://github.com/bidhya/polenet (private)
- [x] `git init`, single clean initial commit, `git remote add origin`, push `main`
- [x] Create `dev` branch, push — both branches live on remote
- [ ] **NEXT: Connect Netlify to GitHub repo**
  - Log in at netlify.com
  - "Add new site" → "Import from Git" → GitHub
  - Select the `bidhya/polenet` repo
  - Branch to deploy: `dev`
  - Publish directory: `site`
  - Build command: *(leave blank)*
  - Click "Deploy site"
- [ ] In Netlify: Site settings → Build & deploy → "main" context → Stop auto publishing (locks production)
- [ ] Verify dev preview URL is working (share with colleague for review)
- [ ] (Later) Connect polenet.org custom domain when ready to launch

---

## Future reference — how to update the site

1. Run `python3 scraper/build_site.py` if content changes
2. `git add site/` and commit on `dev`
3. Push `dev` → Netlify auto-deploys preview
4. When happy: `git checkout main && git merge dev && git push`
5. Netlify deploys to polenet.org
