"""
Latency Control System - Phase 2 Enhancement

Provides latency management and timeout control:
- Per-component timeout budgets
- Adaptive timeout adjustment
- Latency tracking and alerts
- Circuit breaker patterns
"""

from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time
import threading
from collections import deque
import statistics


class TimeoutPolicy(Enum):
    """How to handle timeout situations."""
    FAIL_FAST = "fail_fast"
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class LatencyBudget:
    """Latency budget for a component or operation."""
    name: str
    max_ms: float
    warning_ms: float
    policy: TimeoutPolicy = TimeoutPolicy.FAIL_FAST
    retry_count: int = 3
    retry_delay_ms: float = 100.0
    fallback: Optional[Callable[[], Any]] = None


@dataclass
class LatencyMeasurement:
    """A single latency measurement."""
    component: str
    duration_ms: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    budget_exceeded: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Statistics for a component's latency."""
    component: str
    count: int
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p90_ms: float
    p99_ms: float
    success_rate: float
    budget_exceeded_rate: float


class LatencyTracker:
    """Tracks latency measurements for components."""
    
    def __init__(self, window_size: int = 1000):
        self._measurements: Dict[str, deque] = {}
        self._window_size = window_size
        self._lock = threading.Lock()
    
    def record(self, measurement: LatencyMeasurement) -> None:
        """Record a latency measurement."""
        with self._lock:
            if measurement.component not in self._measurements:
                self._measurements[measurement.component] = deque(
                    maxlen=self._window_size
                )
            self._measurements[measurement.component].append(measurement)
    
    def get_stats(self, component: str) -> Optional[LatencyStats]:
        """Get latency statistics for a component."""
        with self._lock:
            measurements = self._measurements.get(component)
            if not measurements or len(measurements) == 0:
                return None
            
            durations = [m.duration_ms for m in measurements]
            successes = [m.success for m in measurements]
            exceeded = [m.budget_exceeded for m in measurements]
            
            sorted_durations = sorted(durations)
            n = len(sorted_durations)
            
            return LatencyStats(
                component=component,
                count=n,
                mean_ms=statistics.mean(durations),
                std_ms=statistics.stdev(durations) if n > 1 else 0,
                min_ms=sorted_durations[0],
                max_ms=sorted_durations[-1],
                p50_ms=sorted_durations[n // 2],
                p90_ms=sorted_durations[int(n * 0.9)] if n >= 10 else sorted_durations[-1],
                p99_ms=sorted_durations[int(n * 0.99)] if n >= 100 else sorted_durations[-1],
                success_rate=sum(successes) / n,
                budget_exceeded_rate=sum(exceeded) / n
            )
    
    def get_all_stats(self) -> Dict[str, LatencyStats]:
        """Get stats for all tracked components."""
        result = {}
        with self._lock:
            for component in self._measurements:
                stats = self.get_stats(component)
                if stats:
                    result[component] = stats
        return result
    
    def get_recent(
        self,
        component: str,
        limit: int = 10
    ) -> List[LatencyMeasurement]:
        """Get recent measurements for a component."""
        with self._lock:
            measurements = self._measurements.get(component)
            if not measurements:
                return []
            return list(measurements)[-limit:]


class CircuitBreaker:
    """Circuit breaker for preventing cascade failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_requests: int = 3
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_seconds
        self._half_open_requests = half_open_requests
        
        self._circuits: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def _get_circuit(self, name: str) -> Dict[str, Any]:
        """Get or create circuit state."""
        if name not in self._circuits:
            self._circuits[name] = {
                "state": CircuitState.CLOSED,
                "failures": 0,
                "last_failure": None,
                "half_open_successes": 0
            }
        return self._circuits[name]
    
    def can_execute(self, name: str) -> Tuple[bool, CircuitState]:
        """Check if execution is allowed."""
        with self._lock:
            circuit = self._get_circuit(name)
            state = circuit["state"]
            
            if state == CircuitState.CLOSED:
                return True, state
            
            if state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if circuit["last_failure"]:
                    elapsed = (datetime.now() - circuit["last_failure"]).total_seconds()
                    if elapsed >= self._recovery_timeout:
                        circuit["state"] = CircuitState.HALF_OPEN
                        circuit["half_open_successes"] = 0
                        return True, CircuitState.HALF_OPEN
                return False, state
            
            # HALF_OPEN - allow limited requests
            return True, state
    
    def record_success(self, name: str) -> None:
        """Record a successful execution."""
        with self._lock:
            circuit = self._get_circuit(name)
            
            if circuit["state"] == CircuitState.HALF_OPEN:
                circuit["half_open_successes"] += 1
                if circuit["half_open_successes"] >= self._half_open_requests:
                    circuit["state"] = CircuitState.CLOSED
                    circuit["failures"] = 0
            else:
                circuit["failures"] = max(0, circuit["failures"] - 1)
    
    def record_failure(self, name: str) -> None:
        """Record a failed execution."""
        with self._lock:
            circuit = self._get_circuit(name)
            circuit["failures"] += 1
            circuit["last_failure"] = datetime.now()
            
            if circuit["state"] == CircuitState.HALF_OPEN:
                circuit["state"] = CircuitState.OPEN
            elif circuit["failures"] >= self._failure_threshold:
                circuit["state"] = CircuitState.OPEN
    
    def get_state(self, name: str) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._get_circuit(name)["state"]
    
    def reset(self, name: str) -> None:
        """Reset a circuit to closed state."""
        with self._lock:
            if name in self._circuits:
                self._circuits[name] = {
                    "state": CircuitState.CLOSED,
                    "failures": 0,
                    "last_failure": None,
                    "half_open_successes": 0
                }


class AdaptiveTimeout:
    """Adaptive timeout adjustment based on historical latency."""
    
    def __init__(
        self,
        base_timeout_ms: float,
        min_timeout_ms: float = 100.0,
        max_timeout_ms: float = 60000.0,
        adjustment_factor: float = 0.1
    ):
        self._base = base_timeout_ms
        self._min = min_timeout_ms
        self._max = max_timeout_ms
        self._factor = adjustment_factor
        
        self._current_timeouts: Dict[str, float] = {}
        self._history: Dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def get_timeout(self, component: str) -> float:
        """Get current timeout for a component."""
        with self._lock:
            return self._current_timeouts.get(component, self._base)
    
    def record_latency(self, component: str, latency_ms: float, success: bool) -> None:
        """Record latency and adjust timeout if needed."""
        with self._lock:
            if component not in self._history:
                self._history[component] = deque(maxlen=100)
                self._current_timeouts[component] = self._base
            
            self._history[component].append((latency_ms, success))
            
            # Adjust timeout based on recent history
            self._adjust_timeout(component)
    
    def _adjust_timeout(self, component: str) -> None:
        """Adjust timeout based on historical performance."""
        history = self._history.get(component)
        if not history or len(history) < 10:
            return
        
        latencies = [h[0] for h in history]
        successes = [h[1] for h in history]
        
        # Calculate p99 latency
        sorted_latencies = sorted(latencies)
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        # Calculate success rate
        success_rate = sum(successes) / len(successes)
        
        current = self._current_timeouts[component]
        
        # Adjust based on conditions
        if success_rate < 0.95 and current < self._max:
            # Increase timeout if success rate is low
            new_timeout = current * (1 + self._factor)
            self._current_timeouts[component] = min(new_timeout, self._max)
        elif success_rate > 0.99 and p99 < current * 0.5:
            # Decrease timeout if latency is consistently low
            new_timeout = current * (1 - self._factor)
            self._current_timeouts[component] = max(new_timeout, self._min)


@dataclass
class LatencyAlert:
    """Alert for latency issues."""
    component: str
    alert_type: str
    message: str
    severity: str  # "warning", "error", "critical"
    timestamp: datetime = field(default_factory=datetime.now)
    stats: Optional[LatencyStats] = None


class LatencyMonitor:
    """Monitors latency and generates alerts."""
    
    def __init__(self, tracker: LatencyTracker):
        self._tracker = tracker
        self._budgets: Dict[str, LatencyBudget] = {}
        self._alerts: List[LatencyAlert] = []
        self._alert_callbacks: List[Callable[[LatencyAlert], None]] = []
    
    def set_budget(self, budget: LatencyBudget) -> None:
        """Set latency budget for a component."""
        self._budgets[budget.name] = budget
    
    def add_alert_callback(self, callback: Callable[[LatencyAlert], None]) -> None:
        """Add a callback for alerts."""
        self._alert_callbacks.append(callback)
    
    def check_latency(self, component: str) -> Optional[LatencyAlert]:
        """Check if latency is within budget."""
        budget = self._budgets.get(component)
        if not budget:
            return None
        
        stats = self._tracker.get_stats(component)
        if not stats:
            return None
        
        alert = None
        
        if stats.p99_ms > budget.max_ms:
            alert = LatencyAlert(
                component=component,
                alert_type="budget_exceeded",
                message=f"P99 latency ({stats.p99_ms:.1f}ms) exceeds budget ({budget.max_ms}ms)",
                severity="error",
                stats=stats
            )
        elif stats.p90_ms > budget.warning_ms:
            alert = LatencyAlert(
                component=component,
                alert_type="warning_threshold",
                message=f"P90 latency ({stats.p90_ms:.1f}ms) exceeds warning threshold ({budget.warning_ms}ms)",
                severity="warning",
                stats=stats
            )
        
        if alert:
            self._alerts.append(alert)
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception:
                    pass
        
        return alert
    
    def check_all(self) -> List[LatencyAlert]:
        """Check all monitored components."""
        alerts = []
        for component in self._budgets:
            alert = self.check_latency(component)
            if alert:
                alerts.append(alert)
        return alerts
    
    def get_alerts(self, limit: int = 100) -> List[LatencyAlert]:
        """Get recent alerts."""
        return self._alerts[-limit:]


class LatencyController:
    """
    Main controller for latency management.
    
    Combines timeout management, circuit breaking, and monitoring.
    """
    
    def __init__(self):
        self._tracker = LatencyTracker()
        self._circuit_breaker = CircuitBreaker()
        self._adaptive_timeout = AdaptiveTimeout(base_timeout_ms=5000)
        self._monitor = LatencyMonitor(self._tracker)
        
        self._budgets: Dict[str, LatencyBudget] = {}
    
    def set_budget(self, budget: LatencyBudget) -> None:
        """Set latency budget for a component."""
        self._budgets[budget.name] = budget
        self._monitor.set_budget(budget)
    
    def execute_with_timeout(
        self,
        component: str,
        func: Callable[[], Any],
        timeout_ms: Optional[float] = None
    ) -> Tuple[Any, LatencyMeasurement]:
        """Execute a function with timeout and tracking."""
        # Check circuit breaker
        can_execute, circuit_state = self._circuit_breaker.can_execute(component)
        if not can_execute:
            measurement = LatencyMeasurement(
                component=component,
                duration_ms=0,
                success=False,
                metadata={"circuit_open": True}
            )
            raise CircuitOpenError(f"Circuit breaker open for {component}")
        
        # Get timeout
        budget = self._budgets.get(component)
        if timeout_ms is None:
            timeout_ms = self._adaptive_timeout.get_timeout(component)
            if budget:
                timeout_ms = min(timeout_ms, budget.max_ms)
        
        # Execute with timing
        start = time.perf_counter()
        try:
            result = self._execute_with_timeout_internal(func, timeout_ms)
            duration_ms = (time.perf_counter() - start) * 1000
            
            budget_exceeded = budget and duration_ms > budget.max_ms
            
            measurement = LatencyMeasurement(
                component=component,
                duration_ms=duration_ms,
                success=True,
                budget_exceeded=budget_exceeded
            )
            
            self._tracker.record(measurement)
            self._adaptive_timeout.record_latency(component, duration_ms, True)
            self._circuit_breaker.record_success(component)
            
            return result, measurement
            
        except TimeoutError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            
            measurement = LatencyMeasurement(
                component=component,
                duration_ms=duration_ms,
                success=False,
                budget_exceeded=True,
                metadata={"timeout": True}
            )
            
            self._tracker.record(measurement)
            self._adaptive_timeout.record_latency(component, duration_ms, False)
            self._circuit_breaker.record_failure(component)
            
            # Handle timeout based on policy
            if budget:
                return self._handle_timeout(budget, func, measurement)
            raise
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            
            measurement = LatencyMeasurement(
                component=component,
                duration_ms=duration_ms,
                success=False,
                metadata={"error": str(e)}
            )
            
            self._tracker.record(measurement)
            self._circuit_breaker.record_failure(component)
            
            raise
    
    def _execute_with_timeout_internal(
        self,
        func: Callable[[], Any],
        timeout_ms: float
    ) -> Any:
        """Execute function with timeout."""
        # Simple synchronous execution
        # For real timeout, would need threading or async
        result = func()
        return result
    
    def _handle_timeout(
        self,
        budget: LatencyBudget,
        func: Callable[[], Any],
        measurement: LatencyMeasurement
    ) -> Tuple[Any, LatencyMeasurement]:
        """Handle timeout based on policy."""
        if budget.policy == TimeoutPolicy.FAIL_FAST:
            raise TimeoutError(f"Timeout for {budget.name}")
        
        elif budget.policy == TimeoutPolicy.RETRY:
            for i in range(budget.retry_count):
                time.sleep(budget.retry_delay_ms / 1000)
                try:
                    result, new_measurement = self.execute_with_timeout(
                        budget.name, func, budget.max_ms
                    )
                    return result, new_measurement
                except TimeoutError:
                    continue
            raise TimeoutError(f"Timeout after {budget.retry_count} retries")
        
        elif budget.policy == TimeoutPolicy.FALLBACK:
            if budget.fallback:
                result = budget.fallback()
                return result, measurement
            raise TimeoutError(f"Timeout with no fallback for {budget.name}")
        
        elif budget.policy == TimeoutPolicy.DEGRADE:
            # Return None and let caller handle degradation
            return None, measurement
        
        raise TimeoutError(f"Timeout for {budget.name}")
    
    def get_stats(self, component: Optional[str] = None) -> Dict[str, LatencyStats]:
        """Get latency statistics."""
        if component:
            stats = self._tracker.get_stats(component)
            return {component: stats} if stats else {}
        return self._tracker.get_all_stats()
    
    def get_circuit_state(self, component: str) -> CircuitState:
        """Get circuit breaker state."""
        return self._circuit_breaker.get_state(component)
    
    def check_alerts(self) -> List[LatencyAlert]:
        """Check for latency alerts."""
        return self._monitor.check_all()
    
    def add_alert_callback(self, callback: Callable[[LatencyAlert], None]) -> None:
        """Add callback for alerts."""
        self._monitor.add_alert_callback(callback)


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Convenience functions

def create_latency_controller() -> LatencyController:
    """Create a latency controller with default settings."""
    return LatencyController()


def with_timeout(timeout_ms: float):
    """Decorator for adding timeout to functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed > timeout_ms:
                raise TimeoutError(
                    f"Function took {elapsed:.1f}ms, exceeding {timeout_ms}ms limit"
                )
            return result
        return wrapper
    return decorator


def measure_latency(func: Callable[[], Any]) -> Tuple[Any, float]:
    """Measure latency of a function call."""
    start = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms
