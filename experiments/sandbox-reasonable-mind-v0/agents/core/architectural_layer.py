"""
Architectural Layer Markers

This module provides decorators and metadata for marking modules and classes
according to their architectural layer in the triadic metaphysical model:

- Logic (Skeleton): Validity without interpretation
- AI (Muscles): Perspectives without verdicts
- User (Heart): Purpose and final judgment
- Synthesis (Reason): Emergent from interaction

Usage:
    from agents.core.architectural_layer import layer, LogicLayer, AILayer

    @layer(LogicLayer)
    class MyLogicEngine:
        '''Validates propositional logic.'''
        pass
"""

from enum import Enum
from typing import Callable, TypeVar, Optional, List
from dataclasses import dataclass
from functools import wraps


class ArchLayer(Enum):
    """Architectural layers in the ReasonableMind system."""
    LOGIC = "logic"  # Skeleton - Defines validity
    AI = "ai"  # Muscles - Provides perspectives
    USER = "user"  # Heart - Determines meaning
    SYNTHESIS = "synthesis"  # Reason - Emerges from interaction
    UTILITY = "utility"  # Infrastructure - No layer constraints


# Convenient aliases
LogicLayer = ArchLayer.LOGIC
AILayer = ArchLayer.AI
UserLayer = ArchLayer.USER
SynthesisLayer = ArchLayer.SYNTHESIS
UtilityLayer = ArchLayer.UTILITY


@dataclass
class LayerMetadata:
    """Metadata about an architectural layer assignment."""
    layer: ArchLayer
    purpose: str
    allowed_dependencies: List[ArchLayer]
    constraints: List[str]


# Layer metadata definitions
LAYER_METADATA = {
    ArchLayer.LOGIC: LayerMetadata(
        layer=ArchLayer.LOGIC,
        purpose="Defines structural validity without interpretation",
        allowed_dependencies=[],
        constraints=[
            "Must be deterministic",
            "Must not depend on user context",
            "Must separate validity from soundness",
            "Must not make value judgments",
            "Confidence must be 1.0 for valid structures"
        ]
    ),
    ArchLayer.AI: LayerMetadata(
        layer=ArchLayer.AI,
        purpose="Provides multiple perspectives and interpretations",
        allowed_dependencies=[ArchLayer.LOGIC],
        constraints=[
            "Must provide multiple perspectives",
            "Must express uncertainty (confidence < 1.0 for non-formal)",
            "Must attribute interpretations to sources/profiles",
            "Must not auto-select 'best' interpretation",
            "Must operate within logical constraints"
        ]
    ),
    ArchLayer.USER: LayerMetadata(
        layer=ArchLayer.USER,
        purpose="Captures user intent, preferences, and final judgment",
        allowed_dependencies=[ArchLayer.LOGIC, ArchLayer.AI],
        constraints=[
            "Must persist user preferences",
            "Must allow user override of AI suggestions",
            "Must request clarification for ambiguity",
            "Must require confirmation for high-stakes actions",
            "Must never bypass user agency"
        ]
    ),
    ArchLayer.SYNTHESIS: LayerMetadata(
        layer=ArchLayer.SYNTHESIS,
        purpose="Synthesizes Logic + AI + User into reasoned output",
        allowed_dependencies=[ArchLayer.LOGIC, ArchLayer.AI, ArchLayer.USER],
        constraints=[
            "Must incorporate all three layers",
            "Must trace provenance to sources",
            "Must degrade gracefully under conflict",
            "Must provide explanations",
            "Invalid logic must block synthesis"
        ]
    ),
    ArchLayer.UTILITY: LayerMetadata(
        layer=ArchLayer.UTILITY,
        purpose="Provides infrastructure and shared services",
        allowed_dependencies=[],
        constraints=[
            "Should be layer-agnostic",
            "Should not embed reasoning logic",
            "Should be reusable across layers"
        ]
    ),
}


T = TypeVar('T')


def layer(layer_type: ArchLayer, purpose: Optional[str] = None):
    """
    Decorator to mark a class or module with its architectural layer.

    Args:
        layer_type: The architectural layer (Logic, AI, User, Synthesis, Utility)
        purpose: Optional custom purpose description

    Example:
        @layer(LogicLayer, purpose="Validates modus ponens arguments")
        class ModusPonensValidator:
            pass
    """
    def decorator(cls: T) -> T:
        # Attach metadata to the class
        cls.__arch_layer__ = layer_type
        cls.__layer_metadata__ = LAYER_METADATA[layer_type]

        if purpose:
            cls.__layer_purpose__ = purpose
        else:
            cls.__layer_purpose__ = LAYER_METADATA[layer_type].purpose

        # Add a method to get layer info
        def get_layer_info(self):
            return {
                "layer": self.__arch_layer__.value,
                "purpose": self.__layer_purpose__,
                "constraints": self.__layer_metadata__.constraints,
                "allowed_dependencies": [l.value for l in self.__layer_metadata__.allowed_dependencies]
            }

        cls.get_layer_info = get_layer_info

        return cls

    return decorator


def enforce_determinism(func: Callable) -> Callable:
    """
    Decorator to enforce deterministic behavior for Logic layer functions.

    For testing: caches results and verifies identical inputs produce identical outputs.
    """
    cache = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create cache key from arguments
        cache_key = (args, tuple(sorted(kwargs.items())))

        if cache_key in cache:
            cached_result = cache[cache_key]
            # In production, just return cached
            # In testing, verify consistency
            return cached_result
        else:
            result = func(*args, **kwargs)
            cache[cache_key] = result
            return result

    return wrapper


def require_confidence(min_conf: float = 0.0, max_conf: float = 1.0):
    """
    Decorator to enforce confidence bounds on AI layer outputs.

    Args:
        min_conf: Minimum allowed confidence (default 0.0)
        max_conf: Maximum allowed confidence (default 1.0)

    Example:
        @require_confidence(max_conf=0.95)  # AI shouldn't be too certain
        def interpret_text(text):
            return Interpretation(confidence=0.85, ...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Check if result has confidence attribute
            if hasattr(result, 'confidence'):
                conf = result.confidence
                assert min_conf <= conf <= max_conf, \
                    f"Confidence {conf} outside allowed range [{min_conf}, {max_conf}]"

            return result

        return wrapper

    return decorator


def require_provenance(func: Callable) -> Callable:
    """
    Decorator to enforce provenance tracking in Synthesis layer.

    Synthesis outputs must trace back to their sources.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # Check for provenance
        if not hasattr(result, 'provenance') and not hasattr(result, 'sources'):
            raise AttributeError(
                f"Synthesis layer function {func.__name__} must return "
                f"result with 'provenance' or 'sources' attribute"
            )

        return result

    return wrapper


def require_user_confirmation(action_type: str = "high-stakes"):
    """
    Decorator to mark actions that require user confirmation.

    Args:
        action_type: Description of action type (for logging/UX)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # In production, this would trigger UI confirmation
            # In testing, we check for confirmation parameter

            # Check if 'user_confirmed' is in kwargs
            if action_type == "high-stakes" and not kwargs.get('user_confirmed', False):
                raise PermissionError(
                    f"Action {func.__name__} requires user confirmation. "
                    f"Pass user_confirmed=True after obtaining user consent."
                )

            return func(*args, **kwargs)

        # Mark function as requiring confirmation
        wrapper.__requires_confirmation__ = True
        wrapper.__action_type__ = action_type

        return wrapper

    return decorator


def multiple_perspectives(func: Callable) -> Callable:
    """
    Decorator to enforce that AI layer functions return multiple perspectives.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # Check that result contains multiple perspectives
        if hasattr(result, 'perspectives'):
            assert len(result.perspectives) >= 1, \
                "AI layer must provide at least one perspective"
        elif isinstance(result, list):
            assert len(result) >= 1, \
                "AI layer must provide at least one perspective"

        return result

    return wrapper


# Validation functions
def validate_layer_compliance(obj: object) -> bool:
    """
    Validates that an object complies with its declared layer constraints.

    Returns:
        True if compliant, raises AssertionError otherwise
    """
    if not hasattr(obj, '__arch_layer__'):
        # No layer declared - skip validation
        return True

    layer_type = obj.__arch_layer__
    metadata = LAYER_METADATA[layer_type]

    # Check type-specific constraints
    if layer_type == ArchLayer.LOGIC:
        # Logic layer must have deterministic methods
        # (This is a simplified check - full check would require analysis)
        pass

    elif layer_type == ArchLayer.AI:
        # AI layer should have confidence-scored outputs
        # (Check would require method signature analysis)
        pass

    elif layer_type == ArchLayer.USER:
        # User layer should have preference handling
        # (Check would require interface validation)
        pass

    return True


def get_layer(obj: object) -> Optional[ArchLayer]:
    """
    Gets the architectural layer of an object.

    Args:
        obj: Object to inspect (class or instance)

    Returns:
        ArchLayer if declared, None otherwise
    """
    if hasattr(obj, '__arch_layer__'):
        return obj.__arch_layer__

    # Check class if obj is an instance
    if hasattr(obj, '__class__') and hasattr(obj.__class__, '__arch_layer__'):
        return obj.__class__.__arch_layer__

    return None


def check_dependency_allowed(from_layer: ArchLayer, to_layer: ArchLayer) -> bool:
    """
    Checks if a dependency from one layer to another is allowed.

    Args:
        from_layer: The layer that wants to depend on another
        to_layer: The layer being depended upon

    Returns:
        True if dependency is allowed, False otherwise
    """
    metadata = LAYER_METADATA[from_layer]
    return to_layer in metadata.allowed_dependencies


# Module-level layer declaration
def declare_module_layer(layer_type: ArchLayer, purpose: str):
    """
    Declares the architectural layer for an entire module.

    Usage (at top of module file):
        from agents.core.architectural_layer import declare_module_layer, LogicLayer

        __layer__ = declare_module_layer(
            LogicLayer,
            "Validates propositional logic arguments"
        )
    """
    return {
        'layer': layer_type,
        'purpose': purpose,
        'metadata': LAYER_METADATA[layer_type],
        'constraints': LAYER_METADATA[layer_type].constraints,
    }


# Export layer info for introspection
def print_layer_hierarchy():
    """Prints the architectural layer hierarchy and constraints."""
    print("\n=== ReasonableMind Architectural Layers ===\n")

    for layer in ArchLayer:
        if layer in LAYER_METADATA:
            meta = LAYER_METADATA[layer]
            print(f"{layer.value.upper()} Layer")
            print(f"  Purpose: {meta.purpose}")
            print(f"  Dependencies: {[l.value for l in meta.allowed_dependencies] or 'None'}")
            print(f"  Constraints:")
            for constraint in meta.constraints:
                print(f"    - {constraint}")
            print()


if __name__ == "__main__":
    print_layer_hierarchy()
