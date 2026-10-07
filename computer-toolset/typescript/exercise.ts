#!/usr/bin/env -S npx --no-install tsx
/**
 * Exercises the computer toolset with the calls a model would make, against a VNC server, with no API key and no model.
 *
 * Usage:
 *
 *     npx tsx exercise.ts
 *
 * The script connects the example driver to the VNC server and sends the toolset the `tool_use` calls a model would
 * send, through `computer.toolResult()`, which runs the same pipeline as the tool runner. It prints each
 * `tool_result` as the model would see it, then checks it:
 *
 * - `screenshot`, `left_click` on the middle of the screen, `type`, `key`, `wait` and a second `screenshot` (taken
 *   again for a few seconds if the server has not caught up) are all answered;
 * - `left_click` one pixel outside the screen, and `zoom`, which the driver leaves out, are both refused (`is_error`).
 *
 * The first call that comes back differently ends the script with a failed assertion, so the script also works as a
 * smoke check.
 *
 * It needs what run.ts needs, minus the API key.
 */

import assert from 'node:assert/strict';

import type { BetaAbstractComputerToolset20260801 } from '@anthropic-ai/sdk/helpers/beta/toolsets';
import type {
  BetaToolResultBlockParam,
  BetaToolResultContentBlockParam,
} from '@anthropic-ai/sdk/resources/beta';
import { VncComputer } from './vnc-computer.js';

/** Sends one tool call as the model would and prints the result as the model would see it. */
async function call(
  computer: BetaAbstractComputerToolset20260801,
  name: string,
  input: Record<string, unknown>,
): Promise<BetaToolResultBlockParam> {
  const result = await computer.toolResult({
    type: 'tool_use',
    id: `toolu_${name}`,
    name,
    input,
    toolset_name: 'computer',
  });
  console.log(`\n${name} ${JSON.stringify(input)} -> ${result.is_error ? 'refused' : 'answered'}`);
  for (const block of blocksOf(result)) {
    console.log(
      '  ' +
        (block.type === 'image' ?
          `{"type":"image", ... ${JSON.stringify(block).length} chars}`
        : JSON.stringify(block)),
    );
  }
  return result;
}

/** Returns the result's content blocks. `content` is a string or a list of blocks; a string becomes one text block. */
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
  const computer = await VncComputer.connect({
    host: process.env['VNC_HOST'] ?? '127.0.0.1',
    port: Number(process.env['VNC_PORT'] ?? 5900),
    // No one is at the terminal, so this confirm approves every call.
    confirm: () => true,
  });
  try {
    const shot = blocksOf(await call(computer, 'screenshot', {}))[0];
    assert(
      shot?.type === 'image' && shot.source.type === 'base64',
      'expected that screenshot answers with an image',
    );
    const png = Buffer.from(shot.source.data, 'base64');
    assert(png.subarray(0, 8).equals(Buffer.from('\x89PNG\r\n\x1a\n', 'latin1')), 'expected a PNG');
    const [width, height] = [png.readUInt32BE(16), png.readUInt32BE(20)]; // The IHDR chunk gives the screen's size.
    const clicked = await call(computer, 'left_click', {
      coordinate: [Math.floor(width / 2), Math.floor(height / 2)],
    });
    assert(!clicked.is_error, 'expected that left_click on the middle of the screen is answered');
    assert(!(await call(computer, 'type', { text: 'hello' })).is_error, 'expected that type is answered');
    assert(!(await call(computer, 'key', { text: 'Return' })).is_error, 'expected that key is answered');
    assert(!(await call(computer, 'wait', { duration: 1 })).is_error, 'expected that wait is answered');
    // x11vnc can answer a screenshot taken right after input with the screen from before it, so look a few times.
    let again = blocksOf(await call(computer, 'screenshot', {}))[0];
    for (let tries = 1; tries < 6 && JSON.stringify(again) === JSON.stringify(shot); tries++) {
      await call(computer, 'wait', { duration: 1 });
      again = blocksOf(await call(computer, 'screenshot', {}))[0];
    }
    assert(
      again?.type === 'image' && JSON.stringify(again) !== JSON.stringify(shot),
      'expected that a later screenshot differs from the first: the typing showed',
    );
    // One pixel past the bottom-right corner is refused by the driver rather than clamped, so the model sees its
    // mistake.
    const outside = await call(computer, 'left_click', { coordinate: [width, height] });
    assert(
      outside.is_error === true && textOf(outside).includes('outside the'),
      'expected that left_click outside the screen is refused',
    );
    // The driver does not implement zoom, so the SDK refuses the call before the driver runs.
    const zoomed = await call(computer, 'zoom', { region: [0, 0, 100, 100] });
    assert(zoomed.is_error === true, 'expected that zoom is refused as a tool the driver leaves out');
  } finally {
    await computer.close();
  }

  console.log('\nAll calls came back as expected.');
}

main().catch((error: unknown) => {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
