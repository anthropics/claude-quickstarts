"""Daytona variant of the webhook-started self-hosted sandbox.

FastAPI app: receives the session.status_run_started webhook, drains the
environment work queue, and per item creates a Daytona sandbox running
``sandbox_runner.py``. Deploy this anywhere that can serve HTTP and reach the
Daytona API (Fly, Render, a VM, and so on).

The webhook is a wake-up signal only. Each delivery drains *all* pending work
items, so a single arriving webhook recovers any earlier missed deliveries.

Env on the orchestrator host:
  ANTHROPIC_WEBHOOK_SECRET, ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_ENVIRONMENT_KEY,
  DAYTONA_API_KEY, DAYTONA_API_URL
  ANTHROPIC_BASE_URL                 optional, default https://api.anthropic.com
  ALLOW_ENVIRONMENT_KEY_IN_SANDBOX   optional, see _sandbox_credentials()
"""

import os
import re
from collections import OrderedDict
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import anthropic
from anthropic.types.beta import UnwrapWebhookEvent
from daytona_sdk import CreateSandboxParams, Daytona
from fastapi import FastAPI, HTTPException, Request, Response

# The SDK the runner needs inside the sandbox. 0.124.0 is the first release
# whose handle_item() accepts the per-session work secret.
SDK_REQUIREMENT = "anthropic>=0.124.0,<1.0.0"
RUNNER_SRC = (Path(__file__).resolve().parent / "sandbox_runner.py").read_text()

# Anthropic's deliveries are a few hundred bytes. The cap bounds the work an
# unsigned caller can make this process do.
MAX_BODY_BYTES = 1024 * 1024

# These become Daytona labels and sandbox env values, so check their shape
# before use even though they come from Anthropic's API.
SESSION_ID = re.compile(r"^sesn_[A-Za-z0-9]+$")
WORK_ID = re.compile(r"^work_[A-Za-z0-9]+$")

app = FastAPI()
daytona = Daytona()  # reads DAYTONA_API_KEY / DAYTONA_API_URL from env

# Dedupe on the delivery's event id. "Handled" and "in flight" are separate so
# a retry that arrives mid-drain is not acked as done before the outcome is
# known, and an id is only marked handled once the drain returned, so the retry
# of a delivery that threw is processed from scratch. This is one process's
# memory: run several workers and a retry may land on another one. Correctness
# does not depend on it, because claiming a work item is atomic on the server
# and a session's sandbox is get-or-create.
MAX_REMEMBERED_EVENTS = 1000
_handled: "OrderedDict[str, None]" = OrderedDict()
_in_flight: set[str] = set()


def _remember_handled(event_id: str) -> None:
    _handled[event_id] = None
    while len(_handled) > MAX_REMEMBERED_EVENTS:
        _handled.popitem(last=False)


@cache
def _client() -> anthropic.AsyncAnthropic:
    """Shared client for both webhook verification and the work poller.

    Async because ``client.beta.environments.work.poller(...)`` is async-only
    (it lives on ``AsyncWork``). ``unwrap()`` is synchronous even on the async
    client, so do not ``await`` it. The ``whsec_`` secret is passed to
    ``webhook_key`` as-is: the SDK decodes its URL-safe base64 internally.
    """
    return anthropic.AsyncAnthropic(
        auth_token=os.environ["ANTHROPIC_ENVIRONMENT_KEY"],
        webhook_key=os.environ["ANTHROPIC_WEBHOOK_SECRET"],
    )


def _verify_webhook(
    client: anthropic.AsyncAnthropic, raw: bytes, headers: "Mapping[str, str]"
) -> UnwrapWebhookEvent:
    # `unwrap()` verifies via `standardwebhooks` and lets its
    # `WebhookVerificationError` propagate unwrapped. Import it the same lazy
    # way the SDK does (it is the `anthropic[webhooks]` extra).
    from standardwebhooks import WebhookVerificationError

    try:
        return client.beta.webhooks.unwrap(raw.decode(), headers=headers)
    except (WebhookVerificationError, KeyError, UnicodeDecodeError) as e:
        # Log the type only. Other exceptions propagate: they indicate a bug,
        # not a bad delivery.
        print(f"[webhook] signature reject: {type(e).__name__}", flush=True)
        raise HTTPException(status_code=401, detail="signature verification failed") from None


def _sandbox_credentials(secret: str | None, environment_key: str) -> dict[str, str] | None:
    """Pick what the sandbox authenticates with, or None to refuse the item.

    The agent in the sandbox runs arbitrary bash, so it can read its env. The
    work item's per-session ``secret`` carries a token scoped to that one
    session, so that is what goes in. The environment key can claim any
    session's work in this environment, so it only goes in when the operator
    opted in with ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true, which is reasonable
    only when every session in the environment trusts every other.
    """
    if secret:
        return {"ANTHROPIC_WORK_SECRET": secret}
    if os.environ.get("ALLOW_ENVIRONMENT_KEY_IN_SANDBOX", "").lower() == "true":
        return {"ANTHROPIC_ENVIRONMENT_KEY": environment_key}
    return None


def _spawn(
    session_id: str, *, environment_id: str, work_id: str, credentials: dict[str, str]
) -> str:
    """Create a Daytona sandbox and start sandbox_runner.py inside it."""
    sb = daytona.create(
        CreateSandboxParams(
            language="python",
            labels={"session_id": session_id},
            # Same env contract as `ant beta:worker poll --on-work`:
            # sandbox_runner.py reads these to build the client and run the
            # worker's handle_item().
            env_vars={
                "ANTHROPIC_BASE_URL": os.environ.get(
                    "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
                ),
                "ANTHROPIC_SESSION_ID": session_id,
                "ANTHROPIC_ENVIRONMENT_ID": environment_id,
                "ANTHROPIC_WORK_ID": work_id,
                **credentials,
            },
        )
    )
    sb.fs.upload_file("/root/sandbox_runner.py", RUNNER_SRC.encode())
    # Both command strings are constants. Nothing from the webhook or the work
    # item is ever interpolated into a shell command.
    sb.process.exec(f"pip install -q '{SDK_REQUIREMENT}'", timeout=180)
    sb.process.exec("nohup python /root/sandbox_runner.py >/tmp/runner.log 2>&1 &")
    return sb.id


def _find_live(session_id: str) -> str | None:
    for sb in daytona.list(labels={"session_id": session_id}):
        if sb.state == "started":
            return sb.id
    return None


async def _drain_work(client: anthropic.AsyncAnthropic, environment_id: str) -> list[dict]:
    """Drain the queue via the SDK poller, spawning a sandbox per work item.

    ``client.beta.environments.work.poller`` builds a scoped sub-client from the
    environment key and yields each ack'd work item. It is async-only.
    ``drain=True`` returns when the queue is empty (the webhook handler must
    respond, not loop forever). ``auto_stop=False`` because each item is handed
    off to a detached Daytona sandbox that owns ``/stop``: the poller must not
    terminate the lease out from under it.
    """
    environment_key = os.environ["ANTHROPIC_ENVIRONMENT_KEY"]
    spawned: list[dict] = []
    async for work in client.beta.environments.work.poller(
        environment_id=environment_id,
        environment_key=environment_key,
        # None -> omit -> non-blocking. The API rejects block_ms=0.
        block_ms=None,
        reclaim_older_than_ms=2000,
        drain=True,
        auto_stop=False,
    ):
        if work.data.type != "session":
            print(f"[webhook] skipping work={work.id} type={work.data.type}", flush=True)
            continue
        session_id = work.data.id
        # The poll is keyed by this environment's id and key, so an item for
        # another environment should be impossible. Check anyway: the cost of
        # being wrong is running someone else's session on this account.
        if (
            work.environment_id != environment_id
            or not SESSION_ID.match(session_id)
            or not WORK_ID.match(work.id)
        ):
            print(
                "[webhook] skipping a work item that is not for this environment or has a malformed id",
                flush=True,
            )
            continue
        try:
            existing = _find_live(session_id)
            if existing is not None:
                print(
                    f"[webhook] work={work.id} session={session_id} sandbox={existing} (live)",
                    flush=True,
                )
                spawned.append(
                    {
                        "session_id": session_id,
                        "work_id": work.id,
                        "sandbox_id": existing,
                        "created": False,
                    }
                )
                continue

            credentials = _sandbox_credentials(getattr(work, "secret", None), environment_key)
            if credentials is None:
                # The poller already ack'd the item. Force-stop it so it does
                # not sit on its lease and come back on every webhook.
                await client.beta.environments.work.stop(
                    work.id, environment_id=environment_id, force=True
                )
                print(
                    f"[webhook] REFUSED work={work.id} session={session_id}: the work item carried no "
                    "per-session secret, and this deploy does not put the environment key in sandboxes. "
                    "Set ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true only if every session in this environment "
                    "trusts every other.",
                    flush=True,
                )
                spawned.append(
                    {"session_id": session_id, "work_id": work.id, "error": "no_session_secret"}
                )
                continue
            if "ANTHROPIC_ENVIRONMENT_KEY" in credentials:
                print(
                    f"[webhook] session={session_id}: the sandbox receives the ENVIRONMENT KEY (opt-in fallback)",
                    flush=True,
                )

            sandbox_id = _spawn(
                session_id, environment_id=environment_id, work_id=work.id, credentials=credentials
            )
            print(
                f"[webhook] work={work.id} session={session_id} sandbox={sandbox_id} (created)",
                flush=True,
            )
            spawned.append(
                {
                    "session_id": session_id,
                    "work_id": work.id,
                    "sandbox_id": sandbox_id,
                    "created": True,
                }
            )
        except Exception as e:  # noqa: BLE001 - one bad item must not stop the drain
            # SDK and Daytona exceptions can embed request context, so log the
            # type only. Skip and keep draining: the lease lapses and the next
            # webhook reclaims the item.
            detail = type(e).__name__
            print(f"[webhook] FAILED work={work.id} session={session_id}: {detail}", flush=True)
            spawned.append({"session_id": session_id, "work_id": work.id, "error": detail})
    return spawned


@app.post("/")
async def webhook(request: Request, response: Response) -> dict:
    declared = request.headers.get("content-length", "0")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    client = _client()
    event = _verify_webhook(client, raw, request.headers)

    if event.data.type != "session.status_run_started":
        return {"status": "ignored", "event_type": event.data.type}

    if event.id in _handled:
        return {"status": "duplicate"}
    if event.id in _in_flight:
        response.status_code = 503
        return {"status": "in_flight"}
    _in_flight.add(event.id)
    try:
        spawned = await _drain_work(client, os.environ["ANTHROPIC_ENVIRONMENT_ID"])
        # Only a drain that returned marks the id handled. If it raised, the
        # response is a 500 and Anthropic's retry is processed from scratch.
        _remember_handled(event.id)
    finally:
        _in_flight.discard(event.id)
    return {"status": "ok", "event_type": event.data.type, "spawned": spawned}
