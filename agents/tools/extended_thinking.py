"""
Extended Thinking Tool for Agent System

Provides chain-of-thought reasoning, multi-layer analysis, and consensus synthesis.
Optional reasoning modules (such as Watson Glaser critical thinking) can be embedded
to add specialized perspectives without changing the core workflow.
"""

from typing import Dict, List, Any, Optional, Callable


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
    
    def __init__(
        self,
        layers: int = 8,
        verbose: bool = False,
        logic_weight: float = 0.75,
        modules: Optional[List[str]] = None
    ):
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

        # Optional specialized reasoning modules
        self.available_modules = self._init_available_modules()
        self.enabled_modules: List[str] = []
        self.module_state: Dict[str, Dict[str, Any]] = {}

        for module_name in modules or []:
            self.enable_module(module_name)
    
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

    def _init_available_modules(self) -> Dict[str, Dict[str, Any]]:
        """Register optional reasoning modules that can augment the base tool."""
        return {
            "watson_glaser": {
                "name": "Watson Glaser Critical Thinking",
                "description": (
                    "Applies Watson Glaser style analysis of assumptions, deductions, "
                    "inferences, interpretations, and evaluation."
                ),
                "initializer": self._init_watson_glaser_state,
                "handler": self._apply_watson_glaser_module
            }
        }

    def enable_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Enable an optional reasoning module."""
        module = self.available_modules.get(module_name)
        if not module or module_name in self.module_state:
            return self.module_state.get(module_name)
        
        state_initializer: Callable[[], Dict[str, Any]] = module["initializer"]
        self.module_state[module_name] = state_initializer()
        self.enabled_modules.append(module_name)
        return self.module_state[module_name]
    
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
        step_number = 1
        
        # Step 1: Question Analysis
        analysis = self._analyze_question(query, context)
        thinking_chain.append({
            "step": step_number,
            "name": "Question Analysis",
            "content": analysis["summary"],
            "details": analysis
        })
        step_number += 1
        
        # Step 2: Key Concepts
        concepts = self._identify_key_concepts(query, context)
        thinking_chain.append({
            "step": step_number,
            "name": "Key Concepts",
            "content": f"Identified {len(concepts)} key concepts",
            "details": {"concepts": concepts}
        })
        step_number += 1
        
        # Step 3: Multi-Layer Analysis
        layer_analyses = self._multi_layer_analysis(query, context, depth)
        thinking_chain.append({
            "step": step_number,
            "name": "Multi-Layer Analysis",
            "content": f"Analyzed from {len(layer_analyses)} perspectives",
            "details": layer_analyses
        })
        step_number += 1
        
        # Step 4: Strategy Selection
        strategies = self._select_strategies(query, concepts)
        thinking_chain.append({
            "step": step_number,
            "name": "Strategy Selection",
            "content": f"Selected {len(strategies)} reasoning strategies",
            "details": strategies
        })
        step_number += 1

        # Embedded specialized modules (if any are enabled)
        module_outputs = self._apply_reasoning_modules(
            query=query,
            context=context,
            concepts=concepts,
            layer_analyses=layer_analyses
        )
        if module_outputs:
            thinking_chain.append({
                "step": step_number,
                "name": "Embedded Reasoning Modules",
                "content": f"Activated {len(module_outputs)} specialized modules",
                "details": module_outputs
            })
            step_number += 1
        
        # Step 5: Option Evaluation (if options provided)
        if options:
            evaluations = self._evaluate_options(options, query, context, strategies)
            thinking_chain.append({
                "step": step_number,
                "name": "Option Evaluation",
                "content": f"Evaluated {len(options)} options",
                "details": evaluations
            })
            step_number += 1
        
        # Step 6: Consensus Synthesis
        consensus = self._synthesize_consensus(
            layer_analyses,
            strategies,
            options if options else None
        )
        thinking_chain.append({
            "step": step_number,
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
            "meta_analysis": self._meta_analysis(thinking_chain),
            "modules": module_outputs
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

    def _analyze_query_confidence(self, query: str, context: Optional[str]) -> float:
        """
        Analyze query characteristics to determine confidence modulation factor.
        Returns a multiplier between 0.7 and 1.3.
        """
        text = f"{context or ''} {query}".lower()
        confidence_factor = 1.0

        # Clear logical structure increases confidence
        logic_indicators = ["all", "if", "then", "therefore", "because", "since"]
        logic_count = sum(1 for ind in logic_indicators if ind in text.split())
        if logic_count >= 2:
            confidence_factor += 0.15
        elif logic_count == 1:
            confidence_factor += 0.05

        # Specific domain terminology increases confidence
        specific_terms = ["engineer", "software", "data", "analysis", "research",
                         "study", "experiment", "test", "measure", "calculate"]
        if any(term in text for term in specific_terms):
            confidence_factor += 0.05

        # Vague or ambiguous language decreases confidence
        vague_terms = ["maybe", "might", "could", "possibly", "perhaps", "unclear"]
        if any(term in text for term in vague_terms):
            confidence_factor -= 0.1

        # Very short queries are less confident
        if len(query.split()) < 5:
            confidence_factor -= 0.1

        # Complex multi-part questions decrease confidence slightly
        if query.count("?") > 1 or len(query.split()) > 50:
            confidence_factor -= 0.05

        # Context availability increases confidence
        if context and len(context) > 20:
            confidence_factor += 0.1

        # Clip to reasonable range
        return max(0.7, min(1.3, confidence_factor))
    
    def _multi_layer_analysis(
        self,
        query: str,
        context: Optional[str],
        depth: int
    ) -> List[Dict[str, Any]]:
        """Analyze from multiple specialized perspectives."""
        analyses = []

        # Analyze query characteristics for confidence modulation
        query_confidence_factor = self._analyze_query_confidence(query, context)

        for layer_id in range(1, min(self.layers + 1, depth + 1)):
            spec = self.layer_specs.get(layer_id, {"name": f"Layer {layer_id}", "focus": "general"})

            # Base confidence increases with layer depth
            base_confidence = 0.6 + (layer_id * 0.05)

            # Modulate based on query characteristics
            layer_confidence = base_confidence * query_confidence_factor

            # Clip to valid range
            layer_confidence = max(0.3, min(0.95, layer_confidence))

            analysis = {
                "layer": layer_id,
                "name": spec["name"],
                "focus": spec["focus"],
                "perspective": self._layer_perspective(layer_id, query, context),
                "confidence": layer_confidence
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

    def _apply_reasoning_modules(
        self,
        query: str,
        context: Optional[str],
        concepts: List[str],
        layer_analyses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Invoke any enabled reasoning modules and capture their insights."""
        outputs = []
        if not self.enabled_modules:
            return outputs
        
        for module_name in self.enabled_modules:
            module = self.available_modules.get(module_name)
            state = self.module_state.get(module_name, {})
            if not module or not state:
                continue
            
            handler: Callable[[Dict[str, Any], str, Optional[str], List[str], List[Dict[str, Any]]], Optional[Dict[str, Any]]] = module["handler"]
            module_output = handler(state, query, context, concepts, layer_analyses)
            if module_output:
                module_output.setdefault("module", module["name"])
                module_output.setdefault("description", module["description"])
                outputs.append(module_output)
        
        return outputs

    def _init_watson_glaser_state(self) -> Dict[str, Any]:
        """Create default state for the embedded Watson Glaser module."""
        return {
            "cognitive_templates": {
                "assumptions": [
                    {"pattern": "implies", "weight": 0.8, "complexity": 1},
                    {"pattern": "presupposes", "weight": 0.85, "complexity": 2},
                    {"pattern": "takes for granted", "weight": 0.75, "complexity": 1}
                ],
                "inferences": [
                    {"pattern": "follows logically", "weight": 0.85, "complexity": 1},
                    {"pattern": "can be concluded", "weight": 0.8, "complexity": 1},
                    {"pattern": "suggests", "weight": 0.7, "complexity": 1}
                ],
                "deductions": [
                    {"pattern": "therefore", "weight": 0.82, "complexity": 2},
                    {"pattern": "must be", "weight": 0.78, "complexity": 2}
                ],
                "interpretations": [
                    {"pattern": "meaning", "weight": 0.7, "complexity": 1},
                    {"pattern": "indicates", "weight": 0.68, "complexity": 1}
                ],
                "evaluations": [
                    {"pattern": "evidence", "weight": 0.8, "complexity": 1},
                    {"pattern": "strength", "weight": 0.75, "complexity": 2}
                ]
            },
            "max_complexity": 1,
            "accuracy_history": [],
            "focus_history": []
        }

    def _apply_watson_glaser_module(
        self,
        state: Dict[str, Any],
        query: str,
        context: Optional[str],
        concepts: List[str],
        layer_analyses: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Apply Watson Glaser style reasoning as an embedded module."""
        text = f"{context or ''} {query}".lower()
        template_matches = self._match_cognitive_templates(text, state["cognitive_templates"])
        focus_area = (
            template_matches[0]["category"]
            if template_matches else
            (concepts[0] if concepts else "general_reasoning")
        )
        state["focus_history"].append(focus_area)
        
        logic_support = self._watson_glaser_logic_summary(layer_analyses)
        recommendations = self._watson_glaser_recommendations(focus_area, concepts)
        
        return {
            "summary": f"Focus on {focus_area.replace('_', ' ')} reasoning (complexity gate {state['max_complexity']}/4)",
            "focus_area": focus_area,
            "matched_templates": template_matches,
            "logic_support": logic_support,
            "recommendations": recommendations,
            "complexity_gate": state["max_complexity"]
        }

    def _match_cognitive_templates(
        self,
        text: str,
        templates: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Find which cognitive templates are triggered by the query."""
        matches = []
        for category, template_list in templates.items():
            category_matches = []
            for tmpl in template_list:
                if tmpl["pattern"] in text:
                    category_matches.append({"pattern": tmpl["pattern"], "weight": tmpl["weight"]})
            if category_matches:
                matches.append({"category": category, "matches": category_matches})
        return matches

    def _watson_glaser_logic_summary(
        self,
        layer_analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize how strongly logic-focused layers support the reasoning."""
        logic_layers = [layer for layer in layer_analyses if "logic" in layer.get("focus", "")]
        if not logic_layers:
            return {"layers": 0, "avg_confidence": 0.0}
        
        avg_conf = sum(layer["confidence"] for layer in logic_layers) / len(logic_layers)
        return {"layers": len(logic_layers), "avg_confidence": round(avg_conf, 3)}

    def _watson_glaser_recommendations(
        self,
        focus_area: str,
        concepts: List[str]
    ) -> List[str]:
        """Provide Watson Glaser style recommendations based on detected focus."""
        recommendations = []
        if focus_area == "assumptions":
            recommendations.append("Test whether any hidden assumptions undermine the conclusion.")
        elif focus_area == "inferences":
            recommendations.append("Check if the conclusion necessarily follows from the premises.")
        elif focus_area == "deductions":
            recommendations.append("Validate each deductive step for necessity and sufficiency.")
        elif focus_area == "interpretations":
            recommendations.append("Compare alternative interpretations of the evidence.")
        elif focus_area == "evaluations":
            recommendations.append("Assess the reliability and strength of the evidence sources.")
        
        if "evidence" in concepts:
            recommendations.append("Balance each claim against available evidence strength.")
        if "probability" in concepts:
            recommendations.append("Quantify likelihoods to avoid overconfidence.")
        
        if not recommendations:
            recommendations.append("Maintain balanced reasoning across the five Watson Glaser domains.")
        
        return recommendations
    
    def _evaluate_options(
        self,
        options: List[str],
        query: str,
        context: Optional[str],
        strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Evaluate each option using selected strategies."""
        evaluations = []
        query_lower = query.lower()

        for idx, option in enumerate(options):
            option_lower = option.lower()

            # Base confidence varies by option characteristics
            confidence = 0.5

            # Option-specific confidence modulation
            # Longer, more specific options tend to be more confident
            if len(option.split()) > 8:
                confidence += 0.1
            elif len(option.split()) < 3:
                confidence -= 0.05

            # Check if option contains key terms from query
            query_words = set(query_lower.split())
            option_words = set(option_lower.split())
            overlap = len(query_words & option_words)
            if overlap > 3:
                confidence += 0.15
            elif overlap > 1:
                confidence += 0.05

            # Absolute/definitive language
            definitive_terms = ["always", "never", "all", "none", "must", "impossible"]
            if any(term in option_lower for term in definitive_terms):
                confidence -= 0.1  # Usually too strong

            # Hedging language (often more accurate)
            hedge_terms = ["likely", "probably", "may", "might", "suggests"]
            if any(term in option_lower for term in hedge_terms):
                confidence += 0.05

            # Add some variance based on position (first option slight advantage)
            if idx == 0:
                confidence += 0.02

            # Apply strategies
            strategy_scores = []
            for strategy in strategies:
                score = confidence * strategy["score"]
                strategy_scores.append(score)

            avg_score = sum(strategy_scores) / len(strategy_scores)

            evaluations.append({
                "option_index": idx,
                "option": option,
                "confidence": min(0.95, max(0.2, avg_score)),
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

        # Depth bonus: More layers = more thorough analysis = higher confidence
        # Each additional layer beyond the first adds a small confidence boost
        depth_bonus = min(0.1, (len(layer_analyses) - 1) * 0.025)

        # Calculate weighted consensus (LOGIC PRIORITIZED)
        if logic_confidences:
            logic_avg = sum(logic_confidences) / len(logic_confidences)
            other_avg = sum(other_confidences) / len(other_confidences) if other_confidences else 0.5

            # Apply logic weight (default 0.75 = 75% logic, 25% other)
            avg_confidence = (logic_avg * self.logic_weight) + (other_avg * (1 - self.logic_weight))
        else:
            # Fallback if no logic layers
            avg_confidence = sum(l["confidence"] for l in layer_analyses) / len(layer_analyses)

        # Add depth bonus to base confidence
        avg_confidence = min(0.95, avg_confidence + depth_bonus)

        # Weight by strategy scores
        strategy_weight = sum(s["score"] for s in strategies) / len(strategies)

        # Overall consensus (still favor confidence over strategy)
        consensus_score = (avg_confidence * 0.7 + strategy_weight * 0.3)

        # Detect logical contradictions
        logic_agreement = self._check_logic_agreement(logic_confidences) if logic_confidences else 1.0

        # Reduce confidence if logic layers disagree
        if logic_agreement < 0.7:
            consensus_score *= 0.9  # 10% penalty for disagreement

        result = {
            "summary": f"Logic-weighted consensus: {consensus_score:.1%} (logic: {self.logic_weight:.0%})",
            "confidence": consensus_score,
            "layer_agreement": avg_confidence,
            "logic_agreement": logic_agreement,
            "logic_weight_applied": self.logic_weight,
            "num_logic_layers": len(logic_confidences),
            "num_other_layers": len(other_confidences),
            "strategy_strength": strategy_weight,
            "depth_bonus": depth_bonus
        }

        if options:
            # Use evaluation scores to pick the best option
            # This requires _evaluate_options to have been called first
            # For now, pick the first option but note this should be improved
            result["recommendation"] = options[0]
            result["recommendation_note"] = "Based on evaluation order - see Option Evaluation for scores"

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
    
    Integrates cognitive templates and curriculum learning as an embedded module.
    """
    
    def __init__(self, **kwargs):
        modules = kwargs.pop("modules", None)
        desired_modules = list(modules) if modules else []
        if "watson_glaser" not in desired_modules:
            desired_modules.append("watson_glaser")
        
        super().__init__(modules=desired_modules, **kwargs)
        self.name = "watson_glaser_thinking"
        self._sync_watson_glaser_attributes()
    
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
        state = self.module_state.get("watson_glaser")
        if not state:
            return None
        
        state["accuracy_history"].append(accuracy)
        updated = False
        message = None
        if accuracy >= 0.9 and state["max_complexity"] < 4:
            state["max_complexity"] = 4
            message = "🎓 Unlocked Complexity Level 4 (Expert)!"
            updated = True
        elif accuracy >= 0.8 and state["max_complexity"] < 3:
            state["max_complexity"] = 3
            message = "🎓 Unlocked Complexity Level 3 (Advanced)!"
            updated = True
        elif accuracy >= 0.7 and state["max_complexity"] < 2:
            state["max_complexity"] = 2
            message = "🎓 Unlocked Complexity Level 2 (Intermediate)!"
            updated = True
        
        if updated:
            self._sync_watson_glaser_attributes()
        return message

    def _sync_watson_glaser_attributes(self):
        """Expose module state on the tool instance for backward compatibility."""
        state = self.module_state.get("watson_glaser", {})
        self.cognitive_templates = state.get("cognitive_templates", {})
        self.max_complexity = state.get("max_complexity", 1)
        self.accuracy_history = state.get("accuracy_history", [])
