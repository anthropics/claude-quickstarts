"""
Calibration System - Phase 2 Enhancement

Provides confidence calibration and adjustment:
- Calibration tracking and scoring
- Confidence adjustment based on history
- Reliability diagrams
- Expected calibration error
"""

from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import statistics
import math


class CalibrationMethod(Enum):
    """Methods for calibration adjustment."""
    PLATT_SCALING = "platt_scaling"
    ISOTONIC_REGRESSION = "isotonic_regression"
    TEMPERATURE_SCALING = "temperature_scaling"
    HISTOGRAM_BINNING = "histogram_binning"


@dataclass
class CalibrationPoint:
    """A single prediction with outcome for calibration."""
    predicted_confidence: float
    actual_outcome: bool  # True if prediction was correct
    category: str = "general"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationBin:
    """A bin for calibration analysis."""
    bin_start: float
    bin_end: float
    count: int
    accuracy: float
    avg_confidence: float
    gap: float  # |accuracy - avg_confidence|


@dataclass
class CalibrationMetrics:
    """Calibration quality metrics."""
    expected_calibration_error: float
    maximum_calibration_error: float
    brier_score: float
    log_loss: float
    reliability_diagram: List[CalibrationBin]
    total_samples: int
    overall_accuracy: float


class CalibrationTracker:
    """Tracks predictions and outcomes for calibration analysis."""
    
    def __init__(self, num_bins: int = 10):
        self._points: List[CalibrationPoint] = []
        self._num_bins = num_bins
    
    def record(
        self,
        predicted_confidence: float,
        actual_outcome: bool,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a prediction and outcome."""
        point = CalibrationPoint(
            predicted_confidence=max(0.0, min(1.0, predicted_confidence)),
            actual_outcome=actual_outcome,
            category=category,
            metadata=metadata or {}
        )
        self._points.append(point)
    
    def get_metrics(self, category: Optional[str] = None) -> CalibrationMetrics:
        """Calculate calibration metrics."""
        points = self._points
        if category:
            points = [p for p in points if p.category == category]
        
        if not points:
            return CalibrationMetrics(
                expected_calibration_error=0,
                maximum_calibration_error=0,
                brier_score=0,
                log_loss=0,
                reliability_diagram=[],
                total_samples=0,
                overall_accuracy=0
            )
        
        # Create bins
        bins = self._create_bins(points)
        
        # Calculate ECE (Expected Calibration Error)
        n = len(points)
        ece = sum(
            (bin.count / n) * bin.gap
            for bin in bins if bin.count > 0
        )
        
        # Calculate MCE (Maximum Calibration Error)
        mce = max((bin.gap for bin in bins if bin.count > 0), default=0)
        
        # Calculate Brier Score
        brier = sum(
            (p.predicted_confidence - (1.0 if p.actual_outcome else 0.0)) ** 2
            for p in points
        ) / n
        
        # Calculate Log Loss
        epsilon = 1e-15
        log_loss_val = -sum(
            (1.0 if p.actual_outcome else 0.0) * math.log(max(p.predicted_confidence, epsilon)) +
            (0.0 if p.actual_outcome else 1.0) * math.log(max(1 - p.predicted_confidence, epsilon))
            for p in points
        ) / n
        
        # Overall accuracy
        correct = sum(1 for p in points if p.actual_outcome)
        accuracy = correct / n
        
        return CalibrationMetrics(
            expected_calibration_error=ece,
            maximum_calibration_error=mce,
            brier_score=brier,
            log_loss=log_loss_val,
            reliability_diagram=bins,
            total_samples=n,
            overall_accuracy=accuracy
        )
    
    def _create_bins(self, points: List[CalibrationPoint]) -> List[CalibrationBin]:
        """Create calibration bins."""
        bins = []
        bin_size = 1.0 / self._num_bins
        
        for i in range(self._num_bins):
            bin_start = i * bin_size
            bin_end = (i + 1) * bin_size
            
            bin_points = [
                p for p in points
                if bin_start <= p.predicted_confidence < bin_end
            ]
            
            if bin_points:
                count = len(bin_points)
                accuracy = sum(1 for p in bin_points if p.actual_outcome) / count
                avg_conf = sum(p.predicted_confidence for p in bin_points) / count
                gap = abs(accuracy - avg_conf)
            else:
                count = 0
                accuracy = 0
                avg_conf = (bin_start + bin_end) / 2
                gap = 0
            
            bins.append(CalibrationBin(
                bin_start=bin_start,
                bin_end=bin_end,
                count=count,
                accuracy=accuracy,
                avg_confidence=avg_conf,
                gap=gap
            ))
        
        return bins
    
    def get_points(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[CalibrationPoint]:
        """Get calibration points."""
        points = self._points
        if category:
            points = [p for p in points if p.category == category]
        if limit:
            points = points[-limit:]
        return points
    
    def clear(self) -> None:
        """Clear all calibration data."""
        self._points.clear()


class PlattScaler:
    """Platt scaling for calibration adjustment."""
    
    def __init__(self):
        self._a: float = 1.0  # Slope
        self._b: float = 0.0  # Intercept
        self._fitted = False
    
    def fit(self, predictions: List[float], outcomes: List[bool]) -> None:
        """Fit the Platt scaler to data."""
        if len(predictions) < 10:
            return
        
        # Simple gradient descent for sigmoid parameters
        a, b = 1.0, 0.0
        learning_rate = 0.1
        
        for _ in range(100):
            grad_a, grad_b = 0.0, 0.0
            
            for pred, out in zip(predictions, outcomes):
                sigmoid = 1.0 / (1.0 + math.exp(-(a * pred + b)))
                target = 1.0 if out else 0.0
                error = sigmoid - target
                
                grad_a += error * pred
                grad_b += error
            
            a -= learning_rate * grad_a / len(predictions)
            b -= learning_rate * grad_b / len(predictions)
        
        self._a = a
        self._b = b
        self._fitted = True
    
    def calibrate(self, confidence: float) -> float:
        """Apply Platt scaling to a confidence value."""
        if not self._fitted:
            return confidence
        
        return 1.0 / (1.0 + math.exp(-(self._a * confidence + self._b)))
    
    def calibrate_batch(self, confidences: List[float]) -> List[float]:
        """Apply Platt scaling to multiple confidences."""
        return [self.calibrate(c) for c in confidences]


class TemperatureScaler:
    """Temperature scaling for calibration adjustment."""
    
    def __init__(self, temperature: float = 1.0):
        self._temperature = temperature
    
    def fit(self, predictions: List[float], outcomes: List[bool]) -> None:
        """Fit the temperature parameter."""
        if len(predictions) < 10:
            return
        
        # Grid search for best temperature
        best_temp = 1.0
        best_loss = float('inf')
        
        for temp in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]:
            self._temperature = temp
            calibrated = self.calibrate_batch(predictions)
            
            # Calculate NLL
            epsilon = 1e-15
            loss = -sum(
                (1.0 if out else 0.0) * math.log(max(cal, epsilon)) +
                (0.0 if out else 1.0) * math.log(max(1 - cal, epsilon))
                for cal, out in zip(calibrated, outcomes)
            ) / len(predictions)
            
            if loss < best_loss:
                best_loss = loss
                best_temp = temp
        
        self._temperature = best_temp
    
    def calibrate(self, confidence: float) -> float:
        """Apply temperature scaling."""
        # Convert to logit, scale, convert back
        epsilon = 1e-15
        confidence = max(epsilon, min(1 - epsilon, confidence))
        logit = math.log(confidence / (1 - confidence))
        scaled_logit = logit / self._temperature
        return 1.0 / (1.0 + math.exp(-scaled_logit))
    
    def calibrate_batch(self, confidences: List[float]) -> List[float]:
        """Apply temperature scaling to multiple confidences."""
        return [self.calibrate(c) for c in confidences]
    
    @property
    def temperature(self) -> float:
        """Get current temperature."""
        return self._temperature


class HistogramBinningCalibrator:
    """Histogram binning for calibration adjustment."""
    
    def __init__(self, num_bins: int = 10):
        self._num_bins = num_bins
        self._bin_accuracies: Dict[int, float] = {}
    
    def fit(self, predictions: List[float], outcomes: List[bool]) -> None:
        """Fit the histogram bins."""
        bin_size = 1.0 / self._num_bins
        
        for i in range(self._num_bins):
            bin_start = i * bin_size
            bin_end = (i + 1) * bin_size
            
            bin_preds = [
                (p, o) for p, o in zip(predictions, outcomes)
                if bin_start <= p < bin_end
            ]
            
            if bin_preds:
                accuracy = sum(1 for _, o in bin_preds if o) / len(bin_preds)
                self._bin_accuracies[i] = accuracy
            else:
                self._bin_accuracies[i] = (bin_start + bin_end) / 2
    
    def calibrate(self, confidence: float) -> float:
        """Apply histogram binning calibration."""
        bin_idx = min(
            int(confidence * self._num_bins),
            self._num_bins - 1
        )
        return self._bin_accuracies.get(bin_idx, confidence)
    
    def calibrate_batch(self, confidences: List[float]) -> List[float]:
        """Apply histogram binning to multiple confidences."""
        return [self.calibrate(c) for c in confidences]


class ConfidenceAdjuster:
    """Adjusts confidence based on historical calibration."""
    
    def __init__(
        self,
        method: CalibrationMethod = CalibrationMethod.TEMPERATURE_SCALING
    ):
        self._method = method
        self._tracker = CalibrationTracker()
        
        if method == CalibrationMethod.PLATT_SCALING:
            self._calibrator = PlattScaler()
        elif method == CalibrationMethod.TEMPERATURE_SCALING:
            self._calibrator = TemperatureScaler()
        elif method == CalibrationMethod.HISTOGRAM_BINNING:
            self._calibrator = HistogramBinningCalibrator()
        else:
            self._calibrator = TemperatureScaler()
        
        self._last_fit_count = 0
        self._refit_threshold = 50
    
    def record_outcome(
        self,
        predicted: float,
        actual: bool,
        category: str = "general"
    ) -> None:
        """Record an outcome for calibration."""
        self._tracker.record(predicted, actual, category)
        
        # Refit if enough new data
        if len(self._tracker._points) - self._last_fit_count >= self._refit_threshold:
            self._refit()
    
    def _refit(self) -> None:
        """Refit the calibrator with current data."""
        points = self._tracker.get_points()
        if len(points) < 20:
            return
        
        predictions = [p.predicted_confidence for p in points]
        outcomes = [p.actual_outcome for p in points]
        
        self._calibrator.fit(predictions, outcomes)
        self._last_fit_count = len(points)
    
    def adjust(self, confidence: float) -> float:
        """Adjust a confidence value based on calibration."""
        return self._calibrator.calibrate(confidence)
    
    def adjust_batch(self, confidences: List[float]) -> List[float]:
        """Adjust multiple confidence values."""
        return self._calibrator.calibrate_batch(confidences)
    
    def get_metrics(self) -> CalibrationMetrics:
        """Get calibration metrics."""
        return self._tracker.get_metrics()


class CategoryCalibrator:
    """Separate calibration for different categories."""
    
    def __init__(self, method: CalibrationMethod = CalibrationMethod.TEMPERATURE_SCALING):
        self._method = method
        self._adjusters: Dict[str, ConfidenceAdjuster] = {}
        self._default_adjuster = ConfidenceAdjuster(method)
    
    def _get_adjuster(self, category: str) -> ConfidenceAdjuster:
        """Get adjuster for category."""
        if category not in self._adjusters:
            self._adjusters[category] = ConfidenceAdjuster(self._method)
        return self._adjusters[category]
    
    def record_outcome(
        self,
        predicted: float,
        actual: bool,
        category: str = "general"
    ) -> None:
        """Record an outcome for a category."""
        adjuster = self._get_adjuster(category)
        adjuster.record_outcome(predicted, actual, category)
    
    def adjust(self, confidence: float, category: str = "general") -> float:
        """Adjust confidence for a category."""
        adjuster = self._adjusters.get(category, self._default_adjuster)
        return adjuster.adjust(confidence)
    
    def get_metrics(self, category: Optional[str] = None) -> Dict[str, CalibrationMetrics]:
        """Get metrics for categories."""
        if category:
            adjuster = self._adjusters.get(category)
            if adjuster:
                return {category: adjuster.get_metrics()}
            return {}
        
        return {
            cat: adj.get_metrics()
            for cat, adj in self._adjusters.items()
        }


class CalibrationSystem:
    """
    Main calibration system.
    
    Provides comprehensive confidence calibration and adjustment.
    """
    
    def __init__(
        self,
        method: CalibrationMethod = CalibrationMethod.TEMPERATURE_SCALING,
        per_category: bool = True
    ):
        self._method = method
        self._per_category = per_category
        
        if per_category:
            self._calibrator = CategoryCalibrator(method)
        else:
            self._calibrator = ConfidenceAdjuster(method)
        
        self._history: List[Dict[str, Any]] = []
    
    def record(
        self,
        predicted_confidence: float,
        actual_outcome: bool,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a prediction outcome."""
        self._calibrator.record_outcome(predicted_confidence, actual_outcome, category)
        
        self._history.append({
            "predicted": predicted_confidence,
            "actual": actual_outcome,
            "category": category,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def calibrate(
        self,
        confidence: float,
        category: str = "general"
    ) -> float:
        """Calibrate a confidence value."""
        if self._per_category and isinstance(self._calibrator, CategoryCalibrator):
            return self._calibrator.adjust(confidence, category)
        return self._calibrator.adjust(confidence)
    
    def calibrate_with_bounds(
        self,
        confidence: float,
        category: str = "general",
        uncertainty: float = 0.1
    ) -> Tuple[float, float, float]:
        """Calibrate with uncertainty bounds."""
        calibrated = self.calibrate(confidence, category)
        
        lower = max(0.0, calibrated - uncertainty)
        upper = min(1.0, calibrated + uncertainty)
        
        return lower, calibrated, upper
    
    def get_metrics(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get calibration metrics."""
        if self._per_category and isinstance(self._calibrator, CategoryCalibrator):
            metrics = self._calibrator.get_metrics(category)
            return {
                cat: {
                    "ece": m.expected_calibration_error,
                    "mce": m.maximum_calibration_error,
                    "brier_score": m.brier_score,
                    "total_samples": m.total_samples,
                    "overall_accuracy": m.overall_accuracy
                }
                for cat, m in metrics.items()
            }
        
        if isinstance(self._calibrator, ConfidenceAdjuster):
            m = self._calibrator.get_metrics()
            return {
                "general": {
                    "ece": m.expected_calibration_error,
                    "mce": m.maximum_calibration_error,
                    "brier_score": m.brier_score,
                    "total_samples": m.total_samples,
                    "overall_accuracy": m.overall_accuracy
                }
            }
        
        return {}
    
    def get_reliability_diagram(
        self,
        category: str = "general"
    ) -> List[Dict[str, Any]]:
        """Get reliability diagram data."""
        if self._per_category and isinstance(self._calibrator, CategoryCalibrator):
            metrics = self._calibrator.get_metrics(category)
            if category in metrics:
                return [
                    {
                        "bin_start": b.bin_start,
                        "bin_end": b.bin_end,
                        "count": b.count,
                        "accuracy": b.accuracy,
                        "avg_confidence": b.avg_confidence,
                        "gap": b.gap
                    }
                    for b in metrics[category].reliability_diagram
                ]
        
        if isinstance(self._calibrator, ConfidenceAdjuster):
            m = self._calibrator.get_metrics()
            return [
                {
                    "bin_start": b.bin_start,
                    "bin_end": b.bin_end,
                    "count": b.count,
                    "accuracy": b.accuracy,
                    "avg_confidence": b.avg_confidence,
                    "gap": b.gap
                }
                for b in m.reliability_diagram
            ]
        
        return []
    
    def is_well_calibrated(
        self,
        category: str = "general",
        ece_threshold: float = 0.1
    ) -> bool:
        """Check if calibration is within acceptable bounds."""
        metrics = self.get_metrics(category)
        if category in metrics:
            return metrics[category]["ece"] < ece_threshold
        return True  # No data, assume calibrated
    
    def get_calibration_quality(self, category: str = "general") -> str:
        """Get a qualitative assessment of calibration."""
        metrics = self.get_metrics(category)
        if category not in metrics:
            return "unknown"
        
        ece = metrics[category]["ece"]
        
        if ece < 0.05:
            return "excellent"
        elif ece < 0.10:
            return "good"
        elif ece < 0.15:
            return "fair"
        elif ece < 0.25:
            return "poor"
        else:
            return "very_poor"


# Convenience functions

def create_calibration_system(
    method: str = "temperature",
    per_category: bool = True
) -> CalibrationSystem:
    """Create a calibration system."""
    method_map = {
        "temperature": CalibrationMethod.TEMPERATURE_SCALING,
        "platt": CalibrationMethod.PLATT_SCALING,
        "histogram": CalibrationMethod.HISTOGRAM_BINNING
    }
    return CalibrationSystem(
        method=method_map.get(method, CalibrationMethod.TEMPERATURE_SCALING),
        per_category=per_category
    )


def calculate_ece(
    predictions: List[float],
    outcomes: List[bool],
    num_bins: int = 10
) -> float:
    """Calculate Expected Calibration Error."""
    tracker = CalibrationTracker(num_bins=num_bins)
    for pred, out in zip(predictions, outcomes):
        tracker.record(pred, out)
    
    metrics = tracker.get_metrics()
    return metrics.expected_calibration_error


def calculate_brier_score(
    predictions: List[float],
    outcomes: List[bool]
) -> float:
    """Calculate Brier score."""
    n = len(predictions)
    if n == 0:
        return 0.0
    
    return sum(
        (p - (1.0 if o else 0.0)) ** 2
        for p, o in zip(predictions, outcomes)
    ) / n
