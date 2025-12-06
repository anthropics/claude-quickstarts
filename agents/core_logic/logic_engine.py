"""
Logic Engine - Deterministic Propositional Logic Evaluation

Provides formal validation of propositional logic arguments using:
- Truth table evaluation (for ≤5 variables)
- Pattern matching against known valid/invalid forms
- Bitset-based efficient evaluation

This is the FOUNDATION layer - always runs before AI enhancement.
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class LogicForm(Enum):
    """Known logical argument forms."""
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
    UNDISTRIBUTED_MIDDLE = "undistributed_middle"
    AFFIRMING_DISJUNCT = "affirming_disjunct"


class TruthValue(Enum):
    """Truth values for propositions."""
    TRUE = True
    FALSE = False
    UNKNOWN = None


@dataclass
class Proposition:
    """A logical proposition with a truth value."""
    symbol: str
    statement: str
    truth_value: TruthValue = TruthValue.UNKNOWN

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol


@dataclass
class LogicalArgument:
    """A formal logical argument."""
    premises: List[str]  # Formal notation (e.g., "P → Q")
    conclusion: str  # Formal notation
    propositions: Set[Proposition]  # Atomic propositions
    natural_language_premises: Optional[List[str]] = None
    natural_language_conclusion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of logic validation."""
    is_valid: bool
    form_identified: Optional[LogicForm]
    truth_table_valid: Optional[bool]  # None if too many variables
    counterexample: Optional[Dict[str, bool]]  # If invalid
    confidence: float  # 1.0 for deterministic, < 1.0 for heuristic
    method: str  # "pattern_match", "truth_table", "heuristic"
    explanation: str
    warnings: List[str]


class LogicEngine:
    """
    Deterministic propositional logic evaluation engine.

    Philosophy: "Logic is the skeleton" - this provides the rigid,
    reliable foundation that AI reasoning builds upon.
    """

    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize logic engine.

        Args:
            data_path: Path to data/ directory with argument_forms.json
        """
        if data_path is None:
            # Default to project data/ directory
            data_path = Path(__file__).parent.parent.parent / "data"

        self.data_path = data_path
        self.valid_forms = {}
        self.invalid_forms = {}
        self._load_argument_forms()

    def _load_argument_forms(self):
        """Load known argument forms from JSON database."""
        forms_file = self.data_path / "argument_forms.json"

        if not forms_file.exists():
            # Fallback to hardcoded forms
            self._init_hardcoded_forms()
            return

        with open(forms_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.valid_forms = data.get("valid_forms", {})
            self.invalid_forms = data.get("invalid_forms", {})

    def _init_hardcoded_forms(self):
        """Fallback hardcoded forms if JSON not available."""
        self.valid_forms = {
            "modus_ponens": {
                "pattern": ["P → Q", "P"],
                "conclusion": "Q"
            },
            "modus_tollens": {
                "pattern": ["P → Q", "¬Q"],
                "conclusion": "¬P"
            },
            "hypothetical_syllogism": {
                "pattern": ["P → Q", "Q → R"],
                "conclusion": "P → R"
            },
            "disjunctive_syllogism": {
                "pattern": ["P ∨ Q", "¬P"],
                "conclusion": "Q"
            }
        }

        self.invalid_forms = {
            "affirming_consequent": {
                "pattern": ["P → Q", "Q"],
                "fallacy": "Cannot conclude P"
            },
            "denying_antecedent": {
                "pattern": ["P → Q", "¬P"],
                "fallacy": "Cannot conclude ¬Q"
            }
        }

    def validate(self, argument: LogicalArgument) -> ValidationResult:
        """
        Validate a logical argument using multiple methods.

        Priority:
        1. Pattern matching against known forms (fastest, 100% confidence)
        2. Truth table evaluation (slow but complete, 100% confidence)
        3. Heuristic analysis (fast but uncertain, < 100% confidence)

        Args:
            argument: The logical argument to validate

        Returns:
            ValidationResult with validity determination
        """
        warnings = []

        # Method 1: Pattern matching (fast, deterministic)
        pattern_result = self._pattern_match(argument)
        if pattern_result:
            return pattern_result

        # Method 2: Truth table evaluation (slow but complete)
        if len(argument.propositions) <= 5:
            truth_result = self._truth_table_validate(argument)
            if truth_result:
                return truth_result
        else:
            warnings.append(
                f"Too many variables ({len(argument.propositions)}) for truth table evaluation"
            )

        # Method 3: Heuristic (fallback)
        warnings.append("Using heuristic evaluation - not deterministic")
        return self._heuristic_validate(argument, warnings)

    def _pattern_match(self, argument: LogicalArgument) -> Optional[ValidationResult]:
        """
        Match argument against known valid/invalid forms.

        Returns ValidationResult if match found, None otherwise.
        """
        premises_str = sorted([p.strip() for p in argument.premises])
        conclusion_str = argument.conclusion.strip()

        # Check valid forms
        for form_name, form_data in self.valid_forms.items():
            pattern = sorted([p.strip() for p in form_data["pattern"]])
            expected_conclusion = form_data["conclusion"].strip()

            if self._patterns_match(premises_str, pattern, conclusion_str, expected_conclusion):
                return ValidationResult(
                    is_valid=True,
                    form_identified=LogicForm(form_name),
                    truth_table_valid=None,
                    counterexample=None,
                    confidence=1.0,
                    method="pattern_match",
                    explanation=f"Matches valid form: {form_name}",
                    warnings=[]
                )

        # Check invalid forms
        for form_name, form_data in self.invalid_forms.items():
            pattern = sorted([p.strip() for p in form_data["pattern"]])

            # Invalid forms might not have explicit conclusion in DB
            if self._patterns_match(premises_str, pattern):
                return ValidationResult(
                    is_valid=False,
                    form_identified=LogicForm(form_name) if form_name in [f.value for f in LogicForm] else None,
                    truth_table_valid=None,
                    counterexample=None,
                    confidence=1.0,
                    method="pattern_match",
                    explanation=f"Matches invalid form (fallacy): {form_name} - {form_data.get('fallacy', '')}",
                    warnings=[]
                )

        return None  # No pattern match

    def _patterns_match(
        self,
        premises: List[str],
        pattern: List[str],
        conclusion: Optional[str] = None,
        expected_conclusion: Optional[str] = None
    ) -> bool:
        """
        Check if premises/conclusion match a pattern.

        Uses variable mapping (P, Q, R can be any propositions as long as consistent).
        """
        if len(premises) != len(pattern):
            return False

        # Build variable mapping
        var_map = {}

        for prem, pat in zip(premises, pattern):
            if not self._match_with_vars(prem, pat, var_map):
                return False

        # Check conclusion if provided
        if conclusion and expected_conclusion:
            if not self._match_with_vars(conclusion, expected_conclusion, var_map):
                return False

        return True

    def _match_with_vars(self, statement: str, pattern: str, var_map: Dict[str, str]) -> bool:
        """
        Match statement against pattern, building/checking variable mapping.

        Example: "A → B" matches "P → Q" with var_map = {"P": "A", "Q": "B"}
        """
        # Normalize
        stmt = statement.replace(" ", "")
        patt = pattern.replace(" ", "")

        # Extract variables and operators
        stmt_parts = self._tokenize(stmt)
        patt_parts = self._tokenize(patt)

        if len(stmt_parts) != len(patt_parts):
            return False

        for sp, pp in zip(stmt_parts, patt_parts):
            if pp in ["→", "∧", "∨", "¬", "↔", "(", ")"]:
                # Operator - must match exactly
                if sp != pp:
                    return False
            else:
                # Variable - check/update mapping
                if pp in var_map:
                    if var_map[pp] != sp:
                        return False
                else:
                    var_map[pp] = sp

        return True

    def _tokenize(self, expression: str) -> List[str]:
        """
        Tokenize logical expression.

        Returns list of tokens (variables, operators, parens).
        """
        tokens = []
        i = 0
        while i < len(expression):
            ch = expression[i]

            if ch in ["→", "∧", "∨", "¬", "↔", "(", ")"]:
                tokens.append(ch)
                i += 1
            elif ch.isalnum():
                # Multi-character variable (e.g., "P1", "Rain")
                var = ch
                i += 1
                while i < len(expression) and (expression[i].isalnum() or expression[i] == "_"):
                    var += expression[i]
                    i += 1
                tokens.append(var)
            else:
                i += 1  # Skip whitespace, etc.

        return tokens

    def _truth_table_validate(self, argument: LogicalArgument) -> Optional[ValidationResult]:
        """
        Validate using truth table (brute force all combinations).

        Only feasible for ≤5 variables (2^5 = 32 rows).
        """
        props = list(argument.propositions)
        n = len(props)

        if n > 5:
            return None  # Too expensive

        # Generate all 2^n truth assignments
        for i in range(2 ** n):
            assignment = {}
            for j, prop in enumerate(props):
                assignment[prop.symbol] = bool((i >> j) & 1)

            # Evaluate premises
            premises_true = all(
                self._evaluate_expression(prem, assignment)
                for prem in argument.premises
            )

            # Evaluate conclusion
            conclusion_value = self._evaluate_expression(argument.conclusion, assignment)

            # Check: if all premises true, conclusion must be true
            if premises_true and not conclusion_value:
                # Counterexample found
                return ValidationResult(
                    is_valid=False,
                    form_identified=None,
                    truth_table_valid=False,
                    counterexample=assignment,
                    confidence=1.0,
                    method="truth_table",
                    explanation=f"Counterexample found: {assignment}",
                    warnings=[]
                )

        # No counterexample - valid!
        return ValidationResult(
            is_valid=True,
            form_identified=None,
            truth_table_valid=True,
            counterexample=None,
            confidence=1.0,
            method="truth_table",
            explanation="Truth table exhaustively verified (no counterexamples)",
            warnings=[]
        )

    def _evaluate_expression(self, expr: str, assignment: Dict[str, bool]) -> bool:
        """
        Evaluate a logical expression given truth assignment.

        Supports: →, ∧, ∨, ¬, ↔, parentheses
        """
        # Normalize
        expr = expr.replace(" ", "")

        # Translate tokens into evaluable pieces
        tokens = self._tokenize(expr)
        translated = []

        for token in tokens:
            if token in assignment:
                translated.append(bool(assignment[token]))
            elif token == "¬":
                translated.append("not")
            elif token == "∧":
                translated.append("and")
            elif token == "∨":
                translated.append("or")
            elif token == "→":
                translated.append("_implies_")
            elif token == "↔":
                translated.append("_iff_")
            elif token in ["(", ")"]:
                translated.append(token)
            else:
                # Unknown variable - assume False (safe default)
                translated.append(False)

        try:
            return self._evaluate_tokens(translated)
        except Exception:
            # Parse error - return False (safe default)
            return False

    def _evaluate_tokens(self, tokens: List[Any]) -> bool:
        """
        Evaluate tokenized boolean expression with support for implication and biconditional.
        Uses a simple shunting-yard style evaluation to avoid lossy string rewriting.
        """

        def precedence(op: str) -> int:
            order = {
                "not": 4,
                "and": 3,
                "or": 2,
                "_implies_": 1,
                "_iff_": 0,
            }
            return order.get(op, -1)

        def apply_op(op_stack: List[str], val_stack: List[bool]) -> None:
            op = op_stack.pop()
            if op == "not":
                operand = val_stack.pop()
                val_stack.append(not operand)
                return

            right = val_stack.pop()
            left = val_stack.pop()

            if op == "and":
                val_stack.append(left and right)
            elif op == "or":
                val_stack.append(left or right)
            elif op == "_implies_":
                val_stack.append((not left) or right)
            elif op == "_iff_":
                val_stack.append(left == right)
            else:
                # Unknown operator - default to False
                val_stack.append(False)

        values: List[bool] = []
        ops: List[str] = []

        for token in tokens:
            if isinstance(token, bool):
                values.append(token)
            elif token == "(":
                ops.append(token)
            elif token == ")":
                while ops and ops[-1] != "(":
                    apply_op(ops, values)
                if ops:
                    ops.pop()  # Remove '('
            else:
                # Operator
                while ops and ops[-1] != "(" and precedence(ops[-1]) >= precedence(token):
                    apply_op(ops, values)
                ops.append(token)

        while ops:
            apply_op(ops, values)

        return values[-1] if values else False

    def _heuristic_validate(self, argument: LogicalArgument, warnings: List[str]) -> ValidationResult:
        """
        Heuristic validation (fallback when pattern match and truth table fail).

        This is NOT deterministic - lower confidence.
        """
        # Simple heuristics

        # Heuristic 1: Check if conclusion mentions terms not in premises
        premise_terms = set()
        for prem in argument.premises:
            premise_terms.update(self._extract_terms(prem))

        conclusion_terms = set(self._extract_terms(argument.conclusion))

        if not conclusion_terms.issubset(premise_terms):
            extra_terms = conclusion_terms - premise_terms
            return ValidationResult(
                is_valid=False,
                form_identified=None,
                truth_table_valid=None,
                counterexample=None,
                confidence=0.8,  # High confidence in this heuristic
                method="heuristic",
                explanation=f"Conclusion introduces new terms not in premises: {extra_terms}",
                warnings=warnings
            )

        # Default: uncertain
        return ValidationResult(
            is_valid=None,  # Uncertain
            form_identified=None,
            truth_table_valid=None,
            counterexample=None,
            confidence=0.3,
            method="heuristic",
            explanation="Unable to determine validity with available methods",
            warnings=warnings + ["Low confidence - recommend AI-enhanced analysis"]
        )

    def _extract_terms(self, expression: str) -> Set[str]:
        """Extract propositional variables from expression."""
        tokens = self._tokenize(expression)
        operators = {"→", "∧", "∨", "¬", "↔", "(", ")"}
        return {t for t in tokens if t not in operators}


def parse_argument(
    premises: List[str],
    conclusion: str,
    nl_premises: Optional[List[str]] = None,
    nl_conclusion: Optional[str] = None
) -> LogicalArgument:
    """
    Parse argument into LogicalArgument structure.

    Args:
        premises: List of formal premises (e.g., ["P → Q", "P"])
        conclusion: Formal conclusion (e.g., "Q")
        nl_premises: Optional natural language versions
        nl_conclusion: Optional natural language conclusion

    Returns:
        LogicalArgument ready for validation
    """
    # Extract all propositional variables
    all_text = " ".join(premises) + " " + conclusion
    engine = LogicEngine()
    terms = engine._extract_terms(all_text)

    propositions = {
        Proposition(symbol=term, statement=term)
        for term in terms
    }

    return LogicalArgument(
        premises=premises,
        conclusion=conclusion,
        propositions=propositions,
        natural_language_premises=nl_premises,
        natural_language_conclusion=nl_conclusion
    )


# Convenience functions for common use cases

def validate_modus_ponens(
    conditional: str,
    antecedent: str,
    expected_conclusion: str
) -> ValidationResult:
    """Quick validation of modus ponens form."""
    arg = parse_argument(
        premises=[conditional, antecedent],
        conclusion=expected_conclusion
    )
    engine = LogicEngine()
    return engine.validate(arg)


def validate_modus_tollens(
    conditional: str,
    negated_consequent: str,
    expected_conclusion: str
) -> ValidationResult:
    """Quick validation of modus tollens form."""
    arg = parse_argument(
        premises=[conditional, negated_consequent],
        conclusion=expected_conclusion
    )
    engine = LogicEngine()
    return engine.validate(arg)
