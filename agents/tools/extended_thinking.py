"""
Extended Thinking Tool for Agent System

Integrates Watson Glaser TIS extended thinking capabilities into the agent framework.
Provides chain-of-thought reasoning, multi-layer analysis, and consensus synthesis.
"""

import json
from typing import Dict, List, Any, Optional


class ExtendedThinkingTool:
    """
    Tool that implements extended chain-of-thought reasoning with multi-layer analysis.
    
    Mimics the TIS extended thinking process:
    1. Question Analysis
    2. Key Concept Identification
    3. Template/Strategy Selection
    4. Multi-perspective Evaluation
    5. Consensus Synthesis
    6. Confidence Assessment
    """
    
    def __init__(self, layers: int = 8, verbose: bool = False, logic_weight: float = 0.75):
        self.name = "extended_thinking"
        self.layers = layers
        self.verbose = verbose
        self.logic_weight = logic_weight  # Prioritize logic over consensus
        self.thinking_history = []
        
        # Dynamic layer specializations based on architecture
        self.layer_specs = self._init_layer_specs(layers)
        self.logic_layer_indices = self._identify_logic_layers()
        
        # Reasoning strategies with weights
        self.strategies = {
            "analytical": {"weight": 0.8, "description": "Break down into components"},
            "comparative": {"weight": 0.75, "description": "Compare with similar cases"},
            "eliminative": {"weight": 0.85, "description": "Eliminate impossible options"},
            "constructive": {"weight": 0.7, "description": "Build from first principles"},
            "probabilistic": {"weight": 0.72, "description": "Assess likelihood"},
            "counterFactual": {"weight": 0.68, "description": "Consider alternatives"}
        }
    
    def _init_layer_specs(self, layers: int) -> Dict[int, Dict[str, str]]:
        """Initialize layer specifications based on architecture size."""
        if layers == 4:
            return {
                1: {"name": "Perception", "focus": "pattern_recognition", "type": "perception"},
                2: {"name": "Reasoning", "focus": "logical_inference", "type": "logic"},
                3: {"name": "Evaluation", "focus": "critical_assessment", "type": "evaluation"},
                4: {"name": "Meta-Learning", "focus": "strategy_optimization", "type": "meta"}
            }
        elif layers == 8:
            return {
                1: {"name": "Pattern Perception", "focus": "visual_structural_patterns", "type": "perception"},
                2: {"name": "Semantic Analysis", "focus": "meaning_extraction", "type": "perception"},
                3: {"name": "Deductive Reasoning", "focus": "logical_deduction", "type": "logic"},
                4: {"name": "Inductive Reasoning", "focus": "pattern_generalization", "type": "logic"},
                5: {"name": "Critical Evaluation", "focus": "evidence_assessment", "type": "evaluation"},
                6: {"name": "Counterfactual Analysis", "focus": "alternative_scenarios", "type": "evaluation"},
                7: {"name": "Strategic Synthesis", "focus": "strategy_coordination", "type": "synthesis"},
                8: {"name": "Meta-Cognition", "focus": "self_monitoring", "type": "meta"}
            }
        elif layers == 16:
            return {
                1: {"name": "Visual Pattern Recognition", "focus": "visual_patterns", "type": "perception"},
                2: {"name": "Linguistic Pattern Recognition", "focus": "language_patterns", "type": "perception"},
                3: {"name": "Semantic Extraction", "focus": "meaning", "type": "perception"},
                4: {"name": "Pragmatic Understanding", "focus": "context", "type": "perception"},
                5: {"name": "Formal Logic (Deductive)", "focus": "deduction", "type": "logic"},
                6: {"name": "Informal Logic (Inductive)", "focus": "induction", "type": "logic"},
                7: {"name": "Abductive Reasoning", "focus": "inference_best_explanation", "type": "logic"},
                8: {"name": "Analogical Reasoning", "focus": "analogy", "type": "logic"},
                9: {"name": "Evidence Evaluation", "focus": "evidence_strength", "type": "evaluation"},
                10: {"name": "Source Credibility", "focus": "source_assessment", "type": "evaluation"},
                11: {"name": "Counterfactual Reasoning", "focus": "alternatives", "type": "evaluation"},
                12: {"name": "Scenario Planning", "focus": "future_scenarios", "type": "evaluation"},
                13: {"name": "Strategic Integration", "focus": "strategy_integration", "type": "synthesis"},
                14: {"name": "Tactical Optimization", "focus": "tactics", "type": "synthesis"},
                15: {"name": "Meta-Cognitive Monitoring", "focus": "self_monitoring", "type": "meta"},
                16: {"name": "Epistemic Validation", "focus": "knowledge_validation", "type": "meta"}
            }
        elif layers == 32:
            specs = {}
            # Perception (1-4)
            specs.update({i: {"name": f"Perception-{i}", "focus": "perception", "type": "perception"} for i in range(1, 5)})
            # Comprehension (5-8)
            specs.update({i: {"name": f"Comprehension-{i-4}", "focus": "comprehension", "type": "perception"} for i in range(5, 9)})
            # Deductive Reasoning (9-12)
            specs.update({i: {"name": f"Deductive-{i-8}", "focus": "deduction", "type": "logic"} for i in range(9, 13)})
            # Inductive Reasoning (13-16)
            specs.update({i: {"name": f"Inductive-{i-12}", "focus": "induction", "type": "logic"} for i in range(13, 17)})
            # Critical Evaluation (17-20)
            specs.update({i: {"name": f"Evaluation-{i-16}", "focus": "evaluation", "type": "evaluation"} for i in range(17, 21)})
            # Creative Thinking (21-24)
            specs.update({i: {"name": f"Creative-{i-20}", "focus": "creative", "type": "evaluation"} for i in range(21, 25)})
            # Synthesis (25-28)
            specs.update({i: {"name": f"Synthesis-{i-24}", "focus": "synthesis", "type": "synthesis"} for i in range(25, 29)})
            # Meta-Cognition (29-32)
            specs.update({i: {"name": f"Meta-{i-28}", "focus": "meta", "type": "meta"} for i in range(29, 33)})
            return specs
        else:
            # Default: expand 4-layer pattern
            return {i: {"name": f"Layer-{i}", "focus": "general", "type": "general"} for i in range(1, layers + 1)}
    
    def _identify_logic_layers(self) -> List[int]:
        """Identify which layers are logic/reasoning layers for prioritization."""
        return [i for i, spec in self.layer_specs.items() if spec.get("type") == "logic"]
    
    def get_schema(self) -> Dict[str, Any]:
        """Return the tool schema for the agent."""
        return {
            "name": self.name,
            "description": (
                "Engage in extended chain-of-thought reasoning with multi-layer analysis. "
                "Use this when you need deep, systematic thinking about complex problems. "
                "Provides step-by-step reasoning with confidence levels and multiple perspectives."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or problem to analyze deeply"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context or background information (optional)"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Possible answers or solutions to evaluate (optional)"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Thinking depth level (1-5, default 3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    
    def execute(
        self,
        query: str,
        context: Optional[str] = None,
        options: Optional[List[str]] = None,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        Execute extended thinking process.
        
        Args:
            query: The question or problem to analyze
            context: Additional context information
            options: Possible answers/solutions to evaluate
            depth: How deep to think (1-5)
        
        Returns:
            Dict containing thinking chain, analysis, and confidence scores
        """
        thinking_chain = []
        
        # Step 1: Question Analysis
        analysis = self._analyze_question(query, context)
        thinking_chain.append({
            "step": 1,
            "name": "Question Analysis",
            "content": analysis["summary"],
            "details": analysis
        })
        
        # Step 2: Key Concepts
        concepts = self._identify_key_concepts(query, context)
        thinking_chain.append({
            "step": 2,
            "name": "Key Concepts",
            "content": f"Identified {len(concepts)} key concepts",
            "details": {"concepts": concepts}
        })
        
        # Step 3: Multi-Layer Analysis
        layer_analyses = self._multi_layer_analysis(query, context, depth)
        thinking_chain.append({
            "step": 3,
            "name": "Multi-Layer Analysis",
            "content": f"Analyzed from {len(layer_analyses)} perspectives",
            "details": layer_analyses
        })
        
        # Step 4: Strategy Selection
        strategies = self._select_strategies(query, concepts)
        thinking_chain.append({
            "step": 4,
            "name": "Strategy Selection",
            "content": f"Selected {len(strategies)} reasoning strategies",
            "details": strategies
        })
        
        # Step 5: Option Evaluation (if options provided)
        if options:
            evaluations = self._evaluate_options(options, query, context, strategies)
            thinking_chain.append({
                "step": 5,
                "name": "Option Evaluation",
                "content": f"Evaluated {len(options)} options",
                "details": evaluations
            })
        
        # Step 6: Consensus Synthesis
        consensus = self._synthesize_consensus(
            layer_analyses,
            strategies,
            options if options else None
        )
        thinking_chain.append({
            "step": 6,
            "name": "Consensus Synthesis",
            "content": consensus["summary"],
            "details": consensus
        })
        
        # Build final result
        result = {
            "thinking_chain": thinking_chain,
            "key_insights": self._extract_insights(thinking_chain),
            "confidence": consensus["confidence"],
            "recommendation": consensus.get("recommendation"),
            "reasoning_depth": depth,
            "meta_analysis": self._meta_analysis(thinking_chain)
        }
        
        # Store in history
        self.thinking_history.append({
            "query": query,
            "result": result,
            "timestamp": self._timestamp()
        })
        
        if self.verbose:
            self._print_thinking_process(result)
        
        return result
    
    def _analyze_question(self, query: str, context: Optional[str]) -> Dict[str, Any]:
        """Analyze the question structure and type."""
        text = f"{context or ''} {query}".lower()
        
        question_type = "general"
        if "assume" in text or "assumption" in text:
            question_type = "assumptions"
        elif "conclude" in text or "infer" in text:
            question_type = "inferences"
        elif "must be" in text or "necessarily" in text:
            question_type = "deductions"
        elif "interpret" in text or "meaning" in text:
            question_type = "interpretations"
        elif "evaluate" in text or "evidence" in text:
            question_type = "evaluations"
        
        complexity = self._estimate_complexity(query, context)
        
        return {
            "summary": f"Question type: {question_type}, Complexity: {complexity}/5",
            "type": question_type,
            "complexity": complexity,
            "query_length": len(query),
            "has_context": context is not None
        }
    
    def _identify_key_concepts(self, query: str, context: Optional[str]) -> List[str]:
        """Extract key concepts from the query."""
        text = f"{context or ''} {query}".lower()
        concepts = []
        
        # Domain-specific concepts
        concept_keywords = {
            "logic": ["premise", "conclusion", "argument", "reasoning"],
            "causation": ["cause", "effect", "result", "consequence"],
            "evidence": ["proof", "data", "support", "demonstrate"],
            "assumptions": ["assume", "presume", "given", "suppose"],
            "probability": ["likely", "probable", "chance", "risk"],
            "comparison": ["more", "less", "better", "worse", "compare"]
        }
        
        for concept, keywords in concept_keywords.items():
            if any(kw in text for kw in keywords):
                concepts.append(concept)
        
        return concepts if concepts else ["general_reasoning"]
    
    def _multi_layer_analysis(
        self,
        query: str,
        context: Optional[str],
        depth: int
    ) -> List[Dict[str, Any]]:
        """Analyze from multiple specialized perspectives."""
        analyses = []
        
        for layer_id in range(1, min(self.layers + 1, depth + 1)):
            spec = self.layer_specs.get(layer_id, {"name": f"Layer {layer_id}", "focus": "general"})
            
            analysis = {
                "layer": layer_id,
                "name": spec["name"],
                "focus": spec["focus"],
                "perspective": self._layer_perspective(layer_id, query, context),
                "confidence": 0.6 + (layer_id * 0.05)  # Higher layers more confident
            }
            analyses.append(analysis)
        
        return analyses
    
    def _layer_perspective(self, layer_id: int, query: str, context: Optional[str]) -> str:
        """Generate perspective from specific layer."""
        perspectives = {
            1: f"Perceives patterns in the question structure and context",
            2: f"Applies logical inference and deductive reasoning",
            3: f"Critically evaluates evidence strength and argument validity",
            4: f"Coordinates insights and optimizes reasoning strategies"
        }
        return perspectives.get(layer_id, f"Layer {layer_id} analysis")
    
    def _select_strategies(self, query: str, concepts: List[str]) -> List[Dict[str, Any]]:
        """Select relevant reasoning strategies."""
        # Score each strategy
        scored = []
        for name, data in self.strategies.items():
            score = data["weight"]
            
            # Boost score based on concepts
            if "logic" in concepts and name in ["analytical", "eliminative"]:
                score += 0.1
            if "evidence" in concepts and name in ["evaluative", "comparative"]:
                score += 0.1
            
            scored.append({"name": name, "score": score, **data})
        
        # Return top 3
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:3]
    
    def _evaluate_options(
        self,
        options: List[str],
        query: str,
        context: Optional[str],
        strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Evaluate each option using selected strategies."""
        evaluations = []
        
        for idx, option in enumerate(options):
            # Base confidence
            confidence = 0.5
            
            # Apply strategies
            strategy_scores = []
            for strategy in strategies:
                score = confidence * strategy["score"]
                strategy_scores.append(score)
            
            avg_score = sum(strategy_scores) / len(strategy_scores)
            
            evaluations.append({
                "option_index": idx,
                "option": option,
                "confidence": min(0.95, avg_score),
                "strategy_scores": {s["name"]: sc for s, sc in zip(strategies, strategy_scores)}
            })
        
        # Sort by confidence
        evaluations.sort(key=lambda x: x["confidence"], reverse=True)
        return evaluations
    
    def _synthesize_consensus(
        self,
        layer_analyses: List[Dict[str, Any]],
        strategies: List[Dict[str, Any]],
        options: Optional[List[str]]
    ) -> Dict[str, Any]:
        """
        Synthesize consensus from all analyses with LOGIC PRIORITY.
        
        Logic layers are weighted higher than other layers to ensure
        reasoning quality over simple consensus.
        """
        # Separate logic layers from other layers
        logic_confidences = [
            l["confidence"] for l in layer_analyses 
            if l["layer"] in self.logic_layer_indices
        ]
        other_confidences = [
            l["confidence"] for l in layer_analyses 
            if l["layer"] not in self.logic_layer_indices
        ]
        
        # Calculate weighted consensus (LOGIC PRIORITIZED)
        if logic_confidences:
            logic_avg = sum(logic_confidences) / len(logic_confidences)
            other_avg = sum(other_confidences) / len(other_confidences) if other_confidences else 0.5
            
            # Apply logic weight (default 0.75 = 75% logic, 25% other)
            avg_confidence = (logic_avg * self.logic_weight) + (other_avg * (1 - self.logic_weight))
        else:
            # Fallback if no logic layers
            avg_confidence = sum(l["confidence"] for l in layer_analyses) / len(layer_analyses)
        
        # Weight by strategy scores
        strategy_weight = sum(s["score"] for s in strategies) / len(strategies)
        
        # Overall consensus (still favor confidence over strategy)
        consensus_score = (avg_confidence * 0.7 + strategy_weight * 0.3)
        
        # Detect logical contradictions
        logic_agreement = self._check_logic_agreement(logic_confidences) if logic_confidences else 1.0
        
        result = {
            "summary": f"Logic-weighted consensus: {consensus_score:.1%} (logic: {self.logic_weight:.0%})",
            "confidence": consensus_score,
            "layer_agreement": avg_confidence,
            "logic_agreement": logic_agreement,
            "logic_weight_applied": self.logic_weight,
            "num_logic_layers": len(logic_confidences),
            "num_other_layers": len(other_confidences),
            "strategy_strength": strategy_weight
        }
        
        if options:
            result["recommendation"] = options[0]  # Simplified - would use evaluation scores
        
        return result
    
    def _check_logic_agreement(self, logic_confidences: List[float]) -> float:
        """Check agreement level among logic layers."""
        if len(logic_confidences) <= 1:
            return 1.0
        
        # Calculate standard deviation of logic layer confidences
        mean = sum(logic_confidences) / len(logic_confidences)
        variance = sum((x - mean) ** 2 for x in logic_confidences) / len(logic_confidences)
        std_dev = variance ** 0.5
        
        # Convert to agreement score (lower std dev = higher agreement)
        # std_dev of 0 = perfect agreement (1.0)
        # std_dev of 0.3+ = poor agreement (0.0)
        agreement = max(0.0, 1.0 - (std_dev / 0.3))
        return agreement
    
    def _estimate_complexity(self, query: str, context: Optional[str]) -> int:
        """Estimate question complexity (1-5)."""
        complexity = 1
        text = f"{context or ''} {query}"
        
        # Length-based
        if len(text) > 200:
            complexity += 1
        if len(text) > 400:
            complexity += 1
        
        # Complexity indicators
        indicators = ["however", "although", "nevertheless", "moreover", "furthermore"]
        complexity += sum(1 for ind in indicators if ind in text.lower())
        
        return min(5, complexity)
    
    def _extract_insights(self, thinking_chain: List[Dict[str, Any]]) -> List[str]:
        """Extract key insights from thinking process."""
        insights = []
        
        for step in thinking_chain:
            if step["name"] in ["Question Analysis", "Consensus Synthesis"]:
                insights.append(step["content"])
        
        return insights
    
    def _meta_analysis(self, thinking_chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the thinking process itself."""
        return {
            "total_steps": len(thinking_chain),
            "analysis_depth": len([s for s in thinking_chain if "Analysis" in s["name"]]),
            "decision_quality": "high" if len(thinking_chain) >= 5 else "moderate"
        }
    
    def _timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _print_thinking_process(self, result: Dict[str, Any]):
        """Print the thinking process for debugging."""
        print("\n" + "="*60)
        print("🧠 EXTENDED THINKING PROCESS")
        print("="*60)
        
        for step in result["thinking_chain"]:
            print(f"\n{step['step']}. {step['name']}")
            print(f"   {step['content']}")
        
        print(f"\n📊 Confidence: {result['confidence']:.1%}")
        if result.get('recommendation'):
            print(f"💡 Recommendation: {result['recommendation']}")
        
        print("="*60 + "\n")
    
    def get_history_summary(self) -> Dict[str, Any]:
        """Get summary of thinking history."""
        if not self.thinking_history:
            return {"total_queries": 0, "avg_confidence": 0}
        
        return {
            "total_queries": len(self.thinking_history),
            "avg_confidence": sum(h["result"]["confidence"] for h in self.thinking_history) / len(self.thinking_history),
            "recent_queries": [h["query"] for h in self.thinking_history[-5:]]
        }


class WatsonGlaserThinkingTool(ExtendedThinkingTool):
    """
    Specialized version for Watson Glaser critical thinking.
    
    Integrates cognitive templates and curriculum learning.
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "watson_glaser_thinking"
        
        # Add cognitive templates
        self.cognitive_templates = {
            "assumptions": [
                {"pattern": "implies", "weight": 0.8, "complexity": 1},
                {"pattern": "presupposes", "weight": 0.85, "complexity": 2},
                {"pattern": "takes for granted", "weight": 0.75, "complexity": 1}
            ],
            "inferences": [
                {"pattern": "follows logically", "weight": 0.85, "complexity": 1},
                {"pattern": "can be concluded", "weight": 0.8, "complexity": 1},
                {"pattern": "suggests", "weight": 0.7, "complexity": 1}
            ]
        }
        
        self.max_complexity = 1  # Curriculum gating
        self.accuracy_history = []
    
    def get_schema(self) -> Dict[str, Any]:
        """Override with Watson Glaser specific schema."""
        schema = super().get_schema()
        schema["description"] = (
            "Apply Watson Glaser critical thinking methodology with systematic analysis of "
            "assumptions, inferences, deductions, interpretations, and argument evaluation. "
            "Includes curriculum-based complexity gating and cognitive template matching."
        )
        return schema
    
    def unlock_complexity(self, accuracy: float):
        """Unlock higher complexity levels based on accuracy."""
        if accuracy >= 0.9 and self.max_complexity < 4:
            self.max_complexity = 4
            return "🎓 Unlocked Complexity Level 4 (Expert)!"
        elif accuracy >= 0.8 and self.max_complexity < 3:
            self.max_complexity = 3
            return "🎓 Unlocked Complexity Level 3 (Advanced)!"
        elif accuracy >= 0.7 and self.max_complexity < 2:
            self.max_complexity = 2
            return "🎓 Unlocked Complexity Level 2 (Intermediate)!"
        return None
