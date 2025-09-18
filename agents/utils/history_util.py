"""Message history with token tracking and prompt caching."""

from typing import Any


class MessageHistory:
    """Manages chat history with token tracking and context management."""

    def __init__(
        self,
        model: str,
        system: str,
        context_window_tokens: int,
        client: Any,
        enable_caching: bool = True,
    ):
        self.model = model
        self.system = system
        self.context_window_tokens = context_window_tokens
        self.messages: list[dict[str, Any]] = []
        self.total_tokens = 0
        self.enable_caching = enable_caching
        self.message_tokens: list[tuple[int, int]] = (
            []
        )  # List of (input_tokens, output_tokens) tuples
        self.client = client

        # set initial total tokens to system prompt
        try:
            system_token = (
                self.client.messages.count_tokens(
                    model=self.model,
                    system=self.system,
                    messages=[{"role": "user", "content": "test"}],
                ).input_tokens
                - 1
            )

        except Exception:
            system_token = len(self.system) / 4

        self.total_tokens = system_token

    async def add_message(
        self,
        role: str,
        content: str | list[dict[str, Any]],
        usage: Any | None = None,
    ):
        """Add a message to the history and track token usage."""
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]

        message = {"role": role, "content": content}
        self.messages.append(message)

        if role == "assistant" and usage:
            total_input = (
                usage.input_tokens
                + getattr(usage, "cache_read_input_tokens", 0)
                + getattr(usage, "cache_creation_input_tokens", 0)
            )
            output_tokens = usage.output_tokens

            current_turn_input = total_input - self.total_tokens
            self.message_tokens.append((current_turn_input, output_tokens))
            self.total_tokens += current_turn_input + output_tokens

    def truncate(self) -> None:
        """Remove oldest messages when context window limit is exceeded."""
        if self.total_tokens <= self.context_window_tokens:
            return

        TRUNCATION_NOTICE_TOKENS = 25
        TRUNCATION_MESSAGE = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "[Earlier history has been truncated.]",
                }
            ],
        }

        def remove_message_pair():
            self.messages.pop(0)
            self.messages.pop(0)

            if self.message_tokens:
                input_tokens, output_tokens = self.message_tokens.pop(0)
                self.total_tokens -= input_tokens + output_tokens

        while (
            self.message_tokens
            and len(self.messages) >= 2
            and self.total_tokens > self.context_window_tokens
        ):
            remove_message_pair()

            if self.messages and self.message_tokens:
                original_input_tokens, original_output_tokens = (
                    self.message_tokens[0]
                )
                self.messages[0] = TRUNCATION_MESSAGE
                self.message_tokens[0] = (
                    TRUNCATION_NOTICE_TOKENS,
                    original_output_tokens,
                )
                self.total_tokens += (
                    TRUNCATION_NOTICE_TOKENS - original_input_tokens
                )

    def format_for_api(self) -> list[dict[str, Any]]:
        """Format messages for Claude API with optional caching."""
        result = [
            {"role": m["role"], "content": m["content"]} for m in self.messages
        ]

        if self.enable_caching and self.messages:
            result[-1]["content"] = [
                {**block, "cache_control": {"type": "ephemeral"}}
                for block in self.messages[-1]["content"]
            ]
        return result
