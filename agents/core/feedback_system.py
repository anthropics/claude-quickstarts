"""
Feedback Loop System - Phase 2 Enhancement

Provides adaptive learning from decision outcomes:
- Decision logging with full context
- Outcome tracking and classification
- Weight adjustment based on success/failure
- Calibration of confidence estimates
- Performance trend analysis
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import json
import statistics


class OutcomeType(Enum):
    """Classification of decision outcomes."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


class AdjustmentDirection(Enum):
    """Direction of weight adjustment."""
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"


@dataclass
class FeedbackEntry:
    """A feedback entry for a decision."""
    entry_id: str
    decision_id: str
    feedback_type: str
    comment: str
    rating: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class FeedbackType(Enum):
    """Types of feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class DecisionRecord:
    """Record of a decision made by the system."""
    record_id: str
    decision_type: str  # e.g., "tool_selection", "strategy_choice"
    chosen_option: str
    alternatives: List[str]
    scores: Dict[str, float]
    confidence: float
    context: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Outcome fields (filled in later)
    outcome: Optional[OutcomeType] = None
    outcome_score: Optional[float] = None  # 0-1 score
    outcome_details: Optional[str] = None
    outcome_timestamp: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class WeightUpdate:
    """Record of a weight update."""
    weight_name: str
    old_value: float
    new_value: float
    reason: str
    trigger_record_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CalibrationMetric:
    """Metrics for confidence calibration."""
    confidence_bucket: float  # e.g., 0.8 means 80-90% confidence
    predicted_count: int
    actual_success_count: int
    calibration_error: float  # Difference between predicted and actual


@dataclass
class PerformanceTrend:
    """Performance trend over time."""
    period: str  # "hourly", "daily", "weekly"
    success_rate: float
    avg_confidence: float
    avg_outcome_score: float
    decision_count: int
    trend_direction: str  # "improving", "declining", "stable"


class WeightManager:
    """Manages and adjusts decision weights."""
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        min_weight: float = 0.01,
        max_weight: float = 1.0,
        momentum: float = 0.9
    ):
        self.learning_rate = learning_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.momentum = momentum
        
        self._weights: Dict[str, float] = {}
        self._gradients: Dict[str, float] = {}  # For momentum
        self._update_history: List[WeightUpdate] = []
    
    def get_weight(self, name: str, default: float = 0.5) -> float:
        """Get a weight value."""
        return self._weights.get(name, default)
    
    def set_weight(self, name: str, value: float) -> None:
        """Set a weight value directly."""
        self._weights[name] = max(self.min_weight, min(self.max_weight, value))
    
    def get_all_weights(self) -> Dict[str, float]:
        """Get all weights."""
        return dict(self._weights)
    
    def adjust_weight(
        self,
        name: str,
        outcome: OutcomeType,
        outcome_score: float,
        confidence: float,
        record_id: str
    ) -> WeightUpdate:
        """
        Adjust a weight based on outcome.
        
        Uses a modified gradient descent approach with momentum.
        """
        current = self.get_weight(name)
        
        # Calculate error: difference between confidence and actual outcome
        # Positive error = overconfident, negative = underconfident
        error = confidence - outcome_score
        
        # Calculate gradient with momentum
        old_gradient = self._gradients.get(name, 0)
        new_gradient = error * self.learning_rate
        smoothed_gradient = self.momentum * old_gradient + (1 - self.momentum) * new_gradient
        self._gradients[name] = smoothed_gradient
        
        # Adjust weight
        # If outcome was good (high score), increase weight
        # If outcome was bad (low score), decrease weight
        if outcome in (OutcomeType.SUCCESS, OutcomeType.PARTIAL_SUCCESS):
            adjustment = (1 - error) * self.learning_rate  # Reward
        else:
            adjustment = -error * self.learning_rate  # Penalty
        
        new_value = current + adjustment
        new_value = max(self.min_weight, min(self.max_weight, new_value))
        
        update = WeightUpdate(
            weight_name=name,
            old_value=current,
            new_value=new_value,
            reason=f"{outcome.value}: score={outcome_score:.2f}, conf={confidence:.2f}",
            trigger_record_id=record_id
        )
        
        self._weights[name] = new_value
        self._update_history.append(update)
        
        return update
    
    def batch_adjust(
        self,
        updates: List[Tuple[str, OutcomeType, float, float, str]]
    ) -> List[WeightUpdate]:
        """Adjust multiple weights at once."""
        results = []
        for name, outcome, score, confidence, record_id in updates:
            update = self.adjust_weight(name, outcome, score, confidence, record_id)
            results.append(update)
        return results
    
    def get_update_history(
        self, 
        weight_name: Optional[str] = None,
        limit: int = 100
    ) -> List[WeightUpdate]:
        """Get weight update history."""
        history = self._update_history
        if weight_name:
            history = [u for u in history if u.weight_name == weight_name]
        return history[-limit:]
    
    def reset_weight(self, name: str, default: float = 0.5) -> None:
        """Reset a weight to default."""
        self._weights[name] = default
        self._gradients[name] = 0
    
    def export_weights(self) -> str:
        """Export weights to JSON."""
        return json.dumps(self._weights, indent=2)
    
    def import_weights(self, json_str: str) -> int:
        """Import weights from JSON. Returns count imported."""
        data = json.loads(json_str)
        for name, value in data.items():
            self.set_weight(name, value)
        return len(data)


class ConfidenceCalibrator:
    """Calibrates confidence estimates based on actual outcomes."""
    
    def __init__(self, bucket_size: float = 0.1):
        self.bucket_size = bucket_size
        self._predictions: Dict[float, List[Tuple[float, float]]] = defaultdict(list)
        # bucket -> list of (predicted_confidence, actual_outcome)
    
    def record_prediction(
        self,
        predicted_confidence: float,
        actual_outcome_score: float
    ) -> None:
        """Record a prediction and its outcome."""
        bucket = self._get_bucket(predicted_confidence)
        self._predictions[bucket].append((predicted_confidence, actual_outcome_score))
    
    def _get_bucket(self, confidence: float) -> float:
        """Get the bucket for a confidence value."""
        return round(confidence / self.bucket_size) * self.bucket_size
    
    def get_calibration_metrics(self) -> List[CalibrationMetric]:
        """Get calibration metrics for all buckets."""
        metrics = []
        
        for bucket, predictions in sorted(self._predictions.items()):
            if not predictions:
                continue
            
            predicted_avg = sum(p[0] for p in predictions) / len(predictions)
            actual_avg = sum(p[1] for p in predictions) / len(predictions)
            
            metrics.append(CalibrationMetric(
                confidence_bucket=bucket,
                predicted_count=len(predictions),
                actual_success_count=sum(1 for p in predictions if p[1] >= 0.5),
                calibration_error=predicted_avg - actual_avg
            ))
        
        return metrics
    
    def get_calibration_adjustment(self, confidence: float) -> float:
        """
        Get adjustment factor for a confidence level.
        
        Returns a multiplier to apply to the raw confidence.
        """
        bucket = self._get_bucket(confidence)
        predictions = self._predictions.get(bucket, [])
        
        if len(predictions) < 5:
            return 1.0  # Not enough data
        
        predicted_avg = sum(p[0] for p in predictions) / len(predictions)
        actual_avg = sum(p[1] for p in predictions) / len(predictions)
        
        if predicted_avg == 0:
            return 1.0
        
        # Adjustment factor to bring predictions in line with reality
        return actual_avg / predicted_avg
    
    def calibrate(self, raw_confidence: float) -> float:
        """Apply calibration to a raw confidence score."""
        adjustment = self.get_calibration_adjustment(raw_confidence)
        calibrated = raw_confidence * adjustment
        return max(0.0, min(1.0, calibrated))
    
    def get_expected_calibration_error(self) -> float:
        """Calculate Expected Calibration Error (ECE)."""
        metrics = self.get_calibration_metrics()
        if not metrics:
            return 0.0
        
        total_samples = sum(m.predicted_count for m in metrics)
        if total_samples == 0:
            return 0.0
        
        ece = sum(
            (m.predicted_count / total_samples) * abs(m.calibration_error)
            for m in metrics
        )
        return ece


class OutcomeTracker:
    """Tracks and analyzes decision outcomes."""
    
    def __init__(self, max_records: int = 10000):
        self.max_records = max_records
        self._records: Dict[str, DecisionRecord] = {}
        self._by_type: Dict[str, List[str]] = defaultdict(list)
        self._by_option: Dict[str, List[str]] = defaultdict(list)
    
    def record_decision(self, record: DecisionRecord) -> None:
        """Record a new decision."""
        self._records[record.record_id] = record
        self._by_type[record.decision_type].append(record.record_id)
        self._by_option[record.chosen_option].append(record.record_id)
        
        # Prune old records if needed
        if len(self._records) > self.max_records:
            self._prune_oldest(self.max_records // 10)
    
    def record_outcome(
        self,
        record_id: str,
        outcome: OutcomeType,
        outcome_score: float,
        details: Optional[str] = None,
        duration_ms: Optional[float] = None
    ) -> bool:
        """Record the outcome of a decision."""
        if record_id not in self._records:
            return False
        
        record = self._records[record_id]
        record.outcome = outcome
        record.outcome_score = outcome_score
        record.outcome_details = details
        record.outcome_timestamp = datetime.now().isoformat()
        record.duration_ms = duration_ms
        
        return True
    
    def get_record(self, record_id: str) -> Optional[DecisionRecord]:
        """Get a decision record."""
        return self._records.get(record_id)
    
    def get_records_by_type(
        self, 
        decision_type: str,
        limit: int = 100
    ) -> List[DecisionRecord]:
        """Get records of a specific decision type."""
        record_ids = self._by_type.get(decision_type, [])[-limit:]
        return [self._records[rid] for rid in record_ids if rid in self._records]
    
    def get_records_by_option(
        self, 
        option: str,
        limit: int = 100
    ) -> List[DecisionRecord]:
        """Get records where a specific option was chosen."""
        record_ids = self._by_option.get(option, [])[-limit:]
        return [self._records[rid] for rid in record_ids if rid in self._records]
    
    def get_outcome_stats(
        self, 
        decision_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get outcome statistics."""
        records = list(self._records.values())
        if decision_type:
            records = [r for r in records if r.decision_type == decision_type]
        
        completed = [r for r in records if r.outcome is not None]
        if not completed:
            return {"count": 0}
        
        outcomes = [r.outcome for r in completed]
        scores = [r.outcome_score for r in completed if r.outcome_score is not None]
        confidences = [r.confidence for r in completed]
        
        return {
            "count": len(completed),
            "success_rate": outcomes.count(OutcomeType.SUCCESS) / len(outcomes),
            "failure_rate": outcomes.count(OutcomeType.FAILURE) / len(outcomes),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "avg_confidence": sum(confidences) / len(confidences),
            "score_std": statistics.stdev(scores) if len(scores) > 1 else 0,
            "by_outcome": {o.value: outcomes.count(o) for o in OutcomeType}
        }
    
    def get_option_performance(self, option: str) -> Dict[str, Any]:
        """Get performance stats for a specific option."""
        records = self.get_records_by_option(option, limit=1000)
        completed = [r for r in records if r.outcome is not None]
        
        if not completed:
            return {"option": option, "count": 0}
        
        scores = [r.outcome_score for r in completed if r.outcome_score is not None]
        success_count = sum(1 for r in completed if r.outcome == OutcomeType.SUCCESS)
        
        return {
            "option": option,
            "count": len(completed),
            "success_rate": success_count / len(completed),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "score_std": statistics.stdev(scores) if len(scores) > 1 else 0
        }
    
    def _prune_oldest(self, count: int) -> None:
        """Remove oldest records."""
        sorted_ids = sorted(
            self._records.keys(),
            key=lambda rid: self._records[rid].timestamp
        )
        
        for rid in sorted_ids[:count]:
            record = self._records.pop(rid, None)
            if record:
                self._by_type[record.decision_type].remove(rid)
                self._by_option[record.chosen_option].remove(rid)


class TrendAnalyzer:
    """Analyzes performance trends over time."""
    
    def __init__(self, tracker: OutcomeTracker):
        self.tracker = tracker
    
    def get_hourly_trend(self, hours: int = 24) -> List[PerformanceTrend]:
        """Get hourly performance trends."""
        return self._get_trends("hourly", hours)
    
    def get_daily_trend(self, days: int = 7) -> List[PerformanceTrend]:
        """Get daily performance trends."""
        return self._get_trends("daily", days)
    
    def _get_trends(
        self, 
        period: str, 
        count: int
    ) -> List[PerformanceTrend]:
        """Calculate trends for a time period."""
        now = datetime.now()
        trends = []
        
        for i in range(count):
            if period == "hourly":
                start = now - timedelta(hours=i+1)
                end = now - timedelta(hours=i)
            else:  # daily
                start = now - timedelta(days=i+1)
                end = now - timedelta(days=i)
            
            # Get records in this period
            records = [
                r for r in self.tracker._records.values()
                if r.outcome is not None and
                start.isoformat() <= r.timestamp <= end.isoformat()
            ]
            
            if not records:
                continue
            
            scores = [r.outcome_score for r in records if r.outcome_score is not None]
            confidences = [r.confidence for r in records]
            success_count = sum(1 for r in records if r.outcome == OutcomeType.SUCCESS)
            
            trends.append(PerformanceTrend(
                period=period,
                success_rate=success_count / len(records),
                avg_confidence=sum(confidences) / len(confidences),
                avg_outcome_score=sum(scores) / len(scores) if scores else 0,
                decision_count=len(records),
                trend_direction="stable"  # Will be calculated
            ))
        
        # Calculate trend directions
        for i in range(len(trends) - 1):
            current = trends[i].avg_outcome_score
            previous = trends[i + 1].avg_outcome_score
            
            if current > previous * 1.1:
                trends[i] = PerformanceTrend(
                    **{**trends[i].__dict__, "trend_direction": "improving"}
                )
            elif current < previous * 0.9:
                trends[i] = PerformanceTrend(
                    **{**trends[i].__dict__, "trend_direction": "declining"}
                )
        
        return trends
    
    def detect_anomalies(
        self, 
        threshold_std: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Detect anomalous performance periods."""
        daily_trends = self.get_daily_trend(30)
        if len(daily_trends) < 7:
            return []
        
        scores = [t.avg_outcome_score for t in daily_trends if t.avg_outcome_score > 0]
        if len(scores) < 5:
            return []
        
        mean_score = statistics.mean(scores)
        std_score = statistics.stdev(scores)
        
        anomalies = []
        for i, trend in enumerate(daily_trends):
            if abs(trend.avg_outcome_score - mean_score) > threshold_std * std_score:
                anomalies.append({
                    "day_offset": i,
                    "score": trend.avg_outcome_score,
                    "expected_range": (
                        mean_score - threshold_std * std_score,
                        mean_score + threshold_std * std_score
                    ),
                    "type": "low" if trend.avg_outcome_score < mean_score else "high"
                })
        
        return anomalies


class FeedbackLoop:
    """
    Main feedback loop integrating all components.
    
    Provides:
    - Decision recording
    - Outcome tracking
    - Weight adjustment
    - Confidence calibration
    - Trend analysis
    """
    
    def __init__(
        self,
        learning_rate: float = 0.1,
        enable_calibration: bool = True,
        enable_trend_analysis: bool = True
    ):
        self.weight_manager = WeightManager(learning_rate=learning_rate)
        self.calibrator = ConfidenceCalibrator() if enable_calibration else None
        self.tracker = OutcomeTracker()
        self.trend_analyzer = TrendAnalyzer(self.tracker) if enable_trend_analysis else None
        
        self._decision_counter = 0
    
    def record_decision(
        self,
        decision_type: str,
        chosen_option: str,
        alternatives: List[str],
        scores: Dict[str, float],
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a decision.
        
        Returns the record ID for later outcome tracking.
        """
        self._decision_counter += 1
        record_id = f"dec_{self._decision_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Apply calibration if available
        calibrated_confidence = confidence
        if self.calibrator:
            calibrated_confidence = self.calibrator.calibrate(confidence)
        
        record = DecisionRecord(
            record_id=record_id,
            decision_type=decision_type,
            chosen_option=chosen_option,
            alternatives=alternatives,
            scores=scores,
            confidence=calibrated_confidence,
            context=context or {}
        )
        
        self.tracker.record_decision(record)
        
        return record_id
    
    def record_outcome(
        self,
        record_id: str,
        outcome: OutcomeType,
        outcome_score: float,
        details: Optional[str] = None,
        duration_ms: Optional[float] = None
    ) -> List[WeightUpdate]:
        """
        Record the outcome of a decision and update weights.
        
        Returns list of weight updates applied.
        """
        # Record outcome
        success = self.tracker.record_outcome(
            record_id, outcome, outcome_score, details, duration_ms
        )
        
        if not success:
            return []
        
        record = self.tracker.get_record(record_id)
        if not record:
            return []
        
        # Update calibrator
        if self.calibrator:
            self.calibrator.record_prediction(record.confidence, outcome_score)
        
        # Adjust weights
        updates = []
        
        # Weight for the decision type
        type_update = self.weight_manager.adjust_weight(
            f"type_{record.decision_type}",
            outcome,
            outcome_score,
            record.confidence,
            record_id
        )
        updates.append(type_update)
        
        # Weight for the chosen option
        option_update = self.weight_manager.adjust_weight(
            f"option_{record.chosen_option}",
            outcome,
            outcome_score,
            record.confidence,
            record_id
        )
        updates.append(option_update)
        
        return updates
    
    def get_option_weights(self, options: List[str]) -> Dict[str, float]:
        """Get current weights for a list of options."""
        return {
            option: self.weight_manager.get_weight(f"option_{option}")
            for option in options
        }
    
    def get_adjusted_scores(
        self,
        base_scores: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Adjust base scores using learned weights.
        
        Combines base scores with option weights.
        """
        adjusted = {}
        for option, base_score in base_scores.items():
            weight = self.weight_manager.get_weight(f"option_{option}")
            # Weighted combination
            adjusted[option] = 0.7 * base_score + 0.3 * weight
        return adjusted
    
    def get_calibrated_confidence(self, raw_confidence: float) -> float:
        """Get calibrated confidence score."""
        if self.calibrator:
            return self.calibrator.calibrate(raw_confidence)
        return raw_confidence
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary."""
        stats = self.tracker.get_outcome_stats()
        
        summary = {
            "total_decisions": stats.get("count", 0),
            "success_rate": stats.get("success_rate", 0),
            "avg_score": stats.get("avg_score", 0),
            "avg_confidence": stats.get("avg_confidence", 0),
            "weight_count": len(self.weight_manager._weights),
            "outcomes": stats.get("by_outcome", {})
        }
        
        if self.calibrator:
            summary["calibration_error"] = self.calibrator.get_expected_calibration_error()
        
        if self.trend_analyzer:
            trends = self.trend_analyzer.get_daily_trend(7)
            if trends:
                summary["recent_trend"] = trends[0].trend_direction
                summary["trend_data"] = [
                    {
                        "success_rate": t.success_rate,
                        "avg_score": t.avg_outcome_score,
                        "count": t.decision_count
                    }
                    for t in trends[:7]
                ]
        
        return summary
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations based on performance analysis."""
        recommendations = []
        
        # Check calibration
        if self.calibrator:
            ece = self.calibrator.get_expected_calibration_error()
            if ece > 0.15:
                recommendations.append(
                    f"High calibration error ({ece:.2f}). Consider reviewing confidence estimation."
                )
        
        # Check for declining trends
        if self.trend_analyzer:
            trends = self.trend_analyzer.get_daily_trend(7)
            declining = sum(1 for t in trends if t.trend_direction == "declining")
            if declining >= 3:
                recommendations.append(
                    "Performance has been declining. Consider reviewing recent changes."
                )
        
        # Check for low-performing options
        stats = self.tracker.get_outcome_stats()
        if stats.get("failure_rate", 0) > 0.3:
            recommendations.append(
                f"High failure rate ({stats['failure_rate']:.1%}). Consider improving decision logic."
            )
        
        # Check for anomalies
        if self.trend_analyzer:
            anomalies = self.trend_analyzer.detect_anomalies()
            if anomalies:
                recommendations.append(
                    f"Detected {len(anomalies)} anomalous performance periods. Review for issues."
                )
        
        return recommendations
    
    def export_state(self) -> str:
        """Export feedback loop state to JSON."""
        return json.dumps({
            "weights": self.weight_manager.get_all_weights(),
            "decision_count": self._decision_counter,
            "exported_at": datetime.now().isoformat()
        }, indent=2)
    
    def import_state(self, json_str: str) -> None:
        """Import feedback loop state from JSON."""
        data = json.loads(json_str)
        self.weight_manager.import_weights(json.dumps(data.get("weights", {})))
        self._decision_counter = data.get("decision_count", 0)


# Convenience factory functions

def create_feedback_loop(
    learning_rate: float = 0.1,
    enable_all_features: bool = True
) -> FeedbackLoop:
    """Create a feedback loop with standard configuration."""
    return FeedbackLoop(
        learning_rate=learning_rate,
        enable_calibration=enable_all_features,
        enable_trend_analysis=enable_all_features
    )


def create_lightweight_feedback_loop(learning_rate: float = 0.1) -> FeedbackLoop:
    """Create a lightweight feedback loop without trend analysis."""
    return FeedbackLoop(
        learning_rate=learning_rate,
        enable_calibration=True,
        enable_trend_analysis=False
    )
