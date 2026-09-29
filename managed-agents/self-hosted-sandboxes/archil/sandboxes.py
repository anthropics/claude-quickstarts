"""Archil persistent sandboxes for this demo, through the `archil` SDK.

A sandbox is a Linux microVM started from any public OCI image:
https://docs.archil.com/compute/persistent-sandboxes. The SDK reads the
account API key and region from ARCHIL_API_KEY and ARCHIL_REGION. Commands
go over the sandbox's process API: the SDK opens a websocket to the
sandbox, starts the process, and streams stdout and stderr back while it
runs. The mount token is a separate, disk-scoped credential used only by
`archil mount` inside the sandbox.
"""

import sys
import time

import archil

# Every sandbox starts from a stock image and installs the two CLIs it needs:
# `ant` (serves the agent's tools) and `archil` (mounts the disk). Sandboxes
# are ARM, so `dpkg --print-architecture` picks the matching `ant` build.
ANT_VERSION = "1.30.0"
BOOTSTRAP = f"""
set -e
apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates curl git ripgrep unzip sqlite3 >/dev/null
curl -fsSL https://github.com/anthropics/anthropic-cli/releases/download/v{ANT_VERSION}/ant_{ANT_VERSION}_linux_$(dpkg --print-architecture).tar.gz | tar -xz -C /usr/local/bin ant
curl -fsSL https://archil.com/install | ARCHIL_CLIENT_VERSION=0.8.31-1787597449 sh >/dev/null
git config --system core.pager cat
"""


def create(name: str) -> archil.Sandbox:
    """Create a sandbox from the stock image and block until it is running."""
    return archil.create_sandbox(
        name=name,
        base_image="python:3.13",
        vcpu_count=2,
        mem_size_mib=4096,
        max_ttl_seconds=28800,  # the maximum, 8 hours; the sandbox stops itself after that
    )


def run(
    sandbox: archil.Sandbox,
    command: str,
    env: dict[str, str] | None = None,
    stream: bool = True,
) -> str:
    """Run a shell command to completion and return its stdout; raise on failure.

    Output arrives as the command writes it. With `stream` on, both stdout
    and stderr are echoed here, so a long command shows progress live. A
    dropped connection does not stop the process: reattach at the last byte
    seen and keep waiting.
    """
    output = {"stdout": bytearray(), "stderr": bytearray()}

    def on_output(chunk: archil.SandboxProcessOutput) -> None:
        output[chunk.stream] += chunk.data
        if stream:
            sys.stdout.buffer.write(chunk.data)
            sys.stdout.flush()

    process = sandbox.processes.start(
        command, env=env or {}, on_output=on_output, collect_output=False
    )
    for attempt in range(10):
        try:
            result = process.wait()
            break
        except ConnectionError:
            time.sleep(2 * attempt)
            process = sandbox.processes.connect(
                process.id,
                offset=process.cursor,
                on_output=on_output,
                collect_output=False,
            )
    else:
        raise ConnectionError(f"lost the process connection 10 times: {command[:80]}")
    stdout, stderr = (output[s].decode(errors="replace") for s in ("stdout", "stderr"))
    if result.status != "completed" or result.exit_code != 0:
        raise RuntimeError(
            f"{result.status} (exit {result.exit_code}): {command[:80]}\n{stderr[-2000:]}"
        )
    return stdout


def destroy(sandbox: archil.Sandbox) -> None:
    """Stop the sandbox (SIGTERM to every process, VM shut down), then delete it.

    Only a stopped, exited, or failed sandbox can be deleted, and the status
    can lag the stop call by a moment.
    """
    sandbox = sandbox.stop()
    while sandbox.status not in ("stopped", "exited", "failed"):
        time.sleep(1)
        sandbox = sandbox.refresh()
    sandbox.delete()
