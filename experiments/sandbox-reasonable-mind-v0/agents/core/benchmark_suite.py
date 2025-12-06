"""
Benchmark Suite - Phase 2 Enhancement

Provides comprehensive benchmarking for the agent system:
- Performance benchmarks
- Accuracy metrics
- Regression tracking
- Comparison across versions
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time
import statistics
import json


class BenchmarkCategory(Enum):
    """Categories of benchmarks."""
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    MEMORY = "memory"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark."""
    name: str
    category: BenchmarkCategory
    warmup_iterations: int = 3
    iterations: int = 10
    timeout_seconds: float = 60.0
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    category: BenchmarkCategory
    success: bool
    iterations: int
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    p50_ms: float
    p90_ms: float
    p99_ms: float
    throughput: Optional[float] = None  # operations per second
    accuracy: Optional[float] = None  # 0-1 for accuracy benchmarks
    memory_mb: Optional[float] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegressionResult:
    """Result of comparing benchmarks across versions."""
    benchmark_name: str
    baseline_mean_ms: float
    current_mean_ms: float
    change_percent: float
    is_regression: bool
    threshold_percent: float
    details: str


class BenchmarkRunner:
    """Runs benchmarks and collects results."""
    
    def __init__(self):
        self._results: Dict[str, List[BenchmarkResult]] = {}
        self._baselines: Dict[str, BenchmarkResult] = {}
    
    def run_benchmark(
        self,
        config: BenchmarkConfig,
        func: Callable[[], Any],
        accuracy_checker: Optional[Callable[[Any], bool]] = None
    ) -> BenchmarkResult:
        """Run a single benchmark."""
        timings = []
        successes = 0
        error_msg = None
        
        # Warmup
        for _ in range(config.warmup_iterations):
            try:
                func()
            except Exception:
                pass
        
        # Actual runs
        for _ in range(config.iterations):
            start = time.perf_counter()
            try:
                result = func()
                elapsed = (time.perf_counter() - start) * 1000
                timings.append(elapsed)
                
                if accuracy_checker is None or accuracy_checker(result):
                    successes += 1
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                timings.append(elapsed)
                error_msg = str(e)
        
        if not timings:
            return BenchmarkResult(
                name=config.name,
                category=config.category,
                success=False,
                iterations=0,
                mean_ms=0, std_ms=0, min_ms=0, max_ms=0,
                p50_ms=0, p90_ms=0, p99_ms=0,
                error="No timings recorded"
            )
        
        sorted_timings = sorted(timings)
        n = len(sorted_timings)
        
        result = BenchmarkResult(
            name=config.name,
            category=config.category,
            success=error_msg is None,
            iterations=n,
            mean_ms=statistics.mean(timings),
            std_ms=statistics.stdev(timings) if n > 1 else 0,
            min_ms=sorted_timings[0],
            max_ms=sorted_timings[-1],
            p50_ms=sorted_timings[n // 2],
            p90_ms=sorted_timings[int(n * 0.9)] if n >= 10 else sorted_timings[-1],
            p99_ms=sorted_timings[int(n * 0.99)] if n >= 100 else sorted_timings[-1],
            throughput=1000 / statistics.mean(timings) if statistics.mean(timings) > 0 else 0,
            accuracy=successes / n if accuracy_checker else None,
            error=error_msg
        )
        
        # Store result
        if config.name not in self._results:
            self._results[config.name] = []
        self._results[config.name].append(result)
        
        return result
    
    def set_baseline(self, name: str, result: BenchmarkResult) -> None:
        """Set a baseline result for regression tracking."""
        self._baselines[name] = result
    
    def check_regression(
        self,
        name: str,
        current: BenchmarkResult,
        threshold_percent: float = 10.0
    ) -> RegressionResult:
        """Check for regression against baseline."""
        baseline = self._baselines.get(name)
        
        if not baseline:
            return RegressionResult(
                benchmark_name=name,
                baseline_mean_ms=0,
                current_mean_ms=current.mean_ms,
                change_percent=0,
                is_regression=False,
                threshold_percent=threshold_percent,
                details="No baseline available"
            )
        
        change = ((current.mean_ms - baseline.mean_ms) / baseline.mean_ms) * 100
        is_regression = change > threshold_percent
        
        return RegressionResult(
            benchmark_name=name,
            baseline_mean_ms=baseline.mean_ms,
            current_mean_ms=current.mean_ms,
            change_percent=change,
            is_regression=is_regression,
            threshold_percent=threshold_percent,
            details=f"{'REGRESSION' if is_regression else 'OK'}: {change:+.1f}% change"
        )
    
    def get_results(self, name: Optional[str] = None) -> Dict[str, List[BenchmarkResult]]:
        """Get benchmark results."""
        if name:
            return {name: self._results.get(name, [])}
        return dict(self._results)
    
    def export_results(self) -> str:
        """Export all results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": {}
        }
        
        for name, results in self._results.items():
            data["benchmarks"][name] = [
                {
                    "category": r.category.value,
                    "success": r.success,
                    "mean_ms": r.mean_ms,
                    "std_ms": r.std_ms,
                    "min_ms": r.min_ms,
                    "max_ms": r.max_ms,
                    "p50_ms": r.p50_ms,
                    "p90_ms": r.p90_ms,
                    "p99_ms": r.p99_ms,
                    "throughput": r.throughput,
                    "accuracy": r.accuracy,
                    "timestamp": r.timestamp
                }
                for r in results
            ]
        
        return json.dumps(data, indent=2)


class AccuracyBenchmarks:
    """Benchmarks for reasoning accuracy."""
    
    def __init__(self):
        self._test_cases: List[Dict[str, Any]] = []
    
    def add_test_case(
        self,
        name: str,
        input_data: Any,
        expected_output: Any,
        category: str = "general"
    ) -> None:
        """Add a test case for accuracy testing."""
        self._test_cases.append({
            "name": name,
            "input": input_data,
            "expected": expected_output,
            "category": category
        })
    
    def run_accuracy_test(
        self,
        evaluator: Callable[[Any], Any],
        comparator: Optional[Callable[[Any, Any], bool]] = None
    ) -> Dict[str, Any]:
        """Run accuracy tests against all test cases."""
        if comparator is None:
            comparator = lambda expected, actual: expected == actual
        
        results = []
        correct = 0
        
        for case in self._test_cases:
            try:
                actual = evaluator(case["input"])
                is_correct = comparator(case["expected"], actual)
                if is_correct:
                    correct += 1
                
                results.append({
                    "name": case["name"],
                    "category": case["category"],
                    "correct": is_correct,
                    "expected": case["expected"],
                    "actual": actual
                })
            except Exception as e:
                results.append({
                    "name": case["name"],
                    "category": case["category"],
                    "correct": False,
                    "error": str(e)
                })
        
        return {
            "total": len(self._test_cases),
            "correct": correct,
            "accuracy": correct / len(self._test_cases) if self._test_cases else 0,
            "results": results
        }
    
    def get_accuracy_by_category(self, results: Dict[str, Any]) -> Dict[str, float]:
        """Get accuracy broken down by category."""
        by_category: Dict[str, List[bool]] = {}
        
        for r in results.get("results", []):
            cat = r.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r.get("correct", False))
        
        return {
            cat: sum(values) / len(values) if values else 0
            for cat, values in by_category.items()
        }


class PerformanceBenchmarks:
    """Pre-defined performance benchmarks for agent components."""
    
    def __init__(self, runner: BenchmarkRunner):
        self.runner = runner
    
    def benchmark_inference(
        self,
        engine: Any,
        premises: List[str],
        iterations: int = 100
    ) -> BenchmarkResult:
        """Benchmark inference engine performance."""
        config = BenchmarkConfig(
            name="inference_engine",
            category=BenchmarkCategory.PERFORMANCE,
            iterations=iterations
        )
        
        def run():
            return engine.infer(premises)
        
        return self.runner.run_benchmark(config, run)
    
    def benchmark_memory_retrieval(
        self,
        memory: Any,
        query: str,
        iterations: int = 100
    ) -> BenchmarkResult:
        """Benchmark memory retrieval performance."""
        config = BenchmarkConfig(
            name="memory_retrieval",
            category=BenchmarkCategory.LATENCY,
            iterations=iterations
        )
        
        def run():
            return memory.retrieve(query)
        
        return self.runner.run_benchmark(config, run)
    
    def benchmark_planning(
        self,
        planner: Any,
        goal: str,
        iterations: int = 50
    ) -> BenchmarkResult:
        """Benchmark planning performance."""
        config = BenchmarkConfig(
            name="planning",
            category=BenchmarkCategory.PERFORMANCE,
            iterations=iterations
        )
        
        def run():
            return planner.plan(goal)
        
        return self.runner.run_benchmark(config, run)
    
    def benchmark_constraint_checking(
        self,
        engine: Any,
        context: Dict[str, Any],
        iterations: int = 200
    ) -> BenchmarkResult:
        """Benchmark constraint checking performance."""
        config = BenchmarkConfig(
            name="constraint_checking",
            category=BenchmarkCategory.PERFORMANCE,
            iterations=iterations
        )
        
        def run():
            return engine.check_all(context)
        
        return self.runner.run_benchmark(config, run)
    
    def benchmark_retrieval_augmentation(
        self,
        retriever: Any,
        query: str,
        iterations: int = 50
    ) -> BenchmarkResult:
        """Benchmark RAG retrieval performance."""
        config = BenchmarkConfig(
            name="rag_retrieval",
            category=BenchmarkCategory.LATENCY,
            iterations=iterations
        )
        
        def run():
            return retriever.retrieve(query)
        
        return self.runner.run_benchmark(config, run)


class BenchmarkSuite:
    """
    Complete benchmark suite for the agent system.
    """
    
    def __init__(self):
        self.runner = BenchmarkRunner()
        self.accuracy = AccuracyBenchmarks()
        self.performance = PerformanceBenchmarks(self.runner)
        self._suite_results: List[Dict[str, Any]] = []
    
    def add_logic_test_cases(self) -> None:
        """Add standard logic test cases."""
        # Modus ponens
        self.accuracy.add_test_case(
            "modus_ponens_1",
            {"premises": ["If A then B", "A"], "goal": "B"},
            True,
            "logic"
        )
        
        # Modus tollens
        self.accuracy.add_test_case(
            "modus_tollens_1",
            {"premises": ["If A then B", "Not B"], "goal": "Not A"},
            True,
            "logic"
        )
        
        # Syllogism
        self.accuracy.add_test_case(
            "syllogism_1",
            {"premises": ["All X are Y", "All Y are Z"], "goal": "All X are Z"},
            True,
            "logic"
        )
        
        # Contradiction detection
        self.accuracy.add_test_case(
            "contradiction_1",
            {"premises": ["A is true", "A is false"]},
            False,  # Should detect contradiction
            "logic"
        )
    
    def run_full_suite(
        self,
        components: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the full benchmark suite."""
        suite_start = time.time()
        results = {
            "timestamp": datetime.now().isoformat(),
            "performance": {},
            "accuracy": {},
            "regressions": []
        }
        
        # Run component benchmarks if provided
        if components:
            if "inference_engine" in components:
                result = self.performance.benchmark_inference(
                    components["inference_engine"],
                    ["If P then Q", "P"]
                )
                results["performance"]["inference"] = {
                    "mean_ms": result.mean_ms,
                    "p99_ms": result.p99_ms,
                    "throughput": result.throughput
                }
            
            if "memory" in components:
                result = self.performance.benchmark_memory_retrieval(
                    components["memory"],
                    "test query"
                )
                results["performance"]["memory"] = {
                    "mean_ms": result.mean_ms,
                    "p99_ms": result.p99_ms
                }
            
            if "constraint_engine" in components:
                result = self.performance.benchmark_constraint_checking(
                    components["constraint_engine"],
                    {"value": 1.0}
                )
                results["performance"]["constraints"] = {
                    "mean_ms": result.mean_ms,
                    "p99_ms": result.p99_ms
                }
        
        # Check for regressions
        for name, result_list in self.runner.get_results().items():
            if result_list:
                current = result_list[-1]
                regression = self.runner.check_regression(name, current)
                if regression.is_regression:
                    results["regressions"].append({
                        "benchmark": name,
                        "change_percent": regression.change_percent,
                        "details": regression.details
                    })
        
        results["duration_seconds"] = time.time() - suite_start
        self._suite_results.append(results)
        
        return results
    
    def generate_report(self) -> str:
        """Generate a markdown report of benchmark results."""
        lines = ["# Benchmark Report", ""]
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Latest results
        if self._suite_results:
            latest = self._suite_results[-1]
            
            lines.append("## Performance Results")
            lines.append("")
            lines.append("| Benchmark | Mean (ms) | P99 (ms) | Throughput |")
            lines.append("|-----------|-----------|----------|------------|")
            
            for name, data in latest.get("performance", {}).items():
                mean = data.get("mean_ms", 0)
                p99 = data.get("p99_ms", 0)
                throughput = data.get("throughput", 0)
                lines.append(f"| {name} | {mean:.2f} | {p99:.2f} | {throughput:.1f}/s |")
            
            lines.append("")
            
            # Regressions
            regressions = latest.get("regressions", [])
            if regressions:
                lines.append("## ⚠️ Regressions Detected")
                lines.append("")
                for reg in regressions:
                    lines.append(f"- **{reg['benchmark']}**: {reg['change_percent']:+.1f}% - {reg['details']}")
                lines.append("")
            else:
                lines.append("## ✅ No Regressions Detected")
                lines.append("")
        
        return "\n".join(lines)
    
    def export_results(self) -> str:
        """Export all suite results to JSON."""
        return json.dumps({
            "suite_results": self._suite_results,
            "benchmark_results": self.runner.export_results()
        }, indent=2)


# Convenience functions

def create_benchmark_suite() -> BenchmarkSuite:
    """Create a benchmark suite with standard test cases."""
    suite = BenchmarkSuite()
    suite.add_logic_test_cases()
    return suite


def quick_benchmark(func: Callable, iterations: int = 100) -> Dict[str, float]:
    """Quick benchmark a single function."""
    runner = BenchmarkRunner()
    config = BenchmarkConfig(
        name="quick_benchmark",
        category=BenchmarkCategory.PERFORMANCE,
        iterations=iterations
    )
    result = runner.run_benchmark(config, func)
    
    return {
        "mean_ms": result.mean_ms,
        "std_ms": result.std_ms,
        "min_ms": result.min_ms,
        "max_ms": result.max_ms,
        "p99_ms": result.p99_ms,
        "throughput": result.throughput or 0.0
    }
