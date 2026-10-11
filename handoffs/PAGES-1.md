# PAGES-1 — static GitHub Pages export

Final commit `cf4465f` on `feat/PAGES` (not pushed). Built site: `web/out/` (gitignored), root of `/qmint/`.

* `scripts/build_static_site.py` precomputes every GET the site uses and a POST grid (mint, attack, hero, certificate presets) with the real FastAPI app → `web/public/snapshot/` (365 files, meta.json has git sha + generated_at).
* `pnpm build:static` → static export with basePath `/qmint`, trailing slashes, unoptimized images; normal dev/build unchanged.
* Client reads `snapshot/<method>/<path>/<sha256(canonical JSON)>.json`; misses raise ApiError `static_snapshot_miss` with the agreed message; site-wide banner shows the snapshot sha.
* `.github/workflows/pages.yml` deploys on push to main (needs Pages source = GitHub Actions in repo settings).
* Verified with Playwright at 1440 px: /, /app, /lab/mint, /lab/attack, /benchmarks, /certificates, /research, /research/T-MVW12-THM1, /docs, /docs/getting-started.

Limitations: see docs/STATIC_SITE.md.
