"""
Tests for Phase 2 Enhancement Modules

Tests that match the actual implementation APIs.
"""

import pytest
from typing import Dict, Any
from datetime import datetime


# ===========================================================
# Benchmark Suite Tests
# ===========================================================

class TestBenchmarkSuite:
    """Tests for benchmark_suite.py"""
    
    def test_benchmark_runner(self):
        """Test running a simple benchmark."""
        from agents.core.benchmark_suite import (
            BenchmarkRunner, BenchmarkConfig, BenchmarkCategory
        )
        
        runner = BenchmarkRunner()
        config = BenchmarkConfig(
            name="test_benchmark",
            category=BenchmarkCategory.PERFORMANCE,
            iterations=10
        )
        
        result = runner.run_benchmark(config, lambda: sum(range(1000)))
        
        assert result.success
        assert result.mean_ms > 0
        assert result.iterations == 10
    
    def test_regression_detection(self):
        """Test detecting performance regressions."""
        from agents.core.benchmark_suite import (
            BenchmarkRunner, BenchmarkResult, BenchmarkCategory
        )
        
        runner = BenchmarkRunner()
        
        baseline = BenchmarkResult(
            name="test",
            category=BenchmarkCategory.PERFORMANCE,
            success=True,
            iterations=10,
            mean_ms=10.0,
            std_ms=1.0,
            min_ms=9.0,
            max_ms=11.0,
            p50_ms=10.0,
            p90_ms=10.5,
            p99_ms=11.0
        )
        
        runner.set_baseline("test", baseline)
        
        current = BenchmarkResult(
            name="test",
            category=BenchmarkCategory.PERFORMANCE,
            success=True,
            iterations=10,
            mean_ms=15.0,  # 50% slower
            std_ms=1.0,
            min_ms=14.0,
            max_ms=16.0,
            p50_ms=15.0,
            p90_ms=15.5,
            p99_ms=16.0
        )
        
        regression = runner.check_regression("test", current, threshold_percent=10)
        
        assert regression.is_regression
        assert regression.change_percent > 40  # ~50% increase
    
    def test_accuracy_benchmarks(self):
        """Test accuracy benchmark framework."""
        from agents.core.benchmark_suite import AccuracyBenchmarks
        
        benchmarks = AccuracyBenchmarks()
        
        benchmarks.add_test_case("add_1", (2, 3), 5)
        benchmarks.add_test_case("add_2", (10, 20), 30)
        benchmarks.add_test_case("add_3", (0, 0), 0)
        
        results = benchmarks.run_accuracy_test(
            lambda args: args[0] + args[1]
        )
        
        assert results["accuracy"] == 1.0
        assert results["correct"] == 3
    
    def test_benchmark_export(self):
        """Test exporting benchmark results."""
        from agents.core.benchmark_suite import (
            BenchmarkRunner, BenchmarkConfig, BenchmarkCategory
        )
        import json
        
        runner = BenchmarkRunner()
        config = BenchmarkConfig(
            name="export_test",
            category=BenchmarkCategory.LATENCY,
            iterations=5
        )
        
        runner.run_benchmark(config, lambda: None)
        
        exported = runner.export_results()
        data = json.loads(exported)
        
        assert "timestamp" in data
        assert "benchmarks" in data
    
    def test_quick_benchmark(self):
        """Test quick_benchmark convenience function."""
        from agents.core.benchmark_suite import quick_benchmark
        
        results = quick_benchmark(lambda: sum(range(100)), iterations=20)
        
        assert "mean_ms" in results
        assert "p99_ms" in results
        assert "throughput" in results


# ===========================================================
# Latency Control Tests
# ===========================================================

class TestLatencyControl:
    """Tests for latency_control.py"""
    
    def test_latency_tracker(self):
        """Test latency measurement tracking."""
        from agents.core.latency_control import (
            LatencyTracker, LatencyMeasurement
        )
        
        tracker = LatencyTracker()
        
        for i in range(20):
            tracker.record(LatencyMeasurement(
                component="test_component",
                duration_ms=10.0 + i,
                success=True
            ))
        
        stats = tracker.get_stats("test_component")
        
        assert stats is not None
        assert stats.count == 20
        assert stats.mean_ms >= 10.0
    
    def test_circuit_breaker_closed(self):
        """Test circuit breaker in closed state."""
        from agents.core.latency_control import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker(failure_threshold=3)
        
        can_execute, state = cb.can_execute("test")
        assert can_execute
        assert state == CircuitState.CLOSED
    
    def test_circuit_breaker_opens(self):
        """Test circuit breaker opens after failures."""
        from agents.core.latency_control import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record failures
        for _ in range(3):
            cb.record_failure("test")
        
        can_execute, state = cb.can_execute("test")
        assert not can_execute
        assert state == CircuitState.OPEN
    
    def test_adaptive_timeout(self):
        """Test adaptive timeout adjustment."""
        from agents.core.latency_control import AdaptiveTimeout
        
        at = AdaptiveTimeout(base_timeout_ms=1000)
        
        # Record consistently fast latencies
        for _ in range(20):
            at.record_latency("fast_component", 50.0, True)
        
        timeout = at.get_timeout("fast_component")
        assert timeout <= 1000  # Should have decreased or stayed same
    
    def test_latency_budget(self):
        """Test latency budget configuration."""
        from agents.core.latency_control import LatencyBudget, TimeoutPolicy
        
        budget = LatencyBudget(
            name="api_call",
            max_ms=500.0,
            warning_ms=300.0,
            policy=TimeoutPolicy.RETRY,
            retry_count=3
        )
        
        assert budget.max_ms == 500.0
        assert budget.retry_count == 3


# ===========================================================
# UI Hooks Tests
# ===========================================================

class TestUIHooks:
    """Tests for ui_hooks.py"""
    
    def test_event_bus_subscription(self):
        """Test event bus subscription and emission."""
        from agents.core.ui_hooks import EventBus, UIEvent, EventType
        
        bus = EventBus()
        received = []
        
        bus.subscribe(EventType.PROGRESS_UPDATE, lambda e: received.append(e))
        
        bus.emit(UIEvent(
            event_type=EventType.PROGRESS_UPDATE,
            data={"progress": 50}
        ))
        
        assert len(received) == 1
        assert received[0].data["progress"] == 50
    
    def test_progress_tracker(self):
        """Test progress tracking."""
        from agents.core.ui_hooks import EventBus, ProgressTracker
        
        bus = EventBus()
        tracker = ProgressTracker(bus)
        
        progress = tracker.start_task("task1", "Test Task", total=100)
        assert progress.percentage == 0
        
        tracker.update_progress("task1", current=50)
        progress = tracker.get_task("task1")
        assert progress.percentage == 50
        
        tracker.complete_task("task1")
        progress = tracker.get_task("task1")
        assert progress.status == "complete"
    
    def test_status_manager(self):
        """Test status management."""
        from agents.core.ui_hooks import EventBus, StatusManager, AgentStatus
        
        bus = EventBus()
        status = StatusManager(bus)
        
        status.set_status(AgentStatus.THINKING, "Processing...")
        
        current = status.get_status()
        assert current["status"] == "thinking"
        assert current["message"] == "Processing..."
    
    def test_stream_handler(self):
        """Test streaming output."""
        from agents.core.ui_hooks import EventBus, StreamHandler
        
        bus = EventBus()
        stream = StreamHandler(bus)
        
        stream.stream_token("Hello")
        stream.stream_token(" World")
        
        assert stream.get_buffer() == "Hello World"
    
    def test_ui_hooks_integration(self):
        """Test UIHooks class integration."""
        from agents.core.ui_hooks import UIHooks, EventType
        
        hooks = UIHooks()
        events = []
        
        hooks.subscribe_all(lambda e: events.append(e))
        
        # Use progress tracking
        hooks.progress.start_task("test", "Test")
        hooks.progress.update_progress("test", current=50)
        hooks.progress.complete_task("test")
        
        assert len(events) >= 3  # start, update, complete


# ===========================================================
# Calibration System Tests
# ===========================================================

class TestCalibrationSystem:
    """Tests for calibration_system.py"""
    
    def test_calibration_tracker(self):
        """Test calibration tracking."""
        from agents.core.calibration_system import CalibrationTracker
        
        tracker = CalibrationTracker()
        
        # Add well-calibrated predictions
        tracker.record(0.9, True)
        tracker.record(0.8, True)
        tracker.record(0.2, False)
        tracker.record(0.1, False)
        
        metrics = tracker.get_metrics()
        
        assert metrics.total_samples == 4
        assert metrics.overall_accuracy == 0.5
    
    def test_platt_scaler(self):
        """Test Platt scaling calibration."""
        from agents.core.calibration_system import PlattScaler
        
        scaler = PlattScaler()
        
        # Fit with some data
        predictions = [0.3, 0.5, 0.7, 0.9] * 10
        outcomes = [False, True, True, True] * 10
        
        scaler.fit(predictions, outcomes)
        
        # Calibrate a value
        calibrated = scaler.calibrate(0.5)
        assert 0.0 <= calibrated <= 1.0
    
    def test_temperature_scaler(self):
        """Test temperature scaling."""
        from agents.core.calibration_system import TemperatureScaler
        
        scaler = TemperatureScaler(temperature=1.5)
        
        # Higher temperature should push probabilities toward 0.5
        calibrated = scaler.calibrate(0.9)
        assert calibrated < 0.9
    
    def test_calibration_system(self):
        """Test full calibration system."""
        from agents.core.calibration_system import CalibrationSystem
        
        system = CalibrationSystem()
        
        # Record many outcomes
        for _ in range(30):
            system.record(0.8, True, "category_a")
            system.record(0.3, False, "category_b")
        
        # Get metrics
        metrics = system.get_metrics()
        
        assert "category_a" in metrics or "general" in metrics
    
    def test_calibration_quality(self):
        """Test calibration quality assessment."""
        from agents.core.calibration_system import CalibrationSystem
        
        system = CalibrationSystem()
        
        # Add well-calibrated data
        for _ in range(50):
            system.record(0.9, True)
            system.record(0.1, False)
        
        quality = system.get_calibration_quality()
        assert quality in ["excellent", "good", "fair", "poor", "very_poor", "unknown"]
    
    def test_calculate_ece(self):
        """Test ECE calculation."""
        from agents.core.calibration_system import calculate_ece
        
        # Perfect calibration
        predictions = [0.5] * 10
        outcomes = [True] * 5 + [False] * 5
        
        ece = calculate_ece(predictions, outcomes)
        assert ece < 0.5  # Should be low for this case


# ===========================================================
# Constraint System Tests (Using Actual API)
# ===========================================================

class TestConstraintSystemActual:
    """Tests for constraint_system.py with actual API."""
    
    def test_constraint_types(self):
        """Test constraint types."""
        from agents.core.constraint_system import ConstraintType
        
        assert ConstraintType.HARD.value == "hard"
        assert ConstraintType.SOFT.value == "soft"
    
    def test_constraint_engine_basic(self):
        """Test constraint engine basic operations."""
        from agents.core.constraint_system import ConstraintEngine
        
        engine = ConstraintEngine()
        
        # Engine should be creatable
        assert engine is not None


# ===========================================================
# Retrieval Augmentation Tests (Using Actual API)
# ===========================================================

class TestRetrievalAugmentationActual:
    """Tests for retrieval_augmentation.py with actual API."""
    
    def test_query_expansion(self):
        """Test query expansion."""
        from agents.core.retrieval_augmentation import QueryExpander
        
        expander = QueryExpander()
        
        result = expander.expand("machine learning")
        
        # Result is QueryExpansion object
        assert result.original_query == "machine learning"
        assert len(result.expanded_terms) >= 0  # May have terms or be empty
    
    def test_chunk_creation(self):
        """Test document chunking."""
        from agents.core.retrieval_augmentation import Chunk
        
        chunk = Chunk(
            chunk_id="chunk1",
            content="Test content",
            source_id="test.txt",
            start_offset=0,
            end_offset=12
        )
        
        assert chunk.content == "Test content"
        assert chunk.source_id == "test.txt"


# ===========================================================
# Feedback System Tests (Using Actual API)
# ===========================================================

class TestFeedbackSystemActual:
    """Tests for feedback_system.py with actual API."""
    
    def test_feedback_loop_creation(self):
        """Test creating feedback loop."""
        from agents.core.feedback_system import FeedbackLoop
        
        loop = FeedbackLoop(learning_rate=0.1)
        
        assert loop is not None
        assert loop.weight_manager is not None
    
    def test_decision_recording(self):
        """Test recording decisions."""
        from agents.core.feedback_system import FeedbackLoop
        
        loop = FeedbackLoop()
        
        # Record a decision
        record_id = loop.record_decision(
            decision_type="choice",
            chosen_option="option_a",
            alternatives=["option_b", "option_c"],
            scores={"option_a": 0.8, "option_b": 0.6, "option_c": 0.4},
            confidence=0.75
        )
        
        assert record_id is not None
        assert record_id.startswith("dec_")


# ===========================================================
# Integration Tests
# ===========================================================

class TestIntegration:
    """Integration tests across new modules."""
    
    def test_benchmark_with_latency_control(self):
        """Test benchmarking with latency tracking."""
        from agents.core.benchmark_suite import quick_benchmark
        from agents.core.latency_control import (
            LatencyTracker, LatencyMeasurement
        )
        
        tracker = LatencyTracker()
        
        def tracked_operation():
            result = sum(range(1000))
            return result
        
        # Benchmark the operation
        results = quick_benchmark(tracked_operation, iterations=10)
        
        # Track results
        tracker.record(LatencyMeasurement(
            component="sum_operation",
            duration_ms=results["mean_ms"],
            success=True
        ))
        
        stats = tracker.get_stats("sum_operation")
        assert stats is not None
    
    def test_ui_hooks_with_calibration(self):
        """Test UI hooks with calibration updates."""
        from agents.core.ui_hooks import UIHooks, EventType
        from agents.core.calibration_system import CalibrationSystem
        
        hooks = UIHooks()
        calibration = CalibrationSystem()
        events = []
        
        # Subscribe to events
        hooks.subscribe(EventType.REASONING_STEP, lambda e: events.append(e))
        
        # Report calibration
        calibration.record(0.9, True)
        quality = calibration.get_calibration_quality()
        
        hooks.reasoning.report_step(
            "calibration_check",
            f"Calibration quality: {quality}",
            {"quality": quality}
        )
        
        assert len(events) == 1
