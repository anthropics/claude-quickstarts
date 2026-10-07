#!/usr/bin/env -S npx --no-install tsx
/**
 * Exercise the browser toolset with the calls a model would make, against a local page: no API key, no model.
 *
 * Usage:
 *
 *     npx tsx exercise.ts
 *
 * The script serves a small page on localhost, launches the example driver with a URL policy that admits that page and
 * nothing else, and sends the toolset the `tool_use` calls a model would send, through `browser.toolResult()`, which
 * runs the same pipeline as the tool runner. It prints each `tool_result` as the model would see it, then checks it:
 *
 * - `navigate` to the page, `read_page`, `left_click` on a `ref_N` from the read and `get_page_text` showing what the
 *   click did: all answered;
 * - `navigate` to the same page by `127.0.0.1`, and `wait` for longer than 30 s: both refused (`is_error`).
 *
 * The first call that comes back differently ends the script with a failed assertion, so the script also works as a
 * smoke check.
 * Requires what run.ts requires, minus the API key.
 */

import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import type { AddressInfo } from 'node:net';

import {
  ToolError,
  type BetaAbstractBrowserToolset20260801,
  type BetaURLPolicy,
} from '@anthropic-ai/sdk/helpers/beta/toolsets';
import type {
  BetaToolResultBlockParam,
  BetaToolResultContentBlockParam,
} from '@anthropic-ai/sdk/resources/beta';
import { CdpBrowser } from './cdp-browser.js';

const PAGE = `<!doctype html>
<title>Exercise page</title>
<h1>Exercise page</h1>
<p id="status">The button has not been clicked.</p>
<button onclick="document.getElementById('status').textContent = 'The button was clicked.'">Click me</button>
<p><a href="/about">About this page</a></p>
`;

/** A URL policy that admits the page this script serves and nothing else. */
function only(origin: string): BetaURLPolicy {
  return (_ctx, url) => {
    const text = String(url);
    let address: URL;
    try {
      address = new URL(text.replaceAll('\\', '/')); // parsed as a browser reads the address: a backslash is a slash
    } catch {
      throw new ToolError(`blocked: ${text} could not be parsed`);
    }
    if (address.origin !== origin) throw new ToolError(`blocked: ${text} is outside this exercise's page`);
  };
}

/** Send one tool call as the model would, and print the result as the model would see it. */
async function call(
  browser: BetaAbstractBrowserToolset20260801,
  name: string,
  input: Record<string, unknown>,
): Promise<BetaToolResultBlockParam> {
  const result = await browser.toolResult({
    type: 'tool_use',
    id: `toolu_${name}`,
    name,
    input,
    toolset_name: 'browser',
  });
  console.log(`\n${name} ${JSON.stringify(input)} -> ${result.is_error ? 'refused' : 'answered'}`);
  for (const block of blocksOf(result)) console.log('  ' + JSON.stringify(block));
  return result;
}

/** The result's content blocks. `content` is a string or a list of blocks. A string becomes one text block. */
function blocksOf(result: BetaToolResultBlockParam): BetaToolResultContentBlockParam[] {
  const content = result.content ?? '';
  return typeof content === 'string' ? [{ type: 'text', text: content }] : [...content];
}

function textOf(result: BetaToolResultBlockParam): string {
  return blocksOf(result)
    .map((block) => (block.type === 'text' ? block.text : ''))
    .join('\n');
}

async function main(): Promise<void> {
  const server = createServer((_request, response) => {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    response.end(PAGE);
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const port = (server.address() as AddressInfo).port;
  const origin = `http://localhost:${port}`;
  const browser = await CdpBrowser.launch({ headless: true, urlPolicy: only(origin) });
  try {
    assert(
      !(await call(browser, 'navigate', { url: `${origin}/` })).is_error,
      'expected that navigate to the page is answered',
    );
    const tree = textOf(await call(browser, 'read_page', {}));
    const button = tree.split('\n').find((line) => line.includes('Click me')) ?? '';
    const ref = /ref_\d+/.exec(button)?.[0];
    assert(ref !== undefined, 'expected that read_page lists the button with a ref');
    const clicked = await call(browser, 'left_click', { target: { type: 'ref', ref } });
    assert(!clicked.is_error, "expected that left_click on the button's ref is answered");
    const text = await call(browser, 'get_page_text', {});
    assert(
      textOf(text).includes('The button was clicked.'),
      "expected that get_page_text shows the click's effect",
    );
    // Same page, but the policy admits only the localhost address, so the SDK refuses this call before the driver runs.
    const probe = await call(browser, 'navigate', { url: `http://127.0.0.1:${port}/` });
    assert(
      probe.is_error === true &&
        textOf(probe).startsWith('blocked:') &&
        textOf(probe).includes("outside this exercise's page"),
      'expected that navigate to 127.0.0.1 is refused by the policy',
    );
    const waited = await call(browser, 'wait', { duration: 31 });
    assert(
      waited.is_error === true && textOf(waited).includes('between 0 and 30'),
      'expected that wait for longer than 30 s is refused for its duration',
    );
  } finally {
    await browser.close();
    server.close();
  }

  console.log('\nAll calls came back as expected.');
}

main().catch((error: unknown) => {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
