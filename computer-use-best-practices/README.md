# Computer and Browser Use with Claude

> [!CAUTION]
> **This is a reference implementation for instructional purposes only.**
>
> Running this agent outside of a virtual machine is **strongly discouraged**.
> The agent has full control of your mouse, keyboard, and screen. There are
> **no safeguards** against it taking screenshots that contain sensitive
> information and uploading them to the API, deleting or overwriting important
> data, or opening and operating any application on your machine.
>
> Run it inside a disposable macOS VM. [UTM](https://mac.getutm.app/) and
> [Parallels](https://www.parallels.com/) both support macOS guests; we use
> these tools internally for this purpose but are not affiliated with either
> project or company in any way and do not endorse them over alternatives.
>
> If you want computer-use functionality with built-in safeguards and
> user-in-the-loop controls rather than a teaching scaffold, use
> [**Cowork**](https://claude.ai/downloads).

This repository is a **reference implementation**: it is meant to be read,
understood, and modified for your own use case rather than imported as a
library or treated as a production-ready SDK. It pairs with the companion
[computer-use best-practices guide](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude),
and the two are intended to be read side by side.

It targets **macOS only**. Key handling, the `pyautogui` backend, and
`sandbox-exec` are all Mac-specific; a containerized or Linux variant is
out of scope here. If you want a minimal containerized starting point
instead, see the [Computer Use Demo](../computer-use-demo) (Docker + X11
desktop) or the [Browser Use Demo](../browser-use-demo) (Docker +
Playwright, browser-only) elsewhere in this repository.

A focused, pedagogical demo of Claude computer-use on **macOS**, running
**locally** (no Docker), with:

- Explicitly defined tools: every computer-use and browser-use tool the model
  sees is fully specified in `computer_use/tools/`, so you can read the exact
  name, description, and JSON schema that go into the API call.
- Correct screenshot sizing: `computer_use/image.py` ports the API's
  reference resize so the model sees exactly the pixels you send and click
  coordinates stay accurate.
- Batch tools: `computer_batch` / `browser_batch` let the model chain
  predictable actions in one turn. Batching can meaningfully reduce latency
  and cost on workloads where the model can confidently plan several steps
  ahead; the demo nudges toward it via the `BATCH_REMINDER` appended after a
  lone single-action call.
- Sandboxed `bash` / `python` via `sandbox-exec` (profile in `sandbox/`).
- Trajectory recording (`runs/…`) and a Streamlit viewer.
- A FastAPI debug panel for exercising tools by hand.

> [!TIP]
> **Quickstart**
>
> Using [Claude Code](https://claude.ai/code)? Open this folder in it and run
> **`/first-run`** for a guided walkthrough.
>
> Otherwise, the three commands you need are:
>
> ```bash
> python -m pip install -r requirements.txt && python -m playwright install chromium
> echo "ANTHROPIC_API_KEY=<YOUR API KEY HERE>" > .env
> python -m computer_use "open TextEdit and type hello world"
> ```
>
> This task will move your real mouse and keyboard; read the
> [caution block](#computer-and-browser-use-with-claude) at the top of this
> file before running it. See [Installation](#installation) for the full setup
> (including the Python 3.11+ requirement).

## Installation

Requires **Python 3.11+**. The `python3` that ships with macOS is 3.9 and
will not work; install a newer interpreter first (for example
`brew install python@3.13`, or the installer from
[python.org](https://www.python.org/downloads/)) and use that to create the
virtual environment below.

```bash
# Replace `python3.13` with whatever 3.11+ interpreter you installed.
python3.13 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Download a headless Chromium for the `browser` tool (one-time, ~150 MB):
python -m playwright install chromium
```

<details>
<summary>Or with <code>uv</code> (faster)</summary>

```bash
uv sync
uv run playwright install chromium
```

The rest of this README shows plain `python ...` commands; with uv installed
you can prefix any of them with `uv run` instead of activating the venv.
</details>

Grant your terminal **Screen Recording** (for screenshots) and
**Accessibility** (for mouse/keyboard control) in System Settings → Privacy &
Security, then fully quit and reopen the terminal so macOS picks up the
change. The agent's preflight will open these panes for you on the first run;
to jump there yourself:

```bash
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
```

<p>
  <img src="docs/images/screen-recording-permissions.jpg" alt="Screen &amp; System Audio Recording pane in System Settings" width="49%">
  <img src="docs/images/accessibility-permissions.jpg" alt="Accessibility pane in System Settings" width="49%">
</p>

On macOS 15 (Sequoia) and later you will also see a separate **"bypass the
system private window picker"** dialog the first time the agent takes a
screenshot, and roughly once a month thereafter. This is a macOS-level
reauthorization for legacy screen-capture APIs and is independent of the
toggle above; click **Allow**.

Set your API key by either exporting it or putting it in a `.env` file at the
repo root (copy `.env.example`):

```bash
cp .env.example .env  # then edit .env
# or: export ANTHROPIC_API_KEY=...
```

## Run the agent

```bash
python -m computer_use "open TextEdit and type hello world"
```

A browser-only example (handy when you do not want the agent touching your
desktop; this disables the `computer` tool entirely):

```bash
CU_ENABLE_COMPUTER_USE_TOOLS=false python -m computer_use \
  "Navigate to https://en.wikipedia.org/wiki/Special:Random three times, \
   take a screenshot each time, then summarize what you saw."
```

This starts an interactive session. After printing the safety banner and
checking macOS permissions, the agent enters a loop:

1. The model's response **streams to your terminal live**: thinking in dim
   gray, assistant text in normal weight, and each tool call as a cyan
   `→ computer({"action": "screenshot"})` line.
2. The loop runs the requested tool against your real machine (takes a
   screenshot, moves the mouse, types, launches an app, etc.) and prints the
   result as a yellow `← computer: [image 105KB]` line.
3. A dim `[usage] in=… cache_read=… out=… | cache_eff=…% | 12.3s` line shows
   token counts and prompt-cache efficiency for that turn.
4. Steps 1-3 repeat until the model stops calling tools, at which point you
   get a `you >` prompt for a follow-up message. Press Ctrl-C at any time to
   interrupt the current turn and drop to that prompt; an empty line exits.

<p align="center">
  <img src="docs/images/hello-world-example.jpg" alt="Terminal output of the agent running the TextEdit hello-world task" width="800">
</p>

Everything the agent sends or receives is also written to
`runs/<timestamp>/` as a JSONL transcript plus the JPEG screenshots, so you
can replay it later in the viewer.

Useful flags: `--model {claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-6,claude-opus-4-7}`,
`--thinking {off,low,medium,high,max}`, `--max-iters N`, `--skip-preflight`.

## View a trajectory

```bash
python -m streamlit run dev_ui/trajectory_viewer/app.py
```

Opens a browser tab with every run listed in the sidebar (newest first). The
main pane renders the selected run as a chat transcript: user messages,
assistant thinking (collapsible), assistant text, each tool call as a code
block, and each tool result as an expanded panel with its text output and
screenshot inline. This is the easiest way to inspect what the model actually
saw and decided after the fact.

<p align="center">
  <img src="docs/images/trajectory-viewer.jpg" alt="Trajectory viewer rendering the hello-world run" width="700">
</p>

## Localization demo

```bash
python -m uvicorn dev_ui.localization_demo.server:app --reload --port 8001
# open http://127.0.0.1:8001
```

A minimal starter for click-style localization, intended to make the
resize/rescale pipeline concrete. Upload any image, type a description ("the
blue Submit button"), and the server: (1) resizes the image with
`target_image_size()` so the API will not resize it again, (2) sends it with a
single `point_at` tool and `tool_choice` forcing, (3) takes the model's
`(x, y)` (which is in the *resized* image's coordinate space), and (4) scales
it back to your original with `x * orig_w / sent_w`. The page shows both
images side by side with a marker on each so you can see the two coordinate
spaces. The whole flow is ~100 lines in `dev_ui/localization_demo/server.py`.

<p align="center">
  <img src="docs/images/localization-demo.jpg" alt="Localization demo locating the Chrome icon in an uploaded screenshot" width="700">
</p>

## Tool panel

```bash
python -m uvicorn dev_ui.tool_panel.server:app --reload
# open http://127.0.0.1:8000
```

A single page for exercising tools by hand without the model in the loop.
Each tool gets a form auto-generated from its `input_schema`; fill in the
fields, set a countdown delay (so you have time to switch focus to the target
window before the action fires), and hit Run. The result pane shows the
returned JSON and any screenshot inline. Clicking on a screenshot fills the
nearest `coordinate` field with the image-pixel position you clicked and
displays the corresponding screen-pixel position, which is the fastest way to
sanity-check coordinate scaling. A red banner appears if Screen Recording or
Accessibility permissions are missing.

<p align="center">
  <img src="docs/images/tool-panel.jpg" alt="Tool panel with per-tool forms on the left and a screenshot result on the right" width="700">
</p>

## Configuration

All tunable knobs live on the `Config` dataclass in `constants.py`. The active
instance is `constants.cfg`; the rest of the codebase reads `cfg.<field>` so
there is one source of truth. You can override any field without editing the
file (later wins):

1. **TOML file**: copy `config.example.toml`, set the fields you want, and
   point `CU_CONFIG` at it.
2. **Per-field env vars**: `CU_<FIELD_NAME>=value`. These layer on top of the
   TOML file.

Both can go in `.env` or your shell. Examples:

```bash
# one-off: turn off browser tools and bump JPEG quality
CU_ENABLE_BROWSER_USE_TOOLS=false CU_JPEG_QUALITY=85 \
  python -m computer_use "open Notes and type hello"

# pin a viewport via env var (string is coerced to a tuple)
CU_BROWSER_VIEWPORT=1280x720 python -m computer_use "..."

# or keep a config.toml and point at it from .env
#   .env:      CU_CONFIG=config.toml
#   config.toml:
#     enable_advisor_tool = true
#     image_prune_strategy = "none"
#     extra_models = ["some-beta-model"]
```

String values are coerced to the declared field type (`"true"`→`True`,
`"80"`→`80`, `"1280x720"`→`(1280, 720)`, `"none"`→`None` for optional ints).

### Feature toggles at a glance

| Field | Default | What it does |
|---|---|---|
| `enable_computer_use_tools` | `true` | `computer`, `computer_batch`, `open_application` (pyautogui screen control). At least one of this or browser must be on. |
| `enable_browser_use_tools` | `true` | `browser`, `browser_batch` (headless Playwright). |
| `enable_editor_tool` | `true` | `editor` (view/create/str_replace/insert) confined to the per-run scratch dir; bash/python share the same workspace. Also adds the TODO.md guidance to the system prompt. |
| `enable_advisor_tool` | `false` | Server-side advisor: the executor model can consult `advisor_model` (Opus by default) mid-generation. See [Advisor tool](#advisor-tool-experimental). |
| `enable_autocompaction` | `true` | Server-side `compact_20260112`: when input tokens cross `autocompaction_trigger_tokens`, the server summarizes older context. Only applied on supported models (Sonnet/Opus). |
| `image_prune_strategy` | `"interval"` | `"none"` keeps every screenshot; `"simple"` keeps the last N (cache-hostile); `"interval"` keeps the prefix stable for `image_prune_interval` turns. See the next section. |
| `print_usage` | `true` | Per-turn `[usage]` line with token counts and cache efficiency. |
| `extra_models` | `()` | Additional model IDs accepted by `--model` (older or beta models not in the built-in enum). |

Everything else on `Config` is a numeric tunable (retry counts, JPEG quality,
viewport size, advisor caps, etc.); see the comments on each field in
`constants.py`.

## Explicit tools vs. the hosted `computer` tool

By default this demo defines every tool explicitly: the `computer` tool's
name, description, and JSON schema are all in
`computer_use/tools/computer.py`, so you can read and edit exactly what the
model sees without any server-side defaults in the way. That is the point of a
reference implementation.

The trade-off is safety classifier coverage. The API runs computer-use-specific
safety classifiers (including prompt-injection detection on screenshot
content) **only** when the request declares the hosted
`{"type": "computer_YYYYMMDD", ...}` tool. With the explicit schema, your
request is on the generic safety path and you must rely on your own
prompt-injection mitigations (the system prompt's instructions, the VM
isolation recommended at the top of this README, and your own monitoring).

If you want those classifiers without giving up the rest of the demo, set
`cfg.use_hosted_computer_tool = True` (or `CU_USE_HOSTED_COMPUTER_TOOL=true`).
The loop will send the hosted `computer` tool param (the server supplies its
description and schema) while keeping `computer_batch`, `browser`, `bash`, and
the rest as explicit tools. Execution stays client-side either way; only the
tool *declaration* changes.

## Providers

`cfg.provider` selects the API surface: `"anthropic"` (default, first-party),
`"vertex"` (Google Cloud, via `AnthropicVertex`), or `"bedrock"` (AWS, via
`AnthropicBedrock`). See `.env.example` for the credentials each one expects.

Vertex and Bedrock impose a request-body size cap that the first-party API
does not. The demo enforces a conservative threshold (18 MB on Vertex, 11 MB
on Bedrock) inside the image pruner: if the serialized message list exceeds
the cap, it force-prunes to `cfg.image_prune_min` images and resets the
interval cycle so subsequent turns start small.

The advisor tool and server-side autocompaction are first-party-only beta
features. Enabling either with `provider != "anthropic"` raises a `ValueError`
at startup that names the conflicting setting; set it to `False` (or switch
provider) to proceed.

## Effective caching and context pruning

A computer-use trajectory accumulates a screenshot on almost every turn, and
each screenshot is roughly 1,500 input tokens. After 30 turns the image
history alone is ~45k tokens that you re-send (and pay for) on every API
call. Two mechanisms in this repo keep that under control:

**Prompt caching.** `loop.py` puts a `cache_control: {"type": "ephemeral"}`
breakpoint on the system prompt and another on the final tool-result block of
the most recent user turn. On the next call the API can serve everything up
to that breakpoint from cache (~10% of the input-token price and noticeably
lower latency). The `[usage]` line printed each turn shows `cache_read` vs
`in` so you can watch the hit rate.

**Image pruning.** Prompt caching only helps if the *prefix* of the request
is byte-identical between calls. The naive way to bound screenshot history
("keep the last N images, replace older ones with a placeholder") changes
which image gets replaced on every single turn once you exceed N, so the
prefix changes every turn and the cache misses every turn.

`cfg.image_prune_strategy = "interval"` (the default, see
`computer_use/formatters.py`) avoids this by letting the kept-image count
*step* from `cfg.image_prune_min` up to
`cfg.image_prune_min + cfg.image_prune_interval - 1` and then drop back. For
`cfg.image_prune_interval` consecutive turns the *same* old images map to the
*same* placeholder text, the prefix stays identical, and the cache keeps
hitting. You pay for one cache write every `cfg.image_prune_interval` turns
instead of one every turn. Set the strategy to
`"none"` to disable pruning entirely, or `"simple"` to see the cache-hostile
behaviour for comparison.

### Pruning vs. server-side context summarization

`cfg.enable_autocompaction` turns on the API's server-side context-management
edit: once total input tokens cross `cfg.autocompaction_trigger_tokens`, the
server runs a separate sub-call that condenses the conversation so far into a
short summary block, and the client drops everything before that block on the
next turn. Pruning and summarization both bound context size, but they trade
off differently:

- **Summarization is the more expensive event.** It is a full extra API turn
  (the entire conversation goes in, a multi-paragraph summary comes out) and
  the next turn starts with a cold cache because the prefix is brand new. By
  comparison, an interval-prune rollover only re-processes the suffix that
  changed and produces no output tokens. Pruning will be much faster and cheaper
  in the short run but may end up being more expensive in the long run (across many
  future turns) image pruning will never delete user/assistant messages and these
  can accumulate over time.
- **Summarization preserves more information.** A summary keeps a textual
  account of what happened; pruning just deletes old screenshots outright.
  That is why `cfg.image_prune_min` matters: keep it high enough that the
  model still has the visual context it needs after a rollover.
- **Pruning is only worth it if it actually prevents a summarization.** Since
  cache reads are roughly an order of magnitude cheaper than uncached input,
  carrying an already-cached screenshot for another turn costs almost nothing,
  while dropping it forces a re-cache of everything that sat after it. The
  saving from dropping an image only pays back the invalidation after that
  image would otherwise have been read on the order of ten more times. On
  short, screenshot-light tasks that never approach the summarization trigger,
  the cheapest setting is therefore "do not prune at all": you pay the small
  cache-read cost of the extra images and avoid both kinds of disruption.
- **Pruning wins on long, screenshot-heavy tasks.** When images alone would
  push you over the trigger, one inexpensive rollover every
  `cfg.image_prune_interval` images is much cheaper than letting the
  conversation hit summarization. That is also where latency diverges most:
  the summarization sub-call's output tokens are slow to generate, so a
  rollover is dramatically faster than a summarization even when their dollar
  costs are close.

The defaults (`image_prune_min=3`, `image_prune_interval=40`,
`autocompaction_trigger_tokens=150_000`) are tuned so that screenshot-heavy
runs prune before they ever reach the summarization trigger, while
screenshot-light runs do neither. If your workload is consistently short, set
`image_prune_strategy="none"` and let summarization act as a rare safety net;
if it is consistently long and visual, lower `image_prune_interval` and keep
summarization for the text that pruning cannot remove.

## Advisor tool (Experimental)

This is not a general recommendation; try it on your own
workload to see whether the quality gain justifies the extra cost and latency.
Set `enable_advisor_tool = true` (via `CU_ENABLE_ADVISOR_TOOL=true` or your
`config.toml`) to let the executor model consult a more capable advisor model
(Opus by default) for strategic guidance mid-generation. This is the one tool
in this repo that is **not** defined in `computer_use/tools/`: it runs
entirely on Anthropic's side and there is no client-side `execute()`. The
loop declares it in the `tools` array, appends an advisor-usage section to
the system prompt (timing guidance plus how to weigh the advice), renders the
advice in dim text when it arrives, and round-trips the result blocks on
subsequent turns. Every `cfg.advisor_reminder_interval` turns without an
advisor call, a short reminder is appended to a tool result.

Related config fields: `advisor_model`, `advisor_max_uses` (per-request cap),
`advisor_max_conversation_uses` (after which the loop drops the advisor and
strips its result blocks from history, since the API rejects orphaned
results), `advisor_caching` (advisor-side prompt caching; breaks even at
roughly three advisor calls per conversation, so the `"5m"` default suits an
agent loop), and `advisor_reminder_interval`. The per-turn `[usage]` line
gains one extra row per advisor call showing the advisor model's tokens,
which are billed separately from the executor's.

## Tests

```bash
python -m pytest
```

## Layout

```
constants.py            Config dataclass + cfg instance, prompts, derived sets
config.example.toml     template for CU_CONFIG overrides
computer_use/
  __main__.py           CLI entrypoint, build_tools(), build_system_prompt()
  loop.py               streaming sampling loop, retry, advisor/compaction wiring
  image.py              target_image_size + JPEG encode + size sanity check
  formatters.py         cache-aware screenshot pruning (interval/simple)
  render.py             terminal output (turn headers, deltas, usage, banners)
  preflight.py          macOS Screen Recording / Accessibility permission check
  trajectory.py         on-disk transcript + images + per-run scratch dir
  tools/
    base.py             Tool ABC + ToolCollection
    result.py           ToolResult + image/document content-block helpers
    computer.py         pyautogui screen control (incl. zoom, key aliasing)
    browser.py          playwright headless chromium
    batch.py            computer_batch / browser_batch
    editor.py           view/create/str_replace/insert in scratch dir
    shell.py            sandboxed bash + python with output cap
    open_app.py         `open -a ...`
sandbox/default.sb      sandbox-exec profile
dev_ui/
  assets/anthropic.css  shared design tokens for all dev UIs below
  trajectory_viewer/    streamlit transcript viewer
  tool_panel/           FastAPI tool-tester (per-tool forms, click-to-coord)
  localization_demo/    label-localization demo (resize/rescale round-trip)
```
