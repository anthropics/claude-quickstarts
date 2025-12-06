"""
Tool Arbitration System - Advanced Enhancement

Provides intelligent tool/action selection:
- Usage statistics tracking
- Fit/cost/reliability scoring
- Multi-armed bandit exploration
- Context-aware tool recommendation
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import math
import random
import time
import hashlib


class SelectionStrategy(Enum):
    """Strategies for tool selection."""
    GREEDY = "greedy"  # Always pick best known
    EPSILON_GREEDY = "epsilon_greedy"  # Explore with probability epsilon
    UCB = "ucb"  # Upper Confidence Bound
    THOMPSON = "thompson"  # Thompson Sampling
    CONTEXTUAL = "contextual"  # Context-aware bandit


class ToolCategory(Enum):
    """Categories of tools."""
    RETRIEVAL = "retrieval"
    COMPUTATION = "computation"
    GENERATION = "generation"
    VALIDATION = "validation"
    EXTERNAL_API = "external_api"
    MEMORY = "memory"


@dataclass
class ToolProfile:
    """Profile of a tool with usage statistics."""
    tool_id: str
    name: str
    category: ToolCategory
    description: str = ""
    
    # Performance metrics
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    
    # Quality metrics
    quality_scores: List[float] = field(default_factory=list)
    user_ratings: List[float] = field(default_factory=list)
    
    # Capability tags
    capabilities: Set[str] = field(default_factory=set)
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    # Thompson sampling priors
    alpha: float = 1.0  # Successes + prior
    beta_param: float = 1.0  # Failures + prior
    
    @property
    def total_calls(self) -> int:
        """Total number of tool invocations."""
        return self.success_count + self.failure_count
    
    @property
    def success_rate(self) -> float:
        """Success rate of the tool."""
        if self.total_calls == 0:
            return 0.5  # Prior belief
        return self.success_count / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        """Average latency per call."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    @property
    def avg_cost(self) -> float:
        """Average cost per call."""
        if self.total_calls == 0:
            return 0.0
        return self.total_cost / self.total_calls
    
    @property
    def avg_quality(self) -> float:
        """Average quality score."""
        if not self.quality_scores:
            return 0.5  # Prior belief
        return sum(self.quality_scores) / len(self.quality_scores)
    
    def update_success(self, latency_ms: float, cost: float, quality: float = 1.0):
        """Record a successful invocation."""
        self.success_count += 1
        self.total_latency_ms += latency_ms
        self.total_cost += cost
        self.quality_scores.append(quality)
        self.alpha += 1  # Update beta distribution
    
    def update_failure(self, latency_ms: float, cost: float):
        """Record a failed invocation."""
        self.failure_count += 1
        self.total_latency_ms += latency_ms
        self.total_cost += cost
        self.beta_param += 1  # Update beta distribution
    
    def sample_thompson(self) -> float:
        """Sample from posterior for Thompson sampling."""
        # Beta distribution sample
        return random.betavariate(self.alpha, self.beta_param)
    
    def ucb_score(self, total_selections: int, c: float = 2.0) -> float:
        """Compute UCB score."""
        if self.total_calls == 0:
            return float('inf')  # Explore unvisited
        
        exploitation = self.success_rate
        exploration = c * math.sqrt(math.log(total_selections + 1) / self.total_calls)
        return exploitation + exploration


@dataclass
class ToolInvocation:
    """Record of a tool invocation."""
    invocation_id: str
    tool_id: str
    context: Dict[str, Any]
    inputs: Dict[str, Any]
    outputs: Optional[Any] = None
    success: bool = False
    latency_ms: float = 0.0
    cost: float = 0.0
    quality_score: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class ToolRecommendation:
    """Recommendation for tool usage."""
    tool_id: str
    score: float
    confidence: float
    rationale: str
    expected_latency_ms: float
    expected_cost: float
    alternative_tools: List[str] = field(default_factory=list)


class ToolScorer(ABC):
    """Abstract base for tool scoring strategies."""
    
    @abstractmethod
    def score(
        self,
        tool: ToolProfile,
        context: Dict[str, Any],
        total_selections: int
    ) -> float:
        """Score a tool for selection."""


class CompositeScorer(ToolScorer):
    """Combines multiple scoring factors."""
    
    def __init__(
        self,
        success_weight: float = 0.4,
        quality_weight: float = 0.3,
        latency_weight: float = 0.15,
        cost_weight: float = 0.15,
        max_latency_ms: float = 5000.0,
        max_cost: float = 1.0
    ):
        self.success_weight = success_weight
        self.quality_weight = quality_weight
        self.latency_weight = latency_weight
        self.cost_weight = cost_weight
        self.max_latency_ms = max_latency_ms
        self.max_cost = max_cost
    
    def score(
        self,
        tool: ToolProfile,
        context: Dict[str, Any],
        total_selections: int
    ) -> float:
        """Compute composite score."""
        # Success rate component
        success_score = tool.success_rate
        
        # Quality component
        quality_score = tool.avg_quality
        
        # Latency component (lower is better)
        latency_ratio = min(tool.avg_latency_ms / self.max_latency_ms, 1.0)
        latency_score = 1.0 - latency_ratio
        
        # Cost component (lower is better)
        cost_ratio = min(tool.avg_cost / self.max_cost, 1.0)
        cost_score = 1.0 - cost_ratio
        
        composite = (
            self.success_weight * success_score +
            self.quality_weight * quality_score +
            self.latency_weight * latency_score +
            self.cost_weight * cost_score
        )
        
        return composite


class ContextualScorer(ToolScorer):
    """Scores tools based on context matching."""
    
    def __init__(self, base_scorer: Optional[ToolScorer] = None):
        self.base_scorer = base_scorer or CompositeScorer()
        self.context_history: List[Tuple[Dict[str, Any], str, float]] = []
    
    def score(
        self,
        tool: ToolProfile,
        context: Dict[str, Any],
        total_selections: int
    ) -> float:
        """Score with context awareness."""
        base_score = self.base_scorer.score(tool, context, total_selections)
        
        # Context matching bonus
        context_bonus = self._compute_context_match(tool, context)
        
        # Capability matching
        required_caps = set(context.get("required_capabilities", []))
        if required_caps:
            cap_overlap = len(required_caps & tool.capabilities) / len(required_caps)
        else:
            cap_overlap = 1.0
        
        return base_score * 0.6 + context_bonus * 0.2 + cap_overlap * 0.2
    
    def _compute_context_match(self, tool: ToolProfile, context: Dict[str, Any]) -> float:
        """Compute context match score from history."""
        if not self.context_history:
            return 0.5
        
        # Find similar contexts in history
        current_features = self._extract_features(context)
        matches = []
        
        for hist_context, hist_tool, quality in self.context_history[-100:]:
            if hist_tool == tool.tool_id:
                hist_features = self._extract_features(hist_context)
                similarity = self._cosine_similarity(current_features, hist_features)
                if similarity > 0.5:
                    matches.append((similarity, quality))
        
        if not matches:
            return 0.5
        
        # Weighted average by similarity
        total_weight = sum(sim for sim, _ in matches)
        weighted_quality = sum(sim * qual for sim, qual in matches) / total_weight
        return weighted_quality
    
    def _extract_features(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Extract feature vector from context."""
        features: Dict[str, float] = {}
        
        # Task type features
        task_type = context.get("task_type", "")
        features[f"task_{task_type}"] = 1.0
        
        # Complexity features
        features["complexity"] = float(context.get("complexity", 0.5))
        
        # Input length features
        input_len = len(str(context.get("input", "")))
        features["input_length"] = min(input_len / 1000, 1.0)
        
        return features
    
    def _cosine_similarity(
        self,
        features1: Dict[str, float],
        features2: Dict[str, float]
    ) -> float:
        """Compute cosine similarity between feature vectors."""
        all_keys = set(features1.keys()) | set(features2.keys())
        
        dot_product = sum(
            features1.get(k, 0) * features2.get(k, 0)
            for k in all_keys
        )
        
        norm1 = math.sqrt(sum(v ** 2 for v in features1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in features2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def record_outcome(
        self,
        context: Dict[str, Any],
        tool_id: str,
        quality: float
    ):
        """Record outcome for future context matching."""
        self.context_history.append((context, tool_id, quality))


class ToolArbitrator:
    """
    Main tool arbitration system.
    
    Token optimization: Caches selection results for similar contexts.
    """
    
    def __init__(
        self,
        strategy: SelectionStrategy = SelectionStrategy.UCB,
        epsilon: float = 0.1,
        ucb_c: float = 2.0,
        cache_ttl_seconds: float = 60.0
    ):
        self.strategy = strategy
        self.epsilon = epsilon
        self.ucb_c = ucb_c
        self.cache_ttl = cache_ttl_seconds
        
        self.tools: Dict[str, ToolProfile] = {}
        self.invocation_log: List[ToolInvocation] = []
        self.total_selections = 0
        
        self.composite_scorer = CompositeScorer()
        self.contextual_scorer = ContextualScorer(self.composite_scorer)
        
        # Selection cache for repeated contexts
        self._selection_cache: Dict[str, Tuple[ToolRecommendation, float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def register_tool(self, tool: ToolProfile):
        """Register a tool for arbitration."""
        self.tools[tool.tool_id] = tool
    
    def get_tool(self, tool_id: str) -> Optional[ToolProfile]:
        """Get a registered tool by ID."""
        return self.tools.get(tool_id)
    
    def select_tool(
        self,
        context: Dict[str, Any],
        candidates: Optional[List[str]] = None,
        required_capabilities: Optional[Set[str]] = None,
        use_cache: bool = True
    ) -> ToolRecommendation:
        """
        Select the best tool for the given context.
        
        Token optimization: Caches deterministic selections.
        """
        # Check cache for deterministic strategies
        cache_key = None
        if use_cache and self.strategy in (SelectionStrategy.GREEDY, SelectionStrategy.UCB):
            cache_key = self._compute_cache_key(context, candidates, required_capabilities)
            cached = self._get_cached(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached
            self._cache_misses += 1
        
        self.total_selections += 1
        
        # Filter candidates
        if candidates:
            available = [self.tools[tid] for tid in candidates if tid in self.tools]
        else:
            available = list(self.tools.values())
        
        # Filter by required capabilities
        if required_capabilities:
            available = [
                t for t in available
                if required_capabilities <= t.capabilities
            ]
        
        if not available:
            raise ValueError("No suitable tools available")
        
        # Apply selection strategy
        if self.strategy == SelectionStrategy.GREEDY:
            selected = self._greedy_select(available, context)
        elif self.strategy == SelectionStrategy.EPSILON_GREEDY:
            selected = self._epsilon_greedy_select(available, context)
        elif self.strategy == SelectionStrategy.UCB:
            selected = self._ucb_select(available, context)
        elif self.strategy == SelectionStrategy.THOMPSON:
            selected = self._thompson_select(available)
        elif self.strategy == SelectionStrategy.CONTEXTUAL:
            selected = self._contextual_select(available, context)
        else:
            selected = self._greedy_select(available, context)
        
        # Build recommendation
        score = self.composite_scorer.score(selected, context, self.total_selections)
        alternatives = [
            t.tool_id for t in available
            if t.tool_id != selected.tool_id
        ][:3]
        
        recommendation = ToolRecommendation(
            tool_id=selected.tool_id,
            score=score,
            confidence=min(0.5 + selected.total_calls * 0.02, 0.95),
            rationale=self._generate_rationale(selected, context),
            expected_latency_ms=selected.avg_latency_ms,
            expected_cost=selected.avg_cost,
            alternative_tools=alternatives
        )
        
        # Cache the result for deterministic strategies
        if cache_key is not None:
            self._set_cached(cache_key, recommendation)
        
        return recommendation
    
    def _compute_cache_key(
        self,
        context: Dict[str, Any],
        candidates: Optional[List[str]],
        required_capabilities: Optional[Set[str]]
    ) -> str:
        """Compute cache key from selection parameters."""
        parts = [
            str(sorted(context.items())),
            str(sorted(candidates) if candidates else "all"),
            str(sorted(required_capabilities) if required_capabilities else "none")
        ]
        return hashlib.md5(":".join(parts).encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[ToolRecommendation]:
        """Get cached result if not expired."""
        if key not in self._selection_cache:
            return None
        result, timestamp = self._selection_cache[key]
        if time.time() - timestamp > self.cache_ttl:
            del self._selection_cache[key]
            return None
        return result
    
    def _set_cached(self, key: str, result: ToolRecommendation) -> None:
        """Cache a result with timestamp."""
        self._selection_cache[key] = (result, time.time())
    
    def clear_cache(self) -> None:
        """Clear selection cache."""
        self._selection_cache.clear()
    
    def cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics for monitoring."""
        total = self._cache_hits + self._cache_misses
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / max(1, total),
            "cache_size": len(self._selection_cache)
        }
    
    def _greedy_select(
        self,
        candidates: List[ToolProfile],
        context: Dict[str, Any]
    ) -> ToolProfile:
        """Greedy selection - always pick best."""
        return max(
            candidates,
            key=lambda t: self.composite_scorer.score(t, context, self.total_selections)
        )
    
    def _epsilon_greedy_select(
        self,
        candidates: List[ToolProfile],
        context: Dict[str, Any]
    ) -> ToolProfile:
        """Epsilon-greedy - explore with probability epsilon."""
        if random.random() < self.epsilon:
            return random.choice(candidates)
        return self._greedy_select(candidates, context)
    
    def _ucb_select(
        self,
        candidates: List[ToolProfile],
        context: Dict[str, Any]
    ) -> ToolProfile:
        """UCB selection - balance exploration/exploitation."""
        return max(
            candidates,
            key=lambda t: t.ucb_score(self.total_selections, self.ucb_c)
        )
    
    def _thompson_select(self, candidates: List[ToolProfile]) -> ToolProfile:
        """Thompson sampling - sample from posteriors."""
        return max(candidates, key=lambda t: t.sample_thompson())
    
    def _contextual_select(
        self,
        candidates: List[ToolProfile],
        context: Dict[str, Any]
    ) -> ToolProfile:
        """Contextual selection - use context matching."""
        return max(
            candidates,
            key=lambda t: self.contextual_scorer.score(t, context, self.total_selections)
        )
    
    def _generate_rationale(
        self,
        tool: ToolProfile,
        context: Dict[str, Any]
    ) -> str:
        """Generate human-readable rationale."""
        parts = [f"Selected {tool.name}"]
        
        if tool.total_calls > 0:
            parts.append(f"success rate: {tool.success_rate:.1%}")
            parts.append(f"avg latency: {tool.avg_latency_ms:.0f}ms")
        else:
            parts.append("exploring new tool")
        
        return " - ".join(parts)
    
    def record_invocation(
        self,
        tool_id: str,
        context: Dict[str, Any],
        inputs: Dict[str, Any],
        outputs: Any,
        success: bool,
        latency_ms: float,
        cost: float = 0.0,
        quality_score: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> ToolInvocation:
        """Record a tool invocation outcome."""
        invocation = ToolInvocation(
            invocation_id=f"inv_{len(self.invocation_log)}",
            tool_id=tool_id,
            context=context,
            inputs=inputs,
            outputs=outputs,
            success=success,
            latency_ms=latency_ms,
            cost=cost,
            quality_score=quality_score,
            error_message=error_message
        )
        
        self.invocation_log.append(invocation)
        
        # Update tool statistics
        tool = self.tools.get(tool_id)
        if tool:
            if success:
                tool.update_success(latency_ms, cost, quality_score or 1.0)
            else:
                tool.update_failure(latency_ms, cost)
            
            # Update contextual scorer
            if quality_score is not None:
                self.contextual_scorer.record_outcome(context, tool_id, quality_score)
        
        return invocation
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall arbitration statistics."""
        if not self.tools:
            return {"tools": 0, "invocations": 0}
        
        return {
            "tools": len(self.tools),
            "invocations": len(self.invocation_log),
            "total_selections": self.total_selections,
            "success_rate": (
                sum(t.success_count for t in self.tools.values()) /
                max(sum(t.total_calls for t in self.tools.values()), 1)
            ),
            "avg_latency_ms": (
                sum(t.total_latency_ms for t in self.tools.values()) /
                max(sum(t.total_calls for t in self.tools.values()), 1)
            ),
            "strategy": self.strategy.value
        }
    
    def get_tool_ranking(
        self,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, float]]:
        """Get ranked list of tools."""
        ctx = context or {}
        rankings = [
            (tool.tool_id, self.composite_scorer.score(tool, ctx, self.total_selections))
            for tool in self.tools.values()
        ]
        return sorted(rankings, key=lambda x: x[1], reverse=True)


class ToolChainPlanner:
    """Plans sequences of tool invocations."""
    
    def __init__(self, arbitrator: ToolArbitrator):
        self.arbitrator = arbitrator
        self.chain_history: List[List[str]] = []
    
    def plan_chain(
        self,
        goal: str,
        context: Dict[str, Any],
        max_steps: int = 5
    ) -> List[ToolRecommendation]:
        """Plan a chain of tool invocations."""
        chain: List[ToolRecommendation] = []
        current_context = context.copy()
        current_context["goal"] = goal
        
        for step in range(max_steps):
            # Determine required capabilities for this step
            required_caps = self._infer_required_capabilities(
                goal, current_context, step
            )
            
            try:
                recommendation = self.arbitrator.select_tool(
                    current_context,
                    required_capabilities=required_caps
                )
                chain.append(recommendation)
                
                # Update context for next step
                current_context["previous_tool"] = recommendation.tool_id
                current_context["step"] = step + 1
                
                # Check if goal achieved
                if self._goal_achieved(goal, chain):
                    break
            except ValueError:
                # No suitable tool found
                break
        
        return chain
    
    def _infer_required_capabilities(
        self,
        goal: str,
        context: Dict[str, Any],
        step: int
    ) -> Optional[Set[str]]:
        """Infer required capabilities for current step."""
        # This would be more sophisticated in practice
        goal_lower = goal.lower()
        
        if step == 0:
            if "retrieve" in goal_lower or "find" in goal_lower:
                return {"search", "retrieval"}
            if "calculate" in goal_lower or "compute" in goal_lower:
                return {"computation"}
            if "generate" in goal_lower or "write" in goal_lower:
                return {"generation"}
        
        return None
    
    def _goal_achieved(self, goal: str, chain: List[ToolRecommendation]) -> bool:
        """Check if goal is likely achieved."""
        # Simple heuristic - would be more sophisticated in practice
        return len(chain) >= 2 and chain[-1].confidence > 0.8


class AdaptiveToolSelector:
    """Adaptive tool selection with learning."""
    
    def __init__(self, arbitrator: ToolArbitrator):
        self.arbitrator = arbitrator
        self.learning_rate = 0.1
        self.feature_weights: Dict[str, float] = {}
    
    def select_and_learn(
        self,
        context: Dict[str, Any],
        feedback: Optional[float] = None
    ) -> ToolRecommendation:
        """Select tool and update weights based on feedback."""
        if feedback is not None:
            self._update_weights(context, feedback)
        
        return self.arbitrator.select_tool(context)
    
    def _update_weights(self, context: Dict[str, Any], feedback: float):
        """Update feature weights based on feedback."""
        # Simple gradient update
        for key, value in context.items():
            if isinstance(value, (int, float)):
                weight = self.feature_weights.get(key, 0.0)
                gradient = (feedback - 0.5) * value
                self.feature_weights[key] = weight + self.learning_rate * gradient


class ToolCostOptimizer:
    """Optimizes tool selection for cost efficiency."""
    
    def __init__(self, arbitrator: ToolArbitrator, budget: float = 1.0):
        self.arbitrator = arbitrator
        self.budget = budget
        self.spent = 0.0
    
    def select_within_budget(
        self,
        context: Dict[str, Any],
        min_quality: float = 0.5
    ) -> Optional[ToolRecommendation]:
        """Select tool within remaining budget."""
        remaining = self.budget - self.spent
        
        # Filter by cost and quality
        candidates = [
            t.tool_id for t in self.arbitrator.tools.values()
            if t.avg_cost <= remaining and t.avg_quality >= min_quality
        ]
        
        if not candidates:
            return None
        
        recommendation = self.arbitrator.select_tool(context, candidates=candidates)
        return recommendation
    
    def record_cost(self, cost: float):
        """Record spent cost."""
        self.spent += cost
    
    def get_remaining_budget(self) -> float:
        """Get remaining budget."""
        return self.budget - self.spent


# Factory functions
def create_tool_arbitrator(
    strategy: str = "ucb",
    epsilon: float = 0.1
) -> ToolArbitrator:
    """Create a tool arbitrator with specified strategy."""
    strategy_enum = SelectionStrategy(strategy)
    return ToolArbitrator(strategy=strategy_enum, epsilon=epsilon)


def create_tool_profile(
    tool_id: str,
    name: str,
    category: str,
    capabilities: Optional[List[str]] = None
) -> ToolProfile:
    """Create a tool profile."""
    return ToolProfile(
        tool_id=tool_id,
        name=name,
        category=ToolCategory(category),
        capabilities=set(capabilities or [])
    )
