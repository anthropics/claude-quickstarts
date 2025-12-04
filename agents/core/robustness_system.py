"""
Robustness System - Phase 2

Implements:
- Input validation and sanitization
- Output guardrails
- Circuit breakers for long inference
- Rate limiting and resource management
"""

from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re
import time
import threading
from functools import wraps


class ValidationResult(Enum):
    """Result of input validation."""
    VALID = "valid"
    INVALID = "invalid"
    SANITIZED = "sanitized"
    REJECTED = "rejected"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class GuardrailType(Enum):
    """Types of output guardrails."""
    CONTENT = "content"  # Content filtering
    LENGTH = "length"  # Length limits
    FORMAT = "format"  # Format requirements
    SAFETY = "safety"  # Safety checks


@dataclass
class ValidationReport:
    """Report from input validation."""
    result: ValidationResult
    original_input: str
    sanitized_input: Optional[str]
    issues_found: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GuardrailReport:
    """Report from output guardrail check."""
    passed: bool
    guardrail_type: GuardrailType
    original_output: str
    filtered_output: Optional[str]
    violations: List[str]


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[str]
    last_state_change: str
    total_rejected: int


class InputValidator:
    """
    Validates and sanitizes input.
    """
    
    def __init__(self):
        self.max_input_length = 10000
        self.forbidden_patterns: List[re.Pattern] = []
        self.required_patterns: List[re.Pattern] = []
        
        # Add default forbidden patterns
        self._add_default_patterns()
    
    def _add_default_patterns(self) -> None:
        """Add default security patterns."""
        # Potential injection patterns
        self.forbidden_patterns.extend([
            re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE),  # Event handlers
            re.compile(r"\{\{.*?\}\}"),  # Template injection
            re.compile(r"\$\{.*?\}"),  # Template literals
        ])
    
    def add_forbidden_pattern(self, pattern: str) -> None:
        """Add a forbidden regex pattern."""
        self.forbidden_patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def add_required_pattern(self, pattern: str) -> None:
        """Add a required regex pattern."""
        self.required_patterns.append(re.compile(pattern))
    
    def validate(
        self,
        input_text: str,
        sanitize: bool = True
    ) -> ValidationReport:
        """Validate and optionally sanitize input."""
        issues = []
        sanitized = input_text
        
        # Check length
        if len(input_text) > self.max_input_length:
            issues.append(f"Input exceeds maximum length ({self.max_input_length})")
            if sanitize:
                sanitized = input_text[:self.max_input_length]
            else:
                return ValidationReport(
                    result=ValidationResult.REJECTED,
                    original_input=input_text[:100] + "...",
                    sanitized_input=None,
                    issues_found=issues
                )
        
        # Check forbidden patterns
        for pattern in self.forbidden_patterns:
            matches = pattern.findall(sanitized)
            if matches:
                issues.append(f"Forbidden pattern found: {pattern.pattern[:50]}")
                if sanitize:
                    sanitized = pattern.sub("", sanitized)
                else:
                    return ValidationReport(
                        result=ValidationResult.REJECTED,
                        original_input=input_text[:500],
                        sanitized_input=None,
                        issues_found=issues
                    )
        
        # Check required patterns
        for pattern in self.required_patterns:
            if not pattern.search(sanitized):
                issues.append(f"Required pattern not found: {pattern.pattern[:50]}")
        
        # Check for empty after sanitization
        if sanitize and not sanitized.strip():
            return ValidationReport(
                result=ValidationResult.REJECTED,
                original_input=input_text[:500],
                sanitized_input=None,
                issues_found=["Input empty after sanitization"]
            )
        
        # Determine result
        if not issues:
            result = ValidationResult.VALID
        elif sanitize and sanitized != input_text:
            result = ValidationResult.SANITIZED
        else:
            result = ValidationResult.INVALID
        
        return ValidationReport(
            result=result,
            original_input=input_text[:500],
            sanitized_input=sanitized if sanitize else None,
            issues_found=issues
        )
    
    def sanitize_for_logging(self, text: str, max_length: int = 500) -> str:
        """Sanitize text for safe logging."""
        # Remove potential secrets
        sanitized = re.sub(r"(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", 
                          r"\1=***", text, flags=re.IGNORECASE)
        
        # Truncate
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
        
        return sanitized


class OutputGuardrail:
    """
    Guardrails for output content.
    """
    
    def __init__(self):
        self.max_output_length = 50000
        self.content_filters: List[re.Pattern] = []
        self.required_disclaimers: List[str] = []
        
        self._add_default_filters()
    
    def _add_default_filters(self) -> None:
        """Add default content filters."""
        # Potentially harmful content patterns
        self.content_filters.extend([
            re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),
            re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
            re.compile(r"secret[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
        ])
    
    def add_content_filter(self, pattern: str) -> None:
        """Add a content filter pattern."""
        self.content_filters.append(re.compile(pattern, re.IGNORECASE))
    
    def add_required_disclaimer(self, disclaimer: str) -> None:
        """Add a required disclaimer."""
        self.required_disclaimers.append(disclaimer)
    
    def check(
        self,
        output: str,
        filter_violations: bool = True
    ) -> GuardrailReport:
        """Check output against guardrails."""
        violations = []
        filtered = output
        
        # Check length
        if len(output) > self.max_output_length:
            violations.append(f"Output exceeds maximum length ({self.max_output_length})")
            if filter_violations:
                filtered = output[:self.max_output_length]
        
        # Check content filters
        for pattern in self.content_filters:
            matches = pattern.findall(filtered)
            if matches:
                violations.append(f"Sensitive content detected: {pattern.pattern[:30]}")
                if filter_violations:
                    filtered = pattern.sub("[REDACTED]", filtered)
        
        # Check required disclaimers
        for disclaimer in self.required_disclaimers:
            if disclaimer.lower() not in filtered.lower():
                violations.append(f"Missing required disclaimer")
                if filter_violations:
                    filtered = f"{filtered}\n\n*{disclaimer}*"
        
        return GuardrailReport(
            passed=len(violations) == 0,
            guardrail_type=GuardrailType.CONTENT,
            original_output=output[:1000] if len(output) > 1000 else output,
            filtered_output=filtered if filter_violations else None,
            violations=violations
        )
    
    def check_format(
        self,
        output: str,
        expected_format: str
    ) -> GuardrailReport:
        """Check output format."""
        violations = []
        
        if expected_format == "json":
            try:
                import json
                json.loads(output)
            except json.JSONDecodeError as e:
                violations.append(f"Invalid JSON: {str(e)[:100]}")
        
        elif expected_format == "markdown":
            # Basic markdown validation
            if not re.search(r"[#*`\[\]]", output):
                violations.append("Output may not be properly formatted as markdown")
        
        return GuardrailReport(
            passed=len(violations) == 0,
            guardrail_type=GuardrailType.FORMAT,
            original_output=output[:500],
            filtered_output=None,
            violations=violations
        )


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change = time.time()
        self.total_rejected = 0
        
        self._lock = threading.Lock()
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        self.state = new_state
        self.last_state_change = time.time()
        
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            elif self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self.last_failure_time:
                    elapsed = time.time() - self.last_failure_time
                    if elapsed >= self.recovery_timeout:
                        self._transition_to(CircuitState.HALF_OPEN)
                        return True
                
                self.total_rejected += 1
                return False
            
            elif self.state == CircuitState.HALF_OPEN:
                # Allow limited calls
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False
        
        return False
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self.success_count += 1
            
            if self.state == CircuitState.HALF_OPEN:
                # Transition back to closed after successful recovery
                if self.success_count >= self.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
    
    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Transition back to open on failure
                self._transition_to(CircuitState.OPEN)
            
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        with self._lock:
            return CircuitBreakerStats(
                state=self.state,
                failure_count=self.failure_count,
                success_count=self.success_count,
                last_failure_time=datetime.fromtimestamp(self.last_failure_time).isoformat() 
                                  if self.last_failure_time else None,
                last_state_change=datetime.fromtimestamp(self.last_state_change).isoformat(),
                total_rejected=self.total_rejected
            )
    
    def reset(self) -> None:
        """Reset the circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self.last_failure_time = None
            self.total_rejected = 0


class RateLimiter:
    """
    Token bucket rate limiter.
    """
    
    def __init__(
        self,
        rate: float = 10.0,  # Requests per second
        burst: int = 20  # Maximum burst size
    ):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        with self._lock:
            self._add_tokens()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_for_token(self, timeout: float = 10.0) -> bool:
        """Wait for a token to become available."""
        start = time.time()
        
        while time.time() - start < timeout:
            if self.try_acquire():
                return True
            time.sleep(0.1)
        
        return False
    
    def get_wait_time(self) -> float:
        """Get estimated wait time for next token."""
        with self._lock:
            self._add_tokens()
            
            if self.tokens >= 1:
                return 0.0
            
            needed = 1 - self.tokens
            return needed / self.rate


class TimeoutManager:
    """
    Manages timeouts for long-running operations.
    """
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self.operation_timeouts: Dict[str, float] = {}
    
    def set_timeout(self, operation: str, timeout: float) -> None:
        """Set timeout for a specific operation."""
        self.operation_timeouts[operation] = timeout
    
    def get_timeout(self, operation: str) -> float:
        """Get timeout for an operation."""
        return self.operation_timeouts.get(operation, self.default_timeout)
    
    def with_timeout(self, operation: str):
        """Decorator for adding timeout to functions."""
        timeout = self.get_timeout(operation)
        
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                import concurrent.futures
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        return future.result(timeout=timeout)
                    except concurrent.futures.TimeoutError:
                        raise TimeoutError(
                            f"Operation '{operation}' timed out after {timeout}s"
                        )
            return wrapper
        return decorator


class ResourceManager:
    """
    Manages resource limits and quotas.
    """
    
    def __init__(self):
        self.limits: Dict[str, int] = {}
        self.usage: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def set_limit(self, resource: str, limit: int) -> None:
        """Set limit for a resource."""
        with self._lock:
            self.limits[resource] = limit
            if resource not in self.usage:
                self.usage[resource] = 0
    
    def try_acquire(self, resource: str, amount: int = 1) -> bool:
        """Try to acquire resource."""
        with self._lock:
            if resource not in self.limits:
                return True
            
            current = self.usage.get(resource, 0)
            limit = self.limits[resource]
            
            if current + amount <= limit:
                self.usage[resource] = current + amount
                return True
            return False
    
    def release(self, resource: str, amount: int = 1) -> None:
        """Release resource."""
        with self._lock:
            if resource in self.usage:
                self.usage[resource] = max(0, self.usage[resource] - amount)
    
    def get_usage(self, resource: str) -> Dict[str, int]:
        """Get usage for a resource."""
        with self._lock:
            return {
                "current": self.usage.get(resource, 0),
                "limit": self.limits.get(resource, -1),
                "available": self.limits.get(resource, -1) - self.usage.get(resource, 0)
            }
    
    def reset(self, resource: Optional[str] = None) -> None:
        """Reset resource usage."""
        with self._lock:
            if resource:
                self.usage[resource] = 0
            else:
                self.usage = {r: 0 for r in self.usage}


class RobustnessSystem:
    """
    Complete robustness system.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        rate_limit: float = 10.0,
        default_timeout: float = 30.0
    ):
        self.validator = InputValidator()
        self.guardrail = OutputGuardrail()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self.rate_limiter = RateLimiter(rate=rate_limit)
        self.timeout_manager = TimeoutManager(default_timeout=default_timeout)
        self.resource_manager = ResourceManager()
        
        # Set default resource limits
        self.resource_manager.set_limit("concurrent_requests", 100)
        self.resource_manager.set_limit("tokens_per_minute", 100000)
    
    def validate_request(
        self,
        input_text: str,
        sanitize: bool = True
    ) -> tuple:
        """
        Validate incoming request.
        
        Returns (is_valid, processed_input, report)
        """
        # Check rate limit
        if not self.rate_limiter.try_acquire():
            return False, None, {"error": "Rate limit exceeded"}
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            return False, None, {"error": "Service temporarily unavailable"}
        
        # Validate input
        report = self.validator.validate(input_text, sanitize)
        
        if report.result == ValidationResult.REJECTED:
            return False, None, {
                "error": "Input rejected",
                "issues": report.issues_found
            }
        
        processed = report.sanitized_input if sanitize else input_text
        return True, processed, {
            "validation": report.result.value,
            "issues": report.issues_found
        }
    
    def process_response(
        self,
        output: str,
        filter_violations: bool = True
    ) -> tuple:
        """
        Process and validate response.
        
        Returns (processed_output, report)
        """
        report = self.guardrail.check(output, filter_violations)
        
        processed = report.filtered_output if filter_violations else output
        
        return processed, {
            "passed": report.passed,
            "violations": report.violations
        }
    
    def record_success(self) -> None:
        """Record successful operation."""
        self.circuit_breaker.record_success()
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.circuit_breaker.record_failure()
    
    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        cb_stats = self.circuit_breaker.get_stats()
        
        return {
            "circuit_breaker": {
                "state": cb_stats.state.value,
                "failure_count": cb_stats.failure_count,
                "total_rejected": cb_stats.total_rejected
            },
            "rate_limiter": {
                "wait_time": self.rate_limiter.get_wait_time()
            },
            "resources": {
                r: self.resource_manager.get_usage(r)
                for r in self.resource_manager.limits
            }
        }
    
    def safe_execute(
        self,
        func: Callable,
        input_text: str,
        operation: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Safely execute a function with all protections.
        """
        # Validate request
        is_valid, processed_input, validation_report = self.validate_request(input_text)
        
        if not is_valid:
            return {
                "success": False,
                "error": validation_report.get("error"),
                "validation": validation_report
            }
        
        # Try to acquire resources
        if not self.resource_manager.try_acquire("concurrent_requests"):
            return {
                "success": False,
                "error": "Resource limit exceeded"
            }
        
        try:
            # Execute with timeout
            timeout = self.timeout_manager.get_timeout(operation)
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, processed_input, **kwargs)
                try:
                    result = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    self.record_failure()
                    return {
                        "success": False,
                        "error": f"Operation timed out after {timeout}s"
                    }
            
            # Process response
            if isinstance(result, str):
                processed_output, output_report = self.process_response(result)
                self.record_success()
                
                return {
                    "success": True,
                    "output": processed_output,
                    "validation": validation_report,
                    "guardrail": output_report
                }
            else:
                self.record_success()
                return {
                    "success": True,
                    "output": result,
                    "validation": validation_report
                }
                
        except Exception as e:
            self.record_failure()
            return {
                "success": False,
                "error": str(e),
                "validation": validation_report
            }
        finally:
            self.resource_manager.release("concurrent_requests")
