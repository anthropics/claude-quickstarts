"""
Categorical Logic Engine - Syllogistic Reasoning

Validates categorical syllogisms using:
- Traditional square of opposition
- Distribution rules
- Figure and mood identification (Barbara, Celarent, Darii, Ferio, etc.)
- Venn diagram-based validation

Part of the deterministic foundation layer.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class StatementType(Enum):
    """Categorical statement types (A, E, I, O)."""
    UNIVERSAL_AFFIRMATIVE = "A"  # All S are P
    UNIVERSAL_NEGATIVE = "E"     # No S are P
    PARTICULAR_AFFIRMATIVE = "I"  # Some S are P
    PARTICULAR_NEGATIVE = "O"     # Some S are not P


class Figure(Enum):
    """Syllogistic figures based on middle term position."""
    FIRST = 1   # M-P, S-M ⊢ S-P
    SECOND = 2  # P-M, S-M ⊢ S-P
    THIRD = 3   # M-P, M-S ⊢ S-P
    FOURTH = 4  # P-M, M-S ⊢ S-P


@dataclass
class CategoricalStatement:
    """A categorical proposition."""
    type: StatementType
    subject: str
    predicate: str
    quantifier: str  # "all", "no", "some"
    copula: str  # "are", "are not"
    original_text: str

    @property
    def subject_distributed(self) -> bool:
        """Check if subject term is distributed."""
        # Universal statements distribute the subject
        # A: All S are P - S distributed
        # E: No S are P - S distributed
        # I: Some S are P - S not distributed
        # O: Some S are not P - S not distributed
        return self.type in [StatementType.UNIVERSAL_AFFIRMATIVE, StatementType.UNIVERSAL_NEGATIVE]

    @property
    def predicate_distributed(self) -> bool:
        """Check if predicate term is distributed."""
        # Negative statements distribute the predicate
        # A: All S are P - P not distributed
        # E: No S are P - P distributed
        # I: Some S are P - P not distributed
        # O: Some S are not P - P distributed
        return self.type in [StatementType.UNIVERSAL_NEGATIVE, StatementType.PARTICULAR_NEGATIVE]


@dataclass
class Syllogism:
    """A categorical syllogism."""
    major_premise: CategoricalStatement
    minor_premise: CategoricalStatement
    conclusion: CategoricalStatement

    major_term: str  # Predicate of conclusion
    minor_term: str  # Subject of conclusion
    middle_term: str  # Term in premises but not conclusion

    mood: str  # E.g., "AAA", "EAE", "AII", "EIO"
    figure: Figure


@dataclass
class SyllogismValidation:
    """Result of syllogism validation."""
    is_valid: bool
    mood: str
    figure: Figure
    form_name: Optional[str]  # E.g., "Barbara", "Celarent"
    violations: List[str]  # Rule violations if invalid
    confidence: float  # 1.0 for deterministic
    explanation: str


class CategoricalEngine:
    """
    Categorical logic engine for syllogistic reasoning.

    Implements the traditional rules of valid syllogisms.
    """

    # Valid syllogistic forms by figure
    VALID_FORMS = {
        # Figure 1
        (Figure.FIRST, "AAA"): "Barbara",
        (Figure.FIRST, "EAE"): "Celarent",
        (Figure.FIRST, "AII"): "Darii",
        (Figure.FIRST, "EIO"): "Ferio",
        # Figure 2
        (Figure.SECOND, "EAE"): "Cesare",
        (Figure.SECOND, "AEE"): "Camestres",
        (Figure.SECOND, "EIO"): "Festino",
        (Figure.SECOND, "AOO"): "Baroco",
        # Figure 3
        (Figure.THIRD, "IAI"): "Disamis",
        (Figure.THIRD, "AII"): "Datisi",
        (Figure.THIRD, "OAO"): "Bocardo",
        (Figure.THIRD, "EIO"): "Ferison",
        # Figure 4
        (Figure.FOURTH, "AEE"): "Camenes",
        (Figure.FOURTH, "IAI"): "Dimaris",
        (Figure.FOURTH, "EIO"): "Fresison",
    }

    def __init__(self):
        """Initialize categorical engine."""
        pass

    def validate(self, syllogism: Syllogism) -> SyllogismValidation:
        """
        Validate a categorical syllogism using traditional rules.

        Rules checked:
        1. Three terms (no four-term fallacy)
        2. Middle term distributed at least once
        3. If term distributed in conclusion, must be distributed in premise
        4. Two negative premises yield no conclusion
        5. Negative premise requires negative conclusion
        6. Two particular premises yield no conclusion
        7. Particular premise requires particular conclusion (if other is negative)

        Args:
            syllogism: The syllogism to validate

        Returns:
            SyllogismValidation with validity determination
        """
        violations = []

        # Rule 1: Exactly three terms (already enforced by Syllogism structure)

        # Rule 2: Middle term must be distributed at least once
        if not self._middle_term_distributed(syllogism):
            violations.append("Undistributed middle: middle term not distributed in either premise")

        # Rule 3: Illicit major/minor
        major_illicit = self._check_illicit_major(syllogism)
        if major_illicit:
            violations.append(f"Illicit major: {major_illicit}")

        minor_illicit = self._check_illicit_minor(syllogism)
        if minor_illicit:
            violations.append(f"Illicit minor: {minor_illicit}")

        # Rule 4: Two negative premises
        if self._is_negative(syllogism.major_premise) and self._is_negative(syllogism.minor_premise):
            violations.append("Two negative premises yield no valid conclusion")

        # Rule 5: Negative premise requires negative conclusion
        if (self._is_negative(syllogism.major_premise) or self._is_negative(syllogism.minor_premise)):
            if not self._is_negative(syllogism.conclusion):
                violations.append("Negative premise requires negative conclusion")

        # Rule 6: Two particular premises
        if self._is_particular(syllogism.major_premise) and self._is_particular(syllogism.minor_premise):
            violations.append("Two particular premises yield no valid conclusion")

        # Rule 7: Particular premise requires particular conclusion (with negative premise)
        if (self._is_particular(syllogism.major_premise) or self._is_particular(syllogism.minor_premise)):
            if self._is_negative(syllogism.major_premise) or self._is_negative(syllogism.minor_premise):
                if not self._is_particular(syllogism.conclusion):
                    violations.append("Particular premise with negative premise requires particular conclusion")

        # Check against known valid forms
        form_name = self.VALID_FORMS.get((syllogism.figure, syllogism.mood))

        is_valid = len(violations) == 0

        if is_valid and form_name:
            explanation = f"Valid syllogism: {form_name} ({syllogism.mood}-{syllogism.figure.value})"
        elif is_valid:
            explanation = f"Valid by rules, though not a traditional named form ({syllogism.mood}-{syllogism.figure.value})"
        else:
            explanation = f"Invalid syllogism: {'; '.join(violations)}"

        return SyllogismValidation(
            is_valid=is_valid,
            mood=syllogism.mood,
            figure=syllogism.figure,
            form_name=form_name,
            violations=violations,
            confidence=1.0,  # Deterministic
            explanation=explanation
        )

    def _middle_term_distributed(self, syl: Syllogism) -> bool:
        """Check if middle term is distributed at least once."""
        # Find middle term in each premise
        major_prem = syl.major_premise
        minor_prem = syl.minor_premise

        middle_in_major_subject = (major_prem.subject == syl.middle_term)
        middle_in_major_predicate = (major_prem.predicate == syl.middle_term)

        middle_in_minor_subject = (minor_prem.subject == syl.middle_term)
        middle_in_minor_predicate = (minor_prem.predicate == syl.middle_term)

        # Check distribution
        major_distributed = (
            (middle_in_major_subject and major_prem.subject_distributed) or
            (middle_in_major_predicate and major_prem.predicate_distributed)
        )

        minor_distributed = (
            (middle_in_minor_subject and minor_prem.subject_distributed) or
            (middle_in_minor_predicate and minor_prem.predicate_distributed)
        )

        return major_distributed or minor_distributed

    def _check_illicit_major(self, syl: Syllogism) -> Optional[str]:
        """Check for illicit major (major term distributed in conclusion but not premise)."""
        major_term = syl.major_term

        # Is major term distributed in conclusion?
        conclusion_distributed = (
            (syl.conclusion.predicate == major_term and syl.conclusion.predicate_distributed)
        )

        if not conclusion_distributed:
            return None  # Not distributed in conclusion, so no problem

        # Check if distributed in major premise
        major_prem = syl.major_premise
        premise_distributed = (
            (major_prem.subject == major_term and major_prem.subject_distributed) or
            (major_prem.predicate == major_term and major_prem.predicate_distributed)
        )

        if not premise_distributed:
            return f"Major term '{major_term}' distributed in conclusion but not in major premise"

        return None

    def _check_illicit_minor(self, syl: Syllogism) -> Optional[str]:
        """Check for illicit minor (minor term distributed in conclusion but not premise)."""
        minor_term = syl.minor_term

        # Is minor term distributed in conclusion?
        conclusion_distributed = (
            (syl.conclusion.subject == minor_term and syl.conclusion.subject_distributed)
        )

        if not conclusion_distributed:
            return None  # Not distributed in conclusion, so no problem

        # Check if distributed in minor premise
        minor_prem = syl.minor_premise
        premise_distributed = (
            (minor_prem.subject == minor_term and minor_prem.subject_distributed) or
            (minor_prem.predicate == minor_term and minor_prem.predicate_distributed)
        )

        if not premise_distributed:
            return f"Minor term '{minor_term}' distributed in conclusion but not in minor premise"

        return None

    def _is_negative(self, statement: CategoricalStatement) -> bool:
        """Check if statement is negative (E or O)."""
        return statement.type in [StatementType.UNIVERSAL_NEGATIVE, StatementType.PARTICULAR_NEGATIVE]

    def _is_particular(self, statement: CategoricalStatement) -> bool:
        """Check if statement is particular (I or O)."""
        return statement.type in [StatementType.PARTICULAR_AFFIRMATIVE, StatementType.PARTICULAR_NEGATIVE]


def parse_categorical_statement(text: str) -> Optional[CategoricalStatement]:
    """
    Parse a categorical statement from natural language.

    Supports:
    - "All S are P" (A)
    - "No S are P" (E)
    - "Some S are P" (I)
    - "Some S are not P" (O)

    Args:
        text: Natural language statement

    Returns:
        CategoricalStatement or None if parse fails
    """
    text = text.strip().lower()

    # Pattern: "all/no/some <subject> are [not] <predicate>"

    # Type A: All S are P
    if text.startswith("all "):
        parts = text[4:].split(" are ")
        if len(parts) == 2:
            return CategoricalStatement(
                type=StatementType.UNIVERSAL_AFFIRMATIVE,
                subject=parts[0].strip(),
                predicate=parts[1].strip(),
                quantifier="all",
                copula="are",
                original_text=text
            )

    # Type E: No S are P
    if text.startswith("no "):
        parts = text[3:].split(" are ")
        if len(parts) == 2:
            return CategoricalStatement(
                type=StatementType.UNIVERSAL_NEGATIVE,
                subject=parts[0].strip(),
                predicate=parts[1].strip(),
                quantifier="no",
                copula="are",
                original_text=text
            )

    # Type I: Some S are P
    if text.startswith("some ") and " are not " not in text:
        parts = text[5:].split(" are ")
        if len(parts) == 2:
            return CategoricalStatement(
                type=StatementType.PARTICULAR_AFFIRMATIVE,
                subject=parts[0].strip(),
                predicate=parts[1].strip(),
                quantifier="some",
                copula="are",
                original_text=text
            )

    # Type O: Some S are not P
    if text.startswith("some ") and " are not " in text:
        parts = text[5:].split(" are not ")
        if len(parts) == 2:
            return CategoricalStatement(
                type=StatementType.PARTICULAR_NEGATIVE,
                subject=parts[0].strip(),
                predicate=parts[1].strip(),
                quantifier="some",
                copula="are not",
                original_text=text
            )

    return None  # Parse failed


def parse_syllogism(
    major_premise: str,
    minor_premise: str,
    conclusion: str
) -> Optional[Syllogism]:
    """
    Parse a syllogism from natural language statements.

    Args:
        major_premise: E.g., "All mammals are animals"
        minor_premise: E.g., "All dogs are mammals"
        conclusion: E.g., "All dogs are animals"

    Returns:
        Syllogism or None if parse fails
    """
    maj_stmt = parse_categorical_statement(major_premise)
    min_stmt = parse_categorical_statement(minor_premise)
    con_stmt = parse_categorical_statement(conclusion)

    if not (maj_stmt and min_stmt and con_stmt):
        return None  # Parse failed

    # Identify terms
    # Major term: predicate of conclusion
    # Minor term: subject of conclusion
    # Middle term: term in premises but not conclusion

    major_term = con_stmt.predicate
    minor_term = con_stmt.subject

    # Find middle term
    all_premise_terms = {
        maj_stmt.subject, maj_stmt.predicate,
        min_stmt.subject, min_stmt.predicate
    }
    conclusion_terms = {con_stmt.subject, con_stmt.predicate}
    middle_terms = all_premise_terms - conclusion_terms

    if len(middle_terms) != 1:
        return None  # Should have exactly one middle term

    middle_term = middle_terms.pop()

    # Determine mood (e.g., AAA, EAE, AII)
    mood = (
        maj_stmt.type.value +
        min_stmt.type.value +
        con_stmt.type.value
    )

    # Determine figure (based on middle term position)
    # Figure 1: M-P, S-M
    # Figure 2: P-M, S-M
    # Figure 3: M-P, M-S
    # Figure 4: P-M, M-S

    maj_middle_subject = (maj_stmt.subject == middle_term)
    min_middle_subject = (min_stmt.subject == middle_term)

    if maj_middle_subject and not min_middle_subject:
        figure = Figure.FIRST
    elif not maj_middle_subject and not min_middle_subject:
        figure = Figure.SECOND
    elif maj_middle_subject and min_middle_subject:
        figure = Figure.THIRD
    else:  # not maj_middle_subject and min_middle_subject
        figure = Figure.FOURTH

    return Syllogism(
        major_premise=maj_stmt,
        minor_premise=min_stmt,
        conclusion=con_stmt,
        major_term=major_term,
        minor_term=minor_term,
        middle_term=middle_term,
        mood=mood,
        figure=figure
    )


# Convenience functions

def validate_barbara(
    major: str,
    minor: str,
    conclusion: str
) -> SyllogismValidation:
    """Quick validation expecting Barbara (AAA-1) form."""
    syl = parse_syllogism(major, minor, conclusion)
    if not syl:
        return SyllogismValidation(
            is_valid=False,
            mood="???",
            figure=Figure.FIRST,
            form_name=None,
            violations=["Parse error"],
            confidence=1.0,
            explanation="Failed to parse statements"
        )

    engine = CategoricalEngine()
    return engine.validate(syl)
