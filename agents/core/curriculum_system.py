"""
Curriculum and Evaluation System - Phase 2

Implements:
- Difficulty-tiered datasets (easy→medium→hard→expert)
- Evaluation harness with structured comparisons
- Performance tracking across difficulty levels
- Adaptive curriculum progression
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import json
import statistics


class DifficultyLevel(Enum):
    """Difficulty levels for curriculum."""
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    # Backwards-compatible aliases
    EASY = 1
    MEDIUM = 2
    HARD = 3


class EvalMetric(Enum):
    """Evaluation metrics."""
    ACCURACY = "accuracy"
    VALIDITY = "validity"  # Logical validity
    SOUNDNESS = "soundness"  # Soundness of reasoning
    COMPLETENESS = "completeness"  # Consideration of all cases
    COHERENCE = "coherence"  # Internal consistency
    LATENCY = "latency"  # Time to answer
    CONFIDENCE_CALIBRATION = "confidence_calibration"


@dataclass
class EvalExample:
    """A single evaluation example."""
    example_id: str
    difficulty: DifficultyLevel
    input_text: str
    expected_output: Any
    domain: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result of evaluating one example."""
    example_id: str
    predicted: Any
    expected: Any
    correct: bool
    confidence: float
    latency_ms: float
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Complete evaluation report."""
    run_id: str
    timestamp: str
    total_examples: int
    results: List[EvalResult]
    aggregate_metrics: Dict[str, float]
    by_difficulty: Dict[str, Dict[str, float]]
    by_domain: Dict[str, Dict[str, float]]


class Dataset(ABC):
    """Abstract base class for evaluation datasets."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Dataset name."""
        ...
    
    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain of the dataset."""
        ...
    
    @abstractmethod
    def get_examples(
        self, 
        difficulty: Optional[DifficultyLevel] = None,
        limit: Optional[int] = None
    ) -> List[EvalExample]:
        """Get examples from the dataset."""
        ...
    
    def get_by_difficulty(self) -> Dict[DifficultyLevel, List[EvalExample]]:
        """Get examples grouped by difficulty."""
        examples = self.get_examples()
        grouped: Dict[DifficultyLevel, List[EvalExample]] = {}
        
        for ex in examples:
            if ex.difficulty not in grouped:
                grouped[ex.difficulty] = []
            grouped[ex.difficulty].append(ex)
        
        return grouped


class LogicDataset(Dataset):
    """Dataset for logical reasoning evaluation."""
    
    def __init__(self):
        self._examples = self._create_examples()
    
    @property
    def name(self) -> str:
        return "logic_reasoning"
    
    @property
    def domain(self) -> str:
        return "logic"
    
    def get_examples(
        self, 
        difficulty: Optional[DifficultyLevel] = None,
        limit: Optional[int] = None
    ) -> List[EvalExample]:
        examples = self._examples
        
        if difficulty:
            examples = [e for e in examples if e.difficulty == difficulty]
        
        if limit:
            examples = examples[:limit]
        
        return examples
    
    def _create_examples(self) -> List[EvalExample]:
        """Create logic reasoning examples."""
        return [
            # Easy - Basic modus ponens
            EvalExample(
                example_id="logic_e1",
                difficulty=DifficultyLevel.EASY,
                input_text="If it rains, the ground is wet. It is raining. Is the ground wet?",
                expected_output={"valid": True, "conclusion": "The ground is wet"},
                domain="logic",
                tags=["modus_ponens", "basic"]
            ),
            EvalExample(
                example_id="logic_e2",
                difficulty=DifficultyLevel.EASY,
                input_text="All dogs are animals. Fido is a dog. Is Fido an animal?",
                expected_output={"valid": True, "conclusion": "Fido is an animal"},
                domain="logic",
                tags=["syllogism", "basic"]
            ),
            # Medium - Chain reasoning
            EvalExample(
                example_id="logic_m1",
                difficulty=DifficultyLevel.MEDIUM,
                input_text="If A then B. If B then C. If C then D. A is true. What follows?",
                expected_output={"valid": True, "conclusion": "D is true"},
                domain="logic",
                tags=["chain_reasoning", "hypothetical_syllogism"]
            ),
            EvalExample(
                example_id="logic_m2",
                difficulty=DifficultyLevel.MEDIUM,
                input_text="Either it's Monday or it's a holiday. It's not Monday. Is it a holiday?",
                expected_output={"valid": True, "conclusion": "It is a holiday"},
                domain="logic",
                tags=["disjunctive_syllogism"]
            ),
            # Hard - Fallacy detection
            EvalExample(
                example_id="logic_h1",
                difficulty=DifficultyLevel.HARD,
                input_text="If I study, I'll pass. I passed. Therefore, I studied. Is this valid?",
                expected_output={"valid": False, "fallacy": "affirming_the_consequent"},
                domain="logic",
                tags=["fallacy", "affirming_consequent"]
            ),
            EvalExample(
                example_id="logic_h2",
                difficulty=DifficultyLevel.HARD,
                input_text="All philosophers are thinkers. Some thinkers are writers. "
                          "Therefore, some philosophers are writers. Valid?",
                expected_output={"valid": False, "fallacy": "undistributed_middle"},
                domain="logic",
                tags=["fallacy", "syllogism"]
            ),
            # Expert - Complex modal logic
            EvalExample(
                example_id="logic_x1",
                difficulty=DifficultyLevel.EXPERT,
                input_text="Necessarily, if P then Q. Possibly P. Does it follow that possibly Q?",
                expected_output={"valid": True, "modal": "K_axiom"},
                domain="logic",
                tags=["modal_logic", "necessity", "possibility"]
            ),
            EvalExample(
                example_id="logic_x2",
                difficulty=DifficultyLevel.EXPERT,
                input_text="If it's known that P, then P is true. P is known. But is it "
                          "known that it's known that P?",
                expected_output={"valid": "depends", "note": "Requires KK principle assumption"},
                domain="logic",
                tags=["epistemic_logic", "KK_principle"]
            ),
        ]


class ArgumentDataset(Dataset):
    """Dataset for argument evaluation."""
    
    def __init__(self):
        self._examples = self._create_examples()
    
    @property
    def name(self) -> str:
        return "argument_evaluation"
    
    @property
    def domain(self) -> str:
        return "argumentation"
    
    def get_examples(
        self, 
        difficulty: Optional[DifficultyLevel] = None,
        limit: Optional[int] = None
    ) -> List[EvalExample]:
        examples = self._examples
        
        if difficulty:
            examples = [e for e in examples if e.difficulty == difficulty]
        
        if limit:
            examples = examples[:limit]
        
        return examples
    
    def _create_examples(self) -> List[EvalExample]:
        """Create argument evaluation examples."""
        return [
            # Easy
            EvalExample(
                example_id="arg_e1",
                difficulty=DifficultyLevel.EASY,
                input_text="Premise: Regular exercise improves health. "
                          "Conclusion: You should exercise regularly.",
                expected_output={"strength": "strong", "type": "practical"},
                domain="argumentation",
                tags=["practical_reasoning"]
            ),
            # Medium
            EvalExample(
                example_id="arg_m1",
                difficulty=DifficultyLevel.MEDIUM,
                input_text="Studies show 70% of experts agree on climate change. "
                          "Therefore, climate change is real.",
                expected_output={
                    "strength": "moderate",
                    "type": "appeal_to_authority",
                    "weakness": "percentage_appeal"
                },
                domain="argumentation",
                tags=["inductive", "authority"]
            ),
            # Hard
            EvalExample(
                example_id="arg_h1",
                difficulty=DifficultyLevel.HARD,
                input_text="Einstein believed in God. Einstein was a genius. "
                          "Therefore, believing in God is rational.",
                expected_output={
                    "valid": False,
                    "fallacy": "appeal_to_authority",
                    "note": "Expertise doesn't transfer between domains"
                },
                domain="argumentation",
                tags=["fallacy", "authority"]
            ),
            # Expert
            EvalExample(
                example_id="arg_x1",
                difficulty=DifficultyLevel.EXPERT,
                input_text="Consider Gettier cases: Smith has a justified true belief "
                          "but arrived at it through false premises. Is this knowledge?",
                expected_output={
                    "analysis": "No by standard JTB+",
                    "frameworks": ["JTB", "reliabilism", "virtue_epistemology"],
                    "note": "Requires philosophical analysis"
                },
                domain="argumentation",
                tags=["epistemology", "gettier", "knowledge"]
            ),
        ]


class Evaluator:
    """
    Evaluator for running and scoring evaluations.
    """
    
    def __init__(self):
        self.scorers: Dict[str, Callable] = {
            "exact_match": self._exact_match,
            "contains": self._contains_match,
            "validity": self._validity_match,
            "semantic": self._semantic_match,
        }
    
    def evaluate(
        self,
        model_fn: Callable[[str], Dict[str, Any]],
        examples: List[EvalExample],
        scoring_method: str = "exact_match"
    ) -> List[EvalResult]:
        """Evaluate model on examples."""
        results = []
        scorer = self.scorers.get(scoring_method, self._exact_match)
        
        for example in examples:
            start = datetime.now()
            
            try:
                output = model_fn(example.input_text)
                elapsed = (datetime.now() - start).total_seconds() * 1000
                
                predicted = output.get("answer") or output.get("conclusion") or output
                confidence = output.get("confidence", 0.5)
                
                correct, score = scorer(predicted, example.expected_output)
                
                results.append(EvalResult(
                    example_id=example.example_id,
                    predicted=predicted,
                    expected=example.expected_output,
                    correct=correct,
                    confidence=confidence,
                    latency_ms=elapsed,
                    metrics={"score": score}
                ))
                
            except Exception as e:
                results.append(EvalResult(
                    example_id=example.example_id,
                    predicted=None,
                    expected=example.expected_output,
                    correct=False,
                    confidence=0.0,
                    latency_ms=0.0,
                    error=str(e)
                ))
        
        return results
    
    def _exact_match(self, predicted: Any, expected: Any) -> tuple:
        """Exact match scoring."""
        if isinstance(expected, dict):
            # For dict expected, check key fields
            if isinstance(predicted, dict):
                matches = sum(
                    1 for k, v in expected.items()
                    if k in predicted and predicted[k] == v
                )
                score = matches / len(expected) if expected else 0
                return score >= 0.8, score
            return False, 0.0
        
        correct = str(predicted).lower() == str(expected).lower()
        return correct, 1.0 if correct else 0.0
    
    def _contains_match(self, predicted: Any, expected: Any) -> tuple:
        """Check if predicted contains expected."""
        pred_str = str(predicted).lower()
        exp_str = str(expected).lower() if not isinstance(expected, dict) else ""
        
        if isinstance(expected, dict):
            # Check if key values are contained
            matches = 0
            for key in ["conclusion", "valid", "answer"]:
                if key in expected:
                    if str(expected[key]).lower() in pred_str:
                        matches += 1
            score = matches / 3
            return score >= 0.5, score
        
        contains = exp_str in pred_str
        return contains, 1.0 if contains else 0.0
    
    def _validity_match(self, predicted: Any, expected: Any) -> tuple:
        """Match on validity specifically."""
        if isinstance(expected, dict) and "valid" in expected:
            exp_valid = expected["valid"]
            
            if isinstance(predicted, dict):
                pred_valid = predicted.get("valid")
            else:
                # Try to extract from text
                pred_str = str(predicted).lower()
                if "valid" in pred_str and "invalid" not in pred_str:
                    pred_valid = True
                elif "invalid" in pred_str or "not valid" in pred_str:
                    pred_valid = False
                else:
                    pred_valid = None
            
            if pred_valid == exp_valid:
                return True, 1.0
            elif pred_valid is None:
                return False, 0.3  # Partial credit for trying
            else:
                return False, 0.0
        
        return self._exact_match(predicted, expected)
    
    def _semantic_match(self, predicted: Any, expected: Any) -> tuple:
        """Semantic similarity matching (simplified)."""
        # Would use embeddings in production
        return self._contains_match(predicted, expected)


class EvalHarness:
    """
    Complete evaluation harness.
    """
    
    def __init__(self):
        self.evaluator = Evaluator()
        self.datasets: Dict[str, Dataset] = {}
        self.run_history: List[EvalReport] = []
        
        # Register built-in datasets
        self.register_dataset(LogicDataset())
        self.register_dataset(ArgumentDataset())
    
    def register_dataset(self, dataset: Dataset) -> None:
        """Register a dataset."""
        self.datasets[dataset.name] = dataset
    
    def run_eval(
        self,
        model_fn: Callable[[str], Dict[str, Any]],
        dataset_name: str,
        difficulty: Optional[DifficultyLevel] = None,
        scoring_method: str = "validity"
    ) -> EvalReport:
        """Run evaluation on a dataset."""
        import hashlib
        
        if dataset_name not in self.datasets:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        
        dataset = self.datasets[dataset_name]
        examples = dataset.get_examples(difficulty=difficulty)
        
        # Run evaluation
        results = self.evaluator.evaluate(model_fn, examples, scoring_method)
        
        # Calculate aggregates
        aggregate = self._calculate_aggregates(results)
        by_difficulty = self._group_by_difficulty(results, examples)
        by_domain = self._group_by_domain(results, examples)
        
        run_id = hashlib.sha256(
            f"{dataset_name}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        report = EvalReport(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            total_examples=len(examples),
            results=results,
            aggregate_metrics=aggregate,
            by_difficulty=by_difficulty,
            by_domain=by_domain
        )
        
        self.run_history.append(report)
        return report
    
    def run_curriculum(
        self,
        model_fn: Callable[[str], Dict[str, Any]],
        dataset_name: str,
        passing_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Run curriculum-based evaluation with progression."""
        if dataset_name not in self.datasets:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        
        dataset = self.datasets[dataset_name]
        progression = []
        
        for difficulty in DifficultyLevel:
            examples = dataset.get_examples(difficulty=difficulty)
            if not examples:
                continue
            
            results = self.evaluator.evaluate(model_fn, examples, "validity")
            accuracy = sum(1 for r in results if r.correct) / len(results)
            
            level_result = {
                "difficulty": difficulty.name,
                "accuracy": accuracy,
                "passed": accuracy >= passing_threshold,
                "examples_tested": len(examples)
            }
            progression.append(level_result)
            
            if accuracy < passing_threshold:
                # Stop at failing level
                break
        
        max_level = None
        for level in progression:
            if level["passed"]:
                max_level = level["difficulty"]
        
        return {
            "progression": progression,
            "max_level_passed": max_level,
            "curriculum_complete": len(progression) == len(DifficultyLevel)
        }
    
    def compare_runs(
        self,
        run_id_1: str,
        run_id_2: str
    ) -> Dict[str, Any]:
        """Compare two evaluation runs."""
        run1 = next((r for r in self.run_history if r.run_id == run_id_1), None)
        run2 = next((r for r in self.run_history if r.run_id == run_id_2), None)
        
        if not run1 or not run2:
            raise ValueError("Run not found")
        
        comparison = {
            "run_1": run_id_1,
            "run_2": run_id_2,
            "metric_changes": {},
            "by_difficulty_changes": {}
        }
        
        # Compare aggregate metrics
        for metric in run1.aggregate_metrics:
            if metric in run2.aggregate_metrics:
                delta = run2.aggregate_metrics[metric] - run1.aggregate_metrics[metric]
                comparison["metric_changes"][metric] = {
                    "run_1": run1.aggregate_metrics[metric],
                    "run_2": run2.aggregate_metrics[metric],
                    "delta": delta,
                    "improved": delta > 0
                }
        
        # Compare by difficulty
        for diff in run1.by_difficulty:
            if diff in run2.by_difficulty:
                acc1 = run1.by_difficulty[diff].get("accuracy", 0)
                acc2 = run2.by_difficulty[diff].get("accuracy", 0)
                comparison["by_difficulty_changes"][diff] = {
                    "run_1": acc1,
                    "run_2": acc2,
                    "delta": acc2 - acc1
                }
        
        return comparison
    
    def _calculate_aggregates(
        self, 
        results: List[EvalResult]
    ) -> Dict[str, float]:
        """Calculate aggregate metrics."""
        if not results:
            return {}
        
        correct = [r for r in results if r.correct]
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        confidences = [r.confidence for r in results]
        
        accuracy = len(correct) / len(results)
        
        # Confidence calibration (ECE approximation)
        ece = 0.0
        for r in results:
            expected_acc = r.confidence
            actual_acc = 1.0 if r.correct else 0.0
            ece += abs(expected_acc - actual_acc)
        ece /= len(results) if results else 1
        
        return {
            "accuracy": accuracy,
            "total_correct": len(correct),
            "total_examples": len(results),
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "median_latency_ms": statistics.median(latencies) if latencies else 0,
            "avg_confidence": statistics.mean(confidences) if confidences else 0,
            "calibration_error": ece
        }
    
    def _group_by_difficulty(
        self,
        results: List[EvalResult],
        examples: List[EvalExample]
    ) -> Dict[str, Dict[str, float]]:
        """Group results by difficulty level."""
        example_map = {e.example_id: e for e in examples}
        grouped: Dict[str, List[EvalResult]] = {}
        
        for result in results:
            example = example_map.get(result.example_id)
            if example:
                diff = example.difficulty.name
                if diff not in grouped:
                    grouped[diff] = []
                grouped[diff].append(result)
        
        return {
            diff: self._calculate_aggregates(group_results)
            for diff, group_results in grouped.items()
        }
    
    def _group_by_domain(
        self,
        results: List[EvalResult],
        examples: List[EvalExample]
    ) -> Dict[str, Dict[str, float]]:
        """Group results by domain."""
        example_map = {e.example_id: e for e in examples}
        grouped: Dict[str, List[EvalResult]] = {}
        
        for result in results:
            example = example_map.get(result.example_id)
            if example:
                domain = example.domain
                if domain not in grouped:
                    grouped[domain] = []
                grouped[domain].append(result)
        
        return {
            domain: self._calculate_aggregates(group_results)
            for domain, group_results in grouped.items()
        }


class CurriculumLearner:
    """
    Adaptive curriculum learning system.
    """
    
    def __init__(self, harness: EvalHarness):
        self.harness = harness
        self.current_level: Dict[str, DifficultyLevel] = {}  # Per dataset
        self.performance_history: Dict[str, List[float]] = {}
        
        self.promotion_threshold = 0.8
        self.demotion_threshold = 0.5
        self.min_examples_for_change = 10
    
    def get_next_examples(
        self,
        dataset_name: str,
        count: int = 5
    ) -> List[EvalExample]:
        """Get next examples based on current curriculum level."""
        if dataset_name not in self.harness.datasets:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        
        current = self.current_level.get(dataset_name, DifficultyLevel.EASY)
        dataset = self.harness.datasets[dataset_name]
        
        examples = dataset.get_examples(difficulty=current, limit=count)
        return examples
    
    def record_performance(
        self,
        dataset_name: str,
        accuracy: float
    ) -> Dict[str, Any]:
        """Record performance and adjust curriculum."""
        if dataset_name not in self.performance_history:
            self.performance_history[dataset_name] = []
        
        self.performance_history[dataset_name].append(accuracy)
        
        # Check for level adjustment
        history = self.performance_history[dataset_name]
        if len(history) < self.min_examples_for_change:
            return {
                "level": self.current_level.get(dataset_name, DifficultyLevel.EASY).name,
                "action": "continue",
                "recent_avg": statistics.mean(history)
            }
        
        recent_avg = statistics.mean(history[-self.min_examples_for_change:])
        current = self.current_level.get(dataset_name, DifficultyLevel.EASY)
        
        action = "continue"
        
        if recent_avg >= self.promotion_threshold:
            # Promote to next level
            if current.value < DifficultyLevel.EXPERT.value:
                new_level = DifficultyLevel(current.value + 1)
                self.current_level[dataset_name] = new_level
                action = "promoted"
                self.performance_history[dataset_name] = []  # Reset
        
        elif recent_avg < self.demotion_threshold:
            # Demote to previous level
            if current.value > DifficultyLevel.EASY.value:
                new_level = DifficultyLevel(current.value - 1)
                self.current_level[dataset_name] = new_level
                action = "demoted"
                self.performance_history[dataset_name] = []  # Reset
        
        return {
            "level": self.current_level.get(dataset_name, DifficultyLevel.EASY).name,
            "action": action,
            "recent_avg": recent_avg
        }
    
    def get_status(self, dataset_name: str) -> Dict[str, Any]:
        """Get current curriculum status."""
        return {
            "dataset": dataset_name,
            "current_level": self.current_level.get(dataset_name, DifficultyLevel.EASY).name,
            "examples_at_level": len(self.performance_history.get(dataset_name, [])),
            "recent_performance": self.performance_history.get(dataset_name, [])[-10:]
        }


# Simple types for quick skill management used in tests
@dataclass
class LearningPath:
    level: DifficultyLevel
    topic: str


@dataclass
class SkillTree:
    domain: str
    skills: List[str] = field(default_factory=list)


class CurriculumSystem:
    """Lightweight curriculum facade for tests."""

    def __init__(self):
        self.user_levels: Dict[str, DifficultyLevel] = {}

    def create_skill_tree(self, domain: str) -> SkillTree:
        return SkillTree(domain=domain)

    def adjust_difficulty(self, current_level: DifficultyLevel, success_rate: float) -> DifficultyLevel:
        if success_rate >= 0.8 and current_level.value < DifficultyLevel.EXPERT.value:
            return DifficultyLevel(current_level.value + 1)
        if success_rate < 0.3 and current_level.value > DifficultyLevel.BEGINNER.value:
            return DifficultyLevel(current_level.value - 1)
        return current_level

    def check_prerequisites(self, skill: str, completed_skills: List[str]) -> bool:
        # Simple heuristic: require at least one completed skill
        return bool(completed_skills)

    def get_current_level(self, user_id: str) -> DifficultyLevel:
        return self.user_levels.get(user_id, DifficultyLevel.BEGINNER)

    def set_level(self, user_id: str, level: DifficultyLevel) -> None:
        self.user_levels[user_id] = level
