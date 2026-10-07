# Browser Toolset Quickstart

The minimal CDP example of Claude's browser toolset (`browser_toolset_20260801`), in Python and TypeScript. You declare one toolset entry in `tools`. The model calls each browser action (`navigate`, `read_page`, `left_click` and the rest) as its own tool, and a driver runs those calls in a browser.

The driver is a few hundred lines. It drives one Chromium tab over the Chrome DevTools Protocol (CDP) and implements five of the toolset's tools. It shows the interface. It is not production code.

| File | What it is |
| --- | --- |
| `run.py` / `run.ts` | The quickstart: builds the example driver, hands it to the tool runner and prints the model's messages. Start here. |
| `exercise.py` / `exercise.ts` | The same toolset driven without a model: sends the calls a model would send against a local page and prints what the model would see. |
| `cdp_browser.py` / `cdp-browser.ts` | The example driver: a subclass of the SDK's abstract browser toolset, one Chromium tab over raw CDP. |

> [!WARNING]
> The pages the model visits affect what it does next. Run this against a throwaway browser profile inside a sandbox with egress controls, not against your everyday browser.
>
> Before you point it at anything else, read "Running a browser toolset safely" in the SDK's tool helper docs: [Python](https://github.com/anthropics/anthropic-sdk-python/blob/main/browser-toolset.md#running-a-browser-toolset-safely), [TypeScript](https://github.com/anthropics/anthropic-sdk-typescript/blob/main/browser-toolset.md#running-a-browser-toolset-safely).

## Install

You need:

- an Anthropic API key in `ANTHROPIC_API_KEY`;
- an Anthropic SDK version with the browser toolset helpers (`anthropic.tools.browser` in Python, `@anthropic-ai/sdk/helpers/beta/toolsets` in TypeScript);
- Python 3.10+ or Node.js 20+;
- a Chromium binary, from `CHROME_PATH` or `google-chrome` / `chromium` on your `PATH`. Ubuntu's snap-packaged Chromium cannot open a profile under `/tmp`. Install Google Chrome's `.deb`, or point `CHROME_PATH` at a non-snap build.

```bash
cd browser-toolset/python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd browser-toolset/typescript
npm install
```

## Run

```bash
python run.py "Open example.com and tell me the heading"          # Python
npm run start -- "Open example.com and tell me the heading"       # TypeScript
```

The whole command line is the task. `run.ts` reads no options, so even `--help` goes to the model. `run.py` answers `--help` itself.

It prints each of the model's messages as it arrives: its tool calls, then its final answer. `run` uses only the SDK's abstract toolset, so another driver works the same way: build it, pass it in `tools`, loop over the tool runner, and close it when the loop ends.

`run` passes the toolset an example URL policy (`example_policy` in `run.py`, `examplePolicy` in `run.ts`) that admits only http(s) pages on the hosts in `ALLOWED_DOMAINS`, subdomains included, and the empty tab. It shows where a policy goes. It is not a production policy. The SDK guide linked above covers what yours needs.

A `confirm` hook, which asks a person before a tool runs, goes in the same place: the toolset's `confirm` option. The example driver enables no tool that needs one.

| Variable | Effect |
| --- | --- |
| `ALLOWED_DOMAINS` | Comma-separated hosts the model may visit, subdomains included. Default: `example.com,iana.org`. Set but empty, it admits no host. |
| `HEADLESS` | Set to `0` to watch the browser. Chromium opens with two tabs: its own blank start-up tab and the one the driver works in. |
| `CHROME_PATH` | A specific Chromium binary. |
| `MODEL` | The model to run. |

## Exercise the toolset without a model

`exercise` needs no API key. It serves a small page on localhost and launches the driver with a policy that admits only that page. Then it sends the calls a model would send, through the entry point the tool runner uses:

```bash
python exercise.py        # Python
npm run exercise          # TypeScript
```

It prints each `tool_result` as the model would see it. Four calls are answered: `navigate`, `read_page`, a `left_click` on a `ref_N` from the read, and `get_page_text`, which shows what the click did. Two are refused with `is_error`: a `navigate` to the same page by `127.0.0.1`, and a `wait` longer than 30 seconds. It exits non-zero if any call comes back differently.

## What the example driver implements, and what it leaves out

Implemented: `navigate` (to a URL; returns once the document is parsed), `read_page` (headings, links, buttons and form controls, each with a `ref_N`), `left_click` (by ref or by coordinate), `get_page_text` and `wait`, plus the `browser_state` report of its one tab. The SDK supplies the rest: the tool schemas, the URL checks that wrap your policy, the refusal of tools the driver doesn't implement, and the tool runner.

Left out:

- every other tool: screenshots, scrolling, typing, form input, find, tabs, uploads and downloads, console and network reads, JavaScript execution;
- modifier keys on clicks and more than one tab;
- a page that stops answering, including one that opens a dialog (alert, confirm, prompt): every later call, navigate included, fails after 60 seconds;
- request interception. The URL policy judges the address the model asks for, not the browser's own requests. A redirect, or an image or script on an allowed page, can still reach a host the policy would refuse. Block those with egress rules;
- a page that replaces itself by script before its document is parsed: `navigate` then waits for a document that never arrives and gives up after 30 seconds;
- a click, or a page script, that starts a navigation: the next read can fail once or read the old page, and the model reads again or waits;
- cleanup after Ctrl-C: in TypeScript the temporary profile directory is left behind.

A production driver needs most of this list. The SDK guide linked above covers each part.
