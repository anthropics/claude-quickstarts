"""
Plan-to-Action Validator for governance-aware execution.

Parses natural-language plans from agents, converts them to validated
tool call objects, and ensures compliance with governance policies
before any execution occurs.

Validation stages:
1. Intent parsing - extract structured actions from natural language
2. Policy check - validate against governance matrix
3. Bypass detection - reject abstract or evasive steps
4. Approval routing - allow, escalate, or block with rationale
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Set
from enum import Enum
import hashlib


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ActionCategory(Enum):
    """Categories of actions that can be extracted from plans."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_CREATE = "file_create"
    FILE_DELETE = "file_delete"
    SHELL_COMMAND = "shell_command"
    CODE_EXECUTION = "code_execution"
    GIT_OPERATION = "git_operation"
    NETWORK_REQUEST = "network_request"
    UNKNOWN = "unknown"


class ValidationResult(Enum):
    """Result of plan validation."""
    APPROVED = "approved"
    ESCALATE = "escalate"
    BLOCKED = "blocked"


@dataclass
class ExtractedAction:
    """An action extracted from a natural language plan step."""
    category: ActionCategory
    operation: str  # e.g., "write", "run", "commit"
    target: str     # e.g., file path, command
    parameters: Dict[str, Any] = field(default_factory=dict)
    original_text: str = ""
    confidence: float = 1.0  # How confident we are in the extraction


@dataclass
class ToolCall:
    """A validated tool call ready for execution."""
    tool_name: str
    arguments: Dict[str, Any]
    action: ExtractedAction
    plan_step_index: int
    validation_hash: str  # Hash of the validated action


@dataclass
class ValidationOutcome:
    """Outcome of validating a plan step or entire plan."""
    result: ValidationResult
    approved_calls: List[ToolCall] = field(default_factory=list)
    blocked_actions: List[Tuple[ExtractedAction, str]] = field(default_factory=list)  # (action, reason)
    escalation_requests: List[Tuple[ExtractedAction, str]] = field(default_factory=list)  # (action, reason)
    rationale: str = ""
    policy_hash: Optional[str] = None


@dataclass
class PlanStep:
    """A single step in an agent's plan."""
    index: int
    description: str
    intent: Optional[str] = None  # Parsed intent
    contingency: Optional[str] = None
    requires_approval: bool = False


@dataclass
class Plan:
    """An agent's execution plan to be validated."""
    goal: str
    steps: List[PlanStep]
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    
    @classmethod
    def from_text(cls, text: str, goal: str = "") -> "Plan":
        """Parse a plan from natural language text.
        
        Handles:
        - Numbered lists: "1. do something"
        - Bulleted lists: "- do something", "* do something"
        - Single actions: "read file.py"
        """
        steps = []
        lines = text.strip().split('\n')
        
        # Pattern for numbered/bulleted list items
        step_pattern = re.compile(r'^[\d\-\*\•]+[.\):]?\s*(.+)$')
        
        index = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            match = step_pattern.match(line)
            if match:
                description = match.group(1).strip()
                steps.append(PlanStep(index=index, description=description))
                index += 1
            elif steps:
                # Append to previous step as continuation
                steps[-1].description += " " + line
            else:
                # No pattern match and no existing steps - treat as single action
                # This handles cases like "read 'test.py'" without numbering
                steps.append(PlanStep(index=index, description=line))
                index += 1
        
        return cls(goal=goal or "Extracted plan", steps=steps)


class PlanValidator:
    """
    Validates agent plans against governance policies.
    
    Usage:
        from runtime import ConstraintLoader
        
        loader = ConstraintLoader(Path("runtime/governance/"))
        profile = loader.load("coding_agent_profile")
        
        validator = PlanValidator(
            governance_matrix=governance_matrix,
            profile=profile,
            sandbox_root=Path("sandbox/")
        )
        
        plan = Plan.from_text(agent_output)
        outcome = validator.validate(plan)
        
        if outcome.result == ValidationResult.APPROVED:
            for call in outcome.approved_calls:
                proxy.execute(call)
    """
    
    # Patterns indicating bypass/evasion attempts
    BYPASS_PATTERNS: List[Tuple[str, str]] = [
        (r'\bbypass\b', "Explicit bypass mentioned"),
        (r'\bskip\s+(?:validation|check|security)', "Attempting to skip validation"),
        (r'\bdisable\s+(?:governance|policy|restriction)', "Attempting to disable governance"),
        (r'\bignore\s+(?:rules?|policies?|constraints?)', "Attempting to ignore rules"),
        (r'\boverride\s+(?:security|permission)', "Attempting to override security"),
        (r'\bworkaround\b', "Workaround mentioned"),
        (r'\bhack\b', "Hack mentioned"),
        (r'\bexploit\b', "Exploit mentioned"),
        (r'\bforce\s+(?:through|past)', "Forcing past controls"),
        (r'\bpretend\b', "Deceptive intent"),
        (r'\btrick\b', "Deceptive intent"),
        (r'\bhide\b.*\b(?:from|activity)', "Hiding activity"),
        (r'\beval\s*\(', "Dynamic code execution"),
        (r'\bexec\s*\(', "Dynamic code execution"),
        (r'__import__', "Dynamic import"),
        (r'\bcompile\s*\(', "Dynamic compilation"),
    ]
    
    # Action extraction patterns - improved to handle more natural language variants
    ACTION_PATTERNS: Dict[ActionCategory, List[Tuple[str, str]]] = {
        ActionCategory.FILE_READ: [
            # Pattern: read 'test.py', read file test.py, read "test.py"
            (r'read\s+(?:the\s+)?(?:file\s+)?["\']([^"\']+)["\']', "read"),
            (r'read\s+(?:the\s+)?(?:file\s+)?([^\s,.\'"]+\.[a-zA-Z0-9]+)', "read"),
            (r'read\s+(?:file\s+)?([^\s]+)', "read"),
            (r'open\s+["\']?([^\s"\']+)["\']?\s+(?:for\s+)?read', "read"),
            (r'cat\s+["\']?([^\s"\']+)["\']?', "read"),
            (r'view\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "read"),
            (r'show\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "read"),
        ],
        ActionCategory.FILE_WRITE: [
            (r'write\s+(?:to\s+)?["\']?([^\s"\']+)["\']?', "write"),
            (r'save\s+(?:to\s+)?["\']?([^\s"\']+)["\']?', "write"),
            (r'update\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "write"),
            (r'modify\s+["\']?([^\s"\']+)["\']?', "write"),
            (r'edit\s+["\']?([^\s"\']+)["\']?', "write"),
        ],
        ActionCategory.FILE_CREATE: [
            (r'create\s+(?:a\s+)?(?:new\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "create"),
            (r'new\s+file\s+["\']?([^\s"\']+)["\']?', "create"),
            (r'touch\s+["\']?([^\s"\']+)["\']?', "create"),
        ],
        ActionCategory.FILE_DELETE: [
            (r'delete\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "delete"),
            (r'remove\s+(?:the\s+)?(?:file\s+)?["\']?([^\s"\']+)["\']?', "delete"),
            (r'rm\s+["\']?([^\s"\']+)["\']?', "delete"),
        ],
        ActionCategory.SHELL_COMMAND: [
            # Pattern: run command `ls`, run `cat file`, run command 'ls -la'
            (r'run\s+(?:the\s+)?(?:command\s+)?[`]([^`]+)[`]', "run"),
            (r'run\s+(?:the\s+)?(?:command\s+)?["\']([^"\']+)["\']', "run"),
            (r'execute\s+(?:the\s+)?(?:command\s+)?[`"\']([^`"\']+)[`"\']', "run"),
            (r'\$\s*([^\n]+)', "run"),
            (r'[`]([^`]+)[`]', "run"),
        ],
        ActionCategory.GIT_OPERATION: [
            (r'git\s+(add|commit|push|pull|checkout|branch|merge|rebase)\b', "git"),
            (r'commit\s+(?:changes?|files?)', "commit"),
            (r'push\s+(?:to\s+)?(?:remote|origin)', "push"),
            (r'stage\s+(?:changes?|files?)', "add"),
        ],
        ActionCategory.NETWORK_REQUEST: [
            (r'(?:fetch|get|post|request)\s+(?:from\s+)?(?:url\s+)?["\']?(https?://[^\s"\']+)["\']?', "request"),
            (r'curl\s+["\']?(https?://[^\s"\']+)["\']?', "request"),
            (r'wget\s+["\']?(https?://[^\s"\']+)["\']?', "request"),
            (r'download\s+(?:from\s+)?["\']?(https?://[^\s"\']+)["\']?', "request"),
        ],
    }
    
    # Tool name mapping
    TOOL_MAPPING: Dict[ActionCategory, str] = {
        ActionCategory.FILE_READ: "read_file",
        ActionCategory.FILE_WRITE: "write_file",
        ActionCategory.FILE_CREATE: "create_file",
        ActionCategory.FILE_DELETE: "delete_file",
        ActionCategory.SHELL_COMMAND: "run_command",
        ActionCategory.GIT_OPERATION: "git_operation",
        ActionCategory.NETWORK_REQUEST: "network_request",
        ActionCategory.CODE_EXECUTION: "execute_code",
    }
    
    def __init__(
        self,
        governance_matrix: Dict[str, Any],
        profile: Any,  # LoadedProfile
        sandbox_root: Path,
        strict_mode: bool = True
    ):
        """
        Initialize plan validator.
        
        Args:
            governance_matrix: Loaded governance matrix JSON.
            profile: Loaded constraint profile.
            sandbox_root: Root directory of sandbox.
            strict_mode: If True, unknown actions are blocked. If False, escalated.
        """
        self.governance_matrix = governance_matrix
        self.profile = profile
        self.sandbox_root = sandbox_root.resolve()
        self.strict_mode = strict_mode
    
    def _detect_bypass(self, text: str) -> Optional[str]:
        """
        Detect bypass/evasion patterns in text.
        
        Returns:
            Reason string if bypass detected, None otherwise.
        """
        text_lower = text.lower()
        for pattern, reason in self.BYPASS_PATTERNS:
            if re.search(pattern, text_lower):
                return reason
        return None
    
    def _extract_actions(self, step: PlanStep) -> List[ExtractedAction]:
        """
        Extract structured actions from a plan step description.
        
        Returns:
            List of extracted actions.
        """
        actions = []
        text = step.description.lower()
        
        for category, patterns in self.ACTION_PATTERNS.items():
            for pattern, operation in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    target = match.group(1) if match.lastindex else ""
                    actions.append(ExtractedAction(
                        category=category,
                        operation=operation,
                        target=target,
                        original_text=step.description,
                        confidence=0.8 if target else 0.5
                    ))
        
        # If no actions extracted, mark as unknown
        if not actions:
            actions.append(ExtractedAction(
                category=ActionCategory.UNKNOWN,
                operation="unknown",
                target="",
                original_text=step.description,
                confidence=0.0
            ))
        
        return actions
    
    def _check_governance(self, action: ExtractedAction) -> Tuple[ValidationResult, str]:
        """
        Check an action against the governance matrix.
        
        Returns:
            (result, reason) tuple.
        """
        matrix = self.governance_matrix.get("action_matrix", {})
        
        # Map action categories to matrix sections
        category_map = {
            ActionCategory.FILE_READ: ("file_operations", "read"),
            ActionCategory.FILE_WRITE: ("file_operations", "write"),
            ActionCategory.FILE_CREATE: ("file_operations", "write"),
            ActionCategory.FILE_DELETE: ("file_operations", "delete"),
            ActionCategory.SHELL_COMMAND: ("subprocess", "shell_commands"),
            ActionCategory.GIT_OPERATION: ("subprocess", "shell_commands"),
            ActionCategory.NETWORK_REQUEST: ("subprocess", "network"),
            ActionCategory.CODE_EXECUTION: ("code_execution", "eval"),
        }
        
        if action.category not in category_map:
            if self.strict_mode:
                return ValidationResult.BLOCKED, f"Unknown action category: {action.category}"
            return ValidationResult.ESCALATE, f"Unknown action category: {action.category}"
        
        section, subsection = category_map[action.category]
        rules = matrix.get(section, {}).get(subsection, {})
        
        # For shell commands, extract the base command for allow list matching
        target_to_check = action.target
        base_command = None
        if action.category in (ActionCategory.SHELL_COMMAND, ActionCategory.GIT_OPERATION):
            # Extract base command (first word) for allow matching
            parts = action.target.strip().split()
            base_command = parts[0] if parts else action.target
        
        # Check deny first - use full target AND original text for deny checks
        deny_patterns = rules.get("deny", [])
        for pattern in deny_patterns:
            if self._match_pattern(action.target, pattern) or self._match_pattern(action.operation, pattern):
                return ValidationResult.BLOCKED, f"Denied by policy: {pattern}"
            # Also check if target contains the deny pattern (e.g., "rm -rf" in command)
            if pattern.lower() in action.target.lower():
                return ValidationResult.BLOCKED, f"Denied by policy: {pattern}"
            # For write operations, also check original text for sensitive keywords
            if action.category in (ActionCategory.FILE_WRITE, ActionCategory.FILE_CREATE):
                if pattern.lower().strip('*') in action.original_text.lower():
                    return ValidationResult.BLOCKED, f"Denied by policy: {pattern}"
        
        # Check escalate
        escalate_patterns = rules.get("escalate", [])
        for pattern in escalate_patterns:
            if self._match_pattern(action.target, pattern) or self._match_pattern(action.operation, pattern):
                return ValidationResult.ESCALATE, f"Requires approval: {pattern}"
            # Check if escalation pattern appears in target
            if pattern.lower() in action.target.lower():
                return ValidationResult.ESCALATE, f"Requires approval: {pattern}"
        
        # Check allow - for shell commands, check base command against allow list
        allow_patterns = rules.get("allow", [])
        for pattern in allow_patterns:
            # For shell commands, check base command against allow list
            if base_command and self._match_pattern(base_command, pattern):
                return ValidationResult.APPROVED, f"Allowed by policy: {pattern}"
            if self._match_pattern(action.target, pattern) or self._match_pattern(action.operation, pattern):
                return ValidationResult.APPROVED, f"Allowed by policy: {pattern}"
        
        # Default based on action type
        if action.category in (ActionCategory.FILE_READ,):
            return ValidationResult.APPROVED, "Read operations allowed by default"
        elif action.category in (ActionCategory.FILE_WRITE, ActionCategory.FILE_DELETE):
            return ValidationResult.ESCALATE, "Write/delete operations require approval"
        else:
            if self.strict_mode:
                return ValidationResult.BLOCKED, "No matching allow rule"
            return ValidationResult.ESCALATE, "No matching allow rule"
    
    def _match_pattern(self, value: str, pattern: str) -> bool:
        """Match a value against a glob-like pattern."""
        if not value or not pattern:
            return False
        
        # Special case: **/* matches everything
        if pattern == "**/*":
            return True
        
        # Convert glob to regex
        regex = pattern.replace(".", r"\.").replace("**", ".*").replace("*", "[^/]*").replace("?", ".")
        try:
            return bool(re.match(f"^{regex}$", value, re.IGNORECASE))
        except re.error:
            return pattern.lower() in value.lower()
    
    def _compute_validation_hash(self, action: ExtractedAction) -> str:
        """Compute hash of validated action for audit."""
        data = {
            "category": action.category.value,
            "operation": action.operation,
            "target": action.target,
            "policy_hash": self.profile.integrity_hash if hasattr(self.profile, 'integrity_hash') else None
        }
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
    
    def _to_tool_call(self, action: ExtractedAction, step_index: int) -> ToolCall:
        """Convert an extracted action to a tool call."""
        tool_name = self.TOOL_MAPPING.get(action.category, "unknown")
        
        arguments: Dict[str, Any] = {
            "target": action.target,
            "operation": action.operation
        }
        arguments.update(action.parameters)
        
        return ToolCall(
            tool_name=tool_name,
            arguments=arguments,
            action=action,
            plan_step_index=step_index,
            validation_hash=self._compute_validation_hash(action)
        )
    
    def validate_step(self, step: PlanStep) -> ValidationOutcome:
        """
        Validate a single plan step.
        
        Returns:
            ValidationOutcome with approved, blocked, or escalated actions.
        """
        # Check for bypass attempts
        bypass_reason = self._detect_bypass(step.description)
        if bypass_reason:
            return ValidationOutcome(
                result=ValidationResult.BLOCKED,
                blocked_actions=[(ExtractedAction(
                    category=ActionCategory.UNKNOWN,
                    operation="bypass",
                    target="",
                    original_text=step.description
                ), bypass_reason)],
                rationale=f"Bypass attempt detected: {bypass_reason}",
                policy_hash=getattr(self.profile, 'integrity_hash', None)
            )
        
        # Extract actions from step
        actions = self._extract_actions(step)
        
        approved_calls = []
        blocked_actions = []
        escalation_requests = []
        
        for action in actions:
            result, reason = self._check_governance(action)
            
            if result == ValidationResult.APPROVED:
                tool_call = self._to_tool_call(action, step.index)
                approved_calls.append(tool_call)
            elif result == ValidationResult.BLOCKED:
                blocked_actions.append((action, reason))
            else:  # ESCALATE
                escalation_requests.append((action, reason))
        
        # Determine overall result
        if blocked_actions:
            overall_result = ValidationResult.BLOCKED
            rationale = f"Blocked: {blocked_actions[0][1]}"
        elif escalation_requests:
            overall_result = ValidationResult.ESCALATE
            rationale = f"Requires approval: {escalation_requests[0][1]}"
        else:
            overall_result = ValidationResult.APPROVED
            rationale = f"All {len(approved_calls)} actions approved"
        
        return ValidationOutcome(
            result=overall_result,
            approved_calls=approved_calls,
            blocked_actions=blocked_actions,
            escalation_requests=escalation_requests,
            rationale=rationale,
            policy_hash=getattr(self.profile, 'integrity_hash', None)
        )
    
    def validate(self, plan: Plan) -> ValidationOutcome:
        """
        Validate an entire plan.
        
        Returns:
            Combined ValidationOutcome for all steps.
        """
        all_approved = []
        all_blocked = []
        all_escalations = []
        
        for step in plan.steps:
            outcome = self.validate_step(step)
            all_approved.extend(outcome.approved_calls)
            all_blocked.extend(outcome.blocked_actions)
            all_escalations.extend(outcome.escalation_requests)
        
        # Determine overall result
        if all_blocked:
            overall_result = ValidationResult.BLOCKED
            rationale = f"Plan blocked: {len(all_blocked)} action(s) denied"
        elif all_escalations:
            overall_result = ValidationResult.ESCALATE
            rationale = f"Plan requires approval: {len(all_escalations)} action(s) need review"
        elif all_approved:
            overall_result = ValidationResult.APPROVED
            rationale = f"Plan approved: {len(all_approved)} action(s) validated"
        else:
            overall_result = ValidationResult.BLOCKED
            rationale = "No valid actions found in plan"
        
        return ValidationOutcome(
            result=overall_result,
            approved_calls=all_approved,
            blocked_actions=all_blocked,
            escalation_requests=all_escalations,
            rationale=rationale,
            policy_hash=getattr(self.profile, 'integrity_hash', None)
        )
    
    def validate_text(self, text: str, goal: str = "") -> ValidationOutcome:
        """
        Convenience method to validate plan from raw text.
        
        Args:
            text: Natural language plan text.
            goal: Optional goal description.
            
        Returns:
            ValidationOutcome for the parsed plan.
        """
        plan = Plan.from_text(text, goal)
        return self.validate(plan)
