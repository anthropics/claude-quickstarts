"""
Persona Locking System for agent identity protection.

Provides immutable agent context with cryptographic binding to
constraint profiles. Any attempt to modify agent identity after
creation raises a governance violation.

Persona metadata is persisted to .sandbox_config.yaml for
cross-session identity verification.
"""

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, FrozenSet
from enum import Enum
import re


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class PersonaViolation(Exception):
    """Raised when persona integrity is violated."""
    pass


class PersonaLockViolation(PersonaViolation):
    """Raised when attempting to modify a locked persona."""
    pass


class PersonaMismatchViolation(PersonaViolation):
    """Raised when persona doesn't match persisted metadata."""
    pass


class AgentType(Enum):
    """Supported agent types with capability sets."""
    CODING_AGENT = "coding_agent"
    REVIEW_AGENT = "review_agent"
    TEST_AGENT = "test_agent"
    READONLY_AGENT = "readonly_agent"
    ORCHESTRATOR = "orchestrator"
    CUSTOM = "custom"


# Capability sets for each agent type
AGENT_CAPABILITIES: Dict[AgentType, FrozenSet[str]] = {
    AgentType.CODING_AGENT: frozenset({
        "file_read", "file_write", "file_create",
        "run_tests", "run_linters", "git_stage", "git_commit"
    }),
    AgentType.REVIEW_AGENT: frozenset({
        "file_read", "run_linters", "add_comments"
    }),
    AgentType.TEST_AGENT: frozenset({
        "file_read", "run_tests", "file_create"
    }),
    AgentType.READONLY_AGENT: frozenset({
        "file_read"
    }),
    AgentType.ORCHESTRATOR: frozenset({
        "file_read", "spawn_agent", "coordinate"
    }),
    AgentType.CUSTOM: frozenset(),  # Defined per-instance
}


class _ImmutableMeta(type):
    """Metaclass that prevents attribute modification after __init__."""
    
    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        instance._locked = True
        return instance


class PersonaContext:
    """
    Immutable agent persona context.
    
    Once created, agent_id, agent_type, and constraint_hash cannot
    be modified. Any attempt raises PersonaLockViolation.
    
    Usage:
        persona = PersonaContext(
            agent_id="agent-001",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash="abc123..."
        )
        
        # This will raise PersonaLockViolation:
        persona.agent_type = AgentType.ORCHESTRATOR
    """
    
    # Immutable fields that cannot be changed after creation
    _IMMUTABLE_FIELDS = {'agent_id', 'agent_type', 'constraint_hash', 'capabilities', 'created_at'}
    
    # Type annotations for attributes
    agent_id: str
    agent_type: AgentType
    constraint_hash: str
    capabilities: FrozenSet[str]
    metadata: Dict[str, Any]
    created_at: datetime
    _locked: bool
    
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        constraint_hash: str,
        capabilities: Optional[FrozenSet[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None
    ):
        # Validate agent_id format
        if not re.match(r'^[a-zA-Z0-9_-]+$', agent_id):
            raise ValueError(f"Invalid agent_id format: {agent_id}")
        
        # Set all attributes before locking
        object.__setattr__(self, '_locked', False)
        object.__setattr__(self, 'agent_id', agent_id)
        object.__setattr__(self, 'agent_type', agent_type)
        object.__setattr__(self, 'constraint_hash', constraint_hash)
        object.__setattr__(self, 'metadata', metadata or {})
        object.__setattr__(self, 'created_at', created_at or _utc_now())
        
        # Set capabilities from agent type if not provided
        if capabilities is None:
            capabilities = AGENT_CAPABILITIES.get(agent_type, frozenset())
        if not isinstance(capabilities, frozenset):
            capabilities = frozenset(capabilities)
        object.__setattr__(self, 'capabilities', capabilities)
        
        # Lock the object
        object.__setattr__(self, '_locked', True)
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent modification of locked attributes."""
        # Check if locked
        if getattr(self, '_locked', False):
            if name in self._IMMUTABLE_FIELDS:
                raise PersonaLockViolation(
                    f"Cannot modify locked field '{name}' on persona '{self.agent_id}'. "
                    f"Attempted change: {getattr(self, name, None)} -> {value}"
                )
        
        # Allow setting
        object.__setattr__(self, name, value)
    
    def __delattr__(self, name: str) -> None:
        """Prevent deletion of any attributes."""
        raise PersonaLockViolation(
            f"Cannot delete attribute '{name}' from locked persona '{self.agent_id}'"
        )
    
    def __hash__(self) -> int:
        """Make persona hashable for use in sets/dicts."""
        return hash((self.agent_id, self.agent_type, self.constraint_hash))
    
    def has_capability(self, capability: str) -> bool:
        """Check if persona has a specific capability."""
        return capability in self.capabilities
    
    def get_identity_hash(self) -> str:
        """
        Compute cryptographic hash of persona identity.
        
        Used for verification against persisted metadata.
        """
        identity = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "constraint_hash": self.constraint_hash,
            "capabilities": sorted(self.capabilities)
        }
        canonical = json.dumps(identity, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "constraint_hash": self.constraint_hash,
            "capabilities": sorted(self.capabilities),
            "identity_hash": self.get_identity_hash(),
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonaContext":
        """
        Recreate persona from persisted dictionary.
        
        Validates identity hash if present.
        """
        agent_type = AgentType(data["agent_type"])
        capabilities = frozenset(data.get("capabilities", []))
        
        # Parse created_at if string
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = _utc_now()
        
        persona = cls(
            agent_id=data["agent_id"],
            agent_type=agent_type,
            constraint_hash=data["constraint_hash"],
            capabilities=capabilities,
            metadata=data.get("metadata", {}),
            created_at=created_at
        )
        
        # Verify identity hash if provided
        stored_hash = data.get("identity_hash")
        if stored_hash and persona.get_identity_hash() != stored_hash:
            raise PersonaMismatchViolation(
                f"Persona identity hash mismatch for '{persona.agent_id}'. "
                f"Stored: {stored_hash[:16]}..., Computed: {persona.get_identity_hash()[:16]}..."
            )
        
        return persona


class PersonaLock:
    """
    Manages persona lifecycle and persistence.
    
    Persists persona metadata to .sandbox_config.yaml and validates
    identity on reload.
    
    Usage:
        lock = PersonaLock(sandbox_root=Path("sandbox/"))
        
        # Create and persist persona
        persona = lock.create_persona(
            agent_id="coding-agent-001",
            agent_type=AgentType.CODING_AGENT,
            constraint_hash=profile.integrity_hash
        )
        
        # Later: reload and verify
        loaded = lock.load_persona("coding-agent-001")
        assert loaded.agent_type == AgentType.CODING_AGENT
    """
    
    CONFIG_FILE = ".sandbox_config.yaml"
    
    def __init__(self, sandbox_root: Path):
        """
        Initialize persona lock manager.
        
        Args:
            sandbox_root: Root directory of sandbox.
        """
        self.sandbox_root = sandbox_root.resolve()
        self.config_path = self.sandbox_root / self.CONFIG_FILE
        self._active_persona: Optional[PersonaContext] = None
    
    @property
    def active_persona(self) -> Optional[PersonaContext]:
        """Get the currently active persona."""
        return self._active_persona
    
    def _load_config(self) -> Dict[str, Any]:
        """Load sandbox config from YAML file."""
        if not self.config_path.exists():
            return {"personas": {}}
        
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            return config
        except ImportError:
            # Fallback to JSON-like parsing if PyYAML not available
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Simple YAML subset parsing
            return self._parse_simple_yaml(content)
    
    def _parse_simple_yaml(self, content: str) -> Dict[str, Any]:
        """Parse simple YAML subset without PyYAML dependency."""
        result: Dict[str, Any] = {"personas": {}}
        current_section = None
        current_persona = None
        
        for line in content.split('\n'):
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            
            # Top-level key
            if not line.startswith(' ') and ':' in line:
                key = line.split(':')[0].strip()
                current_section = key
                if key == "personas":
                    result["personas"] = {}
            # Nested persona
            elif line.startswith('  ') and not line.startswith('    ') and ':' in line:
                key = line.strip().split(':')[0].strip()
                current_persona = key
                result["personas"][key] = {}
            # Persona field
            elif line.startswith('    ') and ':' in line and current_persona:
                parts = line.strip().split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""
                # Handle quoted strings
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                result["personas"][current_persona][key] = value
        
        return result
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """Save sandbox config to YAML file."""
        try:
            import yaml
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=True)
        except ImportError:
            # Fallback to simple YAML generation
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self._write_simple_yaml(f, config)
    
    def _write_simple_yaml(self, f, config: Dict[str, Any], indent: int = 0) -> None:
        """Write simple YAML without PyYAML dependency."""
        prefix = "  " * indent
        for key, value in config.items():
            if isinstance(value, dict):
                f.write(f"{prefix}{key}:\n")
                self._write_simple_yaml(f, value, indent + 1)
            elif isinstance(value, list):
                f.write(f"{prefix}{key}:\n")
                for item in value:
                    f.write(f"{prefix}  - {item}\n")
            else:
                # Quote strings with special chars
                if isinstance(value, str) and any(c in value for c in ':{}[],"\''):
                    value = f'"{value}"'
                f.write(f"{prefix}{key}: {value}\n")
    
    def create_persona(
        self,
        agent_id: str,
        agent_type: AgentType,
        constraint_hash: str,
        capabilities: Optional[FrozenSet[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True
    ) -> PersonaContext:
        """
        Create a new persona and optionally persist it.
        
        Args:
            agent_id: Unique identifier for the agent.
            agent_type: Type of agent (determines capabilities).
            constraint_hash: Hash of the constraint profile.
            capabilities: Override default capabilities.
            metadata: Additional metadata.
            persist: Whether to save to config file.
            
        Returns:
            Locked PersonaContext.
            
        Raises:
            PersonaMismatchViolation: If agent_id already exists with different type.
        """
        # Check if persona already exists
        config = self._load_config()
        existing = config.get("personas", {}).get(agent_id)
        
        if existing:
            # Verify type matches
            if existing.get("agent_type") != agent_type.value:
                raise PersonaMismatchViolation(
                    f"Persona '{agent_id}' already exists with type "
                    f"'{existing.get('agent_type')}', cannot create as '{agent_type.value}'"
                )
        
        persona = PersonaContext(
            agent_id=agent_id,
            agent_type=agent_type,
            constraint_hash=constraint_hash,
            capabilities=capabilities or frozenset(),
            metadata=metadata or {}
        )
        
        if persist:
            self._persist_persona(persona)
        
        self._active_persona = persona
        return persona
    
    def _persist_persona(self, persona: PersonaContext) -> None:
        """Save persona to config file."""
        config = self._load_config()
        
        if "personas" not in config:
            config["personas"] = {}
        
        config["personas"][persona.agent_id] = persona.to_dict()
        self._save_config(config)
    
    def load_persona(self, agent_id: str) -> PersonaContext:
        """
        Load and verify a persisted persona.
        
        Args:
            agent_id: ID of persona to load.
            
        Returns:
            Verified PersonaContext.
            
        Raises:
            PersonaViolation: If persona not found.
            PersonaMismatchViolation: If identity hash doesn't match.
        """
        config = self._load_config()
        personas = config.get("personas", {})
        
        if agent_id not in personas:
            raise PersonaViolation(f"Persona '{agent_id}' not found in config")
        
        persona = PersonaContext.from_dict(personas[agent_id])
        self._active_persona = persona
        return persona
    
    def verify_active(self, expected_type: AgentType) -> bool:
        """
        Verify the active persona matches expected type.
        
        Args:
            expected_type: Expected agent type.
            
        Returns:
            True if matches.
            
        Raises:
            PersonaMismatchViolation: If type doesn't match.
        """
        if not self._active_persona:
            raise PersonaViolation("No active persona")
        
        if self._active_persona.agent_type != expected_type:
            raise PersonaMismatchViolation(
                f"Active persona type mismatch. "
                f"Expected: {expected_type.value}, "
                f"Actual: {self._active_persona.agent_type.value}"
            )
        
        return True
    
    def list_personas(self) -> Dict[str, Dict[str, Any]]:
        """List all persisted personas."""
        config = self._load_config()
        return config.get("personas", {})
    
    def delete_persona(self, agent_id: str) -> bool:
        """
        Delete a persisted persona.
        
        Args:
            agent_id: ID of persona to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        config = self._load_config()
        personas = config.get("personas", {})
        
        if agent_id in personas:
            del personas[agent_id]
            config["personas"] = personas
            self._save_config(config)
            
            if self._active_persona and self._active_persona.agent_id == agent_id:
                self._active_persona = None
            
            return True
        
        return False
