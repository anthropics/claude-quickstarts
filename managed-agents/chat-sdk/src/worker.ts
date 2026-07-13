// Cloudflare Workers entrypoint. A Hono app is a valid Workers export as-is;
// wrangler.jsonc serves public/ as static assets and sends /api/* here.
// Workers meter CPU time rather than wall-clock, so the minutes-long held
// /api/chat response fits naturally -- most of the turn is spent idle on the
// Anthropic event stream.
//
// Credentials come from Worker secrets (`wrangler secret put` for
// ANTHROPIC_API_KEY, CLAUDE_AGENT_ID, and CLAUDE_ENVIRONMENT_ID), surfaced
// as process.env by the nodejs_compat flag in wrangler.jsonc. The Anthropic
// client reads them at module scope, so keep compatibility_date at
// 2025-04-01 or later -- earlier dates don't populate process.env and the
// client would freeze with no key at isolate startup.

import { deployedApi } from "./app";

export default deployedApi();
