"""
Project-wide configuration.

All user-tunable knobs live on the ``Config`` dataclass below. The active
instance is ``cfg``; consumers do ``from constants import cfg`` and read
``cfg.jpeg_quality`` etc.

Override sources, later wins:
  1. Dataclass defaults
  2. A TOML file (path from ``CU_CONFIG`` env var or ``--config`` on the CLI)
  3. ``CU_<FIELD_NAME>`` environment variables (e.g. ``CU_JPEG_QUALITY=80``)
  4. ``--set FIELD=VALUE`` on the CLI

Types, paths, prompt strings, and derived sets stay as plain module-level
values since they are not the kind of thing you override per-run.
"""

import os
import sys
import tomllib
from dataclasses import dataclass, field, fields, replace
from enum import StrEnum
from pathlib import Path
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
RUNS_DIR = REPO_ROOT / "runs"
SANDBOX_PROFILE = REPO_ROOT / "sandbox" / "default.sb"

# Load .env first so CU_* and ANTHROPIC_* vars are visible below.
load_dotenv(REPO_ROOT / ".env")


class Model(StrEnum):
    HAIKU_4_5 = "claude-haiku-4-5"
    SONNET_4_6 = "claude-sonnet-4-6"
    OPUS_4_6 = "claude-opus-4-6"
    OPUS_4_7 = "claude-opus-4-7"


ThinkingEffort = Literal["off", "low", "medium", "high", "max"]
ImagePruneStrategy = Literal["none", "simple", "interval"]
AdvisorCaching = Literal["off", "5m", "1h"]
Provider = Literal["anthropic", "vertex", "bedrock"]


AUTOCOMPACTION_MIN_TRIGGER = 50_000

# Per-provider serialized-request size cap (MB). Vertex documents ~30 MB but
# trips empirically at ~21 MB of base64 image data; Bedrock at ~13 MB. The
# values below leave headroom for system/tool/text content. None = no cap.
PROVIDER_MAX_MESSAGE_MB: dict[Provider, int | None] = {
    "anthropic": None,
    "vertex": 18,
    "bedrock": 11,
}

# Hosted (Anthropic-defined) computer-use tool. Newer dated revisions exist;
# this is the GA-adjacent one. When cfg.use_hosted_computer_tool is true, the
# computer tool is sent as this server-side type instead of an explicit schema.
HOSTED_COMPUTER_TOOL_TYPE = "computer_20250124"
COMPUTER_USE_BETA = "computer-use-2025-01-24"


@dataclass(frozen=True)
class Config:
    # Which API surface to call. "anthropic" = first-party api.anthropic.com
    # via ANTHROPIC_API_KEY; "vertex" = AnthropicVertex (GOOGLE_CLOUD_PROJECT/
    # GOOGLE_CLOUD_REGION); "bedrock" = AnthropicBedrock (standard AWS creds +
    # AWS_REGION).
    provider: Provider = "anthropic"

    # Send the computer tool as the server-hosted {"type":"computer_YYYYMMDD"}
    # param instead of the explicit schema in computer_use/tools/computer.py.
    # Opting in engages the API's computer-use-specific safety classifiers
    # (including prompt-injection detection on screenshots); the explicit-schema
    # default does not. Only the `computer` tool changes; batch/browser/etc.
    # remain explicit.
    use_hosted_computer_tool: bool = False

    # Additional model IDs accepted by --model (older or beta models not in the
    # Model enum). Supplied via CU_EXTRA_MODELS or the legacy
    # COMPUTER_USE_EXTRA_MODELS env var, comma-separated.
    extra_models: tuple[str, ...] = ()
    # Reasoning effort used when neither --thinking nor a per-model entry in
    # thinking_effort applies.
    default_thinking_effort: ThinkingEffort = "medium"

    # JPEG quality for all screenshots sent to the model. 75 matches the value
    # the desktop app's Swift encoder uses and is a good size/fidelity trade.
    jpeg_quality: int = 75
    # Reject screenshots that encode below this size; catches degenerate
    # captures. The preflight permission check is the primary guard for the
    # all-black case; this is a backstop.
    min_screenshot_bytes: int = 1024
    # Vision-encoder tiling parameters. The API resizes any image whose long
    # edge exceeds max_edge_px *or* whose tile count exceeds max_tokens. We
    # pre-resize so the server's early-return fires and the model sees the
    # exact pixels we send, which is what makes coordinate scaling correct.
    px_per_token: int = 28
    max_edge_px: int = 1568
    max_tokens: int = 1568
    # Headless browser viewport. Chosen so screenshots arrive already within
    # the vision token budget and need no resize.
    browser_viewport: tuple[int, int] = (1456, 819)

    # Maximum model turns per user message before the loop gives up.
    default_max_iters: int = 200
    # Cap on combined stdout+stderr captured from a sandboxed bash/python
    # call. Without a cap, `yes` or similar fills RAM in seconds before the
    # 30s timeout fires; this also bounds what we send back to the model.
    max_shell_output_bytes: int = 64 * 1024
    # Retry recoverable API errors (rate limit, 5xx, overloaded, connection)
    # with exponential backoff. Unrecoverable errors (4xx) re-raise.
    api_retry_max_attempts: int = 5
    api_retry_base_delay: float = 1.0
    # If the model returns an empty assistant message, append a "please
    # continue" nudge and retry the turn this many times before giving up.
    empty_response_retry_max: int = 3
    # Print per-turn token usage and cache efficiency to stdout.
    print_usage: bool = True

    # How to bound the number of screenshots kept in the running message list.
    #   "none"     - keep every image; simplest, but cost grows unbounded.
    #   "simple"   - keep only the last keep_n_most_recent_images; busts the
    #                prompt cache every turn past the cap.
    #   "interval" - stepped scheme that keeps the *same* prefix for
    #                image_prune_interval consecutive turns; see formatters.py.
    image_prune_strategy: ImagePruneStrategy = "interval"
    keep_n_most_recent_images: int = 10
    image_prune_min: int = 3
    image_prune_interval: int = 40

    # Include the computer / computer_batch / open_application tools.
    enable_computer_use_tools: bool = True
    # Include the browser / browser_batch tools.
    enable_browser_use_tools: bool = True
    # Expose an editor tool (view/create/str_replace/insert) confined to the
    # per-run scratch directory; bash and python share the same workspace.
    enable_editor_tool: bool = True

    # Enable Anthropic's server-side advisor tool: the executor model can
    # consult a more capable advisor model mid-generation. Runs entirely
    # server-side; this repo just declares it and renders the result.
    enable_advisor_tool: bool = False
    advisor_model: str = Model.OPUS_4_6.value
    advisor_max_uses: int | None = None  # per-request cap; None = unlimited
    # Conversation-wide cap; once reached the advisor is dropped and its
    # result blocks stripped (the API 400s on orphaned results).
    advisor_max_conversation_uses: int | None = 6
    # Advisor-side prompt caching; break-even is ~3 calls per conversation.
    advisor_caching: AdvisorCaching = "5m"
    # Append a reminder to a tool result every N turns that pass without an
    # advisor call, so the executor doesn't forget the tool exists on long
    # tasks. None disables the nudge.
    advisor_reminder_interval: int | None = 20

    # Enable Anthropic's server-side autocompaction: when input tokens cross
    # the trigger threshold, the server summarizes older context into a
    # compaction block before the model sees it.
    enable_autocompaction: bool = True
    # The API rejects trigger.value < 50000; values below the floor are clamped
    # in __post_init__ with a stderr note.
    autocompaction_trigger_tokens: int = 150_000
    autocompaction_instructions: str | None = None

    # Per-model default reasoning effort. "off" sends thinking={"type":"disabled"};
    # any other value sends output_config={"effort": <value>}. Override at
    # runtime with --thinking on the CLI.
    thinking_effort: dict[str, ThinkingEffort] = field(
        default_factory=lambda: {
            **{m.value: "medium" for m in Model},
            Model.HAIKU_4_5.value: "off",  # haiku-4-5 does not support output_config.effort
            Model.OPUS_4_7.value: "high",
        }
    )

    @classmethod
    def load(cls, toml_path: str | Path | None = None, **overrides: Any) -> "Config":
        """Build a Config from defaults -> toml -> CU_* env vars -> overrides."""
        data: dict[str, Any] = {}
        if toml_path:
            data.update(tomllib.loads(Path(toml_path).read_text()))
        for f in fields(cls):
            env = os.environ.get(f"CU_{f.name.upper()}")
            if env is not None:
                data[f.name] = env
        data.update(overrides)
        coerced = {
            k: _coerce(cls, k, v) for k, v in data.items() if k in {f.name for f in fields(cls)}
        }
        return cls(**coerced)

    def __post_init__(self) -> None:
        if self.autocompaction_trigger_tokens < AUTOCOMPACTION_MIN_TRIGGER:
            print(
                f"[config] autocompaction_trigger_tokens={self.autocompaction_trigger_tokens} "
                f"is below the API floor; clamping to {AUTOCOMPACTION_MIN_TRIGGER}.",
                file=sys.stderr,
            )
            object.__setattr__(self, "autocompaction_trigger_tokens", AUTOCOMPACTION_MIN_TRIGGER)

        if self.provider != "anthropic":
            first_party_only = []

            if self.enable_advisor_tool:
                first_party_only.append("enable_advisor_tool")

            if self.enable_autocompaction:
                first_party_only.append("enable_autocompaction")

            if first_party_only:
                joined = ", ".join(first_party_only)
                raise ValueError(
                    f"{joined} {'is' if len(first_party_only) == 1 else 'are'} only available "
                    f"on the first-party Anthropic API; provider={self.provider!r} does not "
                    f"support {'it' if len(first_party_only) == 1 else 'them'}. "
                    f"Set {joined} to False, or set provider='anthropic'."
                )

    def with_overrides(self, **overrides: Any) -> "Config":
        coerced = {k: _coerce(type(self), k, v) for k, v in overrides.items()}
        return replace(self, **coerced)


_NULLISH = {"", "none", "null"}


def _coerce(cls: type, name: str, value: Any) -> Any:
    """Best-effort coercion of string values (from env/toml/--set) to the
    declared field type. Non-string values (e.g. from TOML) pass through."""
    if not isinstance(value, str):
        return value
    f = next(f for f in fields(cls) if f.name == name)
    t = f.type
    args = get_args(t)
    base = (
        next((a for a in args if a is not type(None)), t)
        if get_origin(t) in {Union, UnionType}
        else t
    )
    s = value.strip()
    if type(None) in args and s.lower() in _NULLISH:
        return None
    if base is bool:
        return s.lower() in {"1", "true", "yes", "on"}
    if base is int:
        return int(s)
    if base is float:
        return float(s)
    if get_origin(base) is tuple:
        elem_args = get_args(base)
        if elem_args and elem_args[0] is int:
            parts = [p.strip() for p in s.replace("x", ",").split(",") if p.strip()]
            return tuple(int(p) for p in parts)
        return tuple(p.strip() for p in s.split(",") if p.strip())
    if get_origin(base) is dict:
        raise ValueError(
            f"Config field {name!r} is dict-typed and cannot be set from a string "
            f"(env var or --set). Use a TOML config file instead."
        )
    return s


def reload(toml_path: str | Path | None = None, **overrides: Any) -> Config:
    """Rebuild ``cfg`` from the given sources. Note that modules which did
    ``from constants import cfg`` hold their own binding; rebind their local
    name too if you need them to pick up the new instance."""
    global cfg
    cfg = Config.load(toml_path, **overrides)
    return cfg


# --- active config ----------------------------------------------------------

cfg = Config.load(os.environ.get("CU_CONFIG"))

# Legacy env-var name kept for compatibility.
if not cfg.extra_models and (legacy := os.environ.get("COMPUTER_USE_EXTRA_MODELS")):
    cfg = cfg.with_overrides(extra_models=legacy)


# --- non-Config module-level values (types, paths, prompts, derived sets) ---

# Models that accept output_config.effort.
EFFORT_SUPPORTED_MODELS = frozenset(
    {Model.SONNET_4_6.value, Model.OPUS_4_6.value, Model.OPUS_4_7.value}
)

# Per the compaction docs; the loop silently disables the edit on other models.
AUTOCOMPACTION_SUPPORTED_MODELS = frozenset(
    {Model.SONNET_4_6.value, Model.OPUS_4_6.value, Model.OPUS_4_7.value}
)

ADVISOR_BETA = "advisor-tool-2026-03-01"
COMPACTION_BETA = "compact-2026-01-12"

SYSTEM_PROMPT = """\
You are operating a macOS computer. You can see the screen via screenshots and
interact via the provided tools.

Guidelines:
* Unless the user is asking for a purely textual response, you should always take
  a screenshot first to understand what the current state of the computer is.
* Coordinates you emit must refer to the most recent screenshot you were shown.
* Prefer the computer_batch and browser_batch tools over individual calls whenever you can confidently
  predict two or more steps ahead, since this is faster and cheaper. Coordinates
  inside a batch all refer to the screenshot taken *before* the batch call.
* Include a screenshot call at the end of your batch tool calls whenever these calls are likely to
  cause a change you need to verify.
* The bash and python tools run inside a restrictive sandbox with no network
  and write access only to a scratch directory.
"""

SCRATCH_PROMPT_ADDENDUM = """\

You have a persistent scratch directory at {scratch_dir} that is shared by the
`editor`, `bash`, and `python` tools. The `editor` tool takes paths relative to
that directory (e.g. `TODO.md`); the `bash` and `python` tools start with it as
their working directory. Files you write there survive across tool calls for
the duration of this run.

Use it to take notes, stash intermediate results, and keep yourself oriented.
For complex tasks (roughly 20 or more actions), create a `TODO.md` checklist up
front with the `editor` tool, tick items off with `str_replace` as you complete
them, and revise the list if you need to replan. Re-read it with
`editor view TODO.md` whenever you are unsure what to do next.
"""

ADVISOR_PROMPT_ADDENDUM = """\

You have access to an `advisor` tool backed by a stronger reviewer model. It
takes NO parameters: when you call advisor(), your entire conversation history
is automatically forwarded. The advisor sees the task, every screenshot, every
tool call you've made, and every result you've seen.

Call advisor BEFORE substantive work: before clicking, typing, opening an
application, or committing to an interpretation of what is on screen. If the
task requires orientation first (taking a screenshot, reading a page,
listing a directory), do that, then call advisor. Orientation is not
substantive work. Clicking, typing, navigating, and declaring an answer are.

Also call advisor:
- When you believe the task is complete. BEFORE this call, make your result
  durable: take a final screenshot showing the end state, save any files. The
  advisor call takes time; if the session ends during it, a durable result
  persists and an unsaved one doesn't.
- When stuck: an action keeps failing, the screen isn't changing as expected,
  results don't match what you predicted.
- When considering a change of approach.

On tasks longer than a few steps, call advisor at least once before
committing to an approach and once before declaring done. On short reactive
tasks where the next click is dictated by the screenshot you just took, you
don't need to keep calling; the advisor adds most of its value on the first
call, before the approach crystallizes.

Give the advice serious weight. If you follow a step and it fails
empirically, or you have direct evidence that contradicts a specific claim
(the screenshot clearly shows X, the file actually contains Y), adapt. A
screenshot that "looks right" is not evidence the advice is wrong; it may be
evidence you aren't checking what the advice is checking.

If you've already observed evidence pointing one way and the advisor points
another: don't silently switch. Surface the conflict in one more advisor
call ("I see X on screen, you suggest Y; which constraint breaks the tie?").
The advisor saw your screenshots but may have underweighted them; a
reconcile call is cheaper than committing to the wrong branch.
"""

ADVISOR_REMINDER = (
    "<reminder>You have not consulted the advisor recently. If you are about "
    "to start a new phase, are stuck, or are planning something irreversible, "
    "consider calling it now.</reminder>"
)

BATCH_REMINDER = (
    "<reminder>You ran a single standalone tool call, you should use the computer_batch"
    " and browser_batch tools extensively for efficiency.</reminder>"
)
BATCH_REMINDER_ACTIONS = {
    "left_click",
    "double_click",
    "triple_click",
    "right_click",
    "middle_click",
    "mouse_move",
    "left_click_drag",
    "scroll",
    "type",
    "key",
    "wait",
    "navigate",
}
