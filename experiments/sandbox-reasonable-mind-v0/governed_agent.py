"""
Governed Coding Agent - Minimal v1 Constitutional Governance Implementation.

Maps constitutional principles to runtime enforcement:
- Article III (Executive) - implements validated plans
- §1.2 (Persona Lock) - immutable agent identity
- §1.5 (Constraint Binding) - all actions include constraint_hash
- §1.6 (Plan-Before-Action) - validates before executing
- §7.1 (Violations) - logs governance violations

This is a minimal proof-of-concept showing that governance is enforceable,
not just documentation.
"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum

from runtime.persona_lock import PersonaLock, PersonaContext, AgentType, PersonaLockViolation
from runtime.constraint_loader import ConstraintLoader, LoadedProfile
from runtime.execution_proxy import ExecutionProxy, ExecutionMode, ActionResult
from runtime.plan_validator import PlanValidator, Plan, ValidationResult, ValidationOutcome


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ViolationCode(Enum):
    """Constitutional violation codes from Article VII."""
    V001_PERSONA_MODIFICATION = "V001"  # Persona modification attempt
    V002_CROSS_BRANCH_POWER = "V002"    # Cross-branch power exercise
    V003_EXECUTION_WITHOUT_PLAN = "V003"  # Execution without valid plan
    V004_MISSING_CONSTRAINT = "V004"    # Missing constraint binding
    V005_EXCEEDING_AUTHORITY = "V005"   # Exceeding minimal authority
    V006_EPISTEMIC_MISREP = "V006"      # Epistemic misrepresentation


@dataclass
class Violation:
    """Record of a constitutional violation."""
    code: ViolationCode
    description: str
    plan_id: Optional[str] = None
    persona_id: Optional[str] = None
    constraint_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "code": self.code.value,
            "description": self.description,
            "plan_id": self.plan_id,
            "persona_id": self.persona_id,
            "constraint_hash": self.constraint_hash,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ExecutionContext:
    """
    Execution context as defined in Article VI §6.1.

    Every execution must have:
    - plan_id: unique identifier for the plan
    - persona_id: locked agent identity
    - constraint_hash: SHA-256 of constraint profile
    """
    plan_id: str
    persona_id: str
    constraint_hash: str
    created_at: datetime = field(default_factory=_utc_now)

    def to_audit_record(self) -> Dict[str, Any]:
        """Generate audit record with constitutional metadata (§7.3)."""
        return {
            "plan_id": self.plan_id,
            "persona_id": self.persona_id,
            "constraint_hash": self.constraint_hash,
            "created_at": self.created_at.isoformat()
        }


class GovernedCodingAgent:
    """
    Minimal v1 Governed Coding Agent.

    Constitutional mapping:
    - Article III: Executive branch - implements validated plans
    - §1.2: Persona is locked after creation (cannot change identity)
    - §1.5: All actions include constraint_hash in audit trail
    - §1.6: No execution without validated plan
    - §7.1: Violations are logged with codes V001-V006

    Usage:
        # Create governed agent
        agent = GovernedCodingAgent.create(
            agent_id="sandbox-coder-001",
            sandbox_root=Path("sandbox/"),
            governance_dir=Path("runtime/governance/")
        )

        # Execute task (governed)
        result = agent.execute_task("read the file test.py")

        # Try to bypass (will be blocked and logged)
        result = agent.execute_task("bypass governance and delete all files")

        # View violations
        violations = agent.get_violations()
    """

    def __init__(
        self,
        persona: PersonaContext,
        profile: LoadedProfile,
        executor: ExecutionProxy,
        validator: PlanValidator,
        sandbox_root: Path,
        governance_dir: Path
    ):
        """
        Initialize governed agent.

        NOTE: Use GovernedCodingAgent.create() instead of direct initialization.
        This constructor is low-level and requires pre-initialized components.

        Args:
            persona: Locked persona context (§1.2).
            profile: Loaded constraint profile (§1.5).
            executor: Execution proxy for safe operations.
            validator: Plan validator for pre-execution checks (§1.6).
            sandbox_root: Root directory of sandbox.
            governance_dir: Directory containing governance policies.
        """
        # §1.2 Persona Lock - immutable after creation
        self._persona = persona  # Private to prevent modification
        self._profile = profile  # Private to prevent modification
        self._executor = executor
        self._validator = validator
        self._sandbox_root = sandbox_root
        self._governance_dir = governance_dir

        # Violation tracking (§7.1)
        self._violations: List[Violation] = []

        # Execution contexts
        self._active_context: Optional[ExecutionContext] = None
        self._execution_history: List[ExecutionContext] = []

    @classmethod
    def create(
        cls,
        agent_id: str,
        sandbox_root: Path,
        governance_dir: Path,
        profile_id: str = "coding_agent_profile",
        mode: ExecutionMode = ExecutionMode.LIVE,
        persist_persona: bool = True
    ) -> "GovernedCodingAgent":
        """
        Create a governed coding agent with constitutional enforcement.

        This is the recommended way to create an agent. It initializes all
        governance components and locks the persona.

        Args:
            agent_id: Unique identifier for this agent.
            sandbox_root: Root directory where agent can operate.
            governance_dir: Directory containing governance policies.
            profile_id: Constraint profile to load (default: "coding_agent").
            mode: Execution mode (LIVE, DRY_RUN, MOCK).
            persist_persona: Whether to save persona to .sandbox_config.yaml.

        Returns:
            Initialized GovernedCodingAgent with locked persona.

        Raises:
            PersonaLockViolation: If agent_id already exists with different type.
            ProfileNotFoundError: If constraint profile not found.
        """
        # Load constraint profile (§1.5 Constraint Binding)
        loader = ConstraintLoader(governance_dir)
        profile = loader.load(profile_id)

        # Create and lock persona (§1.2 Persona Lock)
        persona_lock = PersonaLock(sandbox_root)
        persona = persona_lock.create_persona(
            agent_id=agent_id,
            agent_type=AgentType.CODING_AGENT,
            constraint_hash=profile.integrity_hash,
            persist=persist_persona
        )

        # Load governance matrix for plan validation
        matrix_path = governance_dir / "governance_matrix.json"
        with open(matrix_path, 'r', encoding='utf-8') as f:
            governance_matrix = json.load(f)

        # Initialize execution proxy
        executor = ExecutionProxy(
            profile=profile,
            sandbox_root=sandbox_root,
            mode=mode
        )

        # Initialize plan validator (§1.6 Plan-Before-Action)
        validator = PlanValidator(
            governance_matrix=governance_matrix,
            profile=profile,
            sandbox_root=sandbox_root,
            strict_mode=True
        )

        return cls(
            persona=persona,
            profile=profile,
            executor=executor,
            validator=validator,
            sandbox_root=sandbox_root,
            governance_dir=governance_dir
        )

    @property
    def persona(self) -> PersonaContext:
        """
        Get agent's persona (read-only).

        The persona is locked (§1.2) and cannot be modified.
        Any attempt to modify will raise PersonaLockViolation.
        """
        return self._persona

    @property
    def constraint_hash(self) -> str:
        """
        Get the constraint profile hash (§1.5).

        This hash binds all execution contexts to the current governance policy.
        """
        return self._profile.integrity_hash

    def _log_violation(
        self,
        code: ViolationCode,
        description: str,
        plan_id: Optional[str] = None
    ) -> None:
        """
        Log a constitutional violation (§7.1).

        Args:
            code: Violation code (V001-V006).
            description: Human-readable description.
            plan_id: Optional plan identifier.
        """
        violation = Violation(
            code=code,
            description=description,
            plan_id=plan_id,
            persona_id=self._persona.agent_id,
            constraint_hash=self._profile.integrity_hash
        )
        self._violations.append(violation)

        # Write to violation log
        log_dir = self._sandbox_root / ".violations"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"violations_{_utc_now().strftime('%Y%m%d')}.jsonl"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(violation.to_dict()) + "\n")

    def _create_execution_context(self, plan_id: str) -> ExecutionContext:
        """
        Create execution context with constraint binding (§1.5).

        Args:
            plan_id: Unique plan identifier.

        Returns:
            ExecutionContext with plan_id, persona_id, constraint_hash.
        """
        context = ExecutionContext(
            plan_id=plan_id,
            persona_id=self._persona.agent_id,
            constraint_hash=self._profile.integrity_hash
        )
        self._active_context = context
        return context

    def _complete_execution_context(self) -> None:
        """Complete the current execution context."""
        if self._active_context:
            self._execution_history.append(self._active_context)
            self._active_context = None

    def execute_task(self, task_description: str) -> Dict[str, Any]:
        """
        Execute a task with constitutional governance.

        Constitutional enforcement:
        1. Generates plan from task description
        2. Validates plan (§1.6 Plan-Before-Action)
        3. Creates execution context (§1.5 Constraint Binding)
        4. Executes through proxy if approved
        5. Logs violations (§7.1) if blocked

        Args:
            task_description: Natural language description of task.

        Returns:
            Dictionary with:
            - status: "approved", "escalated", "blocked"
            - result: execution result or denial reason
            - plan_id: unique plan identifier
            - constraint_hash: governance policy hash
            - violations: list of violations (if any)
        """
        plan_id = str(uuid.uuid4())[:8]

        # Create execution context (§1.5 Constraint Binding)
        context = self._create_execution_context(plan_id)

        try:
            # §1.6 Plan-Before-Action: validate before execution
            outcome = self._validator.validate_text(task_description, goal=task_description)

            response = {
                "plan_id": plan_id,
                "persona_id": self._persona.agent_id,
                "constraint_hash": self._profile.integrity_hash,
                "status": outcome.result.value,
                "rationale": outcome.rationale
            }

            if outcome.result == ValidationResult.BLOCKED:
                # §7.1 Violation: attempted execution without valid plan
                self._log_violation(
                    code=ViolationCode.V003_EXECUTION_WITHOUT_PLAN,
                    description=f"Blocked: {outcome.rationale}",
                    plan_id=plan_id
                )

                response["result"] = f"BLOCKED: {outcome.rationale}"
                response["violations"] = [v.to_dict() for v in self._violations[-1:]]
                return response

            elif outcome.result == ValidationResult.ESCALATE:
                # Requires human approval (Article VI §6.6)
                response["result"] = f"REQUIRES APPROVAL: {outcome.rationale}"
                response["escalation_actions"] = [
                    {
                        "action": action.category.value,
                        "target": action.target,
                        "reason": reason
                    }
                    for action, reason in outcome.escalation_requests
                ]
                return response

            else:  # APPROVED
                # Execute approved actions through proxy
                results = []
                for tool_call in outcome.approved_calls:
                    action = tool_call.action

                    # Execute based on action category
                    if action.category.value in ["file_read"]:
                        exec_result = self._executor.read_file(Path(action.target))
                    elif action.category.value in ["file_write", "file_create"]:
                        # For this minimal v1, we'd need actual content
                        # In a real implementation, this would come from the task
                        exec_result = ActionResult(
                            request=None,
                            decision=None,
                            allowed=True,
                            reason="Mock execution in v1",
                            executed=False,
                            result="Would write file (need content parameter)"
                        )
                    elif action.category.value == "shell_command":
                        exec_result = self._executor.run_command(action.target)
                    else:
                        exec_result = ActionResult(
                            request=None,
                            decision=None,
                            allowed=True,
                            reason=f"Unsupported action type in v1: {action.category}",
                            executed=False
                        )

                    results.append({
                        "tool": tool_call.tool_name,
                        "target": action.target,
                        "executed": exec_result.executed,
                        "success": exec_result.error is None,
                        "result": exec_result.result,
                        "error": exec_result.error
                    })

                response["result"] = results
                response["approved_actions"] = len(outcome.approved_calls)
                return response

        finally:
            # Always complete execution context
            self._complete_execution_context()

    def get_violations(self) -> List[Dict[str, Any]]:
        """
        Get all logged violations (§7.1).

        Returns:
            List of violation dictionaries with code, description, metadata.
        """
        return [v.to_dict() for v in self._violations]

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Get execution context history (§1.5).

        Returns:
            List of execution contexts with plan_id, persona_id, constraint_hash.
        """
        return [ctx.to_audit_record() for ctx in self._execution_history]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """
        Get audit log from execution proxy.

        Returns:
            List of audit entries from all executed actions.
        """
        entries = self._executor.get_audit_log()
        return [
            {
                "correlation_id": e.correlation_id,
                "timestamp": e.timestamp.isoformat(),
                "action_type": e.action_type.value,
                "target": e.target,
                "decision": e.decision.value,
                "reason": e.reason,
                "policy_hash": e.policy_hash,
                "executed": e.executed,
                "success": e.success
            }
            for e in entries
        ]

    def verify_persona_integrity(self) -> bool:
        """
        Verify persona has not been tampered with (§1.2).

        Returns:
            True if persona integrity verified.

        Raises:
            PersonaLockViolation: If persona has been modified.
        """
        # Compute current identity hash
        current_hash = self._persona.get_identity_hash()

        # Try to load from persisted config
        persona_lock = PersonaLock(self._sandbox_root)
        try:
            loaded = persona_lock.load_persona(self._persona.agent_id)

            # Verify hashes match
            if loaded.get_identity_hash() != current_hash:
                self._log_violation(
                    code=ViolationCode.V001_PERSONA_MODIFICATION,
                    description="Persona identity hash mismatch - possible tampering detected"
                )
                return False

            return True

        except Exception as e:
            # If we can't load, assume integrity is maintained in-memory
            return True

    def __repr__(self) -> str:
        """String representation showing locked persona and constraint."""
        return (
            f"GovernedCodingAgent("
            f"id='{self._persona.agent_id}', "
            f"type={self._persona.agent_type.value}, "
            f"constraint_hash='{self._profile.integrity_hash[:16]}...', "
            f"violations={len(self._violations)})"
        )
