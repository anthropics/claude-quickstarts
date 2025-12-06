"""
Categorical Engine - Aristotelian Syllogistic Logic

Implements validation of categorical syllogisms with proper term distribution:
- Valid forms: Barbara, Celarent, Darii, Ferio
- Term distribution rules
- Middle term validation
"""

from typing import Optional, Tuple
from agents.core_logic.categorical_engine import parse_categorical_statement
from enum import Enum
from dataclasses import dataclass


class SyllogismType(Enum):
    """Valid syllogistic forms (Aristotelian)."""
    BARBARA = "AAA-1"  # All M are P, All S are M → All S are P
    CELARENT = "EAE-1"  # No M are P, All S are M → No S are P
    DARII = "AII-1"     # All M are P, Some S are M → Some S are P
    FERIO = "EIO-1"     # No M are P, Some S are M → Some S are not P
    CESARE = "EAE-2"    # No P are M, All S are M → No S are P
    CAMESTRES = "AEE-2" # All P are M, No S are M → No S are P
    FESTINO = "EIO-2"   # No P are M, Some S are M → Some S are not P
    BAROCO = "AOO-2"    # All P are M, Some S are not M → Some S are not P


@dataclass
class SyllogismResult:
    """Result of syllogism validation."""
    valid: bool
    form: Optional[SyllogismType]
    explanation: str
    confidence: float = 1.0


class CategoricalEngine:
    """Validates categorical syllogisms using Aristotelian logic."""
    
    def __init__(self):
        self.valid_forms = {
            SyllogismType.BARBARA: {
                "major": "All M are P",
                "minor": "All S are M",
                "conclusion": "All S are P",
                "description": "Universal affirmative throughout (AAA-1)",
                "example": "All humans are mortal; Socrates is human; therefore Socrates is mortal"
            },
            SyllogismType.CELARENT: {
                "major": "No M are P",
                "minor": "All S are M",
                "conclusion": "No S are P",
                "description": "Universal negative major, universal affirmative minor (EAE-1)",
                "example": "No reptiles are mammals; all snakes are reptiles; therefore no snakes are mammals"
            },
            SyllogismType.DARII: {
                "major": "All M are P",
                "minor": "Some S are M",
                "conclusion": "Some S are P",
                "description": "Universal affirmative major, particular affirmative minor (AII-1)",
                "example": "All birds fly; some animals are birds; therefore some animals fly"
            },
            SyllogismType.FERIO: {
                "major": "No M are P",
                "minor": "Some S are M",
                "conclusion": "Some S are not P",
                "description": "Universal negative major, particular affirmative minor (EIO-1)",
                "example": "No fish are mammals; some animals are fish; therefore some animals are not mammals"
            },
            SyllogismType.CESARE: {
                "major": "No P are M",
                "minor": "All S are M",
                "conclusion": "No S are P",
                "description": "Universal negative major (EAE-2)",
                "example": "No mammals are cold-blooded; all dogs are mammals; therefore no dogs are cold-blooded"
            },
            SyllogismType.CAMESTRES: {
                "major": "All P are M",
                "minor": "No S are M",
                "conclusion": "No S are P",
                "description": "Universal affirmative major, universal negative minor (AEE-2)",
                "example": "All cats are mammals; no rocks are mammals; therefore no rocks are cats"
            },
            SyllogismType.FESTINO: {
                "major": "No P are M",
                "minor": "Some S are M",
                "conclusion": "Some S are not P",
                "description": "Universal negative major, particular affirmative minor (EIO-2)",
                "example": "No mammals are insects; some animals are insects; therefore some animals are not mammals"
            },
            SyllogismType.BAROCO: {
                "major": "All P are M",
                "minor": "Some S are not M",
                "conclusion": "Some S are not P",
                "description": "Universal affirmative major, particular negative minor (AOO-2)",
                "example": "All dogs are mammals; some pets are not mammals; therefore some pets are not dogs"
            }
        }
    
    def validate_syllogism(self, major: str, minor: str, conclusion: str) -> SyllogismResult:
        """
        Validate a categorical syllogism.
        
        Args:
            major: Major premise (contains predicate of conclusion)
            minor: Minor premise (contains subject of conclusion)
            conclusion: Conclusion statement
            
        Returns:
            SyllogismResult with validity, form, and explanation
        """
        parsed_major = parse_categorical_statement(self._normalize_statement(major))
        parsed_minor = parse_categorical_statement(self._normalize_statement(minor))
        parsed_conclusion = parse_categorical_statement(self._normalize_statement(conclusion))

        if not (parsed_major and parsed_minor and parsed_conclusion):
            return SyllogismResult(
                valid=False,
                form=None,
                explanation="Parse error in premises or conclusion",
                confidence=0.0
            )

        major_type = parsed_major.type.value
        minor_type = parsed_minor.type.value
        conclusion_type = parsed_conclusion.type.value
        
        form_code = f"{major_type}{minor_type}{conclusion_type}"
        figure = self._determine_figure(
            (parsed_major.subject, parsed_major.predicate),
            (parsed_minor.subject, parsed_minor.predicate),
            (parsed_conclusion.subject, parsed_conclusion.predicate),
        )
        
        # Check for Barbara form (AAA-1)
        if form_code == "AAA" and figure == 1:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.BARBARA,
                explanation="Valid: Barbara form (AAA-1) - All M are P; All S are M; therefore All S are P"
            )
        
        # Check for Celarent form (EAE-1)
        if form_code == "EAE" and figure == 1:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.CELARENT,
                explanation="Valid: Celarent form (EAE-1) - No M are P; All S are M; therefore No S are P"
            )
        
        # Check for Darii form (AII-1)
        if form_code == "AII" and figure == 1:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.DARII,
                explanation="Valid: Darii form (AII-1) - All M are P; Some S are M; therefore Some S are P"
            )
        
        # Check for Ferio form (EIO-1)
        if form_code == "EIO" and figure == 1:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.FERIO,
                explanation="Valid: Ferio form (EIO-1) - No M are P; Some S are M; therefore Some S are not P"
            )

        # Figure 2 forms
        if form_code == "EAE" and figure == 2:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.CESARE,
                explanation="Valid: Cesare form (EAE-2) - No P are M; All S are M; therefore No S are P"
            )

        if form_code == "AEE" and figure == 2:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.CAMESTRES,
                explanation="Valid: Camestres form (AEE-2) - All P are M; No S are M; therefore No S are P"
            )

        if form_code == "EIO" and figure == 2:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.FESTINO,
                explanation="Valid: Festino form (EIO-2) - No P are M; Some S are M; therefore Some S are not P"
            )

        if form_code == "AOO" and figure == 2:
            return SyllogismResult(
                valid=True,
                form=SyllogismType.BAROCO,
                explanation="Valid: Baroco form (AOO-2) - All P are M; Some S are not M; therefore Some S are not P"
            )
        
        return SyllogismResult(
            valid=False,
            form=None,
            explanation=f"Does not match known valid syllogistic forms (detected {form_code} in figure {figure or 'unknown'})",
            confidence=0.0
        )

    def _normalize_statement(self, text: str) -> str:
        """Ensure statement fits 'quantifier subject are [not] predicate' pattern."""
        lower = text.lower()
        if " are " in lower or " are not " in lower:
            return text
        tokens = text.split()
        if len(tokens) >= 3 and tokens[0] in ("All", "all", "No", "no", "Some", "some"):
            quant = tokens[0]
            subject = tokens[1]
            predicate = " ".join(tokens[2:])
            connector = "are not" if "not" in tokens[2:] else "are"
            return f"{quant} {subject} {connector} {predicate}"
        return text
    
    def _classify_proposition(self, statement: str) -> str:
        """
        Classify a categorical proposition.
        
        Returns:
            'A' for universal affirmative (All S are P)
            'E' for universal negative (No S are P)
            'I' for particular affirmative (Some S are P)
            'O' for particular negative (Some S are not P)
        """
        statement_lower = statement.lower()
        
        if statement_lower.startswith("all "):
            return "A"
        elif statement_lower.startswith("no "):
            return "E"
        elif statement_lower.startswith("some "):
            if " not " in statement_lower or " are not " in statement_lower:
                return "O"
            else:
                return "I"
        else:
            # Default to universal affirmative if unclear
            return "A"
    
    def _is_first_figure(self, major: str, minor: str, conclusion: str) -> bool:
        """
        Check if syllogism is in first figure.
        First figure: Middle term is subject of major, predicate of minor.
        
        This is a simplified check - full implementation would need semantic parsing.
        """
        return self._determine_figure(major, minor, conclusion) == 1

    def _determine_figure(
        self,
        major_terms: Tuple[str, str],
        minor_terms: Tuple[str, str],
        conclusion_terms: Tuple[str, str],
    ) -> Optional[int]:
        """Roughly determine syllogistic figure based on middle-term placement."""
        maj_subj, maj_pred = major_terms
        min_subj, min_pred = minor_terms
        con_subj, con_pred = conclusion_terms

        # Middle term should appear in both premises but not in the conclusion
        common_premise_terms = ({maj_subj, maj_pred} & {min_subj, min_pred}) - {con_subj, con_pred}
        if not common_premise_terms:
            return None

        middle = next(iter(common_premise_terms))

        if maj_subj == middle and min_pred == middle:
            return 1
        if maj_pred == middle and min_pred == middle:
            return 2
        if maj_subj == middle and min_subj == middle:
            return 3
        if maj_pred == middle and min_subj == middle:
            return 4

        return None
    
    def get_form_description(self, form: SyllogismType) -> str:
        """Get description of a syllogism form."""
        if form in self.valid_forms:
            return self.valid_forms[form]["description"]
        return "Unknown form"
    
    def get_example(self, form: SyllogismType) -> str:
        """Get example of a syllogism form."""
        if form in self.valid_forms:
            return self.valid_forms[form]["example"]
        return "No example available"
    
    def list_valid_forms(self) -> list[SyllogismType]:
        """List all valid syllogism forms."""
        return list(self.valid_forms.keys())
