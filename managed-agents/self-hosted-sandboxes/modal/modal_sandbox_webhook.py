"""Modal app: Anthropic session webhook → drain environment work queue → start a Sandbox per item.

The webhook is a wake-up signal only. Each delivery drains *all* pending work
items (not only the one that triggered it), so a single arriving webhook
recovers any earlier missed deliveries.

Flow per webhook delivery:
  1. Verify the Standard Webhooks signature via ``client.beta.webhooks.unwrap()``.
  2. Only act on data.type == "session.status_run_started".
  3. ``client.beta.environments.work.poller(drain=True, auto_stop=False)``
     polls until empty. Each yielded ``work`` item has already been ack'd.
     Get-or-create a Modal Sandbox keyed on the work item's session_id running
     sandbox_runner.py. ``auto_stop=False`` because the sandbox owns ``/stop``,
     not the webhook: see sandbox_runner.py.

Secrets (modal secret create self-hosted-sandboxes-secrets ...):
  ANTHROPIC_WEBHOOK_SECRET   - issued by Anthropic at webhook registration
  ANTHROPIC_ENVIRONMENT_ID   - the self-hosted environment id
  ANTHROPIC_ENVIRONMENT_KEY  - the environment key: Bearer auth for the work
                               poll/ack/stop. It stays in this function.
  ANTHROPIC_BASE_URL         - optional, default https://api.anthropic.com
  ALLOW_ENVIRONMENT_KEY_IN_SANDBOX - optional, see _sandbox_credentials()

Deploy:
  modal secret create self-hosted-sandboxes-secrets \
      ANTHROPIC_WEBHOOK_SECRET=placeholder \
      ANTHROPIC_ENVIRONMENT_KEY=placeholder \
      ANTHROPIC_ENVIRONMENT_ID=env_01...
  modal deploy modal_sandbox_webhook.py
  # register the printed URL with Anthropic, then re-create the secret with --force.
"""

import os
import re
from collections import OrderedDict
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import anthropic
from anthropic.types.beta import UnwrapWebhookEvent
from fastapi import HTTPException, Request, Response

import modal

APP_NAME = "self-hosted-sandboxes"
SECRET_NAME = "self-hosted-sandboxes-secrets"

# 0.124.0 is the first release whose handle_item() accepts the per-session
# work secret. Pinned to a range so a rebuild cannot pick up a 1.x.
SDK_REQUIREMENT = "anthropic>=0.124.0,<1.0.0"
RUNNER_PATH = "/root/sandbox_runner.py"

# Anthropic's deliveries are a few hundred bytes. The cap bounds the work an
# unsigned caller can make this function do.
MAX_BODY_BYTES = 1024 * 1024

# These become Modal sandbox and volume names and sandbox env values, so check
# their shape before use even though they come from Anthropic's API.
SESSION_ID = re.compile(r"^sesn_[A-Za-z0-9]+$")
WORK_ID = re.compile(r"^work_[A-Za-z0-9]+$")

app = modal.App(APP_NAME)
secrets = modal.Secret.from_name(SECRET_NAME)

_runner_src = Path(__file__).parent / "sandbox_runner.py"

# `standardwebhooks` backs `client.beta.webhooks.unwrap()` (the SDK's
# `[webhooks]` extra). Only the webhook image needs it: sandbox_runner.py
# never sees raw deliveries.
webhook_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]", "standardwebhooks", SDK_REQUIREMENT)
    .add_local_file(_runner_src, RUNNER_PATH, copy=True)
)

sandbox_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(SDK_REQUIREMENT)
    .add_local_file(_runner_src, RUNNER_PATH, copy=True)
)

# Best-effort dedupe on the delivery's event id. This is one container's
# memory: Modal may serve a retry from another container that has never seen
# the id. Correctness does not depend on it, because claiming a work item is
# atomic on the server and a session's sandbox is get-or-create. "Handled" and
# "in flight" are separate so a retry that arrives mid-drain is not acked as
# done before the outcome is known.
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

    Lazy because ``modal deploy`` imports this module locally, where the
    secret env vars are not set. Constructing at module scope breaks deploy.
    """
    return anthropic.AsyncAnthropic(
        auth_token=os.environ["ANTHROPIC_ENVIRONMENT_KEY"],
        webhook_key=os.environ["ANTHROPIC_WEBHOOK_SECRET"],
    )


def _verify_webhook(
    client: anthropic.AsyncAnthropic, raw: bytes, headers: "Mapping[str, str]"
) -> UnwrapWebhookEvent:
    """``unwrap()`` is synchronous even on the async client, so do not ``await``
    it. The ``whsec_`` secret is passed to ``webhook_key`` as-is: the SDK
    decodes its URL-safe base64 internally."""
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


async def _find_live_sandbox(key: str) -> modal.Sandbox | None:
    try:
        sb = await modal.Sandbox.from_name.aio(APP_NAME, name=key)
    except modal.exception.NotFoundError:
        return None
    return sb if await sb.poll.aio() is None else None


async def _create_sandbox(
    session_id: str,
    *,
    environment_id: str,
    work_id: str,
    credentials: dict[str, str],
    sandbox_timeout: int,
) -> modal.Sandbox:
    sb_app = await modal.App.lookup.aio(APP_NAME, create_if_missing=True)
    # Persist the whole workdir, not only outputs/, so the agent's working
    # tree and downloaded skills survive across sandbox lifetimes for the
    # same session. Mounted at /workspace so {workdir}/skills/<name>/ matches
    # what the agent's prompt and the other variants use.
    session_vol = modal.Volume.from_name(f"shs-session-{session_id}", create_if_missing=True)
    sb = await modal.Sandbox.create.aio(
        "python",
        RUNNER_PATH,
        app=sb_app,
        name=session_id,
        image=sandbox_image,
        timeout=sandbox_timeout,
        volumes={"/workspace": session_vol},
        # Same env contract as `ant beta:worker poll --on-work`:
        # sandbox_runner.py reads these to build the client and run
        # EnvironmentWorker.handle_item().
        env={
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "ANTHROPIC_SESSION_ID": session_id,
            "ANTHROPIC_ENVIRONMENT_ID": environment_id,
            "ANTHROPIC_WORK_ID": work_id,
            **credentials,
        },
    )
    await sb.set_tags.aio({"session_id": session_id})
    return sb


async def _start_sandbox(
    *, session_id: str, work_id: str, environment_id: str, credentials: dict[str, str]
) -> dict:
    """Create a Modal Sandbox for one already-ack'd work item.

    Raises on Modal API errors. The caller treats any raise as "skip this item
    and keep draining".
    """
    sb = await _create_sandbox(
        session_id,
        environment_id=environment_id,
        work_id=work_id,
        credentials=credentials,
        sandbox_timeout=3600,
    )
    print(
        f"[webhook] work={work_id} session={session_id} sandbox={sb.object_id} (created)",
        flush=True,
    )
    return {
        "session_id": session_id,
        "work_id": work_id,
        "sandbox_id": sb.object_id,
        "created": True,
    }


async def _drain_work(client: anthropic.AsyncAnthropic, environment_id: str) -> list[dict]:
    """Drain the queue via the SDK poller, spawning a sandbox per work item.

    ``drain=True`` returns when the queue is empty (the webhook handler must
    respond, not loop forever). ``auto_stop=False`` because each item is
    handed off to a detached Modal Sandbox that owns ``/stop``: the poller
    must not terminate the lease out from under it. Items the poller already
    ack'd that then fail to spawn are logged and skipped. They reclaim on the
    next webhook (``reclaim_older_than_ms``) once the lease lapses.
    """
    environment_key = os.environ["ANTHROPIC_ENVIRONMENT_KEY"]
    spawned: list[dict] = []
    failed: list[dict] = []
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
            # A live sandbox for this session is already serving it. Leave it
            # alone, whatever this follow-up item carries.
            existing = await _find_live_sandbox(session_id)
            if existing is not None:
                print(
                    f"[webhook] work={work.id} session={session_id} sandbox={existing.object_id} (live)",
                    flush=True,
                )
                spawned.append(
                    {
                        "session_id": session_id,
                        "work_id": work.id,
                        "sandbox_id": existing.object_id,
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
                    "Set ALLOW_ENVIRONMENT_KEY_IN_SANDBOX=true in the Modal secret only if every session "
                    "in this environment trusts every other.",
                    flush=True,
                )
                failed.append(
                    {"work_id": work.id, "session_id": session_id, "error": "no_session_secret"}
                )
                continue
            if "ANTHROPIC_ENVIRONMENT_KEY" in credentials:
                print(
                    f"[webhook] session={session_id}: the sandbox receives the ENVIRONMENT KEY (opt-in fallback)",
                    flush=True,
                )
            spawned.append(
                await _start_sandbox(
                    session_id=session_id,
                    work_id=work.id,
                    environment_id=environment_id,
                    credentials=credentials,
                )
            )
        except Exception as e:  # noqa: BLE001 - one bad item must not stop the drain
            # SDK, httpx, and Modal exceptions can embed request context, so
            # log the type only, never the message.
            detail = type(e).__name__
            print(f"[webhook] FAILED work={work.id} session={session_id}: {detail}", flush=True)
            failed.append({"work_id": work.id, "session_id": session_id, "error": detail})
    if failed:
        print(f"[webhook] drain finished: spawned={len(spawned)} failed={len(failed)}", flush=True)
    return spawned + failed


@app.function(image=webhook_image, secrets=[secrets])
@modal.fastapi_endpoint(method="POST")
async def webhook(request: Request, response: Response) -> dict:
    declared = request.headers.get("content-length", "0")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")

    client = _client()
    event = _verify_webhook(client, raw, request.headers)

    print(f"[webhook] event={event.data.type} session_id={event.data.id}", flush=True)
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
