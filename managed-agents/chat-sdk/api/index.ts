// Vercel entrypoint. vercel.json rewrites /api/:path* here; Vercel preserves
// the original request URL, so the full-path routes in src/app.ts match as
// written. The page is prebuilt into public/ by scripts/build-web.ts and
// served from the CDN, so this function never touches node:fs or esbuild.
// Deployment caveats (auth, duration, activity feed): skill.md,
// "Deploying off the Node server".

import { handle } from "hono/vercel";
import { deployedApi } from "../src/app";

export default handle(deployedApi());
