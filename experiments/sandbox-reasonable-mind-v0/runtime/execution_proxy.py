"""
Execution proxy implementing Strictness B governance.

Wraps Python operations (open, pathlib writes, subprocess) with
policy enforcement. All actions are validated against loaded
constraint profiles before execution.

Strictness B: Semi-open subprocess + restricted writes
- Read-only commands: allowed
- Python tooling (pytest, python): allowed
- git add/commit: requires approval
- push, pip install, network: blocked
"""

import subprocess
import functools
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Union, Set
from enum import Enum
import fnmatch
import re

from .constraint_loader import ConstraintLoader, LoadedProfile, ActionPolicy


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ExecutionMode(Enum):
    """Proxy execution modes."""
    LIVE = "live"          # Execute operations
    DRY_RUN = "dry_run"    # Validate only, don't execute
    MOCK = "mock"          # Return mock results


class ActionType(Enum):
    """Types of actions the proxy can intercept."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_CREATE = "file_create"
    SUBPROCESS = "subprocess"
    NETWORK = "network"


class Decision(Enum):
    """Policy decision for an action."""
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


@dataclass
class ActionRequest:
    """Request for an action to be validated."""
    action_type: ActionType
    target: str  # file path or command
    details: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass
class ActionResult:
    """Result of an action request."""
    request: ActionRequest
    decision: Decision
    allowed: bool
    reason: str
    executed: bool = False
    result: Any = None
    error: Optional[str] = None
    policy_hash: Optional[str] = None


@dataclass
class AuditEntry:
    """Audit log entry for governance."""
    correlation_id: str
    timestamp: datetime
    action_type: ActionType
    target: str
    decision: Decision
    reason: str
    policy_hash: Optional[str]
    executed: bool
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


class ExecutionProxy:
    """
    Governance-aware execution proxy for Strictness B.
    
    Intercepts and validates:
    - File operations (read, write, create, delete)
    - Subprocess calls
    - Network operations (blocked by default)
    
    Usage:
        loader = ConstraintLoader(Path("runtime/governance/"))
        profile = loader.load("coding_agent_profile")
        proxy = ExecutionProxy(profile, sandbox_root=Path("sandbox/"))
        
        # File operations
        result = proxy.read_file(Path("test.py"))
        result = proxy.write_file(Path("output.txt"), "content")
        
        # Subprocess
        result = proxy.run_command(["pytest", "tests/"])
    """
    
    # Read-only commands always allowed
    READONLY_COMMANDS: Set[str] = {
        "ls", "cat", "head", "tail", "wc", "grep", "find", "pwd", 
        "echo", "date", "which", "type", "file", "stat", "diff"
    }
    
    # Python tooling allowed
    PYTHON_TOOLING: Set[str] = {
        "python", "python3", "pytest", "pylint", "flake8", "ruff",
        "mypy", "black", "isort"
    }
    
    # Commands requiring approval
    APPROVAL_REQUIRED: Set[str] = {
        "git add", "git commit", "git stash", "git checkout",
        "git branch", "git merge", "git rebase"
    }
    
    # Always blocked
    BLOCKED_COMMANDS: Set[str] = {
        "git push", "git pull", "pip install", "pip uninstall",
        "npm install", "yarn add", "brew install",
        "curl", "wget", "nc", "netcat", "ssh", "scp", "rsync",
        "rm -rf", "sudo", "chmod 777", "chown",
        "shutdown", "reboot", "halt"
    }
    
    # Blocked patterns (regex)
    BLOCKED_PATTERNS: List[str] = [
        r".*\|\s*sh\b",           # pipe to sh
        r".*\|\s*bash\b",         # pipe to bash
        r"curl.*\|",              # curl piped
        r"wget.*\|",              # wget piped
        r".*>\s*/etc/",           # writes to /etc
        r".*>\s*/usr/",           # writes to /usr
        r"rm\s+-[rf]*\s+/",       # rm with absolute path
    ]
    
    def __init__(
        self,
        profile: LoadedProfile,
        sandbox_root: Path,
        mode: ExecutionMode = ExecutionMode.LIVE,
        approval_callback: Optional[Callable[[ActionRequest], bool]] = None,
        log_dir: Optional[Path] = None
    ):
        """
        Initialize execution proxy.
        
        Args:
            profile: Loaded constraint profile for policy decisions.
            sandbox_root: Root directory of the sandbox (all writes restricted here).
            mode: Execution mode (LIVE, DRY_RUN, MOCK).
            approval_callback: Function to call for escalated actions.
            log_dir: Directory for audit logs (defaults to sandbox_root/.audit/).
        """
        self.profile = profile
        self.sandbox_root = sandbox_root.resolve()
        self.mode = mode
        self.approval_callback = approval_callback
        self.log_dir = log_dir or (sandbox_root / ".audit")
        
        self._audit_log: List[AuditEntry] = []
        self._friction_log: Dict[str, int] = {}  # Track denials for tuning
        
        # Ensure log directory exists
        if mode == ExecutionMode.LIVE:
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _is_in_sandbox(self, path: Path) -> bool:
        """Check if path is within sandbox root."""
        try:
            # Resolve both paths to handle symlinks (e.g., /var -> /private/var on macOS)
            resolved = path.resolve()
            sandbox_resolved = self.sandbox_root.resolve()
            return str(resolved).startswith(str(sandbox_resolved))
        except (OSError, ValueError):
            return False
    
    def _match_patterns(self, value: str, patterns: List[str]) -> bool:
        """Check if value matches any glob patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(value, pattern):
                return True
        return False
    
    def _match_regex_patterns(self, value: str, patterns: List[str]) -> bool:
        """Check if value matches any regex patterns."""
        for pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    def _get_command_base(self, cmd: Union[str, List[str]]) -> str:
        """Extract base command from command string or list."""
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
        return cmd_str.strip()
    
    def _check_file_policy(self, action_type: ActionType, path: Path) -> Decision:
        """Check policy for file operations."""
        permissions = self.profile.resolved_permissions.get("file_operations", {})
        path_str = str(path)
        # Use resolved paths to handle symlinks
        try:
            relative_path = str(path.resolve().relative_to(self.sandbox_root.resolve())) if self._is_in_sandbox(path) else path_str
        except ValueError:
            relative_path = path_str
        
        # Map action type to permission key
        action_map = {
            ActionType.FILE_READ: "read",
            ActionType.FILE_WRITE: "write",
            ActionType.FILE_CREATE: "create",
            ActionType.FILE_DELETE: "delete"
        }
        action_key = action_map.get(action_type, "read")
        
        # Check deny first (deny takes precedence)
        deny_section = permissions.get("deny", {})
        deny_patterns = deny_section.get(action_key, [])
        if isinstance(deny_patterns, list) and self._match_patterns(relative_path, deny_patterns):
            return Decision.DENY
        
        # Check escalate
        escalate_section = permissions.get("escalate", {})
        escalate_patterns = escalate_section.get(action_key, [])
        if isinstance(escalate_patterns, list) and self._match_patterns(relative_path, escalate_patterns):
            return Decision.ESCALATE
        
        # Check allow
        allow_section = permissions.get("allow", {})
        allow_patterns = allow_section.get(action_key, [])
        if isinstance(allow_patterns, list) and self._match_patterns(relative_path, allow_patterns):
            return Decision.ALLOW
        
        # Default: deny for writes, allow for reads
        if action_type in (ActionType.FILE_WRITE, ActionType.FILE_DELETE, ActionType.FILE_CREATE):
            return Decision.DENY
        return Decision.ALLOW
    
    def _check_subprocess_policy(self, cmd: str) -> Decision:
        """Check policy for subprocess commands."""
        cmd_lower = cmd.lower().strip()
        cmd_parts = cmd_lower.split()
        base_cmd = cmd_parts[0] if cmd_parts else ""
        
        # Check blocked patterns first
        if self._match_regex_patterns(cmd, self.BLOCKED_PATTERNS):
            return Decision.DENY
        
        # Check explicit blocks
        for blocked in self.BLOCKED_COMMANDS:
            if cmd_lower.startswith(blocked) or blocked in cmd_lower:
                return Decision.DENY
        
        # Check approval required
        for approval_cmd in self.APPROVAL_REQUIRED:
            if cmd_lower.startswith(approval_cmd):
                return Decision.ESCALATE
        
        # Check read-only commands
        if base_cmd in self.READONLY_COMMANDS:
            return Decision.ALLOW
        
        # Check Python tooling
        if base_cmd in self.PYTHON_TOOLING:
            return Decision.ALLOW
        
        # Check profile permissions
        permissions = self.profile.resolved_permissions.get("subprocess", {})
        
        # Check deny
        deny_cmds = permissions.get("deny", {}).get("commands", [])
        if base_cmd in deny_cmds or cmd_lower in deny_cmds:
            return Decision.DENY
        
        # Check allow
        allow_cmds = permissions.get("allow", {}).get("commands", [])
        if base_cmd in allow_cmds:
            return Decision.ALLOW
        
        # Check escalate
        escalate_cmds = permissions.get("escalate", {}).get("commands", [])
        if base_cmd in escalate_cmds:
            return Decision.ESCALATE
        
        # Default: escalate unknown commands
        return Decision.ESCALATE
    
    def _request_approval(self, request: ActionRequest) -> bool:
        """Request approval for escalated action."""
        if self.approval_callback:
            return self.approval_callback(request)
        # No callback = deny by default
        return False
    
    def _log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry."""
        self._audit_log.append(entry)
        
        # Track friction (denials) for tuning
        if entry.decision == Decision.DENY:
            key = f"{entry.action_type.value}:{entry.target}"
            self._friction_log[key] = self._friction_log.get(key, 0) + 1
        
        # Write to disk in LIVE mode
        if self.mode == ExecutionMode.LIVE and self.log_dir.exists():
            log_file = self.log_dir / f"audit_{_utc_now().strftime('%Y%m%d')}.jsonl"
            import json
            with open(log_file, 'a', encoding='utf-8') as f:
                record = {
                    "correlation_id": entry.correlation_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "action_type": entry.action_type.value,
                    "target": entry.target,
                    "decision": entry.decision.value,
                    "reason": entry.reason,
                    "policy_hash": entry.policy_hash,
                    "executed": entry.executed,
                    "success": entry.success,
                    "details": entry.details
                }
                f.write(json.dumps(record) + "\n")
    
    def _validate_and_execute(
        self,
        request: ActionRequest,
        decision: Decision,
        reason: str,
        executor: Callable[[], Any]
    ) -> ActionResult:
        """Validate decision and execute if allowed."""
        allowed = decision == Decision.ALLOW
        
        # Handle escalation
        if decision == Decision.ESCALATE:
            if self._request_approval(request):
                allowed = True
                reason = f"Escalated and approved: {reason}"
            else:
                reason = f"Escalated and denied: {reason}"
        
        result = ActionResult(
            request=request,
            decision=decision,
            allowed=allowed,
            reason=reason,
            policy_hash=self.profile.integrity_hash
        )
        
        # Execute if allowed and in LIVE mode
        if allowed and self.mode == ExecutionMode.LIVE:
            try:
                result.result = executor()
                result.executed = True
            except Exception as e:
                result.error = str(e)
                result.executed = True
        elif allowed and self.mode == ExecutionMode.MOCK:
            result.result = {"mock": True, "action": request.action_type.value}
            result.executed = True
        
        # Log audit
        self._log_audit(AuditEntry(
            correlation_id=request.correlation_id,
            timestamp=request.timestamp,
            action_type=request.action_type,
            target=request.target,
            decision=decision,
            reason=reason,
            policy_hash=self.profile.integrity_hash,
            executed=result.executed,
            success=result.error is None,
            details=request.details
        ))
        
        return result
    
    # ==================== File Operations ====================
    
    def read_file(self, path: Path, encoding: str = "utf-8") -> ActionResult:
        """
        Read a file with governance validation.
        
        Args:
            path: Path to file to read.
            encoding: File encoding.
            
        Returns:
            ActionResult with file contents or error.
        """
        request = ActionRequest(
            action_type=ActionType.FILE_READ,
            target=str(path),
            details={"encoding": encoding}
        )
        
        decision = self._check_file_policy(ActionType.FILE_READ, path)
        reason = f"File read: {path.name}"
        
        def executor():
            return path.read_text(encoding=encoding)
        
        return self._validate_and_execute(request, decision, reason, executor)
    
    def write_file(
        self, 
        path: Path, 
        content: str, 
        encoding: str = "utf-8",
        create_parents: bool = False
    ) -> ActionResult:
        """
        Write to a file with governance validation.
        
        Args:
            path: Path to file to write.
            content: Content to write.
            encoding: File encoding.
            create_parents: Whether to create parent directories.
            
        Returns:
            ActionResult indicating success or denial.
        """
        # Must be in sandbox
        if not self._is_in_sandbox(path):
            request = ActionRequest(
                action_type=ActionType.FILE_WRITE,
                target=str(path),
                details={"encoding": encoding, "size": len(content)}
            )
            return ActionResult(
                request=request,
                decision=Decision.DENY,
                allowed=False,
                reason=f"Write denied: path outside sandbox ({self.sandbox_root})",
                policy_hash=self.profile.integrity_hash
            )
        
        action_type = ActionType.FILE_CREATE if not path.exists() else ActionType.FILE_WRITE
        request = ActionRequest(
            action_type=action_type,
            target=str(path),
            details={"encoding": encoding, "size": len(content)}
        )
        
        decision = self._check_file_policy(action_type, path)
        reason = f"File {'create' if action_type == ActionType.FILE_CREATE else 'write'}: {path.name}"
        
        def executor():
            if create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=encoding)
            return {"written": len(content)}
        
        return self._validate_and_execute(request, decision, reason, executor)
    
    def delete_file(self, path: Path) -> ActionResult:
        """
        Delete a file with governance validation.
        
        Args:
            path: Path to file to delete.
            
        Returns:
            ActionResult indicating success or denial.
        """
        if not self._is_in_sandbox(path):
            request = ActionRequest(
                action_type=ActionType.FILE_DELETE,
                target=str(path)
            )
            return ActionResult(
                request=request,
                decision=Decision.DENY,
                allowed=False,
                reason=f"Delete denied: path outside sandbox",
                policy_hash=self.profile.integrity_hash
            )
        
        request = ActionRequest(
            action_type=ActionType.FILE_DELETE,
            target=str(path)
        )
        
        decision = self._check_file_policy(ActionType.FILE_DELETE, path)
        reason = f"File delete: {path.name}"
        
        def executor():
            path.unlink()
            return {"deleted": True}
        
        return self._validate_and_execute(request, decision, reason, executor)
    
    # ==================== Subprocess Operations ====================
    
    def run_command(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[Path] = None,
        timeout: Optional[int] = 60,
        capture_output: bool = True
    ) -> ActionResult:
        """
        Run a subprocess command with governance validation.
        
        Args:
            cmd: Command to run (string or list).
            cwd: Working directory (must be in sandbox).
            timeout: Command timeout in seconds.
            capture_output: Whether to capture stdout/stderr.
            
        Returns:
            ActionResult with command output or denial.
        """
        cmd_str = self._get_command_base(cmd)
        
        # Validate cwd is in sandbox
        if cwd and not self._is_in_sandbox(cwd):
            request = ActionRequest(
                action_type=ActionType.SUBPROCESS,
                target=cmd_str,
                details={"cwd": str(cwd)}
            )
            return ActionResult(
                request=request,
                decision=Decision.DENY,
                allowed=False,
                reason=f"Subprocess denied: cwd outside sandbox",
                policy_hash=self.profile.integrity_hash
            )
        
        request = ActionRequest(
            action_type=ActionType.SUBPROCESS,
            target=cmd_str,
            details={
                "cwd": str(cwd) if cwd else str(self.sandbox_root),
                "timeout": timeout
            }
        )
        
        decision = self._check_subprocess_policy(cmd_str)
        reason = f"Subprocess: {cmd_str[:50]}{'...' if len(cmd_str) > 50 else ''}"
        
        def executor():
            result = subprocess.run(
                cmd if isinstance(cmd, list) else cmd,
                shell=isinstance(cmd, str),
                cwd=cwd or self.sandbox_root,
                timeout=timeout,
                capture_output=capture_output,
                text=True
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout if capture_output else None,
                "stderr": result.stderr if capture_output else None
            }
        
        return self._validate_and_execute(request, decision, reason, executor)
    
    # ==================== Reporting ====================
    
    def get_audit_log(self) -> List[AuditEntry]:
        """Get in-memory audit log."""
        return self._audit_log.copy()
    
    def get_friction_report(self) -> Dict[str, int]:
        """
        Get friction report showing frequently denied actions.
        
        Use this to tune governance policies - high friction on
        legitimate actions suggests policy is too restrictive.
        """
        return dict(sorted(
            self._friction_log.items(),
            key=lambda x: x[1],
            reverse=True
        ))
    
    def clear_logs(self) -> None:
        """Clear in-memory audit and friction logs."""
        self._audit_log.clear()
        self._friction_log.clear()
