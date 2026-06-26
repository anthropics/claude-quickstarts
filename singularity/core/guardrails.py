"""
Singularity — Content Moderation / Safety Guardrails (Fáze 27).

Pre-flight (input) and post-flight (output) scanning of prompts and responses.
Detects PII, leaked secrets, and prompt-injection patterns; applies one of four
actions per matched rule:

  ALLOW   — informational only; never blocks
  FLAG    — record a match but let the text through
  REDACT  — replace the matched span with a placeholder
  BLOCK   — reject the request entirely

Built-in rules cover common PII (email, phone, SSN, credit card), secrets
(API keys, private keys), and prompt-injection phrases. Custom rules can be
registered at runtime. Fully offline — regex + heuristics, no external deps.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import structlog

log = structlog.get_logger()


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    FLAG = "flag"
    REDACT = "redact"
    BLOCK = "block"


class RuleCategory(str, Enum):
    PII = "pii"
    SECRET = "secret"
    INJECTION = "injection"
    PROFANITY = "profanity"
    CUSTOM = "custom"


# Ordering for "most severe action wins" when several rules match.
_ACTION_SEVERITY = {
    GuardrailAction.ALLOW: 0,
    GuardrailAction.FLAG: 1,
    GuardrailAction.REDACT: 2,
    GuardrailAction.BLOCK: 3,
}


@dataclass
class GuardrailRule:
    rule_id: str
    name: str
    category: RuleCategory
    pattern: str                       # regex source
    action: GuardrailAction
    placeholder: str = "[REDACTED]"    # used when action == REDACT
    enabled: bool = True
    builtin: bool = False
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    _compiled: re.Pattern | None = field(default=None, repr=False, compare=False)

    def compiled(self) -> re.Pattern:
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, re.IGNORECASE)
        return self._compiled

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category.value,
            "pattern": self.pattern,
            "action": self.action.value,
            "placeholder": self.placeholder,
            "enabled": self.enabled,
            "builtin": self.builtin,
            "created_at": self.created_at,
        }


@dataclass
class GuardrailResult:
    allowed: bool
    action: GuardrailAction
    text: str                          # possibly-redacted text
    original_length: int
    matched: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "action": self.action.value,
            "text": self.text,
            "original_length": self.original_length,
            "redacted": self.action == GuardrailAction.REDACT,
            "matched": self.matched,
            "match_count": len(self.matched),
        }


# ── Built-in rule definitions ─────────────────────────────────────────────────

_BUILTIN_RULES: tuple[tuple[str, RuleCategory, str, GuardrailAction, str], ...] = (
    # name, category, pattern, action, placeholder
    ("email", RuleCategory.PII,
     r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
     GuardrailAction.REDACT, "[EMAIL]"),
    ("phone_us", RuleCategory.PII,
     r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
     GuardrailAction.REDACT, "[PHONE]"),
    ("ssn", RuleCategory.PII,
     r"\b\d{3}-\d{2}-\d{4}\b",
     GuardrailAction.REDACT, "[SSN]"),
    ("credit_card", RuleCategory.PII,
     r"\b(?:\d[ -]?){13,16}\b",
     GuardrailAction.REDACT, "[CARD]"),
    ("anthropic_key", RuleCategory.SECRET,
     r"sk-ant-[A-Za-z0-9_-]{8,}",
     GuardrailAction.BLOCK, "[SECRET]"),
    ("openai_key", RuleCategory.SECRET,
     r"sk-[A-Za-z0-9]{20,}",
     GuardrailAction.BLOCK, "[SECRET]"),
    ("aws_key", RuleCategory.SECRET,
     r"AKIA[0-9A-Z]{16}",
     GuardrailAction.BLOCK, "[SECRET]"),
    ("private_key", RuleCategory.SECRET,
     r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
     GuardrailAction.BLOCK, "[SECRET]"),
    ("injection_ignore", RuleCategory.INJECTION,
     r"ignore (?:all |the |your )?(?:previous|prior|above) (?:instructions|prompts?)",
     GuardrailAction.BLOCK, "[INJECTION]"),
    ("injection_system", RuleCategory.INJECTION,
     r"(?:disregard|forget|override) (?:your |the |all )?(?:system prompt|instructions|rules)",
     GuardrailAction.BLOCK, "[INJECTION]"),
    ("injection_roleplay", RuleCategory.INJECTION,
     r"you are (?:now |no longer )?(?:DAN|a different AI|unrestricted|jailbroken)",
     GuardrailAction.FLAG, "[INJECTION]"),
)


class GuardrailManager:
    """
    Thread-safe registry + scanner for content-safety rules.

    Usage:
        gm = GuardrailManager()
        result = gm.scan("My email is foo@bar.com", direction="input")
        if not result.allowed:
            raise ValueError("Blocked by guardrails")
        clean_text = result.text
    """

    def __init__(self, *, load_builtins: bool = True) -> None:
        self._rules: dict[str, GuardrailRule] = {}
        self._lock = threading.Lock()
        self._total_scans = 0
        self._blocked = 0
        self._redacted = 0
        self._flagged = 0
        if load_builtins:
            self._load_builtins()

    def _load_builtins(self) -> None:
        for name, category, pattern, action, placeholder in _BUILTIN_RULES:
            rid = f"builtin-{name}"
            self._rules[rid] = GuardrailRule(
                rule_id=rid,
                name=name,
                category=category,
                pattern=pattern,
                action=action,
                placeholder=placeholder,
                builtin=True,
            )

    # ── Rule CRUD ─────────────────────────────────────────────────────────────

    def add_rule(
        self,
        name: str,
        pattern: str,
        action: str | GuardrailAction,
        *,
        category: str | RuleCategory = RuleCategory.CUSTOM,
        placeholder: str = "[REDACTED]",
    ) -> str:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if not pattern or not pattern.strip():
            raise ValueError("pattern must not be empty")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern: {exc}")
        try:
            act = GuardrailAction(action) if isinstance(action, str) else action
        except ValueError:
            raise ValueError(
                f"action must be one of {[a.value for a in GuardrailAction]}"
            )
        try:
            cat = RuleCategory(category) if isinstance(category, str) else category
        except ValueError:
            raise ValueError(
                f"category must be one of {[c.value for c in RuleCategory]}"
            )

        rule_id = str(uuid.uuid4())
        with self._lock:
            self._rules[rule_id] = GuardrailRule(
                rule_id=rule_id,
                name=name,
                category=cat,
                pattern=pattern,
                action=act,
                placeholder=placeholder,
                builtin=False,
            )
        log.info("guardrail_rule_added", rule_id=rule_id, name=name, action=act.value)
        return rule_id

    def get_rule(self, rule_id: str) -> dict | None:
        with self._lock:
            r = self._rules.get(rule_id)
        return r.to_dict() if r else None

    def list_rules(self, category: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._rules.values())
        if category is not None:
            items = [r for r in items if r.category.value == category]
        return [r.to_dict() for r in items]

    def set_enabled(self, rule_id: str, enabled: bool) -> bool:
        with self._lock:
            r = self._rules.get(rule_id)
            if r is None:
                return False
            r.enabled = enabled
        log.info("guardrail_rule_toggled", rule_id=rule_id, enabled=enabled)
        return True

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            r = self._rules.get(rule_id)
            if r is None:
                return False
            if r.builtin:
                raise ValueError("cannot delete a built-in rule; disable it instead")
            del self._rules[rule_id]
        return True

    def rule_count(self) -> int:
        with self._lock:
            return len(self._rules)

    # ── Scanning ──────────────────────────────────────────────────────────────

    def scan(self, text: str, *, direction: str = "input") -> GuardrailResult:
        """
        Scan text against all enabled rules.

        Returns a GuardrailResult. The effective action is the most severe one
        across all matched rules. BLOCK → allowed=False. REDACT → text replaced.
        """
        original_length = len(text)
        with self._lock:
            self._total_scans += 1
            rules = [r for r in self._rules.values() if r.enabled]

        matched: list[dict] = []
        effective = GuardrailAction.ALLOW
        result_text = text

        for rule in rules:
            hits = list(rule.compiled().finditer(result_text))
            if not hits:
                continue
            matched.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "category": rule.category.value,
                "action": rule.action.value,
                "count": len(hits),
            })
            if _ACTION_SEVERITY[rule.action] > _ACTION_SEVERITY[effective]:
                effective = rule.action
            # Apply redaction immediately so later rules see masked text
            if rule.action == GuardrailAction.REDACT:
                result_text = rule.compiled().sub(rule.placeholder, result_text)

        allowed = effective != GuardrailAction.BLOCK

        with self._lock:
            if effective == GuardrailAction.BLOCK:
                self._blocked += 1
            elif effective == GuardrailAction.REDACT:
                self._redacted += 1
            elif effective == GuardrailAction.FLAG:
                self._flagged += 1

        if matched:
            log.info("guardrail_scan", direction=direction, action=effective.value,
                     match_count=len(matched), allowed=allowed)

        return GuardrailResult(
            allowed=allowed,
            action=effective,
            text=result_text if allowed else text,
            original_length=original_length,
            matched=matched,
        )

    def stats(self) -> dict:
        with self._lock:
            return {
                "total_scans": self._total_scans,
                "blocked": self._blocked,
                "redacted": self._redacted,
                "flagged": self._flagged,
                "rule_count": len(self._rules),
                "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._total_scans = 0
            self._blocked = 0
            self._redacted = 0
            self._flagged = 0
