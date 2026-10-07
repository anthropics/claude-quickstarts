#!/usr/bin/env -S npx --no-install tsx
/**
 * Run Claude's computer toolset from the command line, with the example driver.
 *
 * Usage:
 *
 *     npx tsx run.ts "Open a terminal, run date, and tell me today's date and time zone."
 *
 * It connects the example driver to a VNC server, hands it to the tool runner, and prints each of the model's
 * messages until the model finishes. Before each action other than a screenshot, it shows you the call and asks y/N.
 * It uses only the SDK's abstract toolset, so any other driver swaps in the same way.
 *
 * It needs `npm install` in this folder (`@anthropic-ai/sdk`, `pngjs`, `tsx`), vnc-computer.ts next to this file, a
 * VNC server without a password (see the README) and an API key in `ANTHROPIC_API_KEY`.
 *
 * Read "Running a computer toolset safely" in the SDK guide (computer-toolset.md) before running this against
 * anything other than a throwaway desktop, because what the model sees on screen steers what it does next.
 *
 * The environment variables `VNC_HOST` (default 127.0.0.1) and `VNC_PORT` (default 5900) pick the server, and `MODEL`
 * picks the model.
 */

import { stdin as input, stdout as output } from 'node:process';
import * as readline from 'node:readline/promises';

import Anthropic from '@anthropic-ai/sdk';
import { VncComputer } from './vnc-computer.js';

async function main(): Promise<void> {
  const task =
    process.argv.slice(2).join(' ') || "Open a terminal, run date, and tell me today's date and time zone.";
  const client = new Anthropic();
  // `terminal: false` reads plain lines, so Ctrl-C still stops the run.
  const terminal = readline.createInterface({ input, output, terminal: false });
  const computer = await VncComputer.connect({
    host: process.env['VNC_HOST'] ?? '127.0.0.1',
    port: Number(process.env['VNC_PORT'] ?? 5900),
    // Shows the person at the terminal the tool call, and runs it only if they answer y.
    confirm: async (ctx) => {
      // A screenshot changes nothing on the desktop, so it runs unasked.
      if (ctx.member === 'screenshot') return true;
      // Escapes every character that is not printable ASCII, so invisible characters show.
      const call = JSON.stringify(ctx.input).replace(
        /[^\x20-\x7e]/g,
        (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`,
      );
      const answer = await terminal.question(`Allow ${ctx.member} ${call}? [y/N] `);
      return answer.trim().toLowerCase() === 'y';
    },
  });
  // The tool runner never closes the connection. The finally closes it, whether the loop ends or fails.
  try {
    const runner = client.beta.messages.toolRunner({
      model: process.env['MODEL'] ?? 'claude-sonnet-5-5',
      max_tokens: 4096,
      tools: [computer],
      messages: [{ role: 'user', content: task }],
    });
    for await (const message of runner) {
      console.dir(message, { depth: 4 });
    }
  } finally {
    terminal.close();
    await computer.close();
  }
}

main().catch((error: unknown) => {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
