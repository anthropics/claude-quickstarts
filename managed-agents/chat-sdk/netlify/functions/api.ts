// Netlify Functions entrypoint. The path config routes every /api/* request
// here with the original URL intact, so the full-path routes in src/app.ts
// match as written. The page is prebuilt into public/ by
// scripts/build-web.ts and served from the CDN.
//
// Mind the duration cap: /api/chat holds its response open for the whole
// research turn (minutes). Netlify's synchronous function limits are tighter
// than that unless streaming responses are enabled on your plan -- verify
// before relying on it, or move the turn into a queue (skill.md,
// "Deploying off the Node server").

import { handle } from "hono/netlify";
import { deployedApi } from "../../src/app";

export default handle(deployedApi());

export const config = { path: "/api/*" };
