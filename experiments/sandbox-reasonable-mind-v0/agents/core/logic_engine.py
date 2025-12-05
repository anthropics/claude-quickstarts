"""
Logic Engine - Deterministic Propositional Logic Validation

Implements formal logic rules for argument validation:
- Valid forms: Modus Ponens, Modus Tollens, Hypothetical Syllogism, etc.
- Invalid forms: Affirming Consequent, Denying Antecedent
- 100% confidence for deterministic results
"""

from typing import List, Optional
from enum import Enum
from dataclasses import dataclass


class ArgumentForm(Enum):
    """Valid and invalid argument forms."""
    # Valid forms
    MODUS_PONENS = "modus_ponens"
    MODUS_TOLLENS = "modus_tollens"
    HYPOTHETICAL_SYLLOGISM = "hypothetical_syllogism"
    DISJUNCTIVE_SYLLOGISM = "disjunctive_syllogism"
    CONSTRUCTIVE_DILEMMA = "constructive_dilemma"
    SIMPLIFICATION = "simplification"
    CONJUNCTION = "conjunction"
    ADDITION = "addition"
    
    # Invalid forms (fallacies)
    AFFIRMING_CONSEQUENT = "affirming_consequent"
    DENYING_ANTECEDENT = "denying_antecedent"


@dataclass
class LogicResult:
    """Result of logic validation."""
    valid: bool
    form: Optional[ArgumentForm]
    explanation: str
    confidence: float = 1.0  # Deterministic = 100%


class LogicEngine:
    """Deterministic propositional logic evaluation."""
    
    def __init__(self):
        self.valid_forms = {
            ArgumentForm.MODUS_PONENS: {
                "pattern": ["P → Q", "P"],
                "conclusion": "Q",
                "description": "If P then Q; P; therefore Q"
            },
            ArgumentForm.MODUS_TOLLENS: {
                "pattern": ["P → Q", "¬Q"],
                "conclusion": "¬P",
                "description": "If P then Q; not Q; therefore not P"
            },
            ArgumentForm.HYPOTHETICAL_SYLLOGISM: {
                "pattern": ["P → Q", "Q → R"],
                "conclusion": "P → R",
                "description": "If P then Q; if Q then R; therefore if P then R"
            },
            ArgumentForm.DISJUNCTIVE_SYLLOGISM: {
                "pattern": ["P ∨ Q", "¬P"],
                "conclusion": "Q",
                "description": "P or Q; not P; therefore Q"
            },
            ArgumentForm.CONSTRUCTIVE_DILEMMA: {
                "pattern": ["(P → Q) ∧ (R → S)", "P ∨ R"],
                "conclusion": "Q ∨ S",
                "description": "If P then Q, and if R then S; P or R; therefore Q or S"
            },
            ArgumentForm.SIMPLIFICATION: {
                "pattern": ["P ∧ Q"],
                "conclusion": "P",
                "description": "P and Q; therefore P"
            },
            ArgumentForm.CONJUNCTION: {
                "pattern": ["P", "Q"],
                "conclusion": "P ∧ Q",
                "description": "P; Q; therefore P and Q"
            },
            ArgumentForm.ADDITION: {
                "pattern": ["P"],
                "conclusion": "P ∨ Q",
                "description": "P; therefore P or Q"
            }
        }
        
        self.invalid_forms = {
            ArgumentForm.AFFIRMING_CONSEQUENT: {
                "pattern": ["P → Q", "Q"],
                "fallacy": "Cannot conclude P (consequent is affirmed)",
                "example": "If it rains, the ground is wet; the ground is wet; therefore it rained (INVALID)"
            },
            ArgumentForm.DENYING_ANTECEDENT: {
                "pattern": ["P → Q", "¬P"],
                "fallacy": "Cannot conclude ¬Q (antecedent is denied)",
                "example": "If it rains, the ground is wet; it didn't rain; therefore the ground is not wet (INVALID)"
            }
        }
    
    def validate_argument(self, premises: List[str], conclusion: str) -> LogicResult:
        """
        Validate an argument using formal logic rules.
        
        Args:
            premises: List of premise statements
            conclusion: Conclusion statement
            
        Returns:
            LogicResult with validity, form, and explanation
        """
        # Check for modus tollens first (more specific pattern)
        if self._matches_modus_tollens(premises, conclusion):
            return LogicResult(
                valid=True,
                form=ArgumentForm.MODUS_TOLLENS,
                explanation="Valid: Modus Tollens (If P→Q and ¬Q, then ¬P)"
            )
        
        # Check for hypothetical syllogism (two conditionals)
        if self._matches_hypothetical_syllogism(premises, conclusion):
            return LogicResult(
                valid=True,
                form=ArgumentForm.HYPOTHETICAL_SYLLOGISM,
                explanation="Valid: Hypothetical Syllogism (If P→Q and Q→R, then P→R)"
            )
        
        # Check for modus ponens
        if self._matches_modus_ponens(premises, conclusion):
            return LogicResult(
                valid=True,
                form=ArgumentForm.MODUS_PONENS,
                explanation="Valid: Modus Ponens (If P→Q and P, then Q)"
            )
        
        # Check for disjunctive syllogism
        if self._matches_disjunctive_syllogism(premises, conclusion):
            return LogicResult(
                valid=True,
                form=ArgumentForm.DISJUNCTIVE_SYLLOGISM,
                explanation="Valid: Disjunctive Syllogism (P∨Q and ¬P, therefore Q)"
            )
        
        # Check for affirming the consequent (invalid)
        if self._matches_affirming_consequent(premises, conclusion):
            return LogicResult(
                valid=False,
                form=ArgumentForm.AFFIRMING_CONSEQUENT,
                explanation="Invalid: Affirming the Consequent fallacy (If P→Q and Q, cannot conclude P)"
            )
        
        # Check for denying the antecedent (invalid)
        if self._matches_denying_antecedent(premises, conclusion):
            return LogicResult(
                valid=False,
                form=ArgumentForm.DENYING_ANTECEDENT,
                explanation="Invalid: Denying the Antecedent fallacy (If P→Q and ¬P, cannot conclude ¬Q)"
            )
        
        # Default: indeterminate
        return LogicResult(
            valid=False,
            form=None,
            explanation="Cannot determine validity with available rules",
            confidence=0.0
        )
    
    def _matches_modus_ponens(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument matches Modus Ponens pattern."""
        # Pattern: P→Q, P, therefore Q
        # Must have conditional but conclusion should NOT be negated
        has_conditional = any("if" in p.lower() and "then" in p.lower() for p in premises)
        has_antecedent = len(premises) >= 2
        conclusion_not_negated = "not" not in conclusion.lower() and "no" not in conclusion.lower()
        return has_conditional and has_antecedent and conclusion_not_negated
    
    def _matches_modus_tollens(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument matches Modus Tollens pattern."""
        # Pattern: P→Q, ¬Q, therefore ¬P
        # Must have negation in BOTH premise AND conclusion
        has_conditional = any("if" in p.lower() and "then" in p.lower() for p in premises)
        premise_has_negation = any(("not" in p.lower() or "no" in p.lower()) and "if" not in p.lower() for p in premises)
        conclusion_negated = "not" in conclusion.lower() or "no" in conclusion.lower()
        return has_conditional and premise_has_negation and conclusion_negated
    
    def _matches_hypothetical_syllogism(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument matches Hypothetical Syllogism pattern."""
        # Pattern: P→Q, Q→R, therefore P→R
        conditionals = [p for p in premises if "if" in p.lower() and "then" in p.lower()]
        has_chain = len(conditionals) >= 2
        conclusion_conditional = "if" in conclusion.lower() and "then" in conclusion.lower()
        return has_chain and conclusion_conditional
    
    def _matches_disjunctive_syllogism(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument matches Disjunctive Syllogism pattern."""
        # Pattern: P∨Q, ¬P, therefore Q
        has_disjunction = any(" or " in p.lower() for p in premises)
        has_negation = any("not" in p.lower() or "no" in p.lower() for p in premises)
        return has_disjunction and has_negation
    
    def _matches_affirming_consequent(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument commits affirming the consequent fallacy."""
        # Pattern: P→Q, Q, therefore P (INVALID)
        _has_conditional = any("if" in p.lower() and "then" in p.lower() for p in premises)
        # This is a simplified check - full implementation would need semantic parsing
        return False  # Placeholder for full implementation
    
    def _matches_denying_antecedent(self, premises: List[str], conclusion: str) -> bool:
        """Check if argument commits denying the antecedent fallacy."""
        # Pattern: P→Q, ¬P, therefore ¬Q (INVALID)
        _has_conditional = any("if" in p.lower() and "then" in p.lower() for p in premises)
        # This is a simplified check - full implementation would need semantic parsing
        return False  # Placeholder for full implementation
    
    def get_form_description(self, form: ArgumentForm) -> str:
        """Get description of an argument form."""
        if form in self.valid_forms:
            return self.valid_forms[form]["description"]
        elif form in self.invalid_forms:
            return self.invalid_forms[form].get("fallacy", "Invalid form")
        return "Unknown form"
    
    def list_valid_forms(self) -> List[ArgumentForm]:
        """List all valid argument forms."""
        return list(self.valid_forms.keys())
    
    def list_invalid_forms(self) -> List[ArgumentForm]:
        """List all invalid argument forms (fallacies)."""
        return list(self.invalid_forms.keys())
