"""
Token usage logging utility for monitoring API token consumption.

This module provides functionality to track, log, and analyze token usage
in API calls to Claude. It helps identify potential areas for optimization
and provides insights into token consumption patterns.
"""

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from logging import LogRecord
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, TypeVar, Union

import httpx
from httpx import Headers

T = TypeVar("T")


class TokenDataLogRecord(LogRecord):
    """Log record with token data."""

    token_data: Dict[str, Any]


# Configure environment variables
LOG_LEVEL = os.environ.get("TOKEN_LOG_LEVEL", "INFO")
ENABLE_TOKEN_LOGGING = os.environ.get("ENABLE_TOKEN_LOGGING", "true").lower() == "true"
LOG_DIR = Path(os.environ.get("TOKEN_LOG_DIR", "~/.anthropic/logs")).expanduser()
LOG_FILE = LOG_DIR / "token_usage.log"
MAX_LOG_SIZE = int(os.environ.get("TOKEN_LOG_SIZE", 10 * 1024 * 1024))  # 10MB
LOG_BACKUP_COUNT = int(os.environ.get("TOKEN_LOG_BACKUPS", 5))

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logger
token_logger = logging.getLogger("token_usage")
token_logger.setLevel(getattr(logging, LOG_LEVEL))

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL))
console_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(console_formatter)
token_logger.addHandler(console_handler)

# Add file handler with rotation
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=MAX_LOG_SIZE, backupCount=LOG_BACKUP_COUNT
)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
token_logger.addHandler(file_handler)

# Add JSON file handler for machine-readable logs
json_log_file = LOG_DIR / "token_usage.json"
json_handler = RotatingFileHandler(
    json_log_file, maxBytes=MAX_LOG_SIZE, backupCount=LOG_BACKUP_COUNT
)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON strings."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "token_data"):
            log_data["token_data"] = record.__dict__["token_data"]
        return json.dumps(log_data)


json_handler.setFormatter(JsonFormatter())
token_logger.addHandler(json_handler)


@dataclass
class TokenUsage:
    """Track token usage statistics for a conversation."""

    session_id: str = field(default_factory=lambda: datetime.now().isoformat())
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    image_count: int = 0
    total_image_bytes: int = 0
    request_times: List[float] = field(default_factory=list)
    token_rates: List[float] = field(default_factory=list)
    message_sizes: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def update_from_headers(self, headers: Union[Dict[str, str], Headers]) -> None:
        """Update token counts from API response headers."""
        if not headers:
            token_logger.warning("No headers provided to extract token counts")
            return

        # Extract token counts from headers
        input_tokens = int(headers.get("anthropic-input-tokens", 0))
        output_tokens = int(headers.get("anthropic-output-tokens", 0))

        # Update totals
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.request_count += 1

        # Log the token usage
        token_logger.info(
            f"Request #{self.request_count}: Input tokens: {input_tokens}, "
            f"Output tokens: {output_tokens}, Total: {input_tokens + output_tokens}"
        )

        # Add structured data for JSON logging
        extra = {
            "token_data": {
                "session_id": self.session_id,
                "request_id": self.request_count,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cumulative_input": self.input_tokens,
                "cumulative_output": self.output_tokens,
                "cumulative_total": self.total_tokens,
            }
        }
        token_logger.info("Token usage updated", extra=extra)

    def log_message_size(self, message_type: str, message: Any) -> None:
        """Log the size information about a message."""
        if not ENABLE_TOKEN_LOGGING:
            return

        # Get rough size estimate based on type
        size = 0
        if isinstance(message, str):
            size = len(message)
        elif isinstance(message, dict):
            size = len(json.dumps(message))
        elif isinstance(message, list):
            size = len(json.dumps(message))

        self.message_sizes[message_type] += size

        token_logger.debug(
            f"Message size - Type: {message_type}, Size: {size} bytes, "
            f"Total for type: {self.message_sizes[message_type]} bytes"
        )

    def log_image_data(self, image_data: str, was_truncated: bool = False) -> None:
        """Log information about image data sent to the API."""
        if not ENABLE_TOKEN_LOGGING or not image_data:
            return

        image_size = len(image_data) * 3 // 4  # Approximate base64 to bytes conversion
        self.image_count += 1
        self.total_image_bytes += image_size

        token_logger.info(
            f"Image #{self.image_count}: Size: {image_size} bytes, "
            f"Truncated: {was_truncated}, Total images: {self.image_count}"
        )

        # Add structured data for JSON logging
        extra = {
            "token_data": {
                "session_id": self.session_id,
                "image_id": self.image_count,
                "image_size_bytes": image_size,
                "truncated": was_truncated,
                "total_images": self.image_count,
                "total_image_bytes": self.total_image_bytes,
            }
        }
        token_logger.info("Image data logged", extra=extra)

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get a summary of token usage statistics."""
        return {
            "session_id": self.session_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
            "image_count": self.image_count,
            "total_image_bytes": self.total_image_bytes,
            "average_tokens_per_request": self.total_tokens
            / max(1, self.request_count),
            "message_sizes": dict(self.message_sizes),
        }


# Global token usage tracker
current_session = TokenUsage()


def extract_token_usage_from_response(
    response: httpx.Response | None,
) -> Dict[str, int]:
    """Extract token usage information from an API response."""
    if not response or not hasattr(response, "headers"):
        return {}

    headers = response.headers
    return {
        "input_tokens": int(headers.get("anthropic-input-tokens", 0)),
        "output_tokens": int(headers.get("anthropic-output-tokens", 0)),
        "total_tokens": int(headers.get("anthropic-input-tokens", 0))
        + int(headers.get("anthropic-output-tokens", 0)),
    }


def log_token_usage_from_response(response: httpx.Response) -> None:
    """Log token usage from an API response."""
    if not ENABLE_TOKEN_LOGGING or not response:
        return

    token_usage = extract_token_usage_from_response(response)
    if token_usage:
        current_session.update_from_headers(response.headers)


def analyze_message_payload(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the size and composition of a message payload."""
    if not ENABLE_TOKEN_LOGGING:
        return {}

    analysis = {
        "total_size_bytes": len(json.dumps(messages)),
        "message_count": len(messages),
        "text_blocks": 0,
        "image_blocks": 0,
        "tool_blocks": 0,
        "text_size_bytes": 0,
        "image_size_bytes": 0,
        "tool_size_bytes": 0,
    }

    for message in messages:
        if isinstance(message.get("content"), list):
            for block in message["content"]:
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type")
                block_size = len(json.dumps(block))

                if block_type == "text":
                    analysis["text_blocks"] += 1
                    analysis["text_size_bytes"] += block_size
                elif block_type == "image":
                    analysis["image_blocks"] += 1
                    analysis["image_size_bytes"] += block_size
                elif block_type in ("tool_use", "tool_result"):
                    analysis["tool_blocks"] += 1
                    analysis["tool_size_bytes"] += block_size

    # Log the analysis
    token_logger.info(
        f"Message payload analysis: {analysis['total_size_bytes']} bytes total, "
        f"{analysis['text_blocks']} text blocks, {analysis['image_blocks']} image blocks, "
        f"{analysis['tool_blocks']} tool blocks"
    )

    # Add structured data for JSON logging
    extra = {"token_data": analysis}
    token_logger.info("Message payload analyzed", extra=extra)

    return analysis


def log_image_truncation(original_count: int, final_count: int) -> None:
    """Log information about image truncation."""
    if not ENABLE_TOKEN_LOGGING:
        return

    if original_count > final_count:
        token_logger.info(
            f"Image truncation: Removed {original_count - final_count} images, "
            f"Original: {original_count}, Final: {final_count}"
        )

        # Add structured data for JSON logging
        extra = {
            "token_data": {
                "session_id": current_session.session_id,
                "original_image_count": original_count,
                "final_image_count": final_count,
                "images_removed": original_count - final_count,
            }
        }
        token_logger.info("Images truncated", extra=extra)


def get_current_session() -> TokenUsage:
    """Get the current token usage session."""
    return current_session


def reset_session() -> None:
    """Reset the current token usage session."""
    global current_session
    current_session = TokenUsage()
    token_logger.info("Token usage session reset")
