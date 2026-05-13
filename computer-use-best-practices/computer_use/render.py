"""
Terminal rendering for the agent loop.

Kept dependency-free: just ANSI escape codes and stdout. Colors degrade
gracefully on non-TTYs (the codes are still emitted, but most log viewers
handle them).
"""

import json
import sys

from .tools.result import ToolResult

DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

_TRUNCATE_AT = 500


def _truncate(s: str, n: int = _TRUNCATE_AT) -> str:
    return s if len(s) <= n else s[:n] + f"… ({len(s) - n} more chars)"


SAFETY_BANNER = f"""\
{RED}┌─────────────────────────────────────────────────────────────────────────────┐
│  REFERENCE IMPLEMENTATION FOR INSTRUCTIONAL PURPOSES ONLY                   │
│                                                                             │
│  This agent controls your real mouse, keyboard, and screen. There are NO    │
│  safeguards against it screenshotting sensitive information and sending it  │
│  to the API, deleting or overwriting data, or operating any application.    │
│                                                                             │
│  Running this outside a macOS VM is STRONGLY DISCOURAGED. See the README    │
│  for VM options (UTM, Parallels).                                           │
│                                                                             │
│  For computer use with safeguards and user control, use Cowork,             │
│  Anthropic's desktop application: https://claude.ai/downloads               │
└─────────────────────────────────────────────────────────────────────────────┘{RESET}
"""


def safety_banner() -> None:
    print(SAFETY_BANNER)


def turn_header(i: int) -> None:
    print(f"\n{DIM}─── turn {i} {'─' * 50}{RESET}")


def thinking_delta(text: str) -> None:
    sys.stdout.write(f"{DIM}{text}{RESET}")
    sys.stdout.flush()


def text_delta(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def block_end() -> None:
    """Newline after a streamed text/thinking block finishes."""
    print()


def tool_call(name: str, tool_input: object) -> None:
    args = json.dumps(tool_input) if isinstance(tool_input, (dict, list)) else repr(tool_input)
    print(f"{CYAN}→ {name}({_truncate(args, 200)}){RESET}")


def tool_result(name: str, res: ToolResult) -> None:
    if res.is_error:
        print(f"{RED}← {name} error: {_truncate(res.error or '')}{RESET}")
        return
    parts: list[str] = []
    if res.output:
        parts.append(_truncate(res.output))
    if res.base64_image:
        parts.append(f"[image {len(res.base64_image) * 3 // 4 // 1024}KB]")
    body = " ".join(parts) if parts else "(ok)"
    print(f"{YELLOW}← {name}: {body}{RESET}")


def usage(line: str) -> None:
    print(f"{DIM}{line}{RESET}")


def advisor_call(advisor_model: str) -> None:
    print(f"{DIM}→ advisor (consulting {advisor_model}…){RESET}")


def context_edits_applied(edits: list[object]) -> None:
    for e in edits:
        kind = getattr(e, "type", None) or (e.get("type") if isinstance(e, dict) else "?")
        print(f"{DIM}[context] applied: {kind}{RESET}")


def advisor_result(content: dict[str, str]) -> None:
    kind = content.get("type")
    if kind == "advisor_result":
        print(f"{DIM}← advisor: {_truncate(content.get('text', ''), 400)}{RESET}")
    elif kind == "advisor_redacted_result":
        print(f"{DIM}← advisor: [redacted advice]{RESET}")
    elif kind == "advisor_tool_result_error":
        print(f"{RED}← advisor error: {content.get('error_code', 'unknown')}{RESET}")


def retry(attempt: int, total: int, exc: Exception, delay: float) -> None:
    print(
        f"{DIM}[retry {attempt}/{total}] {type(exc).__name__}: {exc}; sleeping {delay:.1f}s{RESET}"
    )


def interrupted() -> None:
    print(f"\n{YELLOW}[interrupted]{RESET}")


def prompt_user() -> str | None:
    """Read a follow-up message. Returns None on EOF or empty input."""
    try:
        line = input(f"\n{CYAN}you >{RESET} ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return line or None
