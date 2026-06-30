# Archive Analysis — Why We Chose the December 7, 2025 Snapshot

## Background

The polenet.org website broke due to an incompatibility between the **Aries WordPress theme**
(by United Themes) and a WordPress core update. The database and server became compromised
with no backup available.

To rebuild the site, we turned to the **Internet Archive Wayback Machine** (archive.org),
which periodically crawls and saves public websites. Our task was to find the most recent
clean snapshot of polenet.org before the failure.

---

## What We Found in the Archives

We queried the Wayback Machine CDX API for all snapshots of polenet.org from 2025 onward.
Here is what the historical record showed:

| Date Captured   | HTTP Status | Meaning                                  |
|-----------------|-------------|------------------------------------------|
| January 2025    | 301         | Redirect (site not yet broken, but brief)|
| February 2025   | 301         | Redirect                                 |
| March–August 2025 | 301       | Redirect                                 |
| September 6, 2025  | **200**  | ✓ Site working normally                  |
| November 19, 2025  | **200**  | ✓ Site working normally                  |
| December 7, 2025   | **200**  | ✓ Site working normally — most recent    |
| February 3, 2026   | 301         | ✗ Site already broken/redirecting        |
| March 2026      | 301         | ✗ Still broken                           |
| April 2026      | 301         | ✗ Still broken                           |

**HTTP 200** = the server returned a valid page (site working).
**HTTP 301** = the server sent a redirect, which in this context means the site was either
misconfigured or already broken. The 2026 redirects are to an error or holding page.

---

## Why We Did Not Use February 2026

When we first started this project, the assumption was that the site was working until
approximately February 2026. However, when we queried the archive, the February 3, 2026
snapshot returned a 301 redirect — meaning the site had already failed by then.

The actual last working state captured by the Wayback Machine is **December 7, 2025**
(snapshot ID: `20251207055143`).

Note: The 301 redirects in early–mid 2025 are a separate issue — the site was likely
configured to redirect `polenet.org` to `www.polenet.org` at that time, but the Wayback
Machine was capturing the non-www version. This is normal and unrelated to the site failure.

---

## Why December 7, 2025 Was Selected

- It is the **most recent 200-status snapshot** — the closest to the time the site failed.
- It contains the complete WordPress-rendered homepage, all navigation, and all content.
- It matches the site content the team was most recently working with.
- The three available good snapshots (Sep, Nov, Dec 2025) all show the same site structure;
  December is simply the most current.

---

## How We Verified the Snapshot Was Good

We downloaded the raw HTML of the December 7 snapshot and confirmed:
- Page title: "POLENET: The Polar Earth Observing Network | Investigating the polar regions from the inside out"
- All 7 navigation items present and linked
- Images loading correctly via Wayback Machine's archived copies
- Blog posts visible on the homepage
- The Aries WordPress theme markup is intact (useful as a layout reference)

---

## Notes for Future Reference

- The Wayback Machine does not archive everything. Some images (especially auto-generated
  gallery thumbnails) were never captured. Full-size photos were captured.
- Some pages within the site (e.g. the photo gallery) have different snapshot timestamps
  than the homepage — the Wayback Machine crawls different URLs at different times.
- We are NOT using the WordPress theme files in the rebuild. They are archived for reference only.
