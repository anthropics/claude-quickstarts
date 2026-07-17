# Neuro-Symbolic Architecture for Agent Systems

## Executive Summary

This architecture implements a hybrid AI system that combines:
- **Backend**: Machine learning (LLM agents with extended thinking)
- **Frontend**: Formal logic (symbolic reasoning with knowledge base)

The key innovation is **rigorous integration** that addresses fundamental challenges in neuro-symbolic AI rather than naive pattern matching.

## Core Challenges Addressed

### 1. The Symbol Grounding Problem

**Problem**: How does natural language map to logical forms while preserving meaning?

**Our Solution**:
```python
# Context-dependent semantic interpretation
ml_context = SemanticContext(
    domain="machine_learning",
    predicates={
        "biased": "exhibits statistical correlation with protected attributes"
    },
    grounding_rules={...}
)

parser = SemanticParser(ml_context)
result = parser.parse("All ML models trained on biased data produce biased outputs")

# Result includes:
# - Logical form: ∀x(BiasedTraining(x) → BiasedOutput(x))
# - Assumptions made during parsing
# - Unparseable fragments
# - Confidence in the parse
```

**Key Features**:
- ✅ Context determines meaning (biased_ML ≠ biased_cognitive)
- ✅ Explicit grounding rules
- ✅ Tracks what can't be formalized
- ✅ Makes assumptions explicit

### 2. Epistemic Status vs. Logical Validity

**Problem**: A single "confidence" score conflates:
- Structural validity (is the argument form correct?)
- Soundness (are the premises actually true?)

**Our Solution**:
```python
status = ValidityChecker.check_modus_ponens(
    "If Socrates is a fish, then Socrates can swim",
    "Socrates is a fish",
    "Socrates can swim"
)

# Returns:
# - validity: VALID (structure is correct)
# - validity_confidence: 0.95
# - soundness: UNSOUND (premises are false)
# - overall_confidence: 0.0 (can't rely on conclusion)
```

**Key Features**:
- ✅ Separate validity and soundness tracking
- ✅ Valid ≠ believable (Socrates is a fish)
- ✅ Invalid ≠ unbelievable (affirming consequent)
- ✅ Multi-dimensional confidence

### 3. Inference Rule Selection & Validation

**Problem**: LLMs pattern-match on training data, they don't actually perform modus ponens. Labeling their outputs with logic terms is post-hoc rationalization unless validated.

**Our Solution**:
```python
# Independent validation (doesn't trust LLM self-labeling)
fallacy = ConfidenceCalculator.detect_fallacy(
    premises=["Tech companies are successful", "Google is a tech company"],
    conclusion="Google is successful",
    claimed_rule="modus_ponens"  # What the LLM claims
)

# Returns: "affirming_the_consequent"
# Reason: Missing universal quantifier ("ALL tech companies")
```

**Key Features**:
- ✅ Fallacy detection independent of LLM
- ✅ Checks for missing quantifiers
- ✅ Validates argument structure formally
- ✅ Doesn't trust LLM to label its own reasoning

### 4. Confidence Propagation

**Problem**: If I chain 10 steps each at 0.9 confidence, what's the final confidence?

**Our Solution**:
```python
breakdown = ConfidenceCalculator.multi_step_chain(
    premise_confidences=[0.7, 0.6],
    rule_confidences=[0.9],
    rule_types=["universal_instantiation"]
)

# Returns detailed breakdown:
# - logical_confidence: 0.9 (argument structure)
# - source_confidence: 0.42 (premise reliability)
# - propagation_method: "sequential_product"
# - chain_length: 1

# For 10 steps at 0.9 each: 0.9^10 = 0.35 (35%)
```

**Key Features**:
- ✅ Explicit propagation rules (product, complement)
- ✅ Separates logical, empirical, source confidence
- ✅ Chain length effects are visible
- ✅ No mysterious black-box scores

### 5. Quantification Types

**Problem**: "All", "most", "some", and generic plurals have different logical structures, and some can't be expressed in first-order logic.

**Our Solution**:
```python
cases = [
    "All birds can fly",   # ∀x(Bird(x) → Fly(x))
    "Some birds can fly",  # ∃x(Bird(x) ∧ Fly(x))
    "Birds fly",           # Gen x(Bird(x) → Fly(x)) - generic
    "Most birds can fly",  # UNPARSEABLE in FOL
]

for statement in cases:
    result = parser.parse(statement)
    # Returns success/failure with unparseable fragments
```

**Key Features**:
- ✅ Distinguishes ∀, ∃, generic, most
- ✅ Reports what can't be formalized
- ✅ Suggests required logic system
- ✅ Graceful degradation

### 6. Modality Detection

**Problem**: Beliefs, obligations, causation require specialized logics beyond first-order.

**Our Solution**:
```python
modality_cases = [
    ("John believes Mary is happy", ModalityType.EPISTEMIC),
    ("You should help others", ModalityType.DEONTIC),
    ("Water boiled because it was heated", ModalityType.CAUSAL),
]

# Parser detects modality and reports:
# "Requires epistemic logic (K_john(Happy(mary)))"
```

**Key Features**:
- ✅ Detects epistemic (believes, knows)
- ✅ Detects deontic (should, must, permitted)
- ✅ Detects causal (because, causes)
- ✅ Reports which specialized logic is needed

## Architecture Layers

### Layer 1: Symbol Grounding (`logic/grounding.py`)

```
Natural Language → Semantic Parser → Logical Form
                         ↓
                 Grounding Context
                  (domain-specific
                   predicate definitions)
```

**Components**:
- `SemanticContext`: Domain-specific predicate definitions
- `SemanticParser`: Robust parsing with assumption tracking
- `ParseResult`: Success/failure with unparseable fragments

### Layer 2: Epistemic Tracking (`logic/epistemic.py`)

```
Argument → Validity Checker → Epistemic Status
                                (validity + soundness)
           ↓
    Confidence Calculator
    (explicit propagation)
```

**Components**:
- `EpistemicStatus`: Separates validity from soundness
- `ConfidenceCalculator`: Explicit propagation rules
- `ValidityChecker`: Formal validation independent of LLM

### Layer 3: Knowledge Base (`logic/knowledge_base.py`)

```
Facts + Rules → Inference Engine → Validated Claims
                       ↓
                 Forward Chaining
                 (logical derivation)
```

**Components**:
- `KnowledgeBase`: Stores facts with provenance
- `InferenceRule`: Modus ponens, universal instantiation, etc.
- `ValidationResult`: Evidence chain for claims

### Layer 4: Reasoning Agent (`logic/reasoning_agent.py`)

```
Query → Decomposition → Reasoning Steps → Formal Argument
                             ↓
                    Knowledge Validation
                         ↓
                  Combined Result
              (ML reasoning + Logic proof)
```

**Components**:
- `ReasoningAgent`: Orchestrates neuro-symbolic reasoning
- `ArgumentBuilder`: Constructs formal arguments from ML
- `FormalArgument`: Complete logical proof

## Integration with Agent Framework

### Standalone Logic System

```python
from logic import ReasoningAgent, LogicType

agent = ReasoningAgent(
    name="Logic Agent",
    logic_framework=LogicType.FIRST_ORDER,
    reasoning_depth=3
)

agent.add_knowledge("All software engineers write code")
agent.add_knowledge("Alice is a software engineer")

result = agent.reason("What can we conclude about Alice?")
# Returns both natural language and formal logic
```

### Full Integration with Claude Agent

```python
from agent import Agent, ModelConfig
from tools.extended_thinking import ExtendedThinkingTool
from logic import ReasoningAgent, LogicType

# Create logic backend
logic_agent = ReasoningAgent(...)

# Create ML backend
extended_thinking = ExtendedThinkingTool(layers=8)

# Bridge the two
logic_tool = LogicTool(logic_agent, extended_thinking)

# Create Claude agent
agent = Agent(
    name="Neuro-Symbolic Reasoner",
    system="You combine neural reasoning with formal logic",
    tools=[logic_tool],
    config=ModelConfig()
)

# Query returns both ML reasoning AND formal proof
response = agent.run("Does GPT-4 produce biased outputs?")
```

## Comparison: Naive vs. Rigorous

### Naive Pattern Matching

```python
def parse_to_logic(statement):
    if "all" in statement and "are" in statement:
        parts = statement.split("are")
        return f"∀x({parts[0]}(x) → {parts[1]}(x))"
    return statement  # Give up

# Problems:
# - No context (what does "biased" mean?)
# - No quantifier distinction (all vs. most vs. generic)
# - No assumption tracking
# - No unparseable fragment handling
# - Single confidence score
```

### Rigorous Approach

```python
context = create_ml_context()  # Domain-specific grounding
parser = SemanticParser(context)
result = parser.parse(statement)

# Returns:
# - success: bool
# - logical_form: str (if parseable)
# - quantifier: QuantifierType
# - modality: ModalityType (if detected)
# - unparseable_fragments: List[str]
# - assumptions: List[str]
# - confidence: float (in the parse)

# Then separate validation:
status = ValidityChecker.check_argument(...)
# - validity: ValidityStatus
# - soundness: SoundnessStatus
# - premise_confidences: List[float]
```

## Usage Examples

### Example 1: Basic Reasoning

```python
agent = ReasoningAgent(...)
agent.add_knowledge("All humans are mortal")
agent.add_knowledge("Socrates is human")

result = agent.reason("Is Socrates mortal?")

print(result["formal_conclusion"])
# → Mortal(Socrates)

print(result["confidence"])
# → 0.85 (with breakdown of how calculated)

print(result["knowledge_validation"])
# → Valid: True, Sources: ["domain_knowledge"]
```

### Example 2: Fallacy Detection

```python
premises = [
    "Tech companies are successful",
    "Google is a tech company"
]

fallacy = ConfidenceCalculator.detect_fallacy(
    premises,
    "Google is successful",
    "modus_ponens"
)

# Returns: "affirming_the_consequent"
# Explanation: Missing "ALL tech companies"
```

### Example 3: Unparseable Fragments

```python
result = parser.parse("Most birds can fly")

# result.success = False
# result.unparseable_fragments = [
#     "Quantifier 'most' requires higher-order logic"
# ]
# result.suggestions = [
#     "Consider probabilistic logic or fuzzy logic"
# ]
```

## Benefits

### For ML-Powered Systems

1. **Transparency**: Every reasoning step is traceable
2. **Validation**: Independent checking of LLM outputs
3. **Error Detection**: Catches fallacies and invalid logic
4. **Explainability**: Formal proofs supplement neural reasoning

### For Logic-Based Systems

1. **Flexibility**: ML handles ambiguity and noise
2. **Learning**: Improves with data, not just rules
3. **Generalization**: Handles cases not in knowledge base
4. **Natural Language**: No manual formalization needed

### Combined

1. **Reliability**: Logic validates ML, ML extends logic
2. **Auditability**: Complete reasoning trace
3. **Confidence**: Multi-dimensional, explicit calculation
4. **Robustness**: Graceful degradation when formalization fails

## Limitations & Future Work

### Current Limitations

1. **Parsing**: Pattern-based, not full NLP
2. **Logic**: First-order only (no higher-order, probabilistic)
3. **Inference**: Forward chaining only (no resolution, tableaux)
4. **Validation**: Simple fallacy detection (not exhaustive)

### Planned Enhancements

1. **NLP Integration**: Dependency parsing, semantic roles
2. **Advanced Logic**: Higher-order, probabilistic, temporal
3. **Theorem Proving**: Coq, Lean, Isabelle integration
4. **Contradiction Handling**: Paraconsistent logic support
5. **Ground Truth**: External knowledge base integration

## Demonstrations

Run these to see the system in action:

```bash
# Standalone logic system
python neuro_symbolic_demo.py

# Full integration with Agent
python neuro_symbolic_integration.py

# Rigorous features (addresses all challenges)
python rigorous_logic_demo.py

# Jupyter notebook with examples
jupyter notebook rigorous_logic_integration.ipynb
```

## References

This implementation draws from:
- **Symbol Grounding**: Harnad (1990), Steels (2008)
- **Neuro-Symbolic AI**: Garcez et al. (2019), Lamb et al. (2020)
- **Epistemic Logic**: Hintikka (1962), Fagin et al. (1995)
- **Fallacy Detection**: Walton (2010), Hamblin (1970)
- **Confidence Propagation**: Pearl (1988), Shafer (1976)
- **Logic Systems**: Enderton (2001), van Benthem (2010)

## Conclusion

This architecture demonstrates that neuro-symbolic AI can be rigorous, not just aspirational. By explicitly addressing:
- Symbol grounding
- Epistemic status vs. validity
- Inference validation
- Confidence propagation
- Unparseable fragments

We create a system that combines the best of both paradigms while acknowledging and handling their limitations.
