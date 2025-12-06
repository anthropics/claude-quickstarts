"""
Constraint profile loader with inheritance and SHA-256 integrity hashing.

Loads JSON policy files, resolves inheritance chains, and computes
cryptographic hashes for tamper detection. Uses Python standard library only.
"""

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum


class LoaderError(Exception):
    """Base exception for constraint loader errors."""
    pass


class ProfileNotFoundError(LoaderError):
    """Raised when a profile file cannot be found."""
    pass


class ProfileValidationError(LoaderError):
    """Raised when a profile fails validation."""
    pass


class InheritanceError(LoaderError):
    """Raised when inheritance chain is invalid or circular."""
    pass


class ProfileConflictError(LoaderError):
    """Raised when merged profiles have conflicting rules."""
    pass


class ActionPolicy(Enum):
    """Policy decisions for actions."""
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


def _utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class LoadedProfile:
    """A loaded and validated constraint profile with integrity hash."""
    profile_id: str
    version: str
    resolved_permissions: Dict[str, Any]
    resolved_constraints: Dict[str, Any]
    inheritance_chain: List[str]
    integrity_hash: str
    loaded_at: datetime = field(default_factory=_utc_now)
    
    def to_audit_record(self) -> Dict[str, Any]:
        """Generate audit-friendly representation."""
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "integrity_hash": self.integrity_hash,
            "inheritance_chain": self.inheritance_chain,
            "loaded_at": self.loaded_at.isoformat()
        }


class ConstraintLoader:
    """
    Loads constraint profiles with inheritance resolution and integrity hashing.
    
    Usage:
        loader = ConstraintLoader(Path("runtime/governance/"))
        profile = loader.load("coding_agent_profile")
        print(profile.integrity_hash)  # SHA-256 of resolved profile
    """
    
    MAX_INHERITANCE_DEPTH = 10
    REQUIRED_METADATA_KEYS = {"profile_id", "version"}
    
    def __init__(self, governance_dir: Path):
        """
        Initialize loader with governance directory.
        
        Args:
            governance_dir: Path to directory containing JSON policy files.
            
        Raises:
            ProfileNotFoundError: If governance directory doesn't exist.
        """
        if not governance_dir.exists():
            raise ProfileNotFoundError(f"Governance directory not found: {governance_dir}")
        if not governance_dir.is_dir():
            raise ProfileNotFoundError(f"Path is not a directory: {governance_dir}")
        
        self.governance_dir = governance_dir
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._active_profile: Optional[LoadedProfile] = None
    
    @property
    def active_hash(self) -> Optional[str]:
        """Get the integrity hash of the currently active profile."""
        return self._active_profile.integrity_hash if self._active_profile else None
    
    def _read_profile_file(self, profile_id: str) -> Dict[str, Any]:
        """
        Read a profile JSON file from disk.
        
        Args:
            profile_id: Profile identifier (filename without .json extension).
            
        Returns:
            Parsed JSON data.
            
        Raises:
            ProfileNotFoundError: If file doesn't exist.
            ProfileValidationError: If JSON is invalid.
        """
        # Check cache first
        if profile_id in self._cache:
            return self._cache[profile_id]
        
        file_path = self.governance_dir / f"{profile_id}.json"
        
        if not file_path.exists():
            raise ProfileNotFoundError(f"Profile not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ProfileValidationError(f"Invalid JSON in {file_path}: {e}")
        except OSError as e:
            raise ProfileNotFoundError(f"Cannot read {file_path}: {e}")
        
        # Basic structure validation
        if not isinstance(data, dict):
            raise ProfileValidationError(f"Profile must be a JSON object: {profile_id}")
        
        if "metadata" not in data:
            raise ProfileValidationError(f"Profile missing 'metadata' section: {profile_id}")
        
        metadata = data["metadata"]
        missing_keys = self.REQUIRED_METADATA_KEYS - set(metadata.keys())
        if missing_keys:
            raise ProfileValidationError(
                f"Profile {profile_id} missing required metadata: {missing_keys}"
            )
        
        self._cache[profile_id] = data
        return data
    
    def _resolve_inheritance(self, profile_id: str, visited: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Resolve inheritance chain for a profile.
        
        Args:
            profile_id: Starting profile identifier.
            visited: List of already visited profiles (for cycle detection).
            
        Returns:
            List of profile data dicts from base to derived.
            
        Raises:
            InheritanceError: If circular inheritance or depth exceeded.
        """
        if visited is None:
            visited = []
        
        if profile_id in visited:
            cycle = " -> ".join(visited + [profile_id])
            raise InheritanceError(f"Circular inheritance detected: {cycle}")
        
        if len(visited) >= self.MAX_INHERITANCE_DEPTH:
            raise InheritanceError(
                f"Inheritance depth exceeded {self.MAX_INHERITANCE_DEPTH}: {' -> '.join(visited)}"
            )
        
        visited.append(profile_id)
        
        profile_data = self._read_profile_file(profile_id)
        extends = profile_data.get("metadata", {}).get("extends")
        
        if extends:
            # Recursively resolve parent chain
            parent_chain = self._resolve_inheritance(extends, visited)
            return parent_chain + [profile_data]
        else:
            # Base profile - no parent
            return [profile_data]
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge overlay onto base, with overlay taking precedence.
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to merge on top.
            
        Returns:
            Merged dictionary.
        """
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _detect_conflicts(
        self, 
        base: Dict[str, Any], 
        overlay: Dict[str, Any], 
        path: str = ""
    ) -> List[str]:
        """
        Detect conflicting rules between profiles.
        
        Conflict: same action in both 'allow' and 'deny' at same level.
        
        Returns:
            List of conflict descriptions.
        """
        conflicts = []
        
        # Check for allow/deny conflicts at current level
        if "allow" in base and "deny" in overlay:
            base_allow = set(self._flatten_values(base.get("allow", {})))
            overlay_deny = set(self._flatten_values(overlay.get("deny", {})))
            overlap = base_allow & overlay_deny
            if overlap:
                conflicts.append(f"{path}: allow/deny conflict on {overlap}")
        
        if "deny" in base and "allow" in overlay:
            base_deny = set(self._flatten_values(base.get("deny", {})))
            overlay_allow = set(self._flatten_values(overlay.get("allow", {})))
            overlap = base_deny & overlay_allow
            # This is intentional override, not a conflict
        
        # Recurse into nested dicts
        for key in set(base.keys()) | set(overlay.keys()):
            if key in base and key in overlay:
                if isinstance(base[key], dict) and isinstance(overlay[key], dict):
                    nested_path = f"{path}.{key}" if path else key
                    conflicts.extend(self._detect_conflicts(base[key], overlay[key], nested_path))
        
        return conflicts
    
    def _flatten_values(self, obj: Any) -> List[str]:
        """Flatten nested dict/list values to a list of strings."""
        if isinstance(obj, str):
            return [obj]
        elif isinstance(obj, list):
            result = []
            for item in obj:
                result.extend(self._flatten_values(item))
            return result
        elif isinstance(obj, dict):
            result = []
            for value in obj.values():
                result.extend(self._flatten_values(value))
            return result
        else:
            return [str(obj)] if obj is not None else []
    
    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """
        Compute SHA-256 hash of canonicalized profile data.
        
        Args:
            data: Profile data to hash.
            
        Returns:
            Hex-encoded SHA-256 hash.
        """
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def load(self, profile_id: str, check_conflicts: bool = True) -> LoadedProfile:
        """
        Load a profile with inheritance resolution and integrity hashing.
        
        Args:
            profile_id: Profile identifier to load.
            check_conflicts: Whether to check for conflicting rules.
            
        Returns:
            LoadedProfile with resolved permissions and integrity hash.
            
        Raises:
            ProfileNotFoundError: If profile or parent not found.
            ProfileValidationError: If profile data is invalid.
            InheritanceError: If inheritance chain is invalid.
            ProfileConflictError: If conflicting rules detected.
        """
        # Resolve inheritance chain
        chain = self._resolve_inheritance(profile_id)
        chain_ids = [p["metadata"]["profile_id"] for p in chain]
        
        # Merge profiles from base to derived
        merged_permissions: Dict[str, Any] = {}
        merged_constraints: Dict[str, Any] = {}
        
        for profile_data in chain:
            permissions = profile_data.get("permissions", {})
            constraints = profile_data.get("constraints", {})
            
            if check_conflicts and merged_permissions:
                conflicts = self._detect_conflicts(merged_permissions, permissions)
                if conflicts:
                    raise ProfileConflictError(
                        f"Conflicting rules in {profile_data['metadata']['profile_id']}: {conflicts}"
                    )
            
            merged_permissions = self._deep_merge(merged_permissions, permissions)
            merged_constraints = self._deep_merge(merged_constraints, constraints)
        
        # Get version from final (most derived) profile
        final_profile = chain[-1]
        version = final_profile["metadata"]["version"]
        
        # Build resolved profile for hashing
        resolved_data = {
            "profile_id": profile_id,
            "version": version,
            "inheritance_chain": chain_ids,
            "permissions": merged_permissions,
            "constraints": merged_constraints
        }
        
        integrity_hash = self._compute_hash(resolved_data)
        
        loaded = LoadedProfile(
            profile_id=profile_id,
            version=version,
            resolved_permissions=merged_permissions,
            resolved_constraints=merged_constraints,
            inheritance_chain=chain_ids,
            integrity_hash=integrity_hash
        )
        
        self._active_profile = loaded
        return loaded
    
    def verify_integrity(self, profile: LoadedProfile) -> bool:
        """
        Verify that a loaded profile's hash still matches source files.
        
        Args:
            profile: Previously loaded profile to verify.
            
        Returns:
            True if integrity verified, False if files changed.
        """
        # Clear cache to force re-read from disk
        self._cache.clear()
        
        try:
            fresh = self.load(profile.profile_id, check_conflicts=False)
            return fresh.integrity_hash == profile.integrity_hash
        except LoaderError:
            return False
    
    def clear_cache(self) -> None:
        """Clear the profile cache, forcing re-read on next load."""
        self._cache.clear()
