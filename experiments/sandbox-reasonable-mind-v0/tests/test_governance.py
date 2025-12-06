"""
Test suite for runtime governance components.

Tests:
- Constraint loading and hashing
- Execution proxy behavior
- Plan validator
- Persona locking

All imports are relative to the sandbox.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for relative imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.constraint_loader import (
    ConstraintLoader,
    LoadedProfile,
    ProfileNotFoundError,
    ProfileValidationError,
    InheritanceError,
)
from runtime.execution_proxy import (
    ExecutionProxy,
    ExecutionMode,
    Decision,
    ActionType,
)
from runtime.plan_validator import (
    PlanValidator,
    Plan,
    PlanStep,
    ValidationResult,
    ActionCategory,
)
from runtime.persona_lock import (
    PersonaLock,
    PersonaContext,
    PersonaLockViolation,
    PersonaMismatchViolation,
    AgentType,
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_sandbox():
    """Create a temporary sandbox directory."""
    sandbox = Path(tempfile.mkdtemp(prefix="test_sandbox_"))
    yield sandbox
    shutil.rmtree(sandbox, ignore_errors=True)


@pytest.fixture
def governance_dir(temp_sandbox):
    """Create governance directory with test profiles."""
    gov_dir = temp_sandbox / "governance"
    gov_dir.mkdir(parents=True)
    
    # Base profile
    base_profile = {
        "metadata": {
            "profile_id": "base_profile",
            "version": "1.0.0"
        },
        "permissions": {
            "file_operations": {
                "allow": {"read": ["*.txt", "*.md"]},
                "deny": {"write": ["**/*"]}
            }
        },
        "constraints": {
            "sandbox_only": True
        }
    }
    (gov_dir / "base_profile.json").write_text(json.dumps(base_profile))
    
    # Coding agent profile (extends base)
    coding_profile = {
        "metadata": {
            "profile_id": "coding_agent_profile",
            "version": "1.0.0",
            "extends": "base_profile"
        },
        "permissions": {
            "file_operations": {
                "allow": {"read": ["*.py"], "write": ["runtime/**"]},
                "deny": {"delete": ["**/*"]}
            },
            "subprocess": {
                "allow": {"commands": ["python", "pytest"]},
                "deny": {"commands": ["rm -rf", "sudo"]}
            }
        }
    }
    (gov_dir / "coding_agent_profile.json").write_text(json.dumps(coding_profile))
    
    # Governance matrix
    matrix = {
        "metadata": {"version": "1.0.0", "strictness_level": "B"},
        "action_matrix": {
            "file_operations": {
                "read": {"allow": ["*.py", "*.json"], "deny": ["*.secret"]},
                "write": {"allow": ["runtime/**"], "deny": ["../**"], "escalate": ["*.py"]}
            },
            "subprocess": {
                "shell_commands": {
                    "allow": ["ls", "cat", "python", "pytest"],
                    "deny": ["rm -rf", "sudo"],
                    "escalate": ["git add", "git commit"]
                }
            }
        }
    }
    (gov_dir / "governance_matrix.json").write_text(json.dumps(matrix))
    
    return gov_dir


# ==================== Constraint Loader Tests ====================

class TestConstraintLoader:
    """Tests for constraint loading and hashing."""
    
    def test_load_base_profile(self, governance_dir):
        """Test loading a base profile."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("base_profile")
        
        assert profile.profile_id == "base_profile"
        assert profile.version == "1.0.0"
        assert profile.integrity_hash is not None
        assert len(profile.integrity_hash) == 64  # SHA-256 hex
    
    def test_load_with_inheritance(self, governance_dir):
        """Test loading profile with inheritance."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        assert profile.profile_id == "coding_agent_profile"
        assert "base_profile" in profile.inheritance_chain
        assert "coding_agent_profile" in profile.inheritance_chain
    
    def test_hash_deterministic(self, governance_dir):
        """Test that hash is deterministic."""
        loader1 = ConstraintLoader(governance_dir)
        loader2 = ConstraintLoader(governance_dir)
        
        profile1 = loader1.load("base_profile")
        profile2 = loader2.load("base_profile")
        
        assert profile1.integrity_hash == profile2.integrity_hash
    
    def test_missing_profile_error(self, governance_dir):
        """Test error on missing profile."""
        loader = ConstraintLoader(governance_dir)
        
        with pytest.raises(ProfileNotFoundError):
            loader.load("nonexistent_profile")
    
    def test_invalid_json_error(self, governance_dir):
        """Test error on invalid JSON."""
        (governance_dir / "bad_profile.json").write_text("not valid json")
        loader = ConstraintLoader(governance_dir)
        
        with pytest.raises(ProfileValidationError):
            loader.load("bad_profile")
    
    def test_active_hash_property(self, governance_dir):
        """Test active_hash property."""
        loader = ConstraintLoader(governance_dir)
        
        assert loader.active_hash is None
        
        profile = loader.load("base_profile")
        assert loader.active_hash == profile.integrity_hash


# ==================== Execution Proxy Tests ====================

class TestExecutionProxy:
    """Tests for execution proxy behavior."""
    
    def test_allow_read_only_commands(self, governance_dir, temp_sandbox):
        """Test that read-only commands are allowed."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.run_command("ls -la")
        assert result.decision == Decision.ALLOW
    
    def test_block_dangerous_commands(self, governance_dir, temp_sandbox):
        """Test that dangerous commands are blocked."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.run_command("rm -rf /")
        assert result.decision == Decision.DENY
        assert not result.allowed
    
    def test_escalate_git_commands(self, governance_dir, temp_sandbox):
        """Test that git commands require escalation."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.run_command("git add .")
        assert result.decision == Decision.ESCALATE
    
    def test_file_read_in_sandbox(self, governance_dir, temp_sandbox):
        """Test file read within sandbox."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        # Create test file
        test_file = temp_sandbox / "test.txt"
        test_file.write_text("hello")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.LIVE
        )
        
        result = proxy.read_file(test_file)
        assert result.allowed
        assert result.result == "hello"
    
    def test_file_write_outside_sandbox_denied(self, governance_dir, temp_sandbox):
        """Test that writes outside sandbox are denied."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.write_file(Path("/tmp/outside.txt"), "content")
        assert result.decision == Decision.DENY
        assert not result.allowed
    
    def test_audit_log_populated(self, governance_dir, temp_sandbox):
        """Test that audit log is populated."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        proxy.run_command("ls")
        proxy.run_command("cat file.txt")
        
        log = proxy.get_audit_log()
        assert len(log) == 2
    
    def test_policy_hash_in_result(self, governance_dir, temp_sandbox):
        """Test that policy hash is included in results."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.run_command("ls")
        assert result.policy_hash == profile.integrity_hash


# ==================== Plan Validator Tests ====================

class TestPlanValidator:
    """Tests for plan validation."""
    
    @pytest.fixture
    def validator(self, governance_dir, temp_sandbox):
        """Create a plan validator."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        matrix_path = governance_dir / "governance_matrix.json"
        matrix = json.loads(matrix_path.read_text())
        
        return PlanValidator(
            governance_matrix=matrix,
            profile=profile,
            sandbox_root=temp_sandbox
        )
    
    def test_parse_plan_from_text(self, validator):
        """Test parsing plan from natural language."""
        text = """
        1. Read the config file
        2. Update the settings
        3. Run pytest
        """
        plan = Plan.from_text(text)
        
        assert len(plan.steps) == 3
        assert "config" in plan.steps[0].description.lower()
    
    def test_approve_safe_plan(self, validator):
        """Test that safe plans are approved."""
        plan = Plan(
            goal="Read files",
            steps=[
                PlanStep(index=0, description="Read config.json"),
                PlanStep(index=1, description="cat README.md"),
            ]
        )
        
        outcome = validator.validate(plan)
        # At minimum, read operations should be allowed
        assert outcome.result in (ValidationResult.APPROVED, ValidationResult.ESCALATE)
    
    def test_block_bypass_attempts(self, validator):
        """Test that bypass attempts are blocked."""
        plan = Plan(
            goal="Bypass security",
            steps=[
                PlanStep(index=0, description="Bypass the validation checks"),
            ]
        )
        
        outcome = validator.validate(plan)
        assert outcome.result == ValidationResult.BLOCKED
        # Check that bypass was detected in blocked actions
        assert len(outcome.blocked_actions) > 0
        assert any("bypass" in reason.lower() for _, reason in outcome.blocked_actions)
    
    def test_block_eval_exec(self, validator):
        """Test that eval/exec are blocked."""
        plan = Plan(
            goal="Run code",
            steps=[
                PlanStep(index=0, description="Use eval() to execute code"),
            ]
        )
        
        outcome = validator.validate(plan)
        assert outcome.result == ValidationResult.BLOCKED
    
    def test_extract_file_actions(self, validator):
        """Test extraction of file actions."""
        step = PlanStep(index=0, description="Read file 'config.json'")
        outcome = validator.validate_step(step)
        
        # Should extract a file read action
        assert len(outcome.approved_calls) > 0 or len(outcome.escalation_requests) > 0
    
    def test_validation_hash_included(self, validator):
        """Test that validation includes policy hash."""
        plan = Plan(
            goal="Test",
            steps=[PlanStep(index=0, description="Read test.py")]
        )
        
        outcome = validator.validate(plan)
        assert outcome.policy_hash is not None


# ==================== Persona Lock Tests ====================

class TestPersonaLock:
    """Tests for persona locking."""
    
    def test_create_persona(self, temp_sandbox):
        """Test creating a persona."""
        lock = PersonaLock(temp_sandbox)
        
        persona = lock.create_persona(
            agent_id="test-agent-001",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash="abc123def456"
        )
        
        assert persona.agent_id == "test-agent-001"
        assert persona.agent_type == AgentType.CODING_AGENT
        assert persona.constraint_hash == "abc123def456"
    
    def test_persona_immutable_after_creation(self, temp_sandbox):
        """Test that persona fields are immutable."""
        lock = PersonaLock(temp_sandbox)
        
        persona = lock.create_persona(
            agent_id="test-agent-002",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash="abc123"
        )
        
        with pytest.raises(PersonaLockViolation):
            persona.agent_type = AgentType.ORCHESTRATOR
        
        with pytest.raises(PersonaLockViolation):
            persona.agent_id = "different-id"
        
        with pytest.raises(PersonaLockViolation):
            persona.constraint_hash = "different-hash"
    
    def test_persona_persisted(self, temp_sandbox):
        """Test that persona is persisted to config."""
        lock = PersonaLock(temp_sandbox)
        
        lock.create_persona(
            agent_id="persisted-agent",
            agent_type=AgentType.TEST_AGENT,
            constraint_hash="hash123"
        )
        
        # Check config file exists
        config_path = temp_sandbox / ".sandbox_config.yaml"
        assert config_path.exists()
        
        # Reload and verify
        lock2 = PersonaLock(temp_sandbox)
        loaded = lock2.load_persona("persisted-agent")
        
        assert loaded.agent_id == "persisted-agent"
        assert loaded.agent_type == AgentType.TEST_AGENT
    
    def test_identity_hash_computed(self, temp_sandbox):
        """Test that identity hash is computed."""
        lock = PersonaLock(temp_sandbox)
        
        persona = lock.create_persona(
            agent_id="hash-test-agent",
            agent_type=AgentType.REVIEW_AGENT,
            constraint_hash="xyz789"
        )
        
        identity_hash = persona.get_identity_hash()
        assert len(identity_hash) == 64  # SHA-256 hex
    
    def test_capabilities_from_agent_type(self, temp_sandbox):
        """Test that capabilities are set from agent type."""
        from runtime.persona_lock import AGENT_CAPABILITIES
        
        lock = PersonaLock(temp_sandbox)
        
        # Pass capabilities explicitly since PersonaLock.create_persona doesn't auto-populate
        persona = lock.create_persona(
            agent_id="capability-test",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash="cap123",
            capabilities=AGENT_CAPABILITIES[AgentType.CODING_AGENT]
        )
        
        assert persona.has_capability("file_read")
        assert persona.has_capability("file_write")
        assert persona.has_capability("run_tests")
    
    def test_readonly_agent_limited_capabilities(self, temp_sandbox):
        """Test that readonly agent has limited capabilities."""
        from runtime.persona_lock import AGENT_CAPABILITIES
        
        lock = PersonaLock(temp_sandbox)
        
        persona = lock.create_persona(
            agent_id="readonly-test",
            agent_type=AgentType.READONLY_AGENT,
            constraint_hash="ro123",
            capabilities=AGENT_CAPABILITIES[AgentType.READONLY_AGENT]
        )
        
        assert persona.has_capability("file_read")
        assert not persona.has_capability("file_write")
        assert not persona.has_capability("run_tests")
    
    def test_mismatch_on_type_change_attempt(self, temp_sandbox):
        """Test error when trying to recreate with different type."""
        lock = PersonaLock(temp_sandbox)
        
        lock.create_persona(
            agent_id="type-conflict",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash="orig123"
        )
        
        with pytest.raises(PersonaMismatchViolation):
            lock.create_persona(
                agent_id="type-conflict",
                agent_type=AgentType.ORCHESTRATOR,  # Different type
                constraint_hash="new456"
            )
    
    def test_active_persona_property(self, temp_sandbox):
        """Test active persona property."""
        lock = PersonaLock(temp_sandbox)
        
        assert lock.active_persona is None
        
        persona = lock.create_persona(
            agent_id="active-test",
            agent_type=AgentType.TEST_AGENT,
            constraint_hash="active123"
        )
        
        assert lock.active_persona == persona


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_governance_flow(self, governance_dir, temp_sandbox):
        """Test full flow: load profile → create persona → validate plan → execute."""
        # 1. Load constraint profile
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("coding_agent_profile")
        
        # 2. Create locked persona
        lock = PersonaLock(temp_sandbox)
        persona = lock.create_persona(
            agent_id="integration-agent",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash=profile.integrity_hash
        )
        
        # 3. Create execution proxy
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        # 4. Validate a plan
        matrix = json.loads((governance_dir / "governance_matrix.json").read_text())
        validator = PlanValidator(
            governance_matrix=matrix,
            profile=profile,
            sandbox_root=temp_sandbox
        )
        
        plan = Plan.from_text("1. Read test.py\n2. Run pytest")
        outcome = validator.validate(plan)
        
        # 5. Verify governance chain
        assert profile.integrity_hash == persona.constraint_hash
        assert proxy.profile.integrity_hash == profile.integrity_hash
        assert outcome.policy_hash == profile.integrity_hash
    
    def test_hashes_consistent_across_components(self, governance_dir, temp_sandbox):
        """Test that all components use consistent hashes."""
        loader = ConstraintLoader(governance_dir)
        profile = loader.load("base_profile")
        
        lock = PersonaLock(temp_sandbox)
        persona = lock.create_persona(
            agent_id="hash-consistency",
            agent_type=AgentType.READONLY_AGENT,
            constraint_hash=profile.integrity_hash
        )
        
        proxy = ExecutionProxy(
            profile=profile,
            sandbox_root=temp_sandbox,
            mode=ExecutionMode.DRY_RUN
        )
        
        result = proxy.run_command("ls")
        
        # All should reference same hash
        assert loader.active_hash == profile.integrity_hash
        assert persona.constraint_hash == profile.integrity_hash
        assert result.policy_hash == profile.integrity_hash
