"""
Singularity — Structured Output Parser (Fáze 44).

Extracts structured data from free-form LLM text. LLMs often wrap JSON in
markdown fences, add prose around it, or emit key-value / list structures
instead of strict JSON. This module pulls the structure back out:

  - extract_json:  find JSON in ```json fences, bare fences, or the first
                   balanced {...}/[...] span; light repair (trailing commas,
                   smart quotes, single→double quotes)
  - extract_key_values:  "key: value" lines → dict
  - extract_list:  bullet (-, *, •) or numbered (1.) lines → list

Dependency-free and deterministic.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any


_FENCE_JSON = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_KV_LINE = re.compile(r"^\s*[-*]?\s*([A-Za-z0-9 _\-]+?)\s*[:=]\s*(.+?)\s*$")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)\s*$")


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    success: bool
    data: Any = None
    method: str = ""          # how it was extracted
    repaired: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "method": self.method,
            "repaired": self.repaired,
            "error": self.error,
        }


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _try_json(text: str) -> tuple[bool, Any]:
    try:
        return True, json.loads(text)
    except (ValueError, TypeError):
        return False, None


def _repair_json(text: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    s = text.strip()
    # smart quotes → straight
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("‘", "'").replace("’", "'")
    # remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # single-quoted keys/values → double (only when no double quotes present)
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    return s


def _find_balanced_span(text: str) -> str | None:
    """Return the first balanced {...} or [...] span, or None."""
    starts = {"{": "}", "[": "]"}
    for i, ch in enumerate(text):
        if ch in starts:
            close = starts[ch]
            depth = 0
            in_str = False
            esc = False
            for j in range(i, len(text)):
                c = text[j]
                if esc:
                    esc = False
                    continue
                if c == "\\":
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                elif not in_str:
                    if c == ch:
                        depth += 1
                    elif c == close:
                        depth -= 1
                        if depth == 0:
                            return text[i:j + 1]
            break
    return None


# ── Parser ──────────────────────────────────────────────────────────────────────

class OutputParser:
    """Pull structured data out of messy LLM text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # metrics
        self._total = 0
        self._json_ok = 0
        self._repaired = 0
        self._failures = 0

    # ── JSON ──────────────────────────────────────────────────────────────────────

    def extract_json(self, text: str) -> ParseResult:
        doc = text or ""

        # 1. fenced block
        candidates: list[tuple[str, str]] = []
        for m in _FENCE_JSON.finditer(doc):
            candidates.append(("fenced", m.group(1).strip()))
        # 2. whole string
        candidates.append(("raw", doc.strip()))
        # 3. first balanced span
        span = _find_balanced_span(doc)
        if span:
            candidates.append(("balanced_span", span))

        for method, cand in candidates:
            if not cand:
                continue
            ok, data = _try_json(cand)
            if ok:
                self._record(json_ok=True)
                return ParseResult(True, data=data, method=method)
            # try repair
            repaired = _repair_json(cand)
            if repaired != cand:
                ok, data = _try_json(repaired)
                if ok:
                    self._record(json_ok=True, repaired=True)
                    return ParseResult(True, data=data, method=method, repaired=True)

        self._record(failure=True)
        return ParseResult(False, method="none", error="No valid JSON found")

    # ── Key-Value ───────────────────────────────────────────────────────────────

    def extract_key_values(self, text: str) -> ParseResult:
        result: dict[str, str] = {}
        for line in (text or "").splitlines():
            m = _KV_LINE.match(line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                if key:
                    result[key] = val
        if result:
            self._record(json_ok=False)
            return ParseResult(True, data=result, method="key_value")
        self._record(failure=True)
        return ParseResult(False, data={}, method="key_value",
                           error="No key-value pairs found")

    # ── List ──────────────────────────────────────────────────────────────────────

    def extract_list(self, text: str) -> ParseResult:
        items: list[str] = []
        for line in (text or "").splitlines():
            m = _BULLET.match(line)
            if m:
                items.append(m.group(1).strip())
        if items:
            self._record(json_ok=False)
            return ParseResult(True, data=items, method="list")
        self._record(failure=True)
        return ParseResult(False, data=[], method="list",
                           error="No list items found")

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, *, json_ok: bool = False, repaired: bool = False,
                failure: bool = False) -> None:
        with self._lock:
            self._total += 1
            if json_ok:
                self._json_ok += 1
            if repaired:
                self._repaired += 1
            if failure:
                self._failures += 1

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_parses": n,
                "json_successes": self._json_ok,
                "repaired": self._repaired,
                "failures": self._failures,
                "success_rate": round((n - self._failures) / n, 4) if n else 0.0,
                "repair_rate": round(self._repaired / n, 4) if n else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._json_ok = 0
            self._repaired = 0
            self._failures = 0
