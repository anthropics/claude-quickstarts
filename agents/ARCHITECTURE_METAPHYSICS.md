# ReasonableMind Architecture: Metaphysical Foundation

## Core Metaphor: Logic as Skeleton, AI as Muscles, User as Heart

This document defines the architectural principles that govern the ReasonableMind system, ensuring clear separation of responsibilities and preservation of user agency.

---

## 1. The Triadic Foundation

### 1.1 Logic (Skeleton)
**Role**: Defines what is valid

**Characteristics**:
- Immutable structural relationships
- Formal correctness checking
- Cannot be overridden by interpretation
- Provides the frame that cannot be broken

**Implementation Modules**:
```
logic_engine.py          - Propositional logic validation
categorical_engine.py    - Aristotelian syllogistic reasoning
inference_engine.py      - Formal inference patterns (modus ponens, etc.)
rule_engine.py          - Theorem proving, unification algorithm
fallacy_detector.py     - Pattern-based structural fallacy detection
```

**Key Principle**:
> Logic does not moralize. It determines validity, not truth or meaning.

**Test Validation**:
- All logic modules must return deterministic results for identical inputs
- Logic modules must not access user preferences or contextual values
- Logic modules must explicitly separate "valid" from "sound"

---

### 1.2 AI (Muscles)
**Role**: Moves within the frame, interprets, extends cognitive reach

**Characteristics**:
- Operates within logical constraints
- Provides multiple perspectives (Marx, Freud, Blackstone, etc.)
- Reformulates, critiques, synthesizes
- Extends reasoning capabilities
- Interpretive, not decisive

**Implementation Modules**:
```
debate_system.py              - Multi-agent adversarial reasoning
critic_system.py              - Self-critique with multiple lenses
semantic_parser.py            - Natural language interpretation
retrieval_augmentation.py     - Context expansion via RAG
retrieval_diversity.py        - Diverse perspective retrieval
multimodal_pipeline.py        - Cross-modal interpretation
reranker.py                   - Prioritization of interpretations
self_consistency.py           - Cross-checking interpretations
```

**Key Principle**:
> AI modules provide voices, not verdicts. They extend, not replace, reasoning.

**Profile System (Interpretive Forces)**:
- Marx: Class analysis, power dynamics
- Freud: Unconscious motivations, defense mechanisms
- Blackstone: Legal precedent, procedural correctness
- Each profile is a **lens**, not a judge

**Test Validation**:
- AI modules must provide confidence scores, not certainties
- AI modules must support multi-perspective output
- AI modules must never claim finality without user confirmation

---

### 1.3 User Agency (Heart)
**Role**: Determines purpose, values, meaning, final judgment

**Characteristics**:
- Sets the goal and context
- Selects which AI perspectives to weight
- Interprets outputs through personal values
- Makes irreducible final decisions
- Cannot be bypassed by system

**Implementation Modules**:
```
role_system.py            - User-selected reasoning profiles
clarification_system.py   - User intention clarification
feedback_system.py        - User corrections and preference learning
constraint_system.py      - User-defined boundaries and values
ui_hooks.py              - User interaction layer
calibration_system.py    - User-specific confidence calibration
```

**Key Principle**:
> The system serves user reasoning, it does not replace it.

**User Controls**:
1. **Profile Selection**: Which interpretive voices to activate
2. **Weighting**: How much to trust each perspective
3. **Constraint Setting**: What is out of bounds
4. **Final Interpretation**: What the output means for their context

**Test Validation**:
- User preferences must be persistently stored
- System must never auto-select final conclusions
- Clarification must be triggered for ambiguous user intent
- User must be able to override any system suggestion

---

### 1.4 Reason (The Emergent Output)
**Role**: Lived, contextual synthesis

**Characteristics**:
- Arises from interaction of skeleton, muscle, and heart
- Synthesizes:
  - What is valid (logic)
  - What is possible (AI perspectives)
  - What is meaningful (user values)
- Context-dependent
- Not a standalone module, but a process

**Implementation Modules**:
```
decision_model.py       - Weighted synthesis of evidence
planning_system.py      - Contextual action planning
evidence_system.py      - Evidence-based reasoning
uncertainty_system.py   - Calibrated confidence
curriculum_system.py    - Adaptive difficulty (reason improves)
```

**Key Principle**:
> Reason is not discovered, it is made—through the disciplined interaction of logic, AI interpretation, and user judgment.

**Test Validation**:
- Synthesis modules must incorporate all three layers
- Outputs must trace back to: logic rules + AI perspectives + user preferences
- Confidence must degrade gracefully when layers conflict

---

## 2. Architectural Invariants

### 2.1 Separation of Concerns

| Layer | Decides | Does NOT Decide |
|-------|---------|-----------------|
| **Logic** | Validity, structural correctness | Truth, meaning, value |
| **AI** | Possible interpretations | Which interpretation is right |
| **User** | Purpose, final judgment | What is logically valid |

### 2.2 Dependency Rules

**Allowed Dependencies**:
```
Logic → (standalone, no dependencies on AI or User)
AI → Logic (can use logical validation)
User → Logic + AI (can use both)
Reason → Logic + AI + User (synthesis layer)
```

**Forbidden Dependencies**:
```
Logic → AI ❌
Logic → User ❌
AI → User ❌ (observes, does not control)
```

### 2.3 Override Hierarchy

```
User > AI > Logic (when there's flexibility)
Logic > AI > User (when there's formal necessity)
```

**Example 1** (Flexibility):
- Logic says: "This syllogism is valid"
- AI says: "But consider Marx's view: class interests bias the premise"
- User says: "I accept the Marxist critique, reject conclusion despite validity"
- **Result**: User decision prevails (validity ≠ soundness)

**Example 2** (Formal Necessity):
- User says: "I want to conclude X from Y"
- Logic says: "X does not follow from Y (invalid inference)"
- AI says: "Under charitable interpretation, maybe..."
- **Result**: Logic blocks the inference (preserves structural integrity)

---

## 3. Implementation Guidelines

### 3.1 Logic Layer (Skeleton)

**Design Principles**:
1. Pure functions where possible
2. Deterministic outputs
3. Zero interpretation
4. Explicit error messages for invalid structures

**Example**:
```python
# logic_engine.py
def validate_modus_ponens(premises: List[str], conclusion: str) -> LogicResult:
    """
    Validates modus ponens: P, P→Q ⊢ Q

    Returns ONLY structural validity, not truth or soundness.
    """
    parsed = parse_premises(premises)

    # Check structure
    if has_conditional(parsed) and has_antecedent(parsed):
        return LogicResult(valid=True, form=ArgumentForm.MODUS_PONENS)

    return LogicResult(valid=False, reason="Structure does not match MP")
```

**Forbidden**:
```python
# ❌ BAD: Logic moralizing
def validate_argument(arg):
    if is_valid(arg):
        if is_about_controversial_topic(arg):  # ❌ No!
            return "Valid but problematic"
```

---

### 3.2 AI Layer (Muscles)

**Design Principles**:
1. Multiple perspectives by default
2. Confidence scores, not certainties
3. Explicit attribution (which profile generated this?)
4. Transparent reasoning chains

**Example**:
```python
# debate_system.py
def multi_perspective_analysis(query: str, profiles: List[Profile]) -> Debate:
    """
    Analyzes query through multiple intellectual traditions.

    Returns interpretations, NOT a singular truth.
    """
    perspectives = []

    for profile in profiles:
        interpretation = profile.interpret(query)
        perspectives.append({
            "profile": profile.name,  # "Marx", "Freud", etc.
            "interpretation": interpretation,
            "confidence": profile.confidence,
            "reasoning": profile.explain()
        })

    return Debate(
        perspectives=perspectives,
        consensus=None,  # User decides, not system
        requires_user_weighting=True
    )
```

**Forbidden**:
```python
# ❌ BAD: AI deciding for user
def analyze(query):
    perspectives = get_perspectives(query)
    best = max(perspectives, key=lambda p: p.confidence)
    return best.interpretation  # ❌ No! User must choose
```

---

### 3.3 User Layer (Heart)

**Design Principles**:
1. Explicit user intent capture
2. Preference persistence
3. Clarification before assumption
4. Final decision always user's

**Example**:
```python
# role_system.py
def select_reasoning_profiles(user_id: str, task: str) -> List[Profile]:
    """
    Allows user to select which intellectual traditions to apply.

    System MAY suggest, but user MUST confirm.
    """
    user_prefs = load_user_preferences(user_id)
    suggested = suggest_profiles_for_task(task, user_prefs)

    # Ask user to confirm/modify
    selected = prompt_user(
        f"Suggested profiles: {suggested}. Accept or customize?",
        allow_modification=True
    )

    return selected
```

**Example - Clarification**:
```python
# clarification_system.py
def detect_ambiguity(query: str) -> Optional[ClarificationRequest]:
    """
    Detects when user intent is unclear.

    NEVER guesses—always asks.
    """
    if is_ambiguous(query):
        return ClarificationRequest(
            question="Did you mean X or Y?",
            options=["X", "Y"],
            allow_free_text=True
        )

    return None
```

---

### 3.4 Reason Layer (Synthesis)

**Design Principles**:
1. Trace provenance: logic + AI + user
2. Graceful degradation under conflict
3. Explicit confidence calibration
4. Explanation of synthesis

**Example**:
```python
# decision_model.py
def synthesize_decision(
    logical_validation: LogicResult,
    ai_perspectives: List[Perspective],
    user_preferences: UserContext
) -> Decision:
    """
    Synthesizes skeleton + muscles + heart into reasoned output.

    All three layers must contribute.
    """
    # Check logical validity (skeleton)
    if not logical_validation.valid:
        return Decision(
            recommendation=None,
            reason="Logically invalid structure",
            confidence=0.0,
            requires_reformulation=True
        )

    # Weight AI perspectives by user preferences (muscles + heart)
    weighted_perspectives = []
    for p in ai_perspectives:
        weight = user_preferences.get_weight(p.profile)
        weighted_perspectives.append((p, weight))

    # Synthesize
    synthesis = combine(weighted_perspectives)

    return Decision(
        recommendation=synthesis.conclusion,
        confidence=synthesis.confidence,
        provenance={
            "logic": logical_validation,
            "ai_perspectives": ai_perspectives,
            "user_weights": user_preferences.weights
        },
        explanation=generate_explanation(synthesis)
    )
```

---

## 4. Testing the Metaphysics

### 4.1 Unit Tests (Layer Isolation)

**Logic Layer Tests** (`test_logic_*.py`):
```python
def test_logic_deterministic():
    """Logic must be deterministic."""
    result1 = engine.validate(premises, conclusion)
    result2 = engine.validate(premises, conclusion)
    assert result1 == result2

def test_logic_no_context_dependency():
    """Logic must not depend on context."""
    # Same input, different user contexts
    result_user_a = engine.validate(arg, context=user_a)
    result_user_b = engine.validate(arg, context=user_b)
    assert result_user_a == result_user_b  # Logic is universal
```

**AI Layer Tests** (`test_debate_*.py`, `test_critic_*.py`):
```python
def test_ai_multiple_perspectives():
    """AI must provide multiple perspectives, not singular truth."""
    result = debate_system.analyze(query, profiles=[marx, freud])
    assert len(result.perspectives) >= 2
    assert result.consensus is None  # No auto-consensus

def test_ai_confidence_not_certainty():
    """AI must express uncertainty."""
    result = critic.review(reasoning)
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence < 1.0 or result.is_tautology
```

**User Layer Tests** (`test_role_*.py`, `test_clarification_*.py`):
```python
def test_user_can_override_ai():
    """User preference must override AI suggestion."""
    ai_suggestion = "Interpret as X"
    user_override = "No, interpret as Y"

    result = apply_user_override(ai_suggestion, user_override)
    assert result == user_override

def test_clarification_required_for_ambiguity():
    """System must ask, not guess."""
    ambiguous_query = "What about banks?"  # River banks? Financial?

    result = process_query(ambiguous_query)
    assert result.requires_clarification
    assert result.clarification_question is not None
```

### 4.2 Integration Tests (Layer Interaction)

**Synthesis Tests** (`test_decision_model.py`):
```python
def test_synthesis_traces_provenance():
    """Synthesis must trace back to all three layers."""
    decision = synthesize(logic_result, ai_perspectives, user_prefs)

    assert "logic" in decision.provenance
    assert "ai_perspectives" in decision.provenance
    assert "user_weights" in decision.provenance

def test_logic_blocks_invalid_synthesis():
    """Logic must block invalid inferences, even if AI/user prefer."""
    invalid_logic = LogicResult(valid=False)
    ai_says_ok = [Perspective(confidence=0.9, says="It's fine")]
    user_wants_it = UserContext(override=True)

    decision = synthesize(invalid_logic, ai_says_ok, user_wants_it)

    # Logic wins: invalid structure cannot be synthesized
    assert decision.recommendation is None
    assert "invalid" in decision.reason.lower()
```

---

## 5. API Design Patterns

### 5.1 Logic Layer API

```python
@dataclass
class LogicResult:
    valid: bool  # Structural validity
    form: Optional[ArgumentForm]
    confidence: float = 1.0  # Logic is certain about structure
    explanation: str = ""

    # No fields for: "is_true", "is_good", "user_should_believe"
```

### 5.2 AI Layer API

```python
@dataclass
class Perspective:
    profile: str  # "Marx", "Freud", "Blackstone"
    interpretation: str
    confidence: float  # 0.0-1.0, rarely 1.0
    reasoning: str  # Explain how this perspective was derived
    alternatives: List[str]  # Other possible interpretations

    # No field for: "is_correct"
```

### 5.3 User Layer API

```python
@dataclass
class UserContext:
    user_id: str
    preferences: Dict[str, float]  # Profile weights
    constraints: List[Constraint]  # User-defined boundaries
    history: List[Interaction]  # Learn from past

    def get_weight(self, profile: str) -> float:
        """How much user trusts this profile."""
        return self.preferences.get(profile, 0.5)
```

### 5.4 Synthesis Layer API

```python
@dataclass
class Decision:
    recommendation: Optional[str]  # May be None if blocked
    confidence: float
    provenance: Dict[str, Any]  # Trace to all layers
    explanation: str  # Human-readable synthesis
    requires_user_approval: bool  # High-stakes decisions

    def to_user_facing_output(self) -> str:
        """Format for user consumption."""
        return f"""
        Recommendation: {self.recommendation}
        Confidence: {self.confidence:.0%}

        Based on:
        - Logical structure: {self.provenance['logic'].form}
        - AI perspectives: {len(self.provenance['ai_perspectives'])} views
        - Your preferences: {self.provenance['user_weights']}

        {self.explanation}

        {"[Requires your approval]" if self.requires_user_approval else ""}
        """
```

---

## 6. Validation Checklist

For every new module or feature, verify:

### ✅ Logic Layer (Skeleton)
- [ ] Returns deterministic results
- [ ] No dependency on user context or AI interpretation
- [ ] Explicitly separates validity from soundness
- [ ] No moral or value judgments
- [ ] Test coverage for edge cases

### ✅ AI Layer (Muscles)
- [ ] Provides multiple perspectives (not singular)
- [ ] Includes confidence scores < 1.0
- [ ] Attributes interpretations to profiles/sources
- [ ] Does not auto-select "best" interpretation
- [ ] Test coverage for diverse profiles

### ✅ User Layer (Heart)
- [ ] Captures user intent explicitly
- [ ] Asks for clarification when ambiguous
- [ ] Persists user preferences
- [ ] Allows user override of system suggestions
- [ ] Test coverage for user interactions

### ✅ Synthesis Layer (Reason)
- [ ] Incorporates all three layers
- [ ] Traces provenance clearly
- [ ] Degrades gracefully under conflict
- [ ] Provides human-readable explanations
- [ ] Test coverage for integration scenarios

---

## 7. Anti-Patterns to Avoid

### ❌ Logic Moralizing
```python
# BAD
def validate_argument(arg):
    if "controversial" in arg:
        return LogicResult(valid=False, reason="Problematic content")
```

### ❌ AI Deciding
```python
# BAD
def get_best_perspective(perspectives):
    return max(perspectives, key=lambda p: p.confidence)
```

### ❌ System Bypassing User
```python
# BAD
def auto_apply_suggestion(suggestion):
    execute(suggestion)  # No user confirmation!
```

### ❌ Opaque Synthesis
```python
# BAD
def decide(args):
    return "Do X"  # Where did this come from?
```

---

## 8. Future Extensions

### 8.1 Profile Expansion
New interpretive lenses can be added as AI "muscles" without touching logic or user layers:
- Kant: Categorical imperative, universalizability
- Rawls: Veil of ignorance, justice as fairness
- Wittgenstein: Language games, meaning-in-use
- Foucault: Power-knowledge, discourse analysis

### 8.2 Logic Extensions
New formal systems can be added to the skeleton:
- Modal logic (necessity, possibility)
- Temporal logic (before, after, always)
- Deontic logic (obligation, permission)
- Fuzzy logic (degrees of truth)

### 8.3 User Modeling
Heart layer can become more sophisticated:
- Implicit preference learning
- Context-aware weighting
- Collaborative filtering (users with similar profiles)
- Explainable preference extraction

---

## Conclusion

This architecture ensures:

1. **Logic provides structure** - Validity without overreach
2. **AI provides voices** - Perspectives without verdicts
3. **Users provide meaning** - Purpose without abandonment
4. **Reason emerges** - From disciplined interaction, not isolated calculation

The system is a **reasoning tool**, not a **reasoning replacement**.

**Architectural Motto**:
> "The skeleton constrains. The muscles extend. The heart decides. Reason emerges."

---

**Document Status**: Living Architecture Document
**Last Updated**: December 5, 2025
**Maintainers**: ReasonableMind Development Team
**Review Cycle**: Quarterly
