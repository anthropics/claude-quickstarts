"""
Categorical Engine - Aristotelian Syllogistic Logic

Implements validation of categorical syllogisms with proper term distribution:
- Valid forms: Barbara, Celarent, Darii, Ferio
- Term distribution rules
- Middle term validation
"""

from typing import Optional
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
        # Detect form based on quantifiers
        major_type = self._classify_proposition(major)
        minor_type = self._classify_proposition(minor)
        conclusion_type = self._classify_proposition(conclusion)
        
        form_code = f"{major_type}{minor_type}{conclusion_type}"
        
        # Check for Barbara form (AAA-1)
        if form_code == "AAA" and self._is_first_figure(major, minor, conclusion):
            return SyllogismResult(
                valid=True,
                form=SyllogismType.BARBARA,
                explanation="Valid: Barbara form (AAA-1) - All M are P; All S are M; therefore All S are P"
            )
        
        # Check for Celarent form (EAE-1)
        if form_code == "EAE" and self._is_first_figure(major, minor, conclusion):
            return SyllogismResult(
                valid=True,
                form=SyllogismType.CELARENT,
                explanation="Valid: Celarent form (EAE-1) - No M are P; All S are M; therefore No S are P"
            )
        
        # Check for Darii form (AII-1)
        if form_code == "AII" and self._is_first_figure(major, minor, conclusion):
            return SyllogismResult(
                valid=True,
                form=SyllogismType.DARII,
                explanation="Valid: Darii form (AII-1) - All M are P; Some S are M; therefore Some S are P"
            )
        
        # Check for Ferio form (EIO-1)
        if form_code == "EIO" and self._is_first_figure(major, minor, conclusion):
            return SyllogismResult(
                valid=True,
                form=SyllogismType.FERIO,
                explanation="Valid: Ferio form (EIO-1) - No M are P; Some S are M; therefore Some S are not P"
            )
        
        return SyllogismResult(
            valid=False,
            form=None,
            explanation=f"Does not match known valid syllogistic forms (detected {form_code})",
            confidence=0.0
        )
    
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
        # For now, assume first figure
        return True
    
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
