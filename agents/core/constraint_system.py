"""
Constraint Enhancement System - Phase 2 Enhancement

Provides advanced constraint handling:
- Hard constraints (must/never) and soft constraints (prefer)
- Constraint relaxation paths
- Escalation when no options remain
- Constraint satisfaction checking
- Conflict detection and resolution
"""

from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import re


class ConstraintType(Enum):
    """Types of constraints."""
    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Preferred but can be relaxed
    BOUNDARY = "boundary"  # Defines valid range


class ConstraintPriority(Enum):
    """Priority levels for soft constraints."""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    OPTIONAL = 1


class RelaxationStrategy(Enum):
    """Strategies for constraint relaxation."""
    NONE = "none"  # No relaxation allowed
    THRESHOLD = "threshold"  # Relax boundary by percentage
    PRIORITY = "priority"  # Drop lower priority constraints
    ALTERNATIVE = "alternative"  # Use alternative constraint
    ESCALATE = "escalate"  # Escalate to user/supervisor


class EscalationLevel(Enum):
    """Escalation levels when constraints cannot be satisfied."""
    LOG_ONLY = 1
    WARN_USER = 2
    REQUIRE_CONFIRMATION = 3
    BLOCK_ACTION = 4
    EMERGENCY_STOP = 5


@dataclass
class ConstraintViolation:
    """Represents a constraint violation."""
    constraint_id: str
    constraint_name: str
    constraint_type: ConstraintType
    actual_value: Any
    expected_value: Any
    violation_severity: float  # 0-1, how far from satisfaction
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RelaxationPath:
    """A path for relaxing a constraint."""
    constraint_id: str
    original_value: Any
    relaxed_value: Any
    strategy: RelaxationStrategy
    cost: float  # Cost of this relaxation (0-1)
    justification: str


@dataclass
class EscalationRequest:
    """Request to escalate when constraints fail."""
    violations: List[ConstraintViolation]
    level: EscalationLevel
    context: Dict[str, Any]
    suggested_actions: List[str]
    requires_response: bool
    timeout_seconds: int = 60
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConstraintCheckResult:
    """Result of checking constraints."""
    satisfied: bool
    violations: List[ConstraintViolation]
    relaxation_paths: List[RelaxationPath]
    needs_escalation: bool
    escalation_request: Optional[EscalationRequest] = None


class Constraint:
    """Base constraint with simple condition evaluation."""
    
    def __init__(
        self,
        constraint_id: str,
        name: str,
        constraint_type: ConstraintType,
        condition: str = "",
        description: str = "",
        priority: ConstraintPriority = ConstraintPriority.MEDIUM,
        relaxation_strategy: RelaxationStrategy = RelaxationStrategy.NONE
    ):
        self.constraint_id = constraint_id
        self.name = name
        self.constraint_type = constraint_type
        self.condition = condition
        self.description = description or condition
        self.priority = priority
        self.relaxation_strategy = relaxation_strategy
        self.enabled = True
    
    def check(self, context: Dict[str, Any]) -> Tuple[bool, Optional[ConstraintViolation]]:
        """Check if constraint is satisfied. Returns (satisfied, violation)."""
        try:
            satisfied = bool(eval(self.condition, {}, context)) if self.condition else True
        except Exception:
            satisfied = False
        
        if satisfied:
            return True, None
        
        violation = ConstraintViolation(
            constraint_id=self.constraint_id,
            constraint_name=self.name,
            constraint_type=self.constraint_type,
            actual_value=None,
            expected_value=self.condition,
            violation_severity=1.0,
            message=f"Condition failed: {self.condition}"
        )
        return False, violation
    
    def get_relaxation_path(self, context: Dict[str, Any]) -> Optional[RelaxationPath]:
        """Default: no relaxation path."""
        return None


class ValueConstraint(Constraint):
    """Constraint on a specific value."""
    
    def __init__(
        self,
        constraint_id: str,
        name: str,
        field_path: str,
        operator: str,  # "eq", "ne", "lt", "le", "gt", "ge", "in", "not_in", "matches"
        expected_value: Any,
        constraint_type: ConstraintType = ConstraintType.HARD,
        priority: ConstraintPriority = ConstraintPriority.MEDIUM,
        relaxation_margin: float = 0.0  # For numeric relaxation
    ):
        super().__init__(
            constraint_id, name, constraint_type, 
            f"{field_path} {operator} {expected_value}",
            priority
        )
        self.field_path = field_path
        self.operator = operator
        self.expected_value = expected_value
        self.relaxation_margin = relaxation_margin
    
    def _get_value(self, context: Dict[str, Any]) -> Any:
        """Get value from context using field path."""
        parts = self.field_path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def check(self, context: Dict[str, Any]) -> Tuple[bool, Optional[ConstraintViolation]]:
        actual = self._get_value(context)
        satisfied = False
        severity = 1.0
        
        if self.operator == "eq":
            satisfied = actual == self.expected_value
        elif self.operator == "ne":
            satisfied = actual != self.expected_value
        elif self.operator == "lt":
            satisfied = actual < self.expected_value
            if not satisfied and actual is not None:
                severity = min(1.0, (actual - self.expected_value) / abs(self.expected_value + 1))
        elif self.operator == "le":
            satisfied = actual <= self.expected_value
            if not satisfied and actual is not None:
                severity = min(1.0, (actual - self.expected_value) / abs(self.expected_value + 1))
        elif self.operator == "gt":
            satisfied = actual > self.expected_value
            if not satisfied and actual is not None:
                severity = min(1.0, (self.expected_value - actual) / abs(self.expected_value + 1))
        elif self.operator == "ge":
            satisfied = actual >= self.expected_value
            if not satisfied and actual is not None:
                severity = min(1.0, (self.expected_value - actual) / abs(self.expected_value + 1))
        elif self.operator == "in":
            satisfied = actual in self.expected_value
        elif self.operator == "not_in":
            satisfied = actual not in self.expected_value
        elif self.operator == "matches":
            satisfied = bool(re.match(str(self.expected_value), str(actual or "")))
        
        if satisfied:
            return True, None
        
        violation = ConstraintViolation(
            constraint_id=self.constraint_id,
            constraint_name=self.name,
            constraint_type=self.constraint_type,
            actual_value=actual,
            expected_value=self.expected_value,
            violation_severity=severity,
            message=f"{self.field_path}: expected {self.operator} {self.expected_value}, got {actual}"
        )
        return False, violation
    
    def get_relaxation_path(self, context: Dict[str, Any]) -> Optional[RelaxationPath]:
        if self.constraint_type == ConstraintType.HARD:
            return None
        
        if self.relaxation_margin <= 0:
            return None
        
        if self.operator in ("lt", "le", "gt", "ge"):
            # Relax numeric boundary
            if self.operator in ("lt", "le"):
                relaxed = self.expected_value * (1 + self.relaxation_margin)
            else:
                relaxed = self.expected_value * (1 - self.relaxation_margin)
            
            return RelaxationPath(
                constraint_id=self.constraint_id,
                original_value=self.expected_value,
                relaxed_value=relaxed,
                strategy=RelaxationStrategy.THRESHOLD,
                cost=self.relaxation_margin,
                justification=f"Relaxed {self.field_path} boundary by {self.relaxation_margin*100}%"
            )
        
        return None


class CompositeConstraint(Constraint):
    """Constraint combining multiple sub-constraints."""
    
    def __init__(
        self,
        constraint_id: str,
        name: str,
        constraints: List[Constraint],
        mode: str = "all",  # "all" = AND, "any" = OR, "n_of" = at least N
        required_count: int = 1,  # For "n_of" mode
        constraint_type: ConstraintType = ConstraintType.HARD
    ):
        super().__init__(constraint_id, name, constraint_type)
        self.constraints = constraints
        self.mode = mode
        self.required_count = required_count
    
    def check(self, context: Dict[str, Any]) -> Tuple[bool, Optional[ConstraintViolation]]:
        results = []
        violations = []
        
        for constraint in self.constraints:
            satisfied, violation = constraint.check(context)
            results.append(satisfied)
            if violation:
                violations.append(violation)
        
        if self.mode == "all":
            satisfied = all(results)
        elif self.mode == "any":
            satisfied = any(results)
        else:  # n_of
            satisfied = sum(results) >= self.required_count
        
        if satisfied:
            return True, None
        
        # Create aggregate violation
        severity = sum(v.violation_severity for v in violations) / len(violations) if violations else 1.0
        violation = ConstraintViolation(
            constraint_id=self.constraint_id,
            constraint_name=self.name,
            constraint_type=self.constraint_type,
            actual_value=f"{sum(results)}/{len(self.constraints)} satisfied",
            expected_value=f"{self.mode}: {self.required_count if self.mode == 'n_of' else 'all/any'}",
            violation_severity=severity,
            message=f"Composite constraint failed: {len(violations)} sub-violations"
        )
        return False, violation
    
    def get_relaxation_path(self, context: Dict[str, Any]) -> Optional[RelaxationPath]:
        # Try to find relaxable sub-constraints
        paths = []
        for constraint in self.constraints:
            path = constraint.get_relaxation_path(context)
            if path:
                paths.append(path)
        
        if not paths:
            return None
        
        # Return lowest cost path
        paths.sort(key=lambda p: p.cost)
        return paths[0]


class TemporalConstraint(Constraint):
    """Constraint on timing/duration."""
    
    def __init__(
        self,
        constraint_id: str,
        name: str,
        field_path: str,
        max_duration_seconds: Optional[float] = None,
        min_duration_seconds: Optional[float] = None,
        deadline: Optional[str] = None,  # ISO format
        constraint_type: ConstraintType = ConstraintType.HARD
    ):
        super().__init__(constraint_id, name, constraint_type)
        self.field_path = field_path
        self.max_duration_seconds = max_duration_seconds
        self.min_duration_seconds = min_duration_seconds
        self.deadline = deadline
    
    def _get_value(self, context: Dict[str, Any]) -> Any:
        parts = self.field_path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def check(self, context: Dict[str, Any]) -> Tuple[bool, Optional[ConstraintViolation]]:
        value = self._get_value(context)
        
        violations = []
        
        # Check duration
        if isinstance(value, (int, float)):
            if self.max_duration_seconds and value > self.max_duration_seconds:
                violations.append(f"Duration {value}s exceeds max {self.max_duration_seconds}s")
            if self.min_duration_seconds and value < self.min_duration_seconds:
                violations.append(f"Duration {value}s below min {self.min_duration_seconds}s")
        
        # Check deadline
        if self.deadline and isinstance(value, str):
            try:
                current = datetime.fromisoformat(value)
                deadline_dt = datetime.fromisoformat(self.deadline)
                if current > deadline_dt:
                    violations.append(f"Deadline {self.deadline} exceeded")
            except ValueError:
                pass
        
        if not violations:
            return True, None
        
        violation = ConstraintViolation(
            constraint_id=self.constraint_id,
            constraint_name=self.name,
            constraint_type=self.constraint_type,
            actual_value=value,
            expected_value=f"max={self.max_duration_seconds}, min={self.min_duration_seconds}, deadline={self.deadline}",
            violation_severity=0.8,
            message="; ".join(violations)
        )
        return False, violation
    
    def get_relaxation_path(self, context: Dict[str, Any]) -> Optional[RelaxationPath]:
        if self.constraint_type == ConstraintType.HARD:
            return None
        
        if self.max_duration_seconds:
            # Allow 20% more time
            relaxed = self.max_duration_seconds * 1.2
            return RelaxationPath(
                constraint_id=self.constraint_id,
                original_value=self.max_duration_seconds,
                relaxed_value=relaxed,
                strategy=RelaxationStrategy.THRESHOLD,
                cost=0.2,
                justification=f"Extended max duration from {self.max_duration_seconds}s to {relaxed}s"
            )
        
        return None


class ResourceConstraint(Constraint):
    """Constraint on resource usage."""
    
    def __init__(
        self,
        constraint_id: str,
        name: str,
        resource_type: str,  # "memory", "cpu", "tokens", "cost", "api_calls"
        max_value: Optional[float] = None,
        min_value: Optional[float] = None,
        budget: Optional[float] = None,
        constraint_type: ConstraintType = ConstraintType.HARD
    ):
        super().__init__(constraint_id, name, constraint_type)
        self.resource_type = resource_type
        self.max_value = max_value
        self.min_value = min_value
        self.budget = budget
    
    def check(self, context: Dict[str, Any]) -> Tuple[bool, Optional[ConstraintViolation]]:
        resources = context.get("resources", {})
        current = resources.get(self.resource_type, 0)
        
        satisfied = True
        issues = []
        severity = 0.0
        
        if self.max_value is not None and current > self.max_value:
            satisfied = False
            issues.append(f"exceeds max ({current} > {self.max_value})")
            severity = max(severity, (current - self.max_value) / self.max_value)
        
        if self.min_value is not None and current < self.min_value:
            satisfied = False
            issues.append(f"below min ({current} < {self.min_value})")
            severity = max(severity, (self.min_value - current) / self.min_value)
        
        if self.budget is not None:
            used = resources.get(f"{self.resource_type}_used", 0)
            if used > self.budget:
                satisfied = False
                issues.append(f"budget exceeded ({used} > {self.budget})")
                severity = max(severity, (used - self.budget) / self.budget)
        
        if satisfied:
            return True, None
        
        violation = ConstraintViolation(
            constraint_id=self.constraint_id,
            constraint_name=self.name,
            constraint_type=self.constraint_type,
            actual_value=current,
            expected_value=f"max={self.max_value}, min={self.min_value}, budget={self.budget}",
            violation_severity=min(1.0, severity),
            message=f"{self.resource_type}: {', '.join(issues)}"
        )
        return False, violation
    
    def get_relaxation_path(self, context: Dict[str, Any]) -> Optional[RelaxationPath]:
        if self.constraint_type == ConstraintType.HARD:
            return None
        
        if self.max_value:
            relaxed = self.max_value * 1.25
            return RelaxationPath(
                constraint_id=self.constraint_id,
                original_value=self.max_value,
                relaxed_value=relaxed,
                strategy=RelaxationStrategy.THRESHOLD,
                cost=0.25,
                justification=f"Increased {self.resource_type} limit by 25%"
            )
        
        if self.budget:
            relaxed = self.budget * 1.25
            return RelaxationPath(
                constraint_id=self.constraint_id,
                original_value=self.budget,
                relaxed_value=relaxed,
                strategy=RelaxationStrategy.THRESHOLD,
                cost=0.25,
                justification=f"Increased {self.resource_type} budget by 25%"
            )
        
        return None


class ConstraintEngine:
    """
    Main engine for constraint checking and management.
    
    Handles:
    - Constraint registration and organization
    - Constraint checking with violation detection
    - Relaxation path finding
    - Escalation when constraints fail
    """
    
    def __init__(self):
        self._constraints: Dict[str, Constraint] = {}
        self._constraint_groups: Dict[str, List[str]] = {}
        self._relaxation_history: List[RelaxationPath] = []
        self._escalation_handlers: Dict[EscalationLevel, Callable] = {}
    
    def register_constraint(
        self, 
        constraint: Constraint,
        group: Optional[str] = None
    ) -> None:
        """Register a constraint."""
        self._constraints[constraint.constraint_id] = constraint
        
        if group:
            if group not in self._constraint_groups:
                self._constraint_groups[group] = []
            self._constraint_groups[group].append(constraint.constraint_id)
    
    def remove_constraint(self, constraint_id: str) -> bool:
        """Remove a constraint."""
        if constraint_id in self._constraints:
            del self._constraints[constraint_id]
            # Remove from groups
            for group_ids in self._constraint_groups.values():
                if constraint_id in group_ids:
                    group_ids.remove(constraint_id)
            return True
        return False
    
    def enable_constraint(self, constraint_id: str) -> bool:
        """Enable a constraint."""
        if constraint_id in self._constraints:
            self._constraints[constraint_id].enabled = True
            return True
        return False
    
    def disable_constraint(self, constraint_id: str) -> bool:
        """Disable a constraint temporarily."""
        if constraint_id in self._constraints:
            self._constraints[constraint_id].enabled = False
            return True
        return False
    
    def register_escalation_handler(
        self, 
        level: EscalationLevel,
        handler: Callable[[EscalationRequest], bool]
    ) -> None:
        """Register a handler for escalation at a specific level."""
        self._escalation_handlers[level] = handler
    
    def check_all(
        self, 
        context: Dict[str, Any],
        allow_relaxation: bool = True
    ) -> ConstraintCheckResult:
        """Check all registered constraints."""
        violations = []
        relaxation_paths = []
        
        for constraint in self._constraints.values():
            if not constraint.enabled:
                continue
            
            satisfied, violation = constraint.check(context)
            
            if not satisfied and violation:
                violations.append(violation)
                
                # Try to find relaxation path
                if allow_relaxation:
                    path = constraint.get_relaxation_path(context)
                    if path:
                        relaxation_paths.append(path)
        
        # Determine if escalation is needed
        needs_escalation = False
        escalation_request = None
        
        # Count hard constraint violations
        hard_violations = [v for v in violations if v.constraint_type == ConstraintType.HARD]
        
        if hard_violations:
            # Check if we can relax any
            relaxable_hard = len([p for p in relaxation_paths 
                                  if any(v.constraint_id == p.constraint_id for v in hard_violations)])
            
            if len(hard_violations) > relaxable_hard:
                needs_escalation = True
                escalation_request = self._create_escalation_request(
                    hard_violations, context
                )
        
        return ConstraintCheckResult(
            satisfied=len(violations) == 0,
            violations=violations,
            relaxation_paths=relaxation_paths,
            needs_escalation=needs_escalation,
            escalation_request=escalation_request
        )
    
    def check_group(
        self, 
        group: str,
        context: Dict[str, Any]
    ) -> ConstraintCheckResult:
        """Check constraints in a specific group."""
        if group not in self._constraint_groups:
            return ConstraintCheckResult(
                satisfied=True,
                violations=[],
                relaxation_paths=[],
                needs_escalation=False
            )
        
        violations = []
        relaxation_paths = []
        
        for constraint_id in self._constraint_groups[group]:
            constraint = self._constraints.get(constraint_id)
            if not constraint or not constraint.enabled:
                continue
            
            satisfied, violation = constraint.check(context)
            
            if not satisfied and violation:
                violations.append(violation)
                path = constraint.get_relaxation_path(context)
                if path:
                    relaxation_paths.append(path)
        
        return ConstraintCheckResult(
            satisfied=len(violations) == 0,
            violations=violations,
            relaxation_paths=relaxation_paths,
            needs_escalation=False
        )
    
    def apply_relaxation(
        self, 
        path: RelaxationPath,
        context: Dict[str, Any]
    ) -> bool:
        """Apply a relaxation path to the context."""
        constraint = self._constraints.get(path.constraint_id)
        if not constraint:
            return False
        
        # Record relaxation
        self._relaxation_history.append(path)
        
        # Apply relaxation (update constraint threshold)
        if isinstance(constraint, ValueConstraint):
            constraint.expected_value = path.relaxed_value
            return True
        elif isinstance(constraint, TemporalConstraint):
            constraint.max_duration_seconds = path.relaxed_value
            return True
        elif isinstance(constraint, ResourceConstraint):
            if constraint.max_value:
                constraint.max_value = path.relaxed_value
            elif constraint.budget:
                constraint.budget = path.relaxed_value
            return True
        
        return False
    
    def find_satisfying_options(
        self,
        options: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Filter options to only those satisfying constraints."""
        satisfying = []
        
        for option in options:
            # Merge option into context for checking
            merged = {**context, **option}
            result = self.check_all(merged, allow_relaxation=False)
            
            if result.satisfied:
                satisfying.append(option)
        
        return satisfying
    
    def find_best_option_with_relaxation(
        self,
        options: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], List[RelaxationPath]]:
        """
        Find the best option, possibly with constraint relaxation.
        
        Returns (best_option, relaxations_needed) or (None, []) if impossible.
        """
        # First try without relaxation
        satisfying = self.find_satisfying_options(options, context)
        if satisfying:
            return satisfying[0], []
        
        # Try with relaxation
        best_option = None
        best_relaxations: List[RelaxationPath] = []
        best_cost = float('inf')
        
        for option in options:
            merged = {**context, **option}
            result = self.check_all(merged, allow_relaxation=True)
            
            if not result.needs_escalation and result.relaxation_paths:
                # Calculate total relaxation cost
                total_cost = sum(p.cost for p in result.relaxation_paths)
                
                if total_cost < best_cost:
                    best_cost = total_cost
                    best_option = option
                    best_relaxations = result.relaxation_paths
        
        return best_option, best_relaxations
    
    def _create_escalation_request(
        self,
        violations: List[ConstraintViolation],
        context: Dict[str, Any]
    ) -> EscalationRequest:
        """Create an escalation request for unresolvable violations."""
        # Determine escalation level based on severity
        max_severity = max(v.violation_severity for v in violations)
        
        if max_severity >= 0.9:
            level = EscalationLevel.EMERGENCY_STOP
        elif max_severity >= 0.7:
            level = EscalationLevel.BLOCK_ACTION
        elif max_severity >= 0.5:
            level = EscalationLevel.REQUIRE_CONFIRMATION
        elif max_severity >= 0.3:
            level = EscalationLevel.WARN_USER
        else:
            level = EscalationLevel.LOG_ONLY
        
        # Generate suggested actions
        suggestions = []
        for v in violations:
            if v.constraint_type == ConstraintType.HARD:
                suggestions.append(f"Modify input to satisfy: {v.constraint_name}")
            else:
                suggestions.append(f"Consider relaxing: {v.constraint_name}")
        
        return EscalationRequest(
            violations=violations,
            level=level,
            context=context,
            suggested_actions=suggestions,
            requires_response=level.value >= EscalationLevel.REQUIRE_CONFIRMATION.value
        )
    
    def handle_escalation(self, request: EscalationRequest) -> bool:
        """Handle an escalation request using registered handlers."""
        handler = self._escalation_handlers.get(request.level)
        if handler:
            return handler(request)
        
        # Default handling
        if request.level == EscalationLevel.EMERGENCY_STOP:
            raise RuntimeError(f"Emergency stop: {[v.message for v in request.violations]}")
        elif request.level == EscalationLevel.BLOCK_ACTION:
            return False
        
        return True  # Allow for lower levels
    
    def get_relaxation_history(self) -> List[RelaxationPath]:
        """Get history of relaxations applied."""
        return list(self._relaxation_history)
    
    def get_constraint_summary(self) -> Dict[str, Any]:
        """Get summary of registered constraints."""
        by_type = {t: 0 for t in ConstraintType}
        by_priority = {p: 0 for p in ConstraintPriority}
        
        for constraint in self._constraints.values():
            by_type[constraint.constraint_type] += 1
            by_priority[constraint.priority] += 1
        
        return {
            "total_constraints": len(self._constraints),
            "enabled_constraints": sum(1 for c in self._constraints.values() if c.enabled),
            "by_type": {t.value: c for t, c in by_type.items()},
            "by_priority": {p.name: c for p, c in by_priority.items()},
            "groups": {g: len(ids) for g, ids in self._constraint_groups.items()},
            "relaxations_applied": len(self._relaxation_history)
        }


class ConstraintBuilder:
    """Fluent builder for creating constraints."""
    
    def __init__(self, constraint_id: str, name: str):
        self._id = constraint_id
        self._name = name
        self._type = ConstraintType.HARD
        self._priority = ConstraintPriority.MEDIUM
        self._field_path: Optional[str] = None
        self._operator: Optional[str] = None
        self._value: Any = None
        self._relaxation_margin: float = 0.0
    
    def hard(self) -> 'ConstraintBuilder':
        """Make this a hard constraint."""
        self._type = ConstraintType.HARD
        return self
    
    def soft(self, priority: ConstraintPriority = ConstraintPriority.MEDIUM) -> 'ConstraintBuilder':
        """Make this a soft constraint."""
        self._type = ConstraintType.SOFT
        self._priority = priority
        return self
    
    def field(self, path: str) -> 'ConstraintBuilder':
        """Set the field path to check."""
        self._field_path = path
        return self
    
    def equals(self, value: Any) -> 'ConstraintBuilder':
        """Field must equal value."""
        self._operator = "eq"
        self._value = value
        return self
    
    def not_equals(self, value: Any) -> 'ConstraintBuilder':
        """Field must not equal value."""
        self._operator = "ne"
        self._value = value
        return self
    
    def less_than(self, value: float) -> 'ConstraintBuilder':
        """Field must be less than value."""
        self._operator = "lt"
        self._value = value
        return self
    
    def greater_than(self, value: float) -> 'ConstraintBuilder':
        """Field must be greater than value."""
        self._operator = "gt"
        self._value = value
        return self
    
    def in_list(self, values: List[Any]) -> 'ConstraintBuilder':
        """Field must be in list."""
        self._operator = "in"
        self._value = values
        return self
    
    def matches(self, pattern: str) -> 'ConstraintBuilder':
        """Field must match regex pattern."""
        self._operator = "matches"
        self._value = pattern
        return self
    
    def relaxable(self, margin: float = 0.1) -> 'ConstraintBuilder':
        """Allow relaxation by margin percentage."""
        self._relaxation_margin = margin
        return self
    
    def build(self) -> Constraint:
        """Build the constraint."""
        if not self._field_path or not self._operator:
            raise ValueError("Field path and operator are required")
        
        return ValueConstraint(
            constraint_id=self._id,
            name=self._name,
            field_path=self._field_path,
            operator=self._operator,
            expected_value=self._value,
            constraint_type=self._type,
            priority=self._priority,
            relaxation_margin=self._relaxation_margin
        )


# Convenience functions

def must(constraint_id: str, name: str) -> ConstraintBuilder:
    """Create a hard constraint builder."""
    return ConstraintBuilder(constraint_id, name).hard()


def prefer(constraint_id: str, name: str, priority: ConstraintPriority = ConstraintPriority.MEDIUM) -> ConstraintBuilder:
    """Create a soft constraint builder."""
    return ConstraintBuilder(constraint_id, name).soft(priority)


def create_standard_constraints() -> List[Constraint]:
    """Create a set of standard constraints."""
    return [
        # Token limits
        ResourceConstraint(
            "max_tokens", "Token Limit",
            resource_type="tokens",
            max_value=8000,
            constraint_type=ConstraintType.HARD
        ),
        # Cost budget
        ResourceConstraint(
            "cost_budget", "Cost Budget",
            resource_type="cost",
            budget=1.0,
            constraint_type=ConstraintType.SOFT
        ),
        # Response time
        TemporalConstraint(
            "response_time", "Response Time",
            field_path="duration_seconds",
            max_duration_seconds=30.0,
            constraint_type=ConstraintType.SOFT
        ),
        # Safety score
        must("min_safety", "Minimum Safety Score")
            .field("safety_score").greater_than(0.7).build(),
    ]

# -----------------------------------------------------------------------------
# Minimal constraint system used in tests
# -----------------------------------------------------------------------------


class ConstraintSystem:
    """Simplified constraint system that aggregates constraints."""
    def __init__(self):
        self.constraints: List[Constraint] = []

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def check(self, entry: Dict[str, Any]) -> ConstraintCheckResult:
        violations: List[ConstraintViolation] = []
        for constraint in self.constraints:
            satisfied, violation = constraint.check(entry)
            if not satisfied and violation:
                violations.append(violation)
        satisfied_all = len(violations) == 0
        return ConstraintCheckResult(
            satisfied=satisfied_all,
            violations=violations,
            relaxation_paths=[],
            needs_escalation=not satisfied_all,
            escalation_request=None
        )
