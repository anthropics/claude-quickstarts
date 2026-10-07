# Computer Toolset Quickstart

The minimal VNC example of Claude's computer toolset (`computer_toolset_20260801`), in Python and TypeScript. You declare one toolset entry in `tools`. The model calls each desktop action (`screenshot`, `left_click`, `type` and the rest) as its own tool, and a driver runs those calls on a desktop.

The driver is a few hundred lines. It drives one desktop over VNC (the RFB protocol) and implements ten of the toolset's tools. It shows the interface. It is not production code.

| File | What it is |
| --- | --- |
| `run.py` / `run.ts` | The quickstart: builds the example driver, hands it to the tool runner and prints the model's messages. Start here. |
| `exercise.py` / `exercise.ts` | The same toolset driven without a model: sends the calls a model would send to your VNC server and prints what the model would see. |
| `vnc_computer.py` / `vnc-computer.ts` | The example driver: a subclass of the SDK's abstract computer toolset, one desktop over raw RFB. |

> [!WARNING]
> What is on the screen steers what the model does next, and a focused terminal runs whatever it types. Run this against a throwaway desktop inside a sandbox, not against your own.
>
> The server runs without a password, so keep it on localhost (`-localhost`, in both commands below); from a container, publish its port to the host's loopback only (`-p 127.0.0.1:5900:5900`).
>
> Before you point it at anything else, read "Running a computer toolset safely" in the SDK's tool helper docs: [Python](https://github.com/anthropics/anthropic-sdk-python/blob/main/computer-toolset.md#running-a-computer-toolset-safely), [TypeScript](https://github.com/anthropics/anthropic-sdk-typescript/blob/main/computer-toolset.md#running-a-computer-toolset-safely).

## Install

You need:

- an Anthropic API key in `ANTHROPIC_API_KEY`;
- an Anthropic SDK version with the computer toolset helpers (`anthropic.tools.computer` in Python, `@anthropic-ai/sdk/helpers/beta/toolsets` in TypeScript);
- Python 3.10+ or Node.js 20+;
- a VNC server without a password, on a screen no larger than 1920×1200. TigerVNC's `Xvnc` is one process and needs nothing else (`apt install tigervnc-standalone-server`); `-SecurityTypes None` turns off the password it asks for by default:

```bash
Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost -rfbport 5900 &
DISPLAY=:1 xterm -geometry 160x50 &
```

`x11vnc` in front of an existing X display also works (`x11vnc -display :0 -nopw -localhost -forever`). It polls the screen, so a screenshot taken right after an input can show the screen from before it, and the model then repeats the action or takes another screenshot.

```bash
cd computer-toolset/python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd computer-toolset/typescript
npm install
```

## Run

```bash
python run.py "Open a terminal, run date, and tell me today's date and time zone"     # Python
npm run start -- "Open a terminal, run date, and tell me today's date and time zone"  # TypeScript
```

The whole command line is the task. `run.ts` reads no options, so even `--help` goes to the model. `run.py` answers `--help` itself.

It prints each of the model's messages as it arrives: its tool calls, then its final answer. `run` uses only the SDK's abstract toolset, so another driver works the same way: build it, pass it in `tools`, loop over the tool runner, and close it when the loop ends.

Before each action other than a screenshot, `run` shows you the call and runs it only if you answer `y`. It does this through the toolset's `confirm` option. `exercise` passes a `confirm` that approves every call.

| Variable | Effect |
| --- | --- |
| `VNC_HOST` | The VNC server's host. Default: `127.0.0.1`. |
| `VNC_PORT` | The VNC server's port. Default: `5900`. |
| `MODEL` | The model to run. Default: `claude-sonnet-5-5`. |

## Exercise the toolset without a model

`exercise` needs no API key. It connects the driver to the VNC server and sends the calls a model would send, through the entry point the tool runner uses:

```bash
python exercise.py        # Python
npm run exercise          # TypeScript
```

It prints each `tool_result` as the model would see it, the screenshot's bytes elided. Six calls are answered: `screenshot`, a `left_click` at the screen's centre, `type`, `key`, `wait` and a second `screenshot` (retried for a few seconds if the server lags). Two are refused with `is_error`: a `left_click` one pixel off the screen, and `zoom`, which the driver leaves out.

It exits non-zero if any call comes back differently.

## What the example driver implements, and what it leaves out

Implemented: `screenshot` (the whole screen, as it is), `left_click`, `right_click`, `double_click`, `triple_click`, `mouse_move`, `scroll`, `type`, `key` (a name such as `Return` or `Page_Up`, a single character, or a chord such as `ctrl+s`) and `wait`. The SDK supplies the rest: the tool schemas, the refusal of tools the driver doesn't implement, and the tool runner.

A click without a coordinate acts where the pointer last was, and a modifier chord in a click's `text` is held during it.

Left out:

- every other tool: `zoom`, `left_click_drag`, `left_mouse_down`, `left_mouse_up`, `middle_click`, `hold_key` and `cursor_position`;
- scaling: the screen is sent as it is, and the driver refuses a screen wider than 1920 or taller than 1200 when it connects. A larger screen may need scaling to fit the model's image limits, and then the coordinates scaled back;
- a VNC password and servers older than RFB 3.7: the driver speaks RFB 3.7 or newer to a server that offers the `None` security type;
- an encoding other than Raw: each screenshot moves the whole screen uncompressed, about 4 MB at 1280×800, which is fine on localhost and slow elsewhere;
- a screen that changes size while the driver is connected;
- a letter under a held shift: `shift+a` types `a`;
- a bound on `wait`: the driver sleeps for whatever duration the model asks;
- recovery when the server stops answering: a screenshot waits 10 seconds, then fails, and so does every later one. Reconnect by building a new driver.

A production driver needs most of this list. The SDK guide linked above covers each part.
