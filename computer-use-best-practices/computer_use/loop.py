"""
The agent loop.

Streams `client.messages.stream` against the configured provider (Anthropic,
Vertex, or Bedrock). Tools are explicit by default; with
`cfg.use_hosted_computer_tool` the `computer` tool is sent as the
server-hosted type instead. Renders thinking/text/tool-calls
to the terminal as they arrive, adds prompt caching on the system block and the
trailing user turn, bounds the screenshot history (cache-aware), retries
recoverable API errors with backoff, recovers from empty responses, and nudges
the model toward batch tools when it issues a lone single-action call.
"""

import random
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

import anthropic
from anthropic.lib.bedrock import AnthropicBedrock
from anthropic.lib.vertex import AnthropicVertex
from anthropic.types import (
    CacheControlEphemeralParam,
    MessageParam,
    TextBlockParam,
    ToolResultBlockParam,
)
from anthropic.types.beta import BetaAdvisorTool20260301Param, BetaCompact20260112EditParam

from constants import (
    ADVISOR_BETA,
    ADVISOR_REMINDER,
    AUTOCOMPACTION_SUPPORTED_MODELS,
    BATCH_REMINDER,
    BATCH_REMINDER_ACTIONS,
    COMPACTION_BETA,
    COMPUTER_USE_BETA,
    EFFORT_SUPPORTED_MODELS,
    PROVIDER_MAX_MESSAGE_MB,
    SYSTEM_PROMPT,
    Provider,
    ThinkingEffort,
    cfg,
)

from . import render
from .formatters import StripImagesAtIntervals, StripOldestImages
from .tools import ToolCollection
from .trajectory import Trajectory

T = TypeVar("T")


_EPHEMERAL: CacheControlEphemeralParam = {"type": "ephemeral"}


_CACHEABLE_BLOCK_TYPES = {"tool_result", "compaction"}
# The API allows 4 cache breakpoints; one is on the system prompt, so spend up
# to 3 in the body. A small ladder means that on the rare turn where the prefix
# shifts (e.g. the image-prune interval rolls over) an earlier breakpoint can
# still hit.
_MAX_BODY_CACHE_BREAKPOINTS = 3


def _set_trailing_cache_control(messages: list[MessageParam]) -> None:
    """Put cache breakpoints on the last few cacheable blocks (`tool_result` in
    a user turn, or `compaction` in an assistant turn). Clears any breakpoints
    set by the previous iteration first."""
    cacheable: list[Any] = []
    for msg in messages:
        content = msg["content"]
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") in _CACHEABLE_BLOCK_TYPES:
                block.pop("cache_control", None)
                cacheable.append(block)

    for block in cacheable[-_MAX_BODY_CACHE_BREAKPOINTS:]:
        block["cache_control"] = _EPHEMERAL


_UNRECOVERABLE = (
    anthropic.BadRequestError,
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.UnprocessableEntityError,
)


def _is_recoverable(e: Exception) -> bool:
    if isinstance(e, _UNRECOVERABLE):
        return False
    if isinstance(e, (anthropic.RateLimitError, anthropic.APIConnectionError)):
        return True
    if isinstance(e, anthropic.APIStatusError) and 500 <= e.status_code < 600:
        return True
    return "overloaded" in str(e).lower()


def _call_with_retry(fn: Callable[[], T]) -> T:
    """Exponential-backoff retry for recoverable API errors."""
    for attempt in range(cfg.api_retry_max_attempts):
        try:
            return fn()
        except Exception as e:
            if not _is_recoverable(e) or attempt + 1 >= cfg.api_retry_max_attempts:
                raise
            delay = cfg.api_retry_base_delay * (2**attempt) + random.uniform(0, 1)
            render.retry(attempt + 1, cfg.api_retry_max_attempts, e, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


def _format_usage(usage: Any, elapsed: float) -> str:
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    eff = cr / (cr + inp) if (cr + inp) else 0.0
    lines = [
        f"[usage] in={inp} cache_read={cr} cache_write={cw} out={out} "
        f"| cache_eff={eff:.0%} | {elapsed:.1f}s"
    ]
    for it in getattr(usage, "iterations", None) or []:
        if getattr(it, "type", None) == "advisor_message":
            lines.append(
                f"[usage]   advisor({getattr(it, 'model', '?')}) "
                f"in={getattr(it, 'input_tokens', 0)} "
                f"cache_read={getattr(it, 'cache_read_input_tokens', 0)} "
                f"out={getattr(it, 'output_tokens', 0)}"
            )
    return "\n".join(lines)


def _truncate_to_last_compaction(messages: list[MessageParam]) -> None:
    """Drop everything before the most recent assistant message that contains a
    `compaction` block. The server does this drop anyway when it sees the
    compaction block, so this is purely an optimization: it stops us re-sending
    bytes the server will ignore and, more importantly, makes the image-pruner
    operate on the same slice the model will actually see."""
    for i in range(len(messages) - 1, -1, -1):
        content = messages[i].get("content")
        if messages[i].get("role") != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if btype == "compaction":
                del messages[:i]
                return


def _autocompaction_edit() -> BetaCompact20260112EditParam:
    edit: BetaCompact20260112EditParam = {
        "type": "compact_20260112",
        "trigger": {"type": "input_tokens", "value": cfg.autocompaction_trigger_tokens},
    }
    if cfg.autocompaction_instructions:
        edit["instructions"] = cfg.autocompaction_instructions
    return edit


def _advisor_tool_param() -> BetaAdvisorTool20260301Param:
    param: BetaAdvisorTool20260301Param = {
        "type": "advisor_20260301",
        "name": "advisor",
        "model": cfg.advisor_model,
    }
    if cfg.advisor_max_uses is not None:
        param["max_uses"] = cfg.advisor_max_uses
    if cfg.advisor_caching != "off":
        param["caching"] = {"type": "ephemeral", "ttl": cfg.advisor_caching}
    return param


def _strip_advisor(messages: list[MessageParam]) -> None:
    """Remove advisor server_tool_use and advisor_tool_result blocks in place.
    Required when dropping the advisor from `tools` mid-conversation; the API
    400s if advisor_tool_result blocks remain without the tool definition."""
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        msg["content"] = [
            b
            for b in content
            if getattr(b, "type", None) not in {"server_tool_use", "advisor_tool_result"}
            and not (
                isinstance(b, dict) and b.get("type") in {"server_tool_use", "advisor_tool_result"}
            )
        ]


def _is_empty_response(content: list[Any]) -> bool:
    if not content:
        return True
    return len(content) == 1 and getattr(content[0], "text", None) == ""


def _effort_kwargs(model: str, effort: ThinkingEffort) -> dict[str, Any]:
    """Translate an effort level into messages.stream() kwargs. Raises if the
    model does not support output_config.effort and effort is not "off"."""
    if effort == "off":
        return {"thinking": {"type": "disabled"}}

    if model not in EFFORT_SUPPORTED_MODELS:
        raise ValueError(
            f"Model {model!r} does not support output_config.effort; "
            f"use --thinking off (or pick one of {sorted(EFFORT_SUPPORTED_MODELS)})."
        )

    return {"output_config": {"effort": effort}}


AnthropicClient = anthropic.Anthropic | AnthropicVertex | AnthropicBedrock


def _make_client(provider: Provider) -> AnthropicClient:
    if provider == "vertex":
        return AnthropicVertex()

    if provider == "bedrock":
        return AnthropicBedrock()

    return anthropic.Anthropic()


def _make_image_pruner(max_message_mb: float | None = None) -> Callable[[list[MessageParam]], None]:
    if cfg.image_prune_strategy == "none":
        return lambda _: None

    if cfg.image_prune_strategy == "interval":
        return StripImagesAtIntervals(
            cfg.image_prune_min, cfg.image_prune_interval, max_message_mb=max_message_mb
        )

    return StripOldestImages(cfg.keep_n_most_recent_images)


def _stream_and_render(
    client: AnthropicClient,
    *,
    model: str,
    system: list[TextBlockParam],
    tool_params: list[Any],
    messages: list[MessageParam],
    effort_kwargs: dict[str, Any],
    betas: list[str],
    context_management: dict[str, Any] | None,
) -> Any:
    """Open a streaming message call, print deltas as they arrive, and return
    the assembled final message (anthropic.types.Message, or BetaMessage when
    `betas` is non-empty)."""
    # `api` (not `client`) is the only widening to Any: branching between
    # client.messages and client.beta.messages yields two distinct
    # stream-manager classes whose event/block unions otherwise fan out into
    # dozens of pyright errors. The return type stays Any for the same reason
    # (Message | BetaMessage); callers only touch attributes present on both.
    api: Any = client.beta.messages if betas else client.messages
    extra: dict[str, Any] = {"betas": betas} if betas else {}
    if context_management:
        extra["context_management"] = context_management

    with api.stream(
        model=model,
        max_tokens=16000,
        system=system,
        tools=tool_params,
        messages=messages,
        **effort_kwargs,
        **extra,
    ) as stream:
        streaming_block: str | None = None
        for event in stream:
            if event.type == "thinking":
                if streaming_block != "thinking":
                    render.block_end() if streaming_block else None
                    streaming_block = "thinking"
                render.thinking_delta(event.thinking)
            elif event.type == "text":
                if streaming_block != "text":
                    render.block_end() if streaming_block else None
                    streaming_block = "text"
                render.text_delta(event.text)
            elif event.type == "content_block_start":
                block = event.content_block
                if (
                    getattr(block, "type", "") == "server_tool_use"
                    and getattr(block, "name", "") == "advisor"
                ):
                    render.advisor_call(cfg.advisor_model)
            elif event.type == "content_block_stop":
                if streaming_block:
                    render.block_end()
                    streaming_block = None
                block = event.content_block
                btype = getattr(block, "type", "")
                if btype == "tool_use":
                    render.tool_call(block.name, block.input)
                elif btype == "advisor_tool_result":
                    content = getattr(block, "content", None)
                    if isinstance(content, dict):
                        render.advisor_result(content)
                    elif content is not None:
                        render.advisor_result(content.model_dump())
        return stream.get_final_message()


def _should_nudge_batch(tool_uses: list[Any]) -> bool:
    """Only nudge after a lone click/type/key/scroll/wait, not after
    screenshots or batch calls (which is what the model is told to do anyway)."""
    if len(tool_uses) != 1:
        return False
    tu = tool_uses[0]
    if tu.name not in {"computer", "browser"}:
        return False
    action = tu.input.get("action") if isinstance(tu.input, dict) else None
    return action in BATCH_REMINDER_ACTIONS


def _interrupted_result(tool_use_id: str) -> ToolResultBlockParam:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": True,
        "content": [{"type": "text", "text": "[interrupted by user]"}],
    }


def sampling_loop(
    *,
    model: str,
    task: str,
    tools: ToolCollection,
    trajectory: Trajectory,
    system_prompt: str = SYSTEM_PROMPT,
    thinking_effort: ThinkingEffort | None = None,
    max_iters: int = cfg.default_max_iters,
    interactive: bool = sys.stdin.isatty(),
) -> list[MessageParam]:
    """Run the agent. Each user message gets up to ``max_iters`` model turns.

    When ``interactive`` is true, the loop prompts for a follow-up after the
    model reaches end_turn (or after Ctrl-C). Ctrl-C during streaming discards
    the partial response; Ctrl-C during tool execution fills any outstanding
    tool_use blocks with an "[interrupted by user]" error result so the message
    list stays API-valid.
    """
    client = _make_client(cfg.provider)
    system: list[TextBlockParam] = [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]
    messages: list[MessageParam] = []

    if thinking_effort is None:
        thinking_effort = cfg.thinking_effort.get(model, cfg.default_thinking_effort)
    effort_kwargs = _effort_kwargs(model, thinking_effort)

    client_tool_params: list[Any] = list(
        tools.to_params(hosted_computer=cfg.use_hosted_computer_tool)
    )
    prune = _make_image_pruner(PROVIDER_MAX_MESSAGE_MB[cfg.provider])

    advisor_enabled = cfg.enable_advisor_tool
    advisor_uses = 0  # cumulative across compaction; messages alone can't tell us this.
    turns_since_advisor = 0
    turn = 0

    next_user_message: str | None = task
    while next_user_message is not None:
        messages.append({"role": "user", "content": next_user_message})
        trajectory.record("user", next_user_message)
        next_user_message = None
        empty_retries = 0

        for _ in range(max_iters):
            turn += 1

            _truncate_to_last_compaction(messages)
            prune(messages)
            if (
                advisor_enabled
                and cfg.advisor_max_conversation_uses is not None
                and advisor_uses >= cfg.advisor_max_conversation_uses
            ):
                _strip_advisor(messages)
                advisor_enabled = False
            _set_trailing_cache_control(messages)

            render.turn_header(turn)

            tool_params = client_tool_params + ([_advisor_tool_param()] if advisor_enabled else [])
            betas: list[str] = []
            if cfg.use_hosted_computer_tool:
                betas.append(COMPUTER_USE_BETA)
            if advisor_enabled:
                betas.append(ADVISOR_BETA)
            compaction_enabled = (
                cfg.enable_autocompaction and model in AUTOCOMPACTION_SUPPORTED_MODELS
            )
            if compaction_enabled:
                betas.append(COMPACTION_BETA)
            ctx_mgmt = {"edits": [_autocompaction_edit()]} if compaction_enabled else None

            try:
                start = time.monotonic()
                response = _call_with_retry(
                    lambda tp=tool_params, b=betas, cm=ctx_mgmt: _stream_and_render(
                        client,
                        model=model,
                        system=system,
                        tool_params=tp,
                        messages=messages,
                        effort_kwargs=effort_kwargs,
                        betas=b,
                        context_management=cm,
                    )
                )
                elapsed = time.monotonic() - start
            except KeyboardInterrupt:
                render.interrupted()
                break

            if cfg.print_usage:
                render.usage(_format_usage(response.usage, elapsed))
            ctx = getattr(response, "context_management", None)
            if ctx is not None and getattr(ctx, "applied_edits", None):
                render.context_edits_applied(ctx.applied_edits)

            if _is_empty_response(response.content):
                empty_retries += 1
                if empty_retries > cfg.empty_response_retry_max:
                    raise RuntimeError(
                        f"{empty_retries} consecutive empty responses from the model"
                    )
                # Don't append the empty assistant turn: a non-final assistant
                # message with empty content is rejected by the API with a 400,
                # which would defeat this retry on its very next request.
                messages.append(
                    {
                        "role": "user",
                        "content": "Please continue, do not produce an empty response.",
                    }
                )
                continue

            empty_retries = 0

            trajectory.record("assistant", [b.model_dump() for b in response.content])
            messages.append({"role": "assistant", "content": response.content})

            advisor_calls_this_turn = sum(
                getattr(b, "type", "") == "server_tool_use" and getattr(b, "name", "") == "advisor"
                for b in response.content
            )
            advisor_uses += advisor_calls_this_turn
            turns_since_advisor = 0 if advisor_calls_this_turn else turns_since_advisor + 1
            advisor_nudge = (
                advisor_enabled
                and cfg.advisor_reminder_interval is not None
                and turns_since_advisor >= cfg.advisor_reminder_interval
            )

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason == "end_turn" or not tool_uses:
                break

            nudge = _should_nudge_batch(tool_uses)
            results: list[ToolResultBlockParam] = []
            try:
                for tu in tool_uses:
                    res = tools.run(tu.name, tu.input)
                    render.tool_result(tu.name, res)
                    content = res.to_api_content()
                    if nudge and not res.is_error:
                        content.append({"type": "text", "text": BATCH_REMINDER})
                    if advisor_nudge and not res.is_error:
                        content.append({"type": "text", "text": ADVISOR_REMINDER})
                        advisor_nudge = False
                        turns_since_advisor = 0
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "is_error": res.is_error,
                            "content": content,
                        }
                    )
            except KeyboardInterrupt:
                render.interrupted()
                done_ids = {r["tool_use_id"] for r in results}
                for tu in tool_uses:
                    if tu.id not in done_ids:
                        results.append(_interrupted_result(tu.id))
                messages.append({"role": "user", "content": results})
                trajectory.record("user", results)
                break

            messages.append({"role": "user", "content": results})
            trajectory.record("user", results)

        # The for-loop can exit with messages ending in a user-role entry (Ctrl-C
        # during streaming, Ctrl-C during tool execution, or max_iters reached on
        # a tool-calling turn). Appending a follow-up user message on top of that
        # would 400; insert a synthetic assistant turn so the API stays valid.
        if messages and messages[-1].get("role") == "user":
            messages.append(
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "[stopped before completing]"}],
                }
            )
            trajectory.record(
                "assistant", [{"type": "text", "text": "[stopped before completing]"}]
            )

        if not interactive:
            return messages

        next_user_message = render.prompt_user()

    return messages
