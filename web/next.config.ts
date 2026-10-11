import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { NextConfig } from "next";

// The research API (FastAPI, qmint/api) runs on :8787. The browser always calls same-origin
// /api/*, which Next rewrites to the API, so there is no CORS in normal use.
const API_ORIGIN = process.env.QMINT_API_ORIGIN ?? "http://127.0.0.1:8787";

// QMINT_STATIC=1: fully static export for GitHub Pages (docs/STATIC_SITE.md). Data comes from
// public/snapshot (scripts/build_static_site.py); there is no API and no rewrite.
const STATIC = process.env.QMINT_STATIC === "1";
const BASE_PATH = process.env.QMINT_BASE_PATH ?? "/qmint";

function snapshotSha(): string {
  try {
    const meta = JSON.parse(readFileSync(join(process.cwd(), "public", "snapshot", "meta.json"), "utf8")) as { git_sha?: string };
    return meta.git_sha ?? "unknown";
  } catch {
    throw new Error("QMINT_STATIC=1 needs public/snapshot/meta.json — run scripts/build_static_site.py first");
  }
}

const base: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  devIndicators: false,
};

const config: NextConfig = STATIC
  ? {
      ...base,
      output: "export",
      basePath: BASE_PATH,
      assetPrefix: BASE_PATH,
      trailingSlash: true,
      images: { unoptimized: true },
      env: {
        NEXT_PUBLIC_QMINT_STATIC: "1",
        NEXT_PUBLIC_QMINT_BASE_PATH: BASE_PATH,
        NEXT_PUBLIC_QMINT_SNAPSHOT_SHA: snapshotSha(),
      },
    }
  : {
      ...base,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
      },
    };

export default config;
