# Static site (GitHub Pages)

The website can be exported as a fully static site, served at <https://udsy19.github.io/qmint/>.
There is no API server in this mode. Every API response the pages use was **precomputed with the real
FastAPI app** (`qmint.api.app`, via `TestClient`) and committed under `web/public/snapshot/`.

## Build

```bash
PY=/Users/udsy/PycharmProjects/Qollab-QMint/.venv/bin/python
$PY scripts/build_static_site.py            # → web/public/snapshot/ (≈40 s with --jobs 4)
cd web && pnpm build:static                  # QMINT_STATIC=1 NEXT_PUBLIC_QMINT_STATIC=1 next build → web/out/
```

`web/out/` is the site root for the `/qmint` prefix (`QMINT_BASE_PATH`, default `/qmint`). Preview it locally:

```bash
mkdir -p /tmp/pages && ln -sfn "$PWD/out" /tmp/pages/qmint
python -m http.server 8931 -d /tmp/pages     # http://127.0.0.1:8931/qmint/
```

CI: `.github/workflows/pages.yml` regenerates the snapshot, builds and deploys with `actions/deploy-pages`
on every push to `main`. Fallback: push the contents of `web/out/` to a `gh-pages` branch (it contains
`.nojekyll`, needed because Next writes `_next/`).

Normal mode is unchanged: without `QMINT_STATIC=1`, `pnpm dev`/`pnpm build` use the `/api` rewrite to :8787 and
render API-backed pages per request.

## How requests are answered

* Snapshot file: `snapshot/<get|post>/<api path>/<sha256(canonical JSON)>.json`. The hashed payload is the POST
  body, or the GET query object (`{}` when there is none).
* Canonical JSON: object keys sorted, no whitespace, numbers in ECMAScript `Number#toString` form.
  `canonical_json` (Python) and `canonicalJson` (`web/lib/api/static.ts`) are tested against the same fixture
  and digest (`tests/unit/api/test_static_snapshot.py`, `web/lib/api/static.test.ts`).
* `snapshot/index.json` lists every file (method, path, key); `snapshot/meta.json` records `git_sha` and
  `generated_at`. The site-wide banner shows that sha.
* Server components are prerendered at build time from the same files (read from disk).
* A request that was not precomputed fails with an `ApiError` (`kind: "http"`, status 404,
  code `static_snapshot_miss`) whose message is
  *"Static snapshot: this exact configuration wasn't precomputed — run QMint locally for live experiments"*.
  Nothing is computed or interpolated in the browser.

## What is precomputed

| Endpoint | Grid |
|---|---|
| all GETs | meta, tracker, games, protocols, evidence, evidence labels/highlights, health, benchmarks, certificate catalog, research sources + every entry detail (81 entries, one static page each) |
| `POST /lab/mint` | both schemes × n 1–8 (W2: n ≥ 2) × backend {aer, exact} × teaching reveal {off, on}, other fields at the form defaults (seed 42, no noise, 2000 shots, 1000 trials, threshold 1) |
| `POST /lab/attack` | every attack × n 1–8 × trials {form default (2000; A08 capped at 400), 0}, other fields at the form defaults (seed 42, no noise) |
| landing page | hero instrument: every scenario × n {1, 2, 4, 8} × sampled on/off; the section probes |
| `POST /certificates` | every catalog preset, serialised exactly as the studio sends it |

## Limitations

* Any other configuration (different seed, noise channel/strength, shots, trials, loss/error allowance,
  probes, or an edited certificate request) shows the "not precomputed" error. Run QMint locally for that.
* Values are those of the commit in the banner; Monte Carlo numbers are the seed-42 runs, not fresh samples.
* `/research?game=…` query filters are not applied on first load in the static export (no request at build time).
* Requires Node ≥ 20.16 for the build (`process.getBuiltinModule`).
