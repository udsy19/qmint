import type { NextConfig } from "next";

// The research API (FastAPI, qmint/api) runs on :8787. The browser always calls same-origin
// /api/*, which Next rewrites to the API, so there is no CORS in normal use.
const API_ORIGIN = process.env.QMINT_API_ORIGIN ?? "http://127.0.0.1:8787";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default config;
