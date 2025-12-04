"""
Safety and Error Handling System - Phase 2 Enhancement

Implements:
- PII and policy filters
- Structured error taxonomy
- Automatic recovery steps
- Input/output sanitization
- Safety gates for tool execution
"""

from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import re
import json


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class ErrorCategory(Enum):
    """Categories of errors for taxonomy."""
    VALIDATION = "validation"
    PARSING = "parsing"
    INFERENCE = "inference"
    TOOL_EXECUTION = "tool_execution"
    CONSTRAINT_VIOLATION = "constraint_violation"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    SAFETY_VIOLATION = "safety_violation"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    STATE_CONFLICT = "state_conflict"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Possible recovery actions."""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    ABORT = "abort"
    REQUEST_INFO = "request_info"
    RELAX_CONSTRAINTS = "relax_constraints"
    USE_CACHE = "use_cache"
    DEGRADE_GRACEFULLY = "degrade_gracefully"


class PolicyType(Enum):
    """Types of policy violations."""
    PII_EXPOSURE = "pii_exposure"
    HARMFUL_CONTENT = "harmful_content"
    BIAS = "bias"
    PRIVACY = "privacy"
    SECURITY = "security"
    LEGAL = "legal"
    ETHICAL = "ethical"


@dataclass
class StructuredError:
    """A structured error with full context."""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_component: str = ""
    stack_trace: Optional[str] = None
    recovery_suggestions: List[RecoveryAction] = field(default_factory=list)
    is_recoverable: bool = True
    retry_count: int = 0
    max_retries: int = 3
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "source_component": self.source_component,
            "recovery_suggestions": [r.value for r in self.recovery_suggestions],
            "is_recoverable": self.is_recoverable,
            "retry_count": self.retry_count
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    action_taken: RecoveryAction
    message: str
    new_state: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class PolicyViolation:
    """A detected policy violation."""
    violation_type: PolicyType
    description: str
    severity: ErrorSeverity
    location: str  # Where in the content
    suggested_fix: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class SanitizationResult:
    """Result of sanitizing input/output."""
    original: str
    sanitized: str
    violations_found: List[PolicyViolation]
    was_modified: bool
    is_safe: bool


class PIIDetector:
    """
    Detects and redacts Personally Identifiable Information.
    """
    
    def __init__(self):
        # PII patterns
        self.patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
            "ssn": r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',
            "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            "date_of_birth": r'\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b',
            "address": r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct)\b',
        }
        
        self.redaction_placeholder = "[REDACTED]"
    
    def detect(self, text: str) -> List[Tuple[str, str, int, int]]:
        """
        Detect PII in text.
        
        Returns:
            List of (pii_type, matched_text, start, end)
        """
        findings = []
        
        for pii_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end()
                ))
        
        return findings
    
    def redact(self, text: str) -> Tuple[str, List[str]]:
        """
        Redact PII from text.
        
        Returns:
            (redacted_text, list of pii types found)
        """
        findings = self.detect(text)
        
        # Sort by position (reverse) to maintain indices
        findings.sort(key=lambda x: x[2], reverse=True)
        
        redacted = text
        types_found = set()
        
        for pii_type, matched, start, end in findings:
            redacted = redacted[:start] + self.redaction_placeholder + redacted[end:]
            types_found.add(pii_type)
        
        return redacted, list(types_found)


class ContentPolicyChecker:
    """
    Checks content against policy rules.
    """
    
    def __init__(self):
        # Harmful content patterns
        self.harmful_patterns = [
            (r'\b(kill|murder|harm|attack)\s+(people|person|someone)\b', "violence"),
            (r'\b(how\s+to\s+make|instructions\s+for)\s+(bomb|weapon|drug)\b', "dangerous"),
            (r'\b(hate|discriminate)\s+against\s+\w+\b', "hate_speech"),
        ]
        
        # Bias indicators
        self.bias_patterns = [
            (r'\b(always|never)\s+\w+\s+(people|group|race|gender)\b', "generalization"),
            (r'\b(all|every)\s+\w+\s+(are|is)\s+\w+\b', "stereotype"),
        ]
    
    def check(self, content: str) -> List[PolicyViolation]:
        """Check content against policies."""
        violations = []
        
        # Check harmful content
        for pattern, category in self.harmful_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                violations.append(PolicyViolation(
                    violation_type=PolicyType.HARMFUL_CONTENT,
                    description=f"Potentially harmful content: {category}",
                    severity=ErrorSeverity.CRITICAL,
                    location=match.group(),
                    auto_fixable=False
                ))
        
        # Check bias
        for pattern, bias_type in self.bias_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                violations.append(PolicyViolation(
                    violation_type=PolicyType.BIAS,
                    description=f"Potential bias detected: {bias_type}",
                    severity=ErrorSeverity.WARNING,
                    location=match.group(),
                    auto_fixable=False
                ))
        
        return violations


class InputSanitizer:
    """
    Sanitizes inputs before processing.
    """
    
    def __init__(
        self,
        pii_detector: Optional[PIIDetector] = None,
        policy_checker: Optional[ContentPolicyChecker] = None,
        redact_pii: bool = True,
        block_harmful: bool = True
    ):
        self.pii_detector = pii_detector or PIIDetector()
        self.policy_checker = policy_checker or ContentPolicyChecker()
        self.redact_pii = redact_pii
        self.block_harmful = block_harmful
    
    def sanitize(self, input_text: str) -> SanitizationResult:
        """Sanitize input text."""
        sanitized = input_text
        violations = []
        was_modified = False
        is_safe = True
        
        # Check PII
        if self.redact_pii:
            redacted, pii_types = self.pii_detector.redact(input_text)
            if pii_types:
                sanitized = redacted
                was_modified = True
                for pii_type in pii_types:
                    violations.append(PolicyViolation(
                        violation_type=PolicyType.PII_EXPOSURE,
                        description=f"PII detected and redacted: {pii_type}",
                        severity=ErrorSeverity.WARNING,
                        location=pii_type,
                        auto_fixable=True
                    ))
        
        # Check content policy
        policy_violations = self.policy_checker.check(sanitized)
        violations.extend(policy_violations)
        
        # Determine if safe
        if self.block_harmful:
            critical_violations = [
                v for v in violations
                if v.severity == ErrorSeverity.CRITICAL
            ]
            if critical_violations:
                is_safe = False
        
        return SanitizationResult(
            original=input_text,
            sanitized=sanitized,
            violations_found=violations,
            was_modified=was_modified,
            is_safe=is_safe
        )


class OutputGuard:
    """
    Guards outputs before emission.
    """
    
    def __init__(
        self,
        pii_detector: Optional[PIIDetector] = None,
        policy_checker: Optional[ContentPolicyChecker] = None,
        block_on_pii: bool = True,
        block_on_harmful: bool = True
    ):
        self.pii_detector = pii_detector or PIIDetector()
        self.policy_checker = policy_checker or ContentPolicyChecker()
        self.block_on_pii = block_on_pii
        self.block_on_harmful = block_on_harmful
    
    def check(self, output: str) -> Tuple[bool, str, List[str]]:
        """
        Check if output is safe to emit.
        
        Returns:
            (is_safe, sanitized_output, warnings)
        """
        warnings = []
        sanitized = output
        is_safe = True
        
        # Check PII
        pii_findings = self.pii_detector.detect(output)
        if pii_findings:
            if self.block_on_pii:
                sanitized, _ = self.pii_detector.redact(output)
                warnings.append(f"PII redacted from output: {len(pii_findings)} instances")
            else:
                warnings.append(f"PII detected in output: {len(pii_findings)} instances")
        
        # Check policy
        violations = self.policy_checker.check(sanitized)
        for v in violations:
            if v.severity == ErrorSeverity.CRITICAL and self.block_on_harmful:
                is_safe = False
                warnings.append(f"Blocked: {v.description}")
            else:
                warnings.append(f"Policy warning: {v.description}")
        
        return is_safe, sanitized, warnings


class ToolArgsSanitizer:
    """
    Sanitizes arguments before passing to tools.
    """
    
    def __init__(self):
        # Dangerous patterns in tool args
        self.dangerous_patterns = [
            (r';\s*rm\s+-rf', "shell_injection"),
            (r'\|\s*sh\b', "pipe_to_shell"),
            (r'`[^`]+`', "command_substitution"),
            (r'\$\([^)]+\)', "command_substitution"),
            (r'>\s*/etc/', "system_file_write"),
            (r'eval\s*\(', "eval_injection"),
            (r'exec\s*\(', "exec_injection"),
        ]
    
    def check_args(
        self,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check tool arguments for safety.
        
        Returns:
            (is_safe, list of issues)
        """
        issues = []
        
        for key, value in args.items():
            if isinstance(value, str):
                for pattern, issue_type in self.dangerous_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        issues.append(
                            f"Dangerous pattern in {tool_name}.{key}: {issue_type}"
                        )
        
        return len(issues) == 0, issues
    
    def sanitize_args(
        self,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Remove or escape dangerous patterns from args."""
        sanitized = {}
        
        for key, value in args.items():
            if isinstance(value, str):
                # Escape shell metacharacters
                sanitized[key] = re.sub(r'[;&|`$(){}]', '', value)
            else:
                sanitized[key] = value
        
        return sanitized


class ErrorHandler:
    """
    Handles errors with structured taxonomy and recovery.
    """
    
    def __init__(self):
        self.error_history: List[StructuredError] = []
        self.recovery_strategies: Dict[ErrorCategory, List[RecoveryAction]] = {
            ErrorCategory.VALIDATION: [
                RecoveryAction.REQUEST_INFO,
                RecoveryAction.RELAX_CONSTRAINTS,
                RecoveryAction.SKIP
            ],
            ErrorCategory.PARSING: [
                RecoveryAction.RETRY,
                RecoveryAction.FALLBACK,
                RecoveryAction.SKIP
            ],
            ErrorCategory.INFERENCE: [
                RecoveryAction.RETRY,
                RecoveryAction.FALLBACK,
                RecoveryAction.DEGRADE_GRACEFULLY
            ],
            ErrorCategory.TOOL_EXECUTION: [
                RecoveryAction.RETRY,
                RecoveryAction.FALLBACK,
                RecoveryAction.SKIP
            ],
            ErrorCategory.CONSTRAINT_VIOLATION: [
                RecoveryAction.RELAX_CONSTRAINTS,
                RecoveryAction.REQUEST_INFO,
                RecoveryAction.ESCALATE
            ],
            ErrorCategory.TIMEOUT: [
                RecoveryAction.RETRY,
                RecoveryAction.USE_CACHE,
                RecoveryAction.DEGRADE_GRACEFULLY
            ],
            ErrorCategory.RESOURCE_LIMIT: [
                RecoveryAction.DEGRADE_GRACEFULLY,
                RecoveryAction.SKIP,
                RecoveryAction.ABORT
            ],
            ErrorCategory.SAFETY_VIOLATION: [
                RecoveryAction.ABORT,
                RecoveryAction.ESCALATE
            ],
            ErrorCategory.EVIDENCE_INSUFFICIENT: [
                RecoveryAction.REQUEST_INFO,
                RecoveryAction.RELAX_CONSTRAINTS,
                RecoveryAction.DEGRADE_GRACEFULLY
            ],
            ErrorCategory.STATE_CONFLICT: [
                RecoveryAction.RETRY,
                RecoveryAction.FALLBACK,
                RecoveryAction.ESCALATE
            ],
        }
    
    def create_error(
        self,
        category: ErrorCategory,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        source_component: str = "",
        details: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> StructuredError:
        """Create a structured error."""
        import hashlib
        error_id = hashlib.sha256(
            f"{category.value}{message}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        recovery_suggestions = self.recovery_strategies.get(
            category, [RecoveryAction.ESCALATE]
        )
        
        is_recoverable = severity not in (ErrorSeverity.FATAL, ErrorSeverity.CRITICAL)
        
        error = StructuredError(
            error_id=error_id,
            category=category,
            severity=severity,
            message=message,
            details=details or {},
            source_component=source_component,
            recovery_suggestions=recovery_suggestions,
            is_recoverable=is_recoverable,
            context=context or {}
        )
        
        self.error_history.append(error)
        return error
    
    def attempt_recovery(
        self,
        error: StructuredError,
        recovery_fn: Optional[Callable[[RecoveryAction], Optional[Dict[str, Any]]]] = None
    ) -> RecoveryResult:
        """Attempt to recover from an error."""
        if not error.is_recoverable:
            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.ABORT,
                message="Error is not recoverable"
            )
        
        if error.retry_count >= error.max_retries:
            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.ABORT,
                message="Max retries exceeded"
            )
        
        # Try recovery actions in order
        for action in error.recovery_suggestions:
            if recovery_fn:
                result = recovery_fn(action)
                if result is not None:
                    error.retry_count += 1
                    return RecoveryResult(
                        success=True,
                        action_taken=action,
                        message=f"Recovery succeeded with {action.value}",
                        new_state=result
                    )
            else:
                # Default recovery behavior
                if action == RecoveryAction.SKIP:
                    return RecoveryResult(
                        success=True,
                        action_taken=action,
                        message="Skipped failed operation",
                        warnings=["Operation skipped due to error"]
                    )
                elif action == RecoveryAction.DEGRADE_GRACEFULLY:
                    return RecoveryResult(
                        success=True,
                        action_taken=action,
                        message="Degraded to simpler operation",
                        warnings=["Operating in degraded mode"]
                    )
        
        return RecoveryResult(
            success=False,
            action_taken=RecoveryAction.ESCALATE,
            message="All recovery actions failed, escalating"
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get statistics on errors."""
        by_category = {}
        by_severity = {}
        
        for error in self.error_history:
            cat = error.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            sev = error.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        return {
            "total_errors": len(self.error_history),
            "by_category": by_category,
            "by_severity": by_severity,
            "recoverable": sum(1 for e in self.error_history if e.is_recoverable)
        }


class SafetyGate:
    """
    Gate that validates safety before critical operations.
    """
    
    def __init__(
        self,
        input_sanitizer: Optional[InputSanitizer] = None,
        output_guard: Optional[OutputGuard] = None,
        tool_sanitizer: Optional[ToolArgsSanitizer] = None
    ):
        self.input_sanitizer = input_sanitizer or InputSanitizer()
        self.output_guard = output_guard or OutputGuard()
        self.tool_sanitizer = tool_sanitizer or ToolArgsSanitizer()
    
    def check_input(self, input_text: str) -> Tuple[bool, str, List[str]]:
        """Check if input is safe to process."""
        result = self.input_sanitizer.sanitize(input_text)
        warnings = [v.description for v in result.violations_found]
        return result.is_safe, result.sanitized, warnings
    
    def check_output(self, output: str) -> Tuple[bool, str, List[str]]:
        """Check if output is safe to emit."""
        return self.output_guard.check(output)
    
    def check_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Check if tool call is safe."""
        is_safe, issues = self.tool_sanitizer.check_args(tool_name, args)
        
        if not is_safe:
            # Try sanitization
            sanitized_args = self.tool_sanitizer.sanitize_args(args)
            return False, sanitized_args, issues
        
        return True, args, []
    
    def full_check(
        self,
        input_text: Optional[str] = None,
        output: Optional[str] = None,
        tool_call: Optional[Tuple[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run full safety check."""
        results = {
            "all_safe": True,
            "warnings": []
        }
        
        if input_text:
            is_safe, sanitized, warnings = self.check_input(input_text)
            results["input"] = {
                "safe": is_safe,
                "sanitized": sanitized,
                "warnings": warnings
            }
            if not is_safe:
                results["all_safe"] = False
            results["warnings"].extend(warnings)
        
        if output:
            is_safe, sanitized, warnings = self.check_output(output)
            results["output"] = {
                "safe": is_safe,
                "sanitized": sanitized,
                "warnings": warnings
            }
            if not is_safe:
                results["all_safe"] = False
            results["warnings"].extend(warnings)
        
        if tool_call:
            tool_name, args = tool_call
            is_safe, sanitized_args, issues = self.check_tool_call(tool_name, args)
            results["tool_call"] = {
                "safe": is_safe,
                "sanitized_args": sanitized_args,
                "issues": issues
            }
            if not is_safe:
                results["all_safe"] = False
            results["warnings"].extend(issues)
        
        return results
