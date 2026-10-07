/**
 * A minimal example of the computer toolset interface over VNC. It drives one desktop with ten tools and no VNC
 * library.
 *
 * It shows the interface. It is not production code. It extends `BetaAbstractComputerToolset20260801` with the
 * tools a first run needs (`screenshot`, the clicks, `mouse_move`, `scroll`, `key`, `type` and `wait`) against a
 * VNC server that asks for no password. The SDK reports every other tool as disabled and offers the model only
 * these.
 *
 * It reads the screen unscaled, in the Raw encoding, over RFB 3.7 or newer. It refuses a screen larger than 1920×1200
 * and a server that needs a password. See the README.
 *
 * Read "Running a computer toolset safely" in the SDK guide (computer-toolset.md) before pointing it at anything but
 * a throwaway desktop, because what the model sees on screen steers what it does next.
 *
 * Run it with run.ts, which contains the install and run instructions.
 */

import { createConnection, type Socket } from 'node:net';
import { setTimeout as sleep } from 'node:timers/promises';

import {
  BetaAbstractComputerToolset20260801,
  ToolError,
  type BetaScreenshotResult,
  type BetaComputerToolsetOptions,
  type BetaToolsetCallContext,
} from '@anthropic-ai/sdk/helpers/beta/toolsets';
import type {
  BetaComputerDoubleClickInput,
  BetaComputerKeyInput,
  BetaComputerLeftClickInput,
  BetaComputerMouseMoveInput,
  BetaComputerRightClickInput,
  BetaComputerScrollInput,
  BetaComputerTripleClickInput,
  BetaComputerTypeInput,
  BetaComputerWaitInput,
} from '@anthropic-ai/sdk/resources/beta';
import { PNG } from 'pngjs';

const MAX_WIDTH = 1920; // Screenshots are not scaled, and a screen this size stays inside the API's image limits.
const MAX_HEIGHT = 1200;
const READ_TIMEOUT_MS = 10_000;
// These bytes ask for 32-bit true-colour pixels with red in the lowest byte, so each pixel arrives as R, G, B and an
// unused byte, which is the order the PNG encoder expects.
const PIXEL_FORMAT = [32, 24, 0, 1, 0, 255, 0, 255, 0, 255, 0, 8, 16, 0, 0, 0];

/** X11 keysyms for the key names the model sends, by lower-cased name. */
const KEYSYMS: Record<string, number> = {
  return: 0xff0d,
  enter: 0xff0d,
  tab: 0xff09,
  escape: 0xff1b,
  backspace: 0xff08,
  delete: 0xffff,
  up: 0xff52,
  down: 0xff54,
  left: 0xff51,
  right: 0xff53,
  home: 0xff50,
  end: 0xff57,
  page_up: 0xff55,
  page_down: 0xff56,
  insert: 0xff63,
  space: 0x20,
  ctrl: 0xffe3,
  control: 0xffe3,
  alt: 0xffe9,
  shift: 0xffe1,
  super: 0xffeb,
  cmd: 0xffeb,
  win: 0xffeb,
};

function keysym(name: string): number {
  const known = KEYSYMS[name.toLowerCase()];
  if (known !== undefined) return known;
  const fKey = /^f([1-9]|1[0-2])$/i.exec(name);
  if (fKey) return 0xffbe + Number(fKey[1]) - 1;
  if ([...name].length !== 1) {
    throw new ToolError(
      `unknown key '${name}'; use a single character or a name such as Return, Page_Up or F5`,
    );
  }
  const codePoint = name.codePointAt(0) ?? 0;
  // A Latin-1 character is its own keysym, and the rest of Unicode is offset.
  return codePoint <= 0xff ? codePoint : 0x01000000 | codePoint;
}

/**
 * Options for `VncComputer.connect`. The SDK's own toolset options pass through unchanged, and `host` and `port`
 * pick the VNC server.
 */
export type VncComputerOptions = BetaComputerToolsetOptions & { host?: string; port?: number };

/** Drives one desktop over VNC. Build it with `VncComputer.connect` and release it with `close()`. */
export class VncComputer extends BetaAbstractComputerToolset20260801 {
  private socket!: Socket;
  private width = 0;
  private height = 0;
  private cursor: [number, number] = [0, 0];

  static async connect(options: VncComputerOptions = {}): Promise<VncComputer> {
    const { host = '127.0.0.1', port = 5900, ...toolsetOptions } = options;
    const computer = new VncComputer(host, port, toolsetOptions);
    try {
      await computer.open();
    } catch (error) {
      await computer.close();
      throw error;
    }
    return computer;
  }

  private constructor(
    private readonly host: string,
    private readonly port: number,
    options: BetaComputerToolsetOptions,
  ) {
    super(options);
  }

  override async close(): Promise<void> {
    await super.close();
    this.socket.destroy();
  }

  /** Connects to the server, runs the RFB handshake, and asks for the pixel format and encoding this driver reads. */
  private async open(): Promise<void> {
    this.socket = createConnection({ host: this.host, port: this.port });
    // A socket error is reported by the next read, through socket.errored, instead of crashing the process.
    this.socket.on('error', () => undefined);
    const greeting = (await this.read(12)).toString('latin1');
    const version = /^RFB (\d{3})\.(\d{3})\n$/.exec(greeting);
    if (!version || Number(version[1]) * 1000 + Number(version[2]) < 3007) {
      throw new Error(`expected an RFB 3.7 or newer server; it greeted with ${JSON.stringify(greeting)}`);
    }
    // A server newer than 3.8 is spoken to as 3.8, as RFC 6143 says.
    const minor = Number(version[1]) > 3 || Number(version[2]) >= 8 ? 8 : 7;
    this.socket.write(`RFB 003.00${minor}\n`);
    const securityTypes = await this.read((await this.read(1)).readUInt8(0));
    if (!securityTypes.includes(1)) {
      throw new Error(
        'this example needs a VNC server without a password; see the README for the Xvnc command',
      );
    }
    this.socket.write(Buffer.from([1])); // Security type 1 is None.
    if (minor === 8 && (await this.read(4)).readUInt32BE(0) !== 0) {
      throw new Error('the VNC server refused the connection');
    }
    this.socket.write(Buffer.from([1])); // ClientInit asks to share the desktop with other viewers.
    const serverInit = await this.read(24);
    this.width = serverInit.readUInt16BE(0);
    this.height = serverInit.readUInt16BE(2);
    await this.read(serverInit.readUInt32BE(20)); // The desktop name is not used.
    if (this.width > MAX_WIDTH || this.height > MAX_HEIGHT) {
      throw new Error(
        `the screen is ${this.width}x${this.height}; this example needs at most ${MAX_WIDTH}x${MAX_HEIGHT}. Lower the server's resolution.`,
      );
    }
    this.socket.write(Buffer.from([0, 0, 0, 0, ...PIXEL_FORMAT])); // SetPixelFormat asks for the format above.
    this.socket.write(Buffer.from([2, 0, 0, 1, 0, 0, 0, 0])); // SetEncodings, with Raw as the only encoding.
  }

  /** Reads the next `length` bytes from the server. */
  private async read(length: number): Promise<Buffer> {
    if (length === 0) return Buffer.alloc(0);
    const deadline = Date.now() + READ_TIMEOUT_MS;
    for (;;) {
      // socket.read is null until `length` bytes have arrived, and short once the stream has ended.
      const chunk: Buffer | null = this.socket.read(length);
      if (chunk?.length === length) return chunk;
      if (this.socket.errored) throw this.socket.errored;
      if (chunk !== null || this.socket.closed) throw new Error('the VNC server closed the connection');
      if (Date.now() > deadline)
        throw new Error(`the VNC server did not answer within ${READ_TIMEOUT_MS / 1000} s`);
      await sleep(5);
    }
  }

  /**
   * Sends a PointerEvent that puts the pointer at (x, y) with the buttons in the `buttons` mask held. Bit 0 is the
   * left button, bit 1 the middle, bit 2 the right, and bits 3 to 6 the wheel.
   */
  private pointer(x: number, y: number, buttons = 0): void {
    // A coordinate off the screen is refused rather than clamped, so the model sees its mistake.
    if (!(x >= 0 && x < this.width && y >= 0 && y < this.height)) {
      throw new ToolError(`(${x}, ${y}) is outside the ${this.width}x${this.height} screen`);
    }
    this.cursor = [x, y];
    this.socket.write(Buffer.from([5, buttons, x >> 8, x & 0xff, y >> 8, y & 0xff]));
  }

  /** Sends a KeyEvent that presses or releases one keysym. */
  private keyEvent(keysym: number, down: boolean): void {
    const message = Buffer.from([4, down ? 1 : 0, 0, 0, 0, 0, 0, 0]);
    message.writeUInt32BE(keysym, 4);
    this.socket.write(message);
  }

  /**
   * Presses and releases `button` at the coordinate, or where the pointer is, `times` times while holding the
   * modifier keys named in `text`.
   */
  private async click(
    input: { coordinate?: number[] | null; text?: string | null },
    button: number,
    times: number,
  ): Promise<void> {
    const [x, y] = (input.coordinate as [number, number] | null | undefined) ?? this.cursor;
    this.pointer(x, y);
    const modifiers = input.text ? input.text.split('+').map(keysym) : [];
    for (const k of modifiers) this.keyEvent(k, true);
    for (let i = 0; i < times; i++) {
      this.pointer(x, y, button);
      this.pointer(x, y);
      await sleep(10); // A 10 ms gap keeps the clicks inside every toolkit's double-click window.
    }
    for (const k of [...modifiers].reverse()) this.keyEvent(k, false);
  }

  protected override async screenshot(): Promise<BetaScreenshotResult> {
    await sleep(500); // VNC has no signal that an action is done, so the desktop gets time to draw the last one.
    const frame = Buffer.alloc(this.width * this.height * 4); // Each pixel is 4 bytes, as SetPixelFormat asked.
    const request = Buffer.from([3, 0, 0, 0, 0, 0, 0, 0, 0, 0]); // This asks for the whole screen, not only what changed.
    request.writeUInt16BE(this.width, 6);
    request.writeUInt16BE(this.height, 8);
    this.socket.write(request);
    for (;;) {
      const type = (await this.read(1)).readUInt8(0);
      if (type === 0) break; // A FramebufferUpdate follows.
      if (type === 2) continue; // A Bell has no body.
      if (type !== 3)
        throw new Error(`the VNC server sent a message of type ${type}, which this example does not read`);
      // ServerCutText carries the clipboard; a click that selects text triggers one. It is skipped.
      await this.read((await this.read(7)).readUInt32BE(3));
    }
    const rectangles = (await this.read(3)).readUInt16BE(1);
    for (let i = 0; i < rectangles; i++) {
      const rectangle = await this.read(12);
      const [x, y, width, height] = [0, 2, 4, 6].map((offset) => rectangle.readUInt16BE(offset)) as [
        number,
        number,
        number,
        number,
      ];
      if (rectangle.readInt32BE(8) !== 0) throw new Error('the VNC server sent an encoding other than Raw');
      const rows = await this.read(width * height * 4);
      for (let row = 0; row < height; row++) {
        rows.copy(frame, ((y + row) * this.width + x) * 4, row * width * 4, (row + 1) * width * 4);
      }
    }
    // The unused byte becomes the PNG's alpha, so it is set to opaque.
    for (let i = 3; i < frame.length; i += 4) frame[i] = 255;
    const png = new PNG({ width: this.width, height: this.height });
    png.data = frame;
    return { data: PNG.sync.write(png).toString('base64') };
  }

  protected override async left_click(
    _ctx: BetaToolsetCallContext,
    input: BetaComputerLeftClickInput,
  ): Promise<void> {
    await this.click(input, 1, 1);
  }

  protected override async right_click(
    _ctx: BetaToolsetCallContext,
    input: BetaComputerRightClickInput,
  ): Promise<void> {
    await this.click(input, 4, 1);
  }

  protected override async double_click(
    _ctx: BetaToolsetCallContext,
    input: BetaComputerDoubleClickInput,
  ): Promise<void> {
    await this.click(input, 1, 2);
  }

  protected override async triple_click(
    _ctx: BetaToolsetCallContext,
    input: BetaComputerTripleClickInput,
  ): Promise<void> {
    await this.click(input, 1, 3);
  }

  protected override mouse_move(_ctx: BetaToolsetCallContext, input: BetaComputerMouseMoveInput): void {
    const [x, y] = input.coordinate as [number, number];
    this.pointer(x, y);
  }

  protected override async scroll(_ctx: BetaToolsetCallContext, input: BetaComputerScrollInput): Promise<void> {
    // A wheel step is a press of one of the four wheel buttons (mask bits 3 to 6).
    const button = { up: 8, down: 16, left: 32, right: 64 }[input.scroll_direction];
    await this.click(input, button, input.scroll_amount);
  }

  protected override key(_ctx: BetaToolsetCallContext, input: BetaComputerKeyInput): void {
    // A chord such as "ctrl+c" presses each key in order and releases them in reverse.
    const keysyms = input.text.split('+').map(keysym);
    for (let i = 0; i < (input.repeat || 1); i++) {
      for (const k of keysyms) this.keyEvent(k, true);
      for (const k of [...keysyms].reverse()) this.keyEvent(k, false);
    }
  }

  protected override async type_(_ctx: BetaToolsetCallContext, input: BetaComputerTypeInput): Promise<void> {
    for (const character of input.text) {
      const k = keysym(
        character === '\n' ? 'return'
        : character === '\t' ? 'tab'
        : character,
      );
      this.keyEvent(k, true);
      this.keyEvent(k, false);
      await sleep(12); // Typing at a fast typist's pace keeps a terminal's echo and output in order.
    }
  }

  protected override async wait(_ctx: BetaToolsetCallContext, input: BetaComputerWaitInput): Promise<void> {
    await sleep(input.duration * 1000);
  }
}
