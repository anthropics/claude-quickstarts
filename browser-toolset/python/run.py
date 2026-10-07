"""Run Claude's browser toolset from the command line, with the example driver.

Usage:

    python run.py "Open example.com and tell me the heading"

It builds the example driver, hands it to the tool runner, and prints each of the model's messages until the model
finishes. It uses only the SDK's abstract toolset, so any other driver swaps in the same way.

Requires: `pip install -r requirements.txt`, `cdp_browser.py` next to this file, a Chromium binary (`CHROME_PATH`, or
`google-chrome` / `chromium` on `PATH`) and an API key in `ANTHROPIC_API_KEY`.

Read "Running a browser toolset safely" in the SDK guide (browser-toolset.md) before running this against anything
other than a throwaway browser profile inside a sandbox, because the pages the model visits affect what it does next.

Environment: `ALLOWED_DOMAINS` (comma-separated hosts the model may visit, subdomains included; default
`example.com,iana.org`), `HEADLESS=0` to watch the browser, `CHROME_PATH` for a specific Chromium binary, `MODEL` to
pick the model.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import urlsplit

from anthropic import Anthropic, AnthropicError
from anthropic.tools import ToolError
from anthropic.tools.browser import BetaURLContext, BetaURLPolicy

from cdp_browser import CdpBrowser


def env_list(name: str, default: str) -> list[str]:
    """A comma-separated environment variable as a list, blanks dropped."""
    return [item.strip().lower() for item in os.environ.get(name, default).split(",") if item.strip()]


def example_policy(allowed_hosts: list[str]) -> BetaURLPolicy:
    """An example policy, not a production one: http(s) pages on the allowed hosts or their subdomains, and the empty
    tab."""

    hosts = [entry.strip().lower().rstrip(".") for entry in allowed_hosts]
    hosts = [host for host in hosts if host]

    def policy(_context: BetaURLContext, url: str) -> None:
        if url.lower() == "about:blank":
            return
        # Judge the address the browser will open: a missing scheme becomes https://, and a backslash reads as a slash.
        with_scheme = url if re.match(r"[a-z][a-z0-9+.-]*:", url, re.I) else f"https://{url}"
        try:
            parts = urlsplit(with_scheme.replace("\\", "/"))
        except ValueError:
            raise ToolError(f"blocked: {url} could not be parsed") from None
        host = (parts.hostname or "").lower()
        on_allowed_host = any(host == allowed or host.endswith("." + allowed) for allowed in hosts)
        if parts.scheme not in ("http", "https") or not on_allowed_host:
            raise ToolError(f"blocked: {url} is not on an allowed host")

    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the browser toolset on a task with the example driver.")
    parser.add_argument("task", nargs="*", help="what the model should do (default: read example.com's heading)")
    args = parser.parse_args()
    task = " ".join(args.task) or "Open example.com and tell me the page heading."
    try:
        client = Anthropic()
        browser = CdpBrowser(
            headless=os.environ.get("HEADLESS", "1") != "0",
            url_policy=example_policy(env_list("ALLOWED_DOMAINS", "example.com,iana.org")),
        )
    except (AnthropicError, OSError, RuntimeError, ToolError) as error:  # no SDK profile, or no usable Chromium
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    # This script closes the browser, not the tool runner.
    # The `with` closes it when the loop ends, fails or exits early.
    with browser:
        runner = client.beta.messages.tool_runner(
            model=os.environ.get("MODEL", "claude-sonnet-5-5"),
            max_tokens=1024,
            tools=[browser],
            messages=[{"role": "user", "content": task}],
        )
        for message in runner:
            print(message)


if __name__ == "__main__":
    main()
