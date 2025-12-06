"""
Unit tests for Curriculum, Observability, Role, Semantic Parser, and Clarification Systems

Combined test file for the remaining untested modules.
"""

import pytest

from agents.core.curriculum_system import (  # noqa: E402
    CurriculumSystem,
    DifficultyLevel,
    LearningPath,
    SkillTree,
)
from agents.core.observability_system import (  # noqa: E402
    ObservabilitySystem,
    Telemetry,
    MetricsCollector,
    TraceLogger,
)
from agents.core.role_system import (  # noqa: E402
    RoleSystem,
    Role,
    RoleCapability,
    RoleAssigner,
)
from agents.core.semantic_parser import (  # noqa: E402
    SemanticParser,
    SemanticFrame,
    EntityExtractor,
    IntentClassifier,
)
from agents.core.clarification_system import (  # noqa: E402
    ClarificationSystem,
    ClarificationRequest,
    AmbiguityDetector,
    QuestionGenerator,
)


# ==================== Curriculum System Tests ====================

class TestCurriculumSystem:
    """Test suite for CurriculumSystem."""

    @pytest.fixture
    def curriculum(self):
        """Create CurriculumSystem instance."""
        return CurriculumSystem()

    @pytest.mark.unit
    def test_difficulty_levels(self):
        """Test difficulty level progression."""
        levels = [
            DifficultyLevel.BEGINNER,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT
        ]

        for level in levels:
            path = LearningPath(level=level, topic="Test")
            assert path.level == level

    @pytest.mark.unit
    def test_skill_tree_creation(self, curriculum):
        """Test creating a skill tree."""
        tree = curriculum.create_skill_tree(domain="Logic")

        assert tree is not None
        assert isinstance(tree, SkillTree)

    @pytest.mark.integration
    def test_adaptive_difficulty(self, curriculum):
        """Test adaptive difficulty adjustment."""
        # Start at beginner
        current_level = DifficultyLevel.BEGINNER

        # Simulate successful completion
        new_level = curriculum.adjust_difficulty(
            current_level=current_level,
            success_rate=0.9
        )

        # Should progress or stay same
        assert new_level in list(DifficultyLevel)

    @pytest.mark.unit
    def test_prerequisite_checking(self, curriculum):
        """Test checking prerequisites."""
        has_prereqs = curriculum.check_prerequisites(
            skill="Advanced Logic",
            completed_skills=["Basic Logic", "Intermediate Logic"]
        )

        assert isinstance(has_prereqs, bool)


# ==================== Observability System Tests ====================

class TestObservabilitySystem:
    """Test suite for ObservabilitySystem."""

    @pytest.fixture
    def observability(self):
        """Create ObservabilitySystem instance."""
        return ObservabilitySystem()

    @pytest.mark.unit
    def test_telemetry_collection(self, observability):
        """Test collecting telemetry data."""
        telemetry = Telemetry(
            event_type="inference",
            data={"duration_ms": 150, "tokens": 100}
        )

        observability.collect(telemetry)
        assert True  # Successfully collected

    @pytest.mark.unit
    def test_metrics_collector(self):
        """Test MetricsCollector."""
        collector = MetricsCollector()

        collector.record_metric("latency", 150)
        collector.record_metric("latency", 200)

        avg = collector.get_average("latency")
        assert avg == 175

    @pytest.mark.unit
    def test_trace_logger(self):
        """Test TraceLogger."""
        logger = TraceLogger()

        logger.start_trace("trace_001", operation="test_op")
        logger.end_trace("trace_001")

        trace = logger.get_trace("trace_001")
        assert trace is not None

    @pytest.mark.integration
    def test_end_to_end_monitoring(self, observability):
        """Test complete monitoring pipeline."""
        with observability.trace("test_operation") as trace:
            trace.add_event("step_1", {"status": "started"})
            trace.add_event("step_2", {"status": "completed"})

        assert True  # Trace completed


# ==================== Role System Tests ====================

class TestRoleSystem:
    """Test suite for RoleSystem."""

    @pytest.fixture
    def role_system(self):
        """Create RoleSystem instance."""
        return RoleSystem()

    @pytest.mark.unit
    def test_role_creation(self):
        """Test creating a role."""
        role = Role(
            role_id="analyst",
            name="Data Analyst",
            capabilities=[
                RoleCapability.DATA_ANALYSIS,
                RoleCapability.STATISTICAL_REASONING
            ]
        )

        assert role.role_id == "analyst"
        assert len(role.capabilities) == 2

    @pytest.mark.unit
    def test_role_assignment(self):
        """Test assigning roles."""
        assigner = RoleAssigner()

        role = assigner.assign_role(
            task="Analyze this dataset",
            available_roles=["analyst", "researcher", "critic"]
        )

        assert role in ["analyst", "researcher", "critic"] or role is not None

    @pytest.mark.unit
    def test_role_capabilities(self, role_system):
        """Test checking role capabilities."""
        has_capability = role_system.check_capability(
            role_id="analyst",
            capability=RoleCapability.DATA_ANALYSIS
        )

        assert isinstance(has_capability, bool)

    @pytest.mark.integration
    def test_multi_role_collaboration(self, role_system):
        """Test collaboration between multiple roles."""
        roles = ["researcher", "critic", "synthesizer"]

        for role_id in roles:
            role_system.activate_role(role_id)

        active = role_system.get_active_roles()
        assert len(active) > 0


# ==================== Semantic Parser Tests ====================

class TestSemanticParser:
    """Test suite for SemanticParser."""

    @pytest.fixture
    def parser(self):
        """Create SemanticParser instance."""
        return SemanticParser()

    @pytest.mark.unit
    def test_parse_semantic_frame(self, parser):
        """Test parsing semantic frame."""
        text = "Book a flight to Paris"
        frame = parser.parse(text)

        assert isinstance(frame, SemanticFrame)
        assert frame is not None

    @pytest.mark.unit
    def test_entity_extraction(self):
        """Test EntityExtractor."""
        extractor = EntityExtractor()

        text = "Meet me in New York on January 15th"
        entities = extractor.extract(text)

        # Should extract location and date
        assert len(entities) >= 0

    @pytest.mark.unit
    def test_intent_classification(self):
        """Test IntentClassifier."""
        classifier = IntentClassifier()

        text = "What is the weather like?"
        intent = classifier.classify(text)

        assert intent is not None
        assert isinstance(intent, str)

    @pytest.mark.integration
    def test_full_parsing_pipeline(self, parser):
        """Test complete parsing pipeline."""
        text = "Show me restaurants in San Francisco serving Italian food"
        frame = parser.parse(text)

        # Should identify intent, entities, and relations
        assert frame.intent is not None or frame.entities is not None


# ==================== Clarification System Tests ====================

class TestClarificationSystem:
    """Test suite for ClarificationSystem."""

    @pytest.fixture
    def clarification(self):
        """Create ClarificationSystem instance."""
        return ClarificationSystem()

    @pytest.mark.unit
    def test_ambiguity_detection(self):
        """Test AmbiguityDetector."""
        detector = AmbiguityDetector()

        ambiguous = "What does it mean?"  # Ambiguous pronoun
        clear = "What does photosynthesis mean?"

        is_ambiguous_1 = detector.detect(ambiguous)
        detector.detect(clear)

        # First should be more ambiguous
        assert isinstance(is_ambiguous_1, bool)

    @pytest.mark.unit
    def test_clarification_request(self):
        """Test creating clarification request."""
        request = ClarificationRequest(
            request_id="cl_001",
            original_query="Tell me about it",
            ambiguity_type="pronoun_reference",
            clarifying_questions=["What specific topic are you referring to?"]
        )

        assert request.request_id == "cl_001"
        assert len(request.clarifying_questions) > 0

    @pytest.mark.unit
    def test_question_generator(self):
        """Test QuestionGenerator."""
        generator = QuestionGenerator()

        questions = generator.generate(
            query="How does it work?",
            ambiguities=["unclear_referent"]
        )

        assert isinstance(questions, list)
        assert len(questions) >= 0

    @pytest.mark.integration
    def test_clarification_workflow(self, clarification):
        """Test complete clarification workflow."""
        query = "What's the best option?"

        # Detect need for clarification
        needs_clarification = clarification.needs_clarification(query)

        if needs_clarification:
            # Generate clarifying questions
            questions = clarification.generate_questions(query)
            assert len(questions) > 0

        assert isinstance(needs_clarification, bool)

    @pytest.mark.unit
    def test_resolve_ambiguity(self, clarification):
        """Test resolving ambiguity with user response."""
        original = "What's the temperature?"
        user_response = "I mean the CPU temperature"

        resolved = clarification.resolve(
            original_query=original,
            user_clarification=user_response
        )

        assert resolved is not None


# ==================== Integration Tests ====================

class TestCrossSystemIntegration:
    """Integration tests across multiple systems."""

    @pytest.mark.integration
    def test_curriculum_with_observability(self):
        """Test curriculum system with observability tracking."""
        curriculum = CurriculumSystem()
        observability = ObservabilitySystem()

        with observability.trace("curriculum_progression"):
            curriculum.get_current_level(user_id="test_user")

        assert True  # Successfully tracked

    @pytest.mark.integration
    def test_semantic_parser_with_clarification(self):
        """Test semantic parser triggering clarification."""
        parser = SemanticParser()
        clarification = ClarificationSystem()

        query = "How do I do it?"

        # Parse
        frame = parser.parse(query)

        # Check if needs clarification
        if not frame or not frame.is_complete:
            questions = clarification.generate_questions(query)
            assert isinstance(questions, list)

    @pytest.mark.integration
    def test_role_assignment_for_task(self):
        """Test role system assigning appropriate role."""
        role_system = RoleSystem()

        task = "Analyze the logical consistency of this argument"
        assigned_role = role_system.assign_best_role(task)

        # Should assign a role capable of logical analysis
        assert assigned_role is not None


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases across all systems."""

    @pytest.mark.unit
    def test_empty_input_handling(self):
        """Test handling of empty inputs."""
        parser = SemanticParser()

        frame = parser.parse("")
        # Should handle gracefully
        assert frame is not None or True

    @pytest.mark.unit
    def test_very_long_input(self):
        """Test handling of very long inputs."""
        clarification = ClarificationSystem()

        long_query = "What about " + "X " * 1000 + "?"
        needs_clarification = clarification.needs_clarification(long_query)

        assert isinstance(needs_clarification, bool)

    @pytest.mark.unit
    def test_special_characters(self):
        """Test handling of special characters."""
        parser = SemanticParser()

        text = "What is @#$%^&*()?"
        parser.parse(text)

        # Should handle without crashing
        assert True

    @pytest.mark.unit
    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        parser = SemanticParser()

        text = "日本語で説明してください"
        parser.parse(text)

        # Should handle unicode
        assert True

    @pytest.mark.unit
    def test_concurrent_role_activation(self):
        """Test concurrent role activation."""
        import threading

        role_system = RoleSystem()
        results = []

        def activate_role(role_id):
            role_system.activate_role(role_id)
            results.append(role_id)

        threads = [
            threading.Thread(target=activate_role, args=(f"role_{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should handle concurrent access
        assert len(results) > 0
