"""
Role Adaptation System - Phase 2

Implements:
- Persona configurations (lawyer, scientist, tutor, etc.)
- Domain-specific reasoning constraints
- Role-appropriate language and framing
- Expertise level calibration
"""

from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum


class ExpertiseLevel(Enum):
    """Level of expertise for role adaptation."""
    NOVICE = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    MASTER = 5


class CommunicationStyle(Enum):
    """Communication style for role."""
    FORMAL = "formal"
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    EDUCATIONAL = "educational"
    SOCRATIC = "socratic"
    AUTHORITATIVE = "authoritative"


@dataclass
class DomainConstraint:
    """Constraint specific to a domain."""
    name: str
    description: str
    check_fn: Optional[Callable[[str], bool]] = None
    violation_message: str = ""


@dataclass
class ReasoningMode:
    """Mode of reasoning for a role."""
    name: str
    description: str
    required_steps: List[str]
    forbidden_fallacies: List[str]
    preferred_argument_forms: List[str]


@dataclass
class RolePersona:
    """Complete persona configuration for a role."""
    role_id: str
    name: str
    description: str
    domain: str


class RoleCapability(Enum):
    """Capabilities used in tests."""
    DATA_ANALYSIS = "data_analysis"
    STATISTICAL_REASONING = "statistical_reasoning"
    LOGICAL_ANALYSIS = "logical_analysis"


@dataclass
class Role:
    role_id: str
    name: str
    capabilities: List[RoleCapability]


class RoleAssigner:
    """Simple heuristic role assigner."""
    def assign_role(self, task: str, available_roles: List[str]) -> Optional[str]:
        # Pick the first available role for simplicity
        return available_roles[0] if available_roles else None


class RoleSystem:
    """Minimal role system covering tests."""
    def __init__(self):
        self.active: Set[str] = set()
        # default capabilities map
        self.role_capabilities: Dict[str, Set[RoleCapability]] = {
            "analyst": {RoleCapability.DATA_ANALYSIS, RoleCapability.STATISTICAL_REASONING},
            "researcher": {RoleCapability.LOGICAL_ANALYSIS},
            "critic": {RoleCapability.LOGICAL_ANALYSIS},
            "synthesizer": {RoleCapability.LOGICAL_ANALYSIS},
        }

    def check_capability(self, role_id: str, capability: RoleCapability) -> bool:
        return capability in self.role_capabilities.get(role_id, set())

    def activate_role(self, role_id: str) -> None:
        self.active.add(role_id)

    def get_active_roles(self) -> List[str]:
        return list(self.active)

    def assign_best_role(self, task: str) -> Optional[str]:
        # Simple heuristic: return role with logical capability if needed
        for role_id, caps in self.role_capabilities.items():
            if RoleCapability.LOGICAL_ANALYSIS in caps:
                return role_id
        return next(iter(self.role_capabilities), None)
    expertise_level: ExpertiseLevel
    communication_style: CommunicationStyle
    reasoning_mode: ReasoningMode
    constraints: List[DomainConstraint] = field(default_factory=list)
    vocabulary: Dict[str, str] = field(default_factory=dict)  # term -> preferred term
    forbidden_phrases: List[str] = field(default_factory=list)
    required_disclaimers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdaptedResponse:
    """Response adapted to a role."""
    original_response: str
    adapted_response: str
    role_id: str
    adaptations_made: List[str]
    constraints_checked: List[str]
    violations: List[str]


class RoleRegistry:
    """Registry of available roles."""
    
    def __init__(self):
        self.roles: Dict[str, RolePersona] = {}
        self._register_default_roles()
    
    def register(self, role: RolePersona) -> None:
        """Register a role."""
        self.roles[role.role_id] = role
    
    def get(self, role_id: str) -> Optional[RolePersona]:
        """Get a role by ID."""
        return self.roles.get(role_id)
    
    def list_roles(self) -> List[Dict[str, str]]:
        """List all available roles."""
        return [
            {"id": r.role_id, "name": r.name, "domain": r.domain}
            for r in self.roles.values()
        ]
    
    def _register_default_roles(self) -> None:
        """Register built-in roles."""
        # Legal Analyst
        self.register(RolePersona(
            role_id="lawyer",
            name="Legal Analyst",
            description="Analyzes arguments from a legal perspective with emphasis on "
                       "precedent, evidence standards, and legal reasoning patterns",
            domain="law",
            expertise_level=ExpertiseLevel.EXPERT,
            communication_style=CommunicationStyle.FORMAL,
            reasoning_mode=ReasoningMode(
                name="legal_reasoning",
                description="Structured legal analysis",
                required_steps=[
                    "Identify the legal issue",
                    "State the relevant rule or precedent",
                    "Apply the rule to the facts",
                    "Reach a conclusion"
                ],
                forbidden_fallacies=[
                    "appeal_to_emotion",
                    "ad_hominem",
                    "hasty_generalization"
                ],
                preferred_argument_forms=[
                    "modus_ponens",
                    "precedent_application",
                    "analogical_reasoning"
                ]
            ),
            constraints=[
                DomainConstraint(
                    name="evidence_standard",
                    description="Claims must be supported by evidence or precedent",
                    violation_message="Claim lacks supporting evidence or precedent"
                ),
                DomainConstraint(
                    name="burden_of_proof",
                    description="Acknowledge who bears the burden of proof",
                    violation_message="Burden of proof not properly assigned"
                )
            ],
            vocabulary={
                "argument": "legal argument",
                "conclusion": "holding",
                "example": "precedent",
                "rule": "legal principle"
            },
            forbidden_phrases=[
                "in my opinion",
                "I feel that",
                "obviously",
                "everyone knows"
            ],
            required_disclaimers=[
                "This analysis is for educational purposes only and does not "
                "constitute legal advice."
            ]
        ))
        
        # Scientific Researcher
        self.register(RolePersona(
            role_id="scientist",
            name="Scientific Researcher",
            description="Evaluates arguments using scientific methodology with emphasis "
                       "on empirical evidence, falsifiability, and statistical rigor",
            domain="science",
            expertise_level=ExpertiseLevel.EXPERT,
            communication_style=CommunicationStyle.TECHNICAL,
            reasoning_mode=ReasoningMode(
                name="scientific_method",
                description="Hypothesis-driven empirical reasoning",
                required_steps=[
                    "State the hypothesis",
                    "Identify testable predictions",
                    "Evaluate evidence",
                    "Consider alternative explanations",
                    "Draw tentative conclusions"
                ],
                forbidden_fallacies=[
                    "appeal_to_authority",
                    "confirmation_bias",
                    "hasty_generalization",
                    "post_hoc"
                ],
                preferred_argument_forms=[
                    "hypothetical_deductive",
                    "inference_to_best_explanation",
                    "statistical_inference"
                ]
            ),
            constraints=[
                DomainConstraint(
                    name="falsifiability",
                    description="Claims must be falsifiable in principle",
                    violation_message="Claim is not falsifiable"
                ),
                DomainConstraint(
                    name="replicability",
                    description="Reference studies that can be replicated",
                    violation_message="Evidence not replicable"
                ),
                DomainConstraint(
                    name="statistical_validity",
                    description="Statistical claims must be properly qualified",
                    violation_message="Statistical claim lacks proper qualification"
                )
            ],
            vocabulary={
                "prove": "support",
                "certain": "likely",
                "always": "typically",
                "never": "rarely"
            },
            forbidden_phrases=[
                "proves beyond doubt",
                "definitely true",
                "impossible that"
            ],
            required_disclaimers=[]
        ))
        
        # Educator / Tutor
        self.register(RolePersona(
            role_id="tutor",
            name="Educational Tutor",
            description="Explains concepts and guides reasoning in an accessible, "
                       "educational manner suitable for learning",
            domain="education",
            expertise_level=ExpertiseLevel.ADVANCED,
            communication_style=CommunicationStyle.EDUCATIONAL,
            reasoning_mode=ReasoningMode(
                name="pedagogical",
                description="Step-by-step educational explanation",
                required_steps=[
                    "Start with what the learner knows",
                    "Introduce new concepts gradually",
                    "Provide examples",
                    "Check understanding",
                    "Summarize key points"
                ],
                forbidden_fallacies=[],  # All fallacies should be explained, not avoided
                preferred_argument_forms=[
                    "example_based",
                    "analogy",
                    "step_by_step_deduction"
                ]
            ),
            constraints=[
                DomainConstraint(
                    name="accessibility",
                    description="Explanations must be accessible to learners",
                    violation_message="Explanation may be too complex"
                ),
                DomainConstraint(
                    name="encouragement",
                    description="Maintain encouraging tone",
                    violation_message="Tone may be discouraging"
                )
            ],
            vocabulary={
                "incorrect": "not quite right",
                "wrong": "let's look at this differently",
                "error": "area for improvement"
            },
            forbidden_phrases=[
                "obviously",
                "simply",
                "just",
                "as everyone knows"
            ],
            required_disclaimers=[]
        ))
        
        # Socratic Philosopher
        self.register(RolePersona(
            role_id="socratic",
            name="Socratic Philosopher",
            description="Guides reasoning through questions rather than direct answers, "
                       "helping the interlocutor discover truth through dialogue",
            domain="philosophy",
            expertise_level=ExpertiseLevel.MASTER,
            communication_style=CommunicationStyle.SOCRATIC,
            reasoning_mode=ReasoningMode(
                name="socratic_dialogue",
                description="Question-based discovery",
                required_steps=[
                    "Identify the thesis",
                    "Ask clarifying questions",
                    "Expose assumptions",
                    "Explore implications",
                    "Guide toward refined understanding"
                ],
                forbidden_fallacies=[
                    "begging_the_question",
                    "false_dichotomy"
                ],
                preferred_argument_forms=[
                    "reductio_ad_absurdum",
                    "dialectic",
                    "elenchus"
                ]
            ),
            constraints=[
                DomainConstraint(
                    name="questioning",
                    description="Prefer questions over statements",
                    violation_message="Response should include more questions"
                )
            ],
            vocabulary={},
            forbidden_phrases=[
                "the answer is",
                "you should",
                "obviously"
            ],
            required_disclaimers=[]
        ))
        
        # Critical Analyst
        self.register(RolePersona(
            role_id="critic",
            name="Critical Analyst",
            description="Rigorous analysis focused on identifying weaknesses, "
                       "assumptions, and potential flaws in arguments",
            domain="analysis",
            expertise_level=ExpertiseLevel.EXPERT,
            communication_style=CommunicationStyle.AUTHORITATIVE,
            reasoning_mode=ReasoningMode(
                name="critical_analysis",
                description="Rigorous critique and evaluation",
                required_steps=[
                    "Identify the main claim",
                    "Examine supporting premises",
                    "Check logical validity",
                    "Identify hidden assumptions",
                    "Evaluate evidence quality",
                    "Consider counterarguments",
                    "Assess overall strength"
                ],
                forbidden_fallacies=[],  # Must identify all fallacies
                preferred_argument_forms=[
                    "modus_tollens",
                    "counterexample",
                    "reductio"
                ]
            ),
            constraints=[
                DomainConstraint(
                    name="thoroughness",
                    description="Analysis must be comprehensive",
                    violation_message="Analysis may be incomplete"
                ),
                DomainConstraint(
                    name="objectivity",
                    description="Maintain objective stance",
                    violation_message="Analysis may lack objectivity"
                )
            ],
            vocabulary={},
            forbidden_phrases=[
                "I believe",
                "in my view",
                "personally"
            ],
            required_disclaimers=[]
        ))


class RoleAdapter:
    """
    Adapts reasoning and responses to specific roles.
    """
    
    def __init__(self, registry: Optional[RoleRegistry] = None):
        self.registry = registry or RoleRegistry()
        self.active_role: Optional[RolePersona] = None
    
    def set_role(self, role_id: str) -> bool:
        """Set the active role."""
        role = self.registry.get(role_id)
        if role:
            self.active_role = role
            return True
        return False
    
    def get_system_prompt(self, role_id: Optional[str] = None) -> str:
        """Generate a system prompt for the role."""
        role = self.registry.get(role_id) if role_id else self.active_role
        if not role:
            return "You are a helpful reasoning assistant."
        
        prompt_parts = [
            f"You are a {role.name} specializing in {role.domain}.",
            f"\n\n{role.description}",
            f"\n\nExpertise Level: {role.expertise_level.name}",
            f"\nCommunication Style: {role.communication_style.value}",
            "\n\nReasoning Approach:",
            f"\n- {role.reasoning_mode.description}"
        ]
        
        if role.reasoning_mode.required_steps:
            prompt_parts.append("\n\nRequired Analysis Steps:")
            for i, step in enumerate(role.reasoning_mode.required_steps, 1):
                prompt_parts.append(f"\n{i}. {step}")
        
        if role.reasoning_mode.forbidden_fallacies:
            prompt_parts.append("\n\nAvoid these fallacies in your reasoning:")
            for fallacy in role.reasoning_mode.forbidden_fallacies:
                prompt_parts.append(f"\n- {fallacy.replace('_', ' ')}")
        
        if role.forbidden_phrases:
            prompt_parts.append("\n\nAvoid these phrases:")
            for phrase in role.forbidden_phrases:
                prompt_parts.append(f'\n- "{phrase}"')
        
        if role.required_disclaimers:
            prompt_parts.append("\n\nInclude these disclaimers when appropriate:")
            for disclaimer in role.required_disclaimers:
                prompt_parts.append(f"\n- {disclaimer}")
        
        return "".join(prompt_parts)
    
    def adapt_response(
        self,
        response: str,
        role_id: Optional[str] = None
    ) -> AdaptedResponse:
        """Adapt a response to the role."""
        role = self.registry.get(role_id) if role_id else self.active_role
        
        if not role:
            return AdaptedResponse(
                original_response=response,
                adapted_response=response,
                role_id="default",
                adaptations_made=[],
                constraints_checked=[],
                violations=[]
            )
        
        adapted = response
        adaptations = []
        violations = []
        
        # Apply vocabulary substitutions
        for original, preferred in role.vocabulary.items():
            if original.lower() in adapted.lower():
                # Case-preserving replacement
                import re
                pattern = re.compile(re.escape(original), re.IGNORECASE)
                adapted = pattern.sub(preferred, adapted)
                adaptations.append(f"Replaced '{original}' with '{preferred}'")
        
        # Check for forbidden phrases
        for phrase in role.forbidden_phrases:
            if phrase.lower() in adapted.lower():
                violations.append(f"Contains forbidden phrase: '{phrase}'")
        
        # Add required disclaimers if not present
        for disclaimer in role.required_disclaimers:
            if disclaimer.lower() not in adapted.lower():
                adapted = f"{adapted}\n\n*{disclaimer}*"
                adaptations.append("Added required disclaimer")
        
        # Check constraints
        constraints_checked = []
        for constraint in role.constraints:
            constraints_checked.append(constraint.name)
            if constraint.check_fn and not constraint.check_fn(adapted):
                violations.append(f"{constraint.name}: {constraint.violation_message}")
        
        return AdaptedResponse(
            original_response=response,
            adapted_response=adapted,
            role_id=role.role_id,
            adaptations_made=adaptations,
            constraints_checked=constraints_checked,
            violations=violations
        )
    
    def validate_reasoning(
        self,
        reasoning_steps: List[str],
        role_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate reasoning against role requirements."""
        role = self.registry.get(role_id) if role_id else self.active_role
        
        if not role:
            return {"valid": True, "missing_steps": [], "issues": []}
        
        required = role.reasoning_mode.required_steps
        missing_steps = []
        
        # Check for required steps (simplified check)
        reasoning_text = " ".join(reasoning_steps).lower()
        for step in required:
            step_keywords = step.lower().split()
            if not any(kw in reasoning_text for kw in step_keywords[:3]):
                missing_steps.append(step)
        
        issues = []
        
        # Check for forbidden fallacies mentioned positively
        for fallacy in role.reasoning_mode.forbidden_fallacies:
            fallacy_text = fallacy.replace("_", " ")
            if fallacy_text in reasoning_text:
                issues.append(f"May contain {fallacy_text}")
        
        return {
            "valid": len(missing_steps) == 0 and len(issues) == 0,
            "missing_steps": missing_steps,
            "issues": issues,
            "required_steps": required
        }
    
    def get_role_context(
        self,
        role_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get context information for a role."""
        role = self.registry.get(role_id) if role_id else self.active_role
        
        if not role:
            return {}
        
        return {
            "role_id": role.role_id,
            "name": role.name,
            "domain": role.domain,
            "expertise_level": role.expertise_level.name,
            "communication_style": role.communication_style.value,
            "reasoning_mode": role.reasoning_mode.name,
            "required_steps": role.reasoning_mode.required_steps,
            "forbidden_fallacies": role.reasoning_mode.forbidden_fallacies,
            "preferred_forms": role.reasoning_mode.preferred_argument_forms
        }


class RoleBasedReasoner:
    """
    Reasoner that adapts behavior based on role.
    """
    
    def __init__(
        self,
        reasoning_fn: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        adapter: Optional[RoleAdapter] = None
    ):
        self.reasoning_fn = reasoning_fn
        self.adapter = adapter or RoleAdapter()
    
    def reason(
        self,
        query: str,
        role_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Perform role-adapted reasoning."""
        # Set role context
        if role_id:
            self.adapter.set_role(role_id)
        
        role_context = self.adapter.get_role_context()
        full_context = {**(context or {}), "role": role_context}
        
        # Get system prompt
        system_prompt = self.adapter.get_system_prompt()
        
        # Perform reasoning
        result = self.reasoning_fn(query, full_context)
        
        # Adapt response
        if "response" in result:
            adapted = self.adapter.adapt_response(result["response"])
            result["response"] = adapted.adapted_response
            result["adaptations"] = adapted.adaptations_made
            result["violations"] = adapted.violations
        
        # Validate reasoning
        if "reasoning_steps" in result:
            validation = self.adapter.validate_reasoning(result["reasoning_steps"])
            result["reasoning_valid"] = validation["valid"]
            result["missing_steps"] = validation["missing_steps"]
        
        result["role_context"] = role_context
        return result


class PersonaManager:
    """
    Manager for creating and customizing personas.
    """
    
    def __init__(self, registry: Optional[RoleRegistry] = None):
        self.registry = registry or RoleRegistry()
    
    def create_custom_persona(
        self,
        role_id: str,
        name: str,
        description: str,
        domain: str,
        expertise: ExpertiseLevel = ExpertiseLevel.ADVANCED,
        style: CommunicationStyle = CommunicationStyle.FORMAL,
        required_steps: Optional[List[str]] = None,
        forbidden_fallacies: Optional[List[str]] = None,
        vocabulary: Optional[Dict[str, str]] = None
    ) -> RolePersona:
        """Create a custom persona."""
        reasoning_mode = ReasoningMode(
            name=f"{role_id}_reasoning",
            description=f"Reasoning mode for {name}",
            required_steps=required_steps or [],
            forbidden_fallacies=forbidden_fallacies or [],
            preferred_argument_forms=[]
        )
        
        persona = RolePersona(
            role_id=role_id,
            name=name,
            description=description,
            domain=domain,
            expertise_level=expertise,
            communication_style=style,
            reasoning_mode=reasoning_mode,
            vocabulary=vocabulary or {}
        )
        
        self.registry.register(persona)
        return persona
    
    def clone_with_modifications(
        self,
        source_role_id: str,
        new_role_id: str,
        modifications: Dict[str, Any]
    ) -> Optional[RolePersona]:
        """Clone an existing role with modifications."""
        source = self.registry.get(source_role_id)
        if not source:
            return None
        
        # Create a copy with modifications
        new_persona = RolePersona(
            role_id=new_role_id,
            name=modifications.get("name", source.name),
            description=modifications.get("description", source.description),
            domain=modifications.get("domain", source.domain),
            expertise_level=modifications.get("expertise_level", source.expertise_level),
            communication_style=modifications.get("communication_style", source.communication_style),
            reasoning_mode=source.reasoning_mode,
            constraints=source.constraints.copy(),
            vocabulary={**source.vocabulary, **modifications.get("vocabulary", {})},
            forbidden_phrases=modifications.get("forbidden_phrases", source.forbidden_phrases.copy()),
            required_disclaimers=modifications.get("required_disclaimers", source.required_disclaimers.copy())
        )
        
        self.registry.register(new_persona)
        return new_persona
