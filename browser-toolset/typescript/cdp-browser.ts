/**
 * A minimal example of the browser toolset interface over the Chrome DevTools Protocol (CDP): one Chromium tab,
 * five tools, no browser library.
 *
 * It shows the interface. It is not production code. It extends `BetaAbstractBrowserToolset20260801` with the tools a
 * first run needs (`navigate`, `read_page`, `left_click`, `get_page_text` and `wait`), against one tab of a Chromium it
 * launches. The SDK turns off every other tool in the toolset's `configs` and offers the model only these.
 *
 * It leaves dialogs and downloads unhandled and does not recover a page that stops answering. It lacks request
 * interception, so the URL policy judges only the addresses the model asks for. See the README.
 *
 * Read "Running a browser toolset safely" in the SDK guide (browser-toolset.md) before pointing it at anything but a
 * throwaway profile inside a sandbox, because the pages the model visits affect what it does next.
 *
 * Run it with run.ts, which contains the install and run instructions.
 */

import { type ChildProcess, spawn } from 'node:child_process';
import { once } from 'node:events';
import { closeSync, existsSync, mkdtempSync, openSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

import {
  BetaAbstractBrowserToolset20260801,
  ToolError,
  type BetaBrowserNavigateResult,
  type BetaBrowserState,
  type BetaBrowserToolsetOptions,
  type BetaToolsetCallContext,
} from '@anthropic-ai/sdk/helpers/beta/toolsets';
import type {
  BetaBrowserGetPageTextInput,
  BetaBrowserLeftClickInput,
  BetaBrowserNavigateInput,
  BetaBrowserReadPageInput,
  BetaBrowserWaitInput,
} from '@anthropic-ai/sdk/resources/beta';
import WebSocket from 'ws';

const COMMAND_TIMEOUT_MS = 30_000; // every CDP command, and the wait for a page to load
const TAB_ID = 'tab_1';

/** The SDK's toolset options (`urlPolicy`, `configs`, `confirm` and the rest), passed on unchanged, plus the two that pick the browser. */
export type CdpBrowserOptions = Omit<BetaBrowserToolsetOptions, 'browserState'> & {
  headless?: boolean;
  chromePath?: string;
};

/** A CDP message: a reply (`id` with `result` or `error`) or an event (`method` and `params`, no `id`). */
interface CdpMessage {
  id?: number;
  method?: string;
  params?: { name?: string; loaderId?: string };
  result?: Record<string, unknown>;
  error?: { message?: string };
}

interface PendingCommand {
  method: string;
  resolve: (result: Record<string, unknown>) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

/**
 * The Chromium binary: the argument, else `CHROME_PATH`, else one of the usual names on `PATH`. A path to a missing
 * binary fails at launch.
 */
export function findChrome(chromePath?: string): string {
  const configured = chromePath || process.env['CHROME_PATH'];
  if (configured) return configured;
  for (const dir of (process.env['PATH'] ?? '').split(delimiter)) {
    for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']) {
      const found = join(dir, name);
      if (existsSync(found)) return found;
    }
  }
  throw new Error('No Chromium binary found: set CHROME_PATH or install google-chrome / chromium.');
}

/**
 * One Chromium tab driven over CDP. Build it with `CdpBrowser.launch` and release it with `close()`. Process exit does
 * not release it.
 */
export class CdpBrowser extends BetaAbstractBrowserToolset20260801 {
  private process: ChildProcess | undefined;
  private profileDir: string | undefined;
  private socket: WebSocket | undefined;
  private sessionId = '';
  private nextId = 1;
  private readonly pending = new Map<number, PendingCommand>();
  private readonly events: CdpMessage[] = [];

  static async launch(options: CdpBrowserOptions = {}): Promise<CdpBrowser> {
    const { headless = true, chromePath, ...toolsetOptions } = options;
    const browser = new CdpBrowser(toolsetOptions);
    try {
      await browser.connect(await browser.start(headless, chromePath));
    } catch (error) {
      await browser.close();
      throw error;
    }
    return browser;
  }

  private constructor(options: Omit<BetaBrowserToolsetOptions, 'browserState'>) {
    super({ ...options, browserState: () => this.browserState() });
  }

  /** Start Chromium with a fresh profile and return its browser DevTools endpoint. */
  private async start(headless: boolean, chromePath: string | undefined): Promise<string> {
    const binary = findChrome(chromePath);
    this.profileDir = mkdtempSync(join(tmpdir(), 'cdp-browser-'));
    // Chromium's output goes to a file in the profile dir, because a pipe nobody drains blocks Chromium once full.
    const logFile = join(this.profileDir, 'chromium.log');
    const log = openSync(logFile, 'w');
    const child = spawn(
      binary,
      [
        ...(headless ? ['--headless=new'] : []),
        '--remote-debugging-port=0',
        `--user-data-dir=${this.profileDir}`,
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-networking',
        '--disable-extensions',
        '--disable-sync',
        '--window-size=1280,720',
        // Chromium cannot start its own sandbox as root, and most containers run it as root.
        ...(process.getuid?.() === 0 ? ['--no-sandbox'] : []),
        'about:blank',
      ],
      { stdio: ['ignore', log, log] },
    );
    closeSync(log); // the child holds its own copy
    this.process = child;
    let spawnError = '';
    child.once('error', (error) => (spawnError = error.message));
    // Chromium writes the port and the browser endpoint's path to DevToolsActivePort once it listens.
    const portFile = join(this.profileDir, 'DevToolsActivePort');
    const deadline = Date.now() + 20_000;
    while (Date.now() < deadline) {
      const [port, path] = (existsSync(portFile) ? readFileSync(portFile, 'utf8') : '').split('\n');
      if (port && /^\d+$/.test(port.trim()) && path?.startsWith('/')) {
        return `ws://127.0.0.1:${port.trim()}${path.trim()}`;
      }
      if (spawnError || child.exitCode !== null || child.signalCode !== null) break;
      await sleep(50);
    }
    const output = (spawnError || readFileSync(logFile, 'utf8')).trim();
    throw new Error(`Chromium did not start: ${output.split('\n').pop() || 'no output'}`);
  }

  /** Open a tab, attach to it and enable the domains the tools use. */
  private async connect(wsUrl: string): Promise<void> {
    const socket = new WebSocket(wsUrl);
    await once(socket, 'open'); // no handshake timeout: Chromium has already written the endpoint, so it answers
    this.socket = socket;
    this.socket.on('message', (raw) => this.receive(String(raw)));
    this.socket.on('error', (error) => this.failPending(`the browser connection failed: ${error.message}`));
    this.socket.on('close', () => {
      this.socket = undefined; // later commands fail at once instead of waiting out their timeout
      this.failPending('the browser connection closed');
    });
    const { targetId } = (await this.send('Target.createTarget', { url: 'about:blank' })) as {
      targetId: string;
    };
    const attached = (await this.send('Target.attachToTarget', { targetId, flatten: true })) as {
      sessionId: string;
    };
    this.sessionId = attached.sessionId;
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('Page.setLifecycleEventsEnabled', { enabled: true });
  }

  /** Stop Chromium and remove its profile. It is safe to call more than once. */
  override async close(): Promise<void> {
    await super.close();
    const socket = this.socket; // the 'close' handler clears this.socket once the browser goes
    if (socket !== undefined) {
      await this.send('Browser.close').catch(() => undefined); // the browser may be gone already; stopped below either way
      socket.close();
      this.socket = undefined;
    }
    if (this.process !== undefined) {
      const child = this.process;
      this.process = undefined;
      if (child.exitCode === null && child.signalCode === null) {
        const exited = new Promise<void>((resolve) => child.once('exit', () => resolve()));
        child.kill();
        const forceKill = setTimeout(() => child.kill('SIGKILL'), 5_000);
        await exited;
        clearTimeout(forceKill);
      }
    }
    if (this.profileDir !== undefined) {
      await removeProfile(this.profileDir);
      this.profileDir = undefined;
    }
  }

  /** Send one CDP command and return its result. `Target.*` and `Browser.*` go to the browser, the rest to the tab. */
  private send(method: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    const socket = this.socket;
    if (socket === undefined) return Promise.reject(new ToolError(`${method} failed: the browser is closed`));
    const id = this.nextId++;
    const command: Record<string, unknown> = { id, method, params };
    if (this.sessionId && !/^(Target|Browser)\./.test(method)) command['sessionId'] = this.sessionId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new ToolError(`${method} timed out`));
      }, COMMAND_TIMEOUT_MS);
      this.pending.set(id, { method, resolve, reject, timer });
      socket.send(JSON.stringify(command));
    });
  }

  private receive(raw: string): void {
    const message = JSON.parse(raw) as CdpMessage;
    // navigate waits for this event. Unlike Page.domContentEventFired, it contains a loaderId, so navigate can match
    // it to its own Page.navigate.
    if (message.method === 'Page.lifecycleEvent' && message.params?.name === 'DOMContentLoaded')
      this.events.push(message);
    if (message.id === undefined) return;
    const command = this.pending.get(message.id);
    if (command === undefined) return;
    this.pending.delete(message.id);
    clearTimeout(command.timer);
    if (message.error)
      command.reject(new ToolError(`${command.method} failed: ${message.error.message ?? 'unknown error'}`));
    else command.resolve(message.result ?? {});
  }

  private failPending(reason: string): void {
    for (const [id, command] of this.pending) {
      this.pending.delete(id);
      clearTimeout(command.timer);
      command.reject(new ToolError(`${command.method} failed: ${reason}`));
    }
  }

  /** Run JavaScript in the page and return its value. */
  private async evaluate<T>(expression: string): Promise<T | undefined> {
    const result = (await this.send('Runtime.evaluate', { expression, returnByValue: true })) as {
      result?: { value?: T };
      exceptionDetails?: { text?: string; exception?: { description?: string } };
    };
    const details = result.exceptionDetails;
    if (details)
      throw new ToolError(`the page script failed: ${details.exception?.description ?? details.text}`);
    return result.result?.value;
  }

  /** The tab's current address and title. */
  private async pageInfo(): Promise<{ url: string; title: string }> {
    const info = (await this.evaluate<{ url?: string; title?: string }>(PAGE_INFO)) ?? {};
    return { url: String(info.url ?? 'about:blank'), title: String(info.title ?? '') };
  }

  protected override async navigate(
    _ctx: BetaToolsetCallContext,
    input: BetaBrowserNavigateInput,
  ): Promise<BetaBrowserNavigateResult> {
    if (['back', 'forward', 'reload'].includes(input.url))
      throw new ToolError(
        'This example only navigates to a URL; back, forward and reload are not supported.',
      );
    this.events.length = 0;
    // Open an address without a scheme as https, the same way the URL policy reads it.
    const url = /^[a-z][a-z0-9+.-]*:/i.test(input.url) ? input.url : `https://${input.url}`;
    const started = (await this.send('Page.navigate', { url })) as { errorText?: string; loaderId?: string };
    if (started.errorText) throw new ToolError(`navigate failed: ${started.errorText}`);
    // Wait until the new document is parsed (DOMContentLoaded), not until its images and other sub-resources load.
    const loaderId = started.loaderId; // absent for a same-document navigation (a #fragment): no new document
    const deadline = Date.now() + COMMAND_TIMEOUT_MS;
    while (loaderId && !this.events.some((event) => event.params?.loaderId === loaderId)) {
      if (this.socket === undefined) throw new ToolError('navigate failed: the browser connection closed');
      if (Date.now() >= deadline)
        throw new ToolError(`navigate failed: the page did not load within ${COMMAND_TIMEOUT_MS / 1000} s`);
      await sleep(50);
    }
    this.events.length = 0;
    const page = await this.pageInfo();
    return { url: page.url, ...(page.title ? { title: page.title } : {}) };
  }

  protected override async read_page(
    _ctx: BetaToolsetCallContext,
    _input: BetaBrowserReadPageInput,
  ): Promise<string> {
    return (await this.evaluate<string>(READ_PAGE)) || ''; // '' on purpose: the SDK substitutes its own "(empty)" text
  }

  protected override async left_click(
    _ctx: BetaToolsetCallContext,
    input: BetaBrowserLeftClickInput,
  ): Promise<void> {
    let point: { x: number; y: number };
    if (input.target.type === 'ref') {
      const found = await this.evaluate<{ x: number; y: number } | null>(
        `${RESOLVE_REF}(${JSON.stringify(input.target.ref)})`,
      );
      if (!found)
        throw new ToolError(
          `Unknown or stale ref: ${input.target.ref}. Call read_page again for current refs.`,
        );
      point = found;
    } else {
      point = { x: input.target.x, y: input.target.y };
    }
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
    for (const type of ['mousePressed', 'mouseReleased']) {
      await this.send('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 });
    }
    await sleep(100); // let the page react before the next call reads it
  }

  protected override async get_page_text(
    _ctx: BetaToolsetCallContext,
    _input: BetaBrowserGetPageTextInput,
  ): Promise<string> {
    return (await this.evaluate<string>(PAGE_TEXT)) || '';
  }

  protected override async wait(_ctx: BetaToolsetCallContext, input: BetaBrowserWaitInput): Promise<void> {
    // The SDK leaves `duration` unbounded, and the tool's documented maximum is 30 seconds.
    if (!(input.duration >= 0 && input.duration <= 30))
      throw new ToolError('duration: must be between 0 and 30 seconds');
    await sleep(input.duration * 1000);
  }

  private async browserState(): Promise<BetaBrowserState> {
    let page = { url: 'about:blank', title: '' };
    try {
      page = await this.pageInfo();
    } catch {
      // the tab cannot answer (renderer gone, or the browser closed): report the empty tab
    }
    return { tabs: [{ tab_id: TAB_ID, url: page.url, title: page.title, active: true }], state_changes: [] };
  }
}

/**
 * Remove the profile directory. Chromium's network service can write state files there just after the browser process
 * exits, so a removal that finds the directory refilled is retried for a few seconds, and then left in place.
 */
async function removeProfile(dir: string): Promise<void> {
  for (let attempt = 0; ; attempt++) {
    try {
      rmSync(dir, { recursive: true, force: true });
      return;
    } catch (error) {
      if (attempt >= 50 || (error as NodeJS.ErrnoException).code !== 'ENOTEMPTY') return; // leave it rather than fail close()
      await sleep(100);
    }
  }
}

// --- the JavaScript the tools run in the page ---

const PAGE_INFO = '({ url: location.href, title: document.title })';
const PAGE_TEXT = "document.body ? document.body.innerText : ''";

// Assigns `ref_N` to each rendered h1-h3, link, button and form control of the current document and lists them one per
// line. The refs are stored on `window`, so a navigation drops them.
const READ_PAGE = `(() => {
  const refs = (window.__cdpBrowserRefs ||= { next: 1, byRef: new Map(), byElement: new WeakMap() });
  const roles = { A: 'link', BUTTON: 'button', INPUT: 'textbox', SELECT: 'combobox', TEXTAREA: 'textbox' };
  const name = (el) => (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || '')
    .trim().replace(/\\s+/g, ' ').slice(0, 80);
  const lines = [];
  const selector = 'h1, h2, h3, a[href], button, input, select, textarea, [role=button], [role=link]';
  for (const el of document.querySelectorAll(selector)) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;  // not rendered
    let ref = refs.byElement.get(el);
    if (!ref) { ref = 'ref_' + refs.next++; refs.byElement.set(el, ref); refs.byRef.set(ref, el); }
    const role = el.getAttribute('role') || roles[el.tagName] || 'heading';
    lines.push(\`- \${role} "\${name(el)}" [\${ref}]\`);
  }
  return lines.join('\\n');
})()`;

// The viewport centre of the ref's element, after scrolling it into view, or null if the document lacks the ref.
const RESOLVE_REF = `((ref) => {
  const el = window.__cdpBrowserRefs && window.__cdpBrowserRefs.byRef.get(ref);
  if (!el || !el.isConnected) return null;
  el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})`;
