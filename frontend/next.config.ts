import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// The project has ONE settings file: `.env` in the repository root (template `.env.example`). Next only looks inside frontend/ by default,
// so load the root file here (forceReload: Next already ran its own lookup). On Vercel there is no such file: the variables come from the
// project's Environment Variables and this call changes nothing.
loadEnvConfig(path.resolve(process.cwd(), ".."), process.env.NODE_ENV !== "production", console, true);

// The Harness panel talks to the local control server (started by ./dev.sh, 127.0.0.1:8765) through this rewrite,
// so the browser only ever sees one origin. On a hosted copy the server does not exist and the panel says how to start it.
const HARNESS_SERVER = "http://127.0.0.1:8765";

// NEXT_PUBLIC_HIDE_HARNESS=true (or 1) removes the Harness tab and this proxy (same rule as isHarnessEnabled in src/lib/config.ts;
// the root .env is loaded above, but the "@/" alias is not available here, so the rule is repeated).
const hide = (process.env.NEXT_PUBLIC_HIDE_HARNESS ?? "").trim().toLowerCase();
const isHarnessEnabled = !(hide === "true" || hide === "1");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!isHarnessEnabled) return [];
    return [{ source: "/harness-api/:path*", destination: `${HARNESS_SERVER}/api/:path*` }];
  },
};

export default nextConfig;
