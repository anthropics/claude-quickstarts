"""Best-effort LLM usage/cost estimation utilities for V3.7.0."""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from typing import Any

INPUT_USD_PER_1M = float(os.environ.get("V3_7_EST_INPUT_USD_PER_1M", os.environ.get("V3_5_EST_INPUT_USD_PER_1M", "3.0")))
OUTPUT_USD_PER_1M = float(
    os.environ.get("V3_7_EST_OUTPUT_USD_PER_1M", os.environ.get("V3_5_EST_OUTPUT_USD_PER_1M", "15.0"))
)
TOKEN_EST_CHARS_PER_TOKEN = float(
    os.environ.get("V3_7_EST_CHARS_PER_TOKEN", os.environ.get("V3_5_EST_CHARS_PER_TOKEN", "4.0"))
)


@dataclass
class UsageEstimate:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    confidence: str = "estimated"
    error_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["estimated_cost_usd"] = round(float(payload["estimated_cost_usd"]), 8)
        return payload


def estimate_usage(prompt: str, response: str) -> UsageEstimate:
    chars_per_token = max(TOKEN_EST_CHARS_PER_TOKEN, 1.0)
    input_tokens = max(1, int(math.ceil(len(prompt) / chars_per_token)))
    output_tokens = max(1, int(math.ceil(len(response) / chars_per_token)))
    total_tokens = input_tokens + output_tokens
    estimated_cost_usd = ((input_tokens * INPUT_USD_PER_1M) + (output_tokens * OUTPUT_USD_PER_1M)) / 1_000_000
    return UsageEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )


def default_run_usage() -> dict[str, Any]:
    return {
        "estimation_version": "v3_5",
        "currency": "USD",
        "rates_usd_per_1m_tokens": {
            "input": INPUT_USD_PER_1M,
            "output": OUTPUT_USD_PER_1M,
        },
        "calls_total": 0,
        "totals": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
        "by_phase": {
            "planner": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
            "builder": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
            "evaluator": {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        },
    }
