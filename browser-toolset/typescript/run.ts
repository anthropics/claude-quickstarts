#!/usr/bin/env -S npx --no-install tsx
/**
 * Run Claude's browser toolset from the command line, with the example driver.
 *
 * Usage:
 *
 *     npx tsx run.ts "Open example.com and tell me the heading"
 *
 * It builds the example driver, hands it to the tool runner, and prints each of the model's messages until the model
 * finishes. It uses only the SDK's abstract toolset, so any other driver swaps in the same way.
 *
 * Requires: `npm install` in this folder (`@anthropic-ai/sdk`, `ws`, `tsx`), cdp-browser.ts next to this file, a Chromium
 * binary (`CHROME_PATH`, or `google-chrome` / `chromium` on `PATH`) and an API key in `ANTHROPIC_API_KEY`.
 *
 * Read "Running a browser toolset safely" in the SDK guide (browser-toolset.md) before running this against anything
 * other than a throwaway browser profile inside a sandbox, because the pages the model visits affect what it does next.
 *
 * Environment: `ALLOWED_DOMAINS` (comma-separated hosts the model may visit, subdomains included; default
 * `example.com,iana.org`), `HEADLESS=0` to watch the browser, `CHROME_PATH` for a specific Chromium binary, `MODEL` to
 * pick the model.
 */

import Anthropic from '@anthropic-ai/sdk';
import { ToolError, type BetaURLPolicy } from '@anthropic-ai/sdk/helpers/beta/toolsets';
import { CdpBrowser } from './cdp-browser.js';

/** A comma-separated environment variable as a lower-cased list, blanks dropped. */
export function envList(name: string, fallback: string): string[] {
  return (process.env[name] ?? fallback)
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter((item) => item !== '');
}

/** An example policy, not a production one: http(s) pages on the allowed hosts or their subdomains, and the empty tab. */
export function examplePolicy(allowedHosts: string[]): BetaURLPolicy {
  const hosts = allowedHosts.map((entry) => entry.trim().toLowerCase().replace(/\.$/, '')).filter(Boolean);
  return (_ctx, url) => {
    const text = String(url);
    if (text.toLowerCase() === 'about:blank') return;
    const withScheme = /^[a-z][a-z0-9+.-]*:/i.test(text) ? text : `https://${text}`; // no scheme written: read as https
    let parts: URL;
    try {
      parts = new URL(withScheme.replaceAll('\\', '/')); // a browser reads a backslash in the address as a slash
    } catch {
      throw new ToolError(`blocked: ${text} could not be parsed`);
    }
    const host = parts.hostname.toLowerCase();
    const onAllowedHost = hosts.some((allowed) => host === allowed || host.endsWith('.' + allowed));
    if (!['http:', 'https:'].includes(parts.protocol) || !onAllowedHost) {
      throw new ToolError(`blocked: ${text} is not on an allowed host`);
    }
  };
}

async function main(): Promise<void> {
  const task = process.argv.slice(2).join(' ') || 'Open example.com and tell me the page heading.';
  const client = new Anthropic();
  const browser = await CdpBrowser.launch({
    headless: process.env['HEADLESS'] !== '0',
    urlPolicy: examplePolicy(envList('ALLOWED_DOMAINS', 'example.com,iana.org')),
  });
  // The tool runner never closes the browser. The finally closes it, whether the loop ends or fails.
  try {
    const runner = client.beta.messages.toolRunner({
      model: process.env['MODEL'] ?? 'claude-sonnet-5-5',
      max_tokens: 1024,
      tools: [browser],
      messages: [{ role: 'user', content: task }],
    });
    for await (const message of runner) {
      console.dir(message, { depth: 4 });
    }
  } finally {
    await browser.close();
  }
}

// Only when run as a script, so importing examplePolicy does not start a run.
if (/(^|[\\/])run\.[cm]?[jt]s$/.test(process.argv[1] ?? '')) {
  main().catch((error: unknown) => {
    console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  });
}
