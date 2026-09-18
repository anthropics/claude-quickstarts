// `npm run fix -- SHOP-1A [https://acme.sentry.io/issues/123/]`: fix one issue
// by hand, no webhook or tunnel needed. Same code path as the server.

import { fixIssue, loadConfig, preflight } from "./fixer";
import { issueFromArguments } from "./sentry";

const [shortId, url] = process.argv.slice(2);
if (!shortId) {
  console.error("usage: npm run fix -- <SHORT-ID> [issue URL]");
  process.exit(2);
}

const config = await (async () => {
  const config = loadConfig();
  const problem = await preflight(config);
  if (problem) throw new Error(problem);
  return config;
})().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});

const run = await fixIssue(issueFromArguments(shortId, url), config);
if (!run) {
  console.log(`The session for ${shortId} has ended. Archive it in the Console to run the issue again.`);
} else {
  console.log(`\n${run.status}${run.pullRequestUrl ? `: ${run.pullRequestUrl}` : ""}\n${run.note ?? ""}`);
  process.exit(run.status === "failed" ? 1 : 0);
}
