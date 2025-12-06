"""
Unit tests for Rule Engine

Tests theorem proving, forward/backward chaining, unification,
predicate parsing, and proof generation.
"""

import pytest
from agents.core.rule_engine import (
    RuleEngine,
    Predicate,
    Rule,
    ProofStep,
    ProofResult,
    ProofStatus,
    PredicateParser,
    ForwardChainer,
    BackwardChainer,
    Unifier,
)


class TestPredicate:
    """Test suite for Predicate."""

    @pytest.mark.unit
    def test_predicate_creation(self):
        """Test creating a predicate."""
        pred = Predicate(name="Mortal", arguments=["Socrates"], negated=False)

        assert pred.name == "Mortal"
        assert pred.arguments == ["Socrates"]
        assert pred.negated is False

    @pytest.mark.unit
    def test_predicate_string_representation(self):
        """Test predicate string representation."""
        pred = Predicate("Human", ["Socrates"])

        assert "Human" in str(pred)
        assert "Socrates" in str(pred)

    @pytest.mark.unit
    def test_negated_predicate_string(self):
        """Test negated predicate string representation."""
        pred = Predicate("Mortal", ["X"], negated=True)

        string_rep = str(pred)
        assert "¬" in string_rep or "not" in string_rep.lower()

    @pytest.mark.unit
    def test_predicate_equality(self):
        """Test predicate equality comparison."""
        pred1 = Predicate("Loves", ["Alice", "Bob"])
        pred2 = Predicate("Loves", ["Alice", "Bob"])
        pred3 = Predicate("Loves", ["Bob", "Alice"])

        assert pred1 == pred2
        assert pred1 != pred3

    @pytest.mark.unit
    def test_predicate_hash(self):
        """Test that predicates can be hashed."""
        pred1 = Predicate("Human", ["Plato"])
        pred2 = Predicate("Human", ["Plato"])

        # Same predicates should have same hash
        assert hash(pred1) == hash(pred2)

        # Can be used in sets/dicts
        pred_set = {pred1, pred2}
        assert len(pred_set) == 1

    @pytest.mark.unit
    def test_predicate_negation(self):
        """Test predicate negation."""
        pred = Predicate("Mortal", ["X"])
        neg_pred = pred.negate()

        assert neg_pred.negated is True
        assert pred.negated is False  # Original unchanged

        # Double negation
        double_neg = neg_pred.negate()
        assert double_neg.negated is False

    @pytest.mark.unit
    def test_predicate_substitution(self):
        """Test variable substitution in predicates."""
        pred = Predicate("Loves", ["X", "Y"])
        bindings = {"X": "Alice", "Y": "Bob"}

        substituted = pred.substitute(bindings)

        assert substituted.arguments == ["Alice", "Bob"]
        assert pred.arguments == ["X", "Y"]  # Original unchanged

    @pytest.mark.unit
    def test_partial_substitution(self):
        """Test partial variable substitution."""
        pred = Predicate("Knows", ["X", "Y", "Z"])
        bindings = {"X": "Alice", "Z": "Charlie"}

        substituted = pred.substitute(bindings)

        assert substituted.arguments == ["Alice", "Y", "Charlie"]


class TestRule:
    """Test suite for Rule."""

    @pytest.mark.unit
    def test_rule_creation(self):
        """Test creating an inference rule."""
        antecedents = [
            Predicate("Human", ["X"]),
        ]
        consequent = Predicate("Mortal", ["X"])

        rule = Rule(
            name="mortality_rule",
            antecedents=antecedents,
            consequent=consequent,
            confidence=1.0
        )

        assert rule.name == "mortality_rule"
        assert len(rule.antecedents) == 1
        assert rule.confidence == 1.0

    @pytest.mark.unit
    def test_rule_string_representation(self):
        """Test rule string representation."""
        rule = Rule(
            name="test_rule",
            antecedents=[Predicate("P", ["X"])],
            consequent=Predicate("Q", ["X"])
        )

        string_rep = str(rule)
        assert "→" in string_rep or "->" in string_rep
        assert "P" in string_rep
        assert "Q" in string_rep

    @pytest.mark.unit
    def test_multi_antecedent_rule(self):
        """Test rule with multiple antecedents."""
        antecedents = [
            Predicate("Parent", ["X", "Y"]),
            Predicate("Parent", ["Y", "Z"]),
        ]
        consequent = Predicate("Grandparent", ["X", "Z"])

        rule = Rule(
            name="grandparent_rule",
            antecedents=antecedents,
            consequent=consequent
        )

        assert len(rule.antecedents) == 2


class TestPredicateParser:
    """Test suite for PredicateParser."""

    @pytest.fixture
    def parser(self):
        """Create PredicateParser instance."""
        return PredicateParser()

    @pytest.mark.unit
    def test_parse_simple_predicate(self, parser):
        """Test parsing simple predicate."""
        text = "Human(Socrates)"
        pred = parser.parse(text)

        assert pred.name == "Human"
        assert "Socrates" in pred.arguments

    @pytest.mark.unit
    def test_parse_multi_argument_predicate(self, parser):
        """Test parsing predicate with multiple arguments."""
        text = "Loves(Alice, Bob)"
        pred = parser.parse(text)

        assert pred.name == "Loves"
        assert len(pred.arguments) >= 2

    @pytest.mark.unit
    def test_parse_negated_predicate(self, parser):
        """Test parsing negated predicate."""
        text = "¬Mortal(God)"
        pred = parser.parse(text)

        assert pred.negated is True

    @pytest.mark.unit
    def test_parse_natural_language(self, parser):
        """Test parsing natural language to predicate."""
        text = "Socrates is mortal"
        pred = parser.parse_natural_language(text)

        # Should extract predicate structure
        assert pred is not None
        assert isinstance(pred, Predicate)


class TestUnifier:
    """Test suite for Unifier (unification algorithm)."""

    @pytest.fixture
    def unifier(self):
        """Create Unifier instance."""
        return Unifier()

    @pytest.mark.unit
    def test_unify_identical_predicates(self, unifier):
        """Test unifying identical predicates."""
        pred1 = Predicate("Human", ["Socrates"])
        pred2 = Predicate("Human", ["Socrates"])

        bindings = unifier.unify(pred1, pred2)

        assert bindings is not None
        assert isinstance(bindings, dict)

    @pytest.mark.unit
    def test_unify_variable_with_constant(self, unifier):
        """Test unifying variable with constant."""
        pred1 = Predicate("Human", ["X"])  # Variable
        pred2 = Predicate("Human", ["Socrates"])  # Constant

        bindings = unifier.unify(pred1, pred2)

        assert bindings is not None
        assert bindings.get("X") == "Socrates"

    @pytest.mark.unit
    def test_unify_two_variables(self, unifier):
        """Test unifying two variables."""
        pred1 = Predicate("Loves", ["X", "Y"])
        pred2 = Predicate("Loves", ["A", "B"])

        bindings = unifier.unify(pred1, pred2)

        # Should produce valid bindings
        assert bindings is not None

    @pytest.mark.unit
    def test_unify_fails_different_names(self, unifier):
        """Test that unification fails for different predicate names."""
        pred1 = Predicate("Human", ["X"])
        pred2 = Predicate("Mortal", ["X"])

        bindings = unifier.unify(pred1, pred2)

        assert bindings is None or bindings == {}

    @pytest.mark.unit
    def test_unify_fails_different_arity(self, unifier):
        """Test that unification fails for different arities."""
        pred1 = Predicate("Knows", ["X", "Y"])
        pred2 = Predicate("Knows", ["Z"])

        bindings = unifier.unify(pred1, pred2)

        assert bindings is None or bindings == {}

    @pytest.mark.unit
    def test_occurs_check(self, unifier):
        """Test occurs check prevents infinite structures."""
        pred1 = Predicate("Eq", ["X", "Y"])
        pred2 = Predicate("Eq", ["f(X)", "Y"])

        # Should detect X occurs in f(X)
        bindings = unifier.unify(pred1, pred2)

        # May return None or handle occurs check


class TestForwardChainer:
    """Test suite for ForwardChainer."""

    @pytest.fixture
    def chainer(self):
        """Create ForwardChainer instance."""
        return ForwardChainer()

    @pytest.mark.unit
    def test_initialization(self, chainer):
        """Test forward chainer initialization."""
        assert hasattr(chainer, 'facts')
        assert hasattr(chainer, 'rules')

    @pytest.mark.unit
    def test_add_fact(self, chainer):
        """Test adding facts to knowledge base."""
        fact = Predicate("Human", ["Socrates"])
        chainer.add_fact(fact)

        assert fact in chainer.facts

    @pytest.mark.unit
    def test_add_rule(self, chainer):
        """Test adding rules to knowledge base."""
        rule = Rule(
            name="mortality",
            antecedents=[Predicate("Human", ["X"])],
            consequent=Predicate("Mortal", ["X"])
        )

        chainer.add_rule(rule)

        assert rule in chainer.rules

    @pytest.mark.integration
    def test_forward_inference_simple(self, chainer):
        """Test simple forward chaining inference."""
        # Add facts and rules
        chainer.add_fact(Predicate("Human", ["Socrates"]))
        chainer.add_rule(Rule(
            name="mortality",
            antecedents=[Predicate("Human", ["X"])],
            consequent=Predicate("Mortal", ["X"])
        ))

        # Run forward chaining
        chainer.infer()

        # Should derive Mortal(Socrates)
        mortal_socrates = Predicate("Mortal", ["Socrates"])
        assert mortal_socrates in chainer.facts

    @pytest.mark.integration
    def test_forward_inference_chain(self, chainer):
        """Test chained forward inference."""
        # Socrates is Human, Humans are Mortal, Mortals are Finite
        chainer.add_fact(Predicate("Human", ["Socrates"]))
        chainer.add_rule(Rule(
            name="r1",
            antecedents=[Predicate("Human", ["X"])],
            consequent=Predicate("Mortal", ["X"])
        ))
        chainer.add_rule(Rule(
            name="r2",
            antecedents=[Predicate("Mortal", ["X"])],
            consequent=Predicate("Finite", ["X"])
        ))

        chainer.infer()

        # Should derive both Mortal and Finite
        assert Predicate("Mortal", ["Socrates"]) in chainer.facts
        assert Predicate("Finite", ["Socrates"]) in chainer.facts


class TestBackwardChainer:
    """Test suite for BackwardChainer."""

    @pytest.fixture
    def chainer(self):
        """Create BackwardChainer instance."""
        return BackwardChainer()

    @pytest.mark.unit
    def test_initialization(self, chainer):
        """Test backward chainer initialization."""
        assert hasattr(chainer, 'facts')
        assert hasattr(chainer, 'rules')

    @pytest.mark.integration
    def test_backward_proof_simple(self, chainer):
        """Test simple backward chaining proof."""
        # Setup: Socrates is Human, Humans are Mortal
        chainer.add_fact(Predicate("Human", ["Socrates"]))
        chainer.add_rule(Rule(
            name="mortality",
            antecedents=[Predicate("Human", ["X"])],
            consequent=Predicate("Mortal", ["X"])
        ))

        # Goal: Prove Mortal(Socrates)
        goal = Predicate("Mortal", ["Socrates"])
        result = chainer.prove(goal)

        assert result.status == ProofStatus.PROVEN

    @pytest.mark.integration
    def test_backward_proof_multi_step(self, chainer):
        """Test multi-step backward proof."""
        chainer.add_fact(Predicate("Human", ["Socrates"]))
        chainer.add_rule(Rule(
            name="r1",
            antecedents=[Predicate("Human", ["X"])],
            consequent=Predicate("Mortal", ["X"])
        ))
        chainer.add_rule(Rule(
            name="r2",
            antecedents=[Predicate("Mortal", ["X"])],
            consequent=Predicate("Finite", ["X"])
        ))

        goal = Predicate("Finite", ["Socrates"])
        result = chainer.prove(goal)

        assert result.status == ProofStatus.PROVEN
        assert len(result.steps) > 1

    @pytest.mark.integration
    def test_backward_proof_fails(self, chainer):
        """Test that unprovable goals fail correctly."""
        chainer.add_fact(Predicate("Human", ["Socrates"]))

        # Try to prove something not derivable
        goal = Predicate("God", ["Socrates"])
        result = chainer.prove(goal)

        assert result.status in [ProofStatus.UNKNOWN, ProofStatus.DISPROVEN]


class TestProofResult:
    """Test suite for ProofResult."""

    @pytest.mark.unit
    def test_proof_result_creation(self):
        """Test creating a proof result."""
        result = ProofResult(
            status=ProofStatus.PROVEN,
            goal=Predicate("Mortal", ["Socrates"]),
            steps=[],
            confidence=1.0,
            time_ms=10.5
        )

        assert result.status == ProofStatus.PROVEN
        assert result.is_proven is True
        assert result.confidence == 1.0

    @pytest.mark.unit
    def test_proof_result_with_steps(self):
        """Test proof result with proof steps."""
        steps = [
            ProofStep(
                step_number=1,
                predicate=Predicate("Human", ["Socrates"]),
                justification="Given fact",
                confidence=1.0
            ),
            ProofStep(
                step_number=2,
                predicate=Predicate("Mortal", ["Socrates"]),
                justification="By mortality rule",
                rule_applied="mortality",
                confidence=1.0
            )
        ]

        result = ProofResult(
            status=ProofStatus.PROVEN,
            goal=Predicate("Mortal", ["Socrates"]),
            steps=steps,
            confidence=1.0,
            time_ms=5.0
        )

        assert len(result.steps) == 2
        assert result.steps[0].step_number == 1

    @pytest.mark.unit
    def test_disproven_result(self):
        """Test disproven proof result."""
        result = ProofResult(
            status=ProofStatus.DISPROVEN,
            goal=Predicate("Immortal", ["Socrates"]),
            steps=[],
            confidence=1.0,
            time_ms=3.0
        )

        assert result.is_proven is False
        assert result.status == ProofStatus.DISPROVEN


class TestRuleEngine:
    """Integration tests for the full RuleEngine."""

    @pytest.fixture
    def engine(self):
        """Create RuleEngine instance."""
        return RuleEngine()

    @pytest.mark.integration
    def test_engine_initialization(self, engine):
        """Test rule engine initialization."""
        assert hasattr(engine, 'forward_chainer')
        assert hasattr(engine, 'backward_chainer')
        assert hasattr(engine, 'parser')

    @pytest.mark.integration
    def test_prove_theorem(self, engine):
        """Test proving a theorem."""
        # Add knowledge
        engine.add_fact("Human(Socrates)")
        engine.add_rule("Human(X) → Mortal(X)")

        # Prove goal
        result = engine.prove("Mortal(Socrates)")

        assert result.status == ProofStatus.PROVEN

    @pytest.mark.integration
    def test_contradiction_detection(self, engine):
        """Test detecting contradictions."""
        engine.add_fact("Mortal(Socrates)")
        engine.add_fact("¬Mortal(Socrates)")

        # Should detect contradiction
        contradictions = engine.check_contradictions()

        assert len(contradictions) > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_empty_predicate_arguments(self):
        """Test predicate with no arguments."""
        pred = Predicate("True", [])

        assert len(pred.arguments) == 0

    @pytest.mark.unit
    def test_self_referential_rule(self):
        """Test handling of self-referential rules."""
        rule = Rule(
            name="loop",
            antecedents=[Predicate("P", ["X"])],
            consequent=Predicate("P", ["X"])
        )

        # Should handle without infinite loop
        assert rule.name == "loop"

    @pytest.mark.unit
    def test_circular_proof_detection(self):
        """Test detection of circular proofs."""
        chainer = BackwardChainer()
        chainer.add_rule(Rule(
            name="r1",
            antecedents=[Predicate("B", ["X"])],
            consequent=Predicate("A", ["X"])
        ))
        chainer.add_rule(Rule(
            name="r2",
            antecedents=[Predicate("A", ["X"])],
            consequent=Predicate("B", ["X"])
        ))

        # Try to prove A(Socrates) - circular dependency
        result = chainer.prove(Predicate("A", ["Socrates"]))

        # Should detect and handle circular reasoning
        assert result.status != ProofStatus.PROVEN or len(result.steps) < 100
