# Neuro-Symbolic Reasoning System

A rigorous hybrid architecture combining ML-powered reasoning with formal logic validation.

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│              (Natural Language Queries)                  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼────┐
    │ ML Layer │          │  Logic   │
    │ (Backend)│          │  Layer   │
    │          │          │(Frontend)│
    └────┬─────┘          └─────┬────┘
         │                      │
         │   ┌──────────────┐   │
         └──►│ Integration  │◄──┘
             │    Layer     │
             └──────┬───────┘
                    │
            ┌───────▼────────┐
            │ Knowledge Base │
            │   Validation   │
            └────────────────┘
```

### Components

#### 1. **Knowledge Base** (`knowledge_base.py`)

- Stores facts with provenance and confidence
- Performs logical inference (forward chaining)
- Validates claims against known facts
- Supports multiple logic types (propositional, first-order, modal)
- **Addresses**: Knowledge consistency, fact provenance, validation circularity

#### 2. **Symbol Grounding** (`grounding.py`)

- Maps natural language to formal logic
- Context-dependent semantic interpretation
- Tracks unparseable fragments
- Handles quantification (∀, ∃, most, generic)
- Detects modality requirements
- **Addresses**: Symbol grounding problem, ontological commitment gap

#### 3. **Epistemic Status** (`epistemic.py`)

- Separates logical validity from empirical soundness
- Explicit confidence propagation rules
- Fallacy detection (independent of LLM)
- Multi-dimensional confidence tracking
- **Addresses**: Epistemic vs. validity, confidence calculus, inference validation

#### 4. **Reasoning Agent** (`reasoning_agent.py`)

- Orchestrates neuro-symbolic reasoning
- Builds formal arguments from ML outputs
- Integrates knowledge base validation
- Generates both intuitive and formal explanations
- **Addresses**: Integration of neural and symbolic layers

### Key Features

#### Rigorous Semantic Parsing

Unlike naive pattern matching, our parser:

- ✅ Tracks what can and cannot be formalized
- ✅ Makes parsing assumptions explicit
- ✅ Handles universal, existential, generic quantification differently
- ✅ Detects when specialized logics are needed (epistemic, deontic, causal)

```python
from logic.grounding import SemanticParser, create_ml_context

context = create_ml_context()
parser = SemanticParser(context)

result = parser.parse("Most birds can fly")
# result.success = False
# result.unparseable_fragments = ["'most' requires higher-order logic"]
```

#### Separated Epistemic Status

We distinguish:

- **Validity**: Is the argument structure correct?
- **Soundness**: Are the premises actually true?

```python
from logic.epistemic import ValidityChecker

status = checker.check_modus_ponens(
    "If Socrates is a fish, then Socrates can swim",
    "Socrates is a fish",
    "Socrates can swim"
)
# status.validity = VALID (structure is correct)
# status.soundness = UNSOUND (premises are false)
```

#### Explicit Confidence Propagation

No more mysterious confidence scores:

```python
from logic.epistemic import ConfidenceCalculator

breakdown = ConfidenceCalculator.multi_step_chain(
    premise_confidences=[0.7, 0.6],
    rule_confidences=[0.9],
    rule_types=["universal_instantiation"]
)
# Returns detailed breakdown:
# - logical_confidence: 0.9 (argument structure)
# - source_confidence: 0.42 (premise reliability)
# - propagation_method: "sequential_product"
```

#### Independent Fallacy Detection

Validates LLM reasoning without trusting the LLM:

```python
fallacy = ConfidenceCalculator.detect_fallacy(
    premises=["Tech companies are successful", "Google is a tech company"],
    conclusion="Google is successful",
    claimed_rule="modus_ponens"
)
# Returns: "affirming_the_consequent"
# Missing universal quantifier: "ALL tech companies"
```

### Usage Examples

#### Basic Reasoning

```python
from logic import ReasoningAgent, LogicType

agent = ReasoningAgent(
    name="Logic Agent",
    system_prompt="Systematic logical reasoning",
    logic_framework=LogicType.FIRST_ORDER,
    reasoning_depth=3
)

# Add knowledge
agent.add_knowledge("All software engineers write code")
agent.add_knowledge("Alice is a software engineer")

# Reason
result = agent.reason("What can we conclude about Alice?")

print(result["formal_conclusion"])
# → WriteCode(Alice)
print(result["confidence"])
# → 0.85 (with breakdown of how this was calculated)
```

#### Context-Aware Grounding

```python
from logic.grounding import SemanticParser, create_ml_context

# Create domain-specific context
ml_context = create_ml_context()
parser = SemanticParser(ml_context)

# Ground "biased" in ML context
result = parser.parse("All ML models trained on biased data produce biased outputs")

# Grounding: "biased" = "statistical correlation with protected attributes"
print(result.logical_form)
# → ∀x(BiasedTraining(x) → BiasedOutput(x))

print(result.assumptions)
# Lists all assumptions made during parsing
```

#### Full Integration with Claude Agent

```python
from agent import Agent, ModelConfig
from tools.extended_thinking import ExtendedThinkingTool
from logic import ReasoningAgent, LogicType

# Create logic backend
logic_agent = ReasoningAgent(
    name="Logic Backend",
    system_prompt="Formal validation",
    logic_framework=LogicType.FIRST_ORDER
)

# Create extended thinking tool
extended_thinking = ExtendedThinkingTool(layers=8, logic_weight=0.75)

# Create integrated tool
logic_tool = LogicTool(logic_agent, extended_thinking)

# Create Claude agent with logic tool
agent = Agent(
    name="Neuro-Symbolic Reasoner",
    system="You combine neural reasoning with formal logic",
    tools=[logic_tool],
    config=ModelConfig()
)

# Query returns both ML reasoning AND formal proof
response = agent.run("Does GPT-4 produce biased outputs?")
```

### Design Principles

#### 1. **Transparency Over Black-Box**

Every reasoning step is traceable and auditable. No "magic" confidence scores.

#### 2. **Separation of Concerns**

- ML layer: Handles ambiguity, learning, generalization
- Logic layer: Ensures validity, soundness, formal guarantees
- Integration layer: Bridges the two

#### 3. **Explicit Assumptions**

When parsing makes assumptions, they're recorded and returned to the user.

#### 4. **Graceful Degradation**

If formal logic can't express something (e.g., "most"), we acknowledge it rather than pretend.

#### 5. **Independent Validation**

Logic validation doesn't depend on the LLM (avoids circular validation).

### Limitations & Future Work

#### Current Limitations

**Semantic Parsing**:

- Pattern-based parsing (not full NLP)
- Limited to common sentence structures
- No dependency tree analysis

**Logic Systems**:

- First-order logic only (no higher-order)
- No probabilistic logic (Markov Logic Networks)
- Limited modal logic support

**Validation**:

- Simple fallacy detection (not exhaustive)
- No automated theorem proving
- Manual ground truth needed

#### Planned Enhancements

1. **Full NLP Integration**
   - Dependency parsing
   - Semantic role labeling
   - Coreference resolution

2. **Advanced Logic Systems**
   - Higher-order logic for "most", "few"
   - Probabilistic logic (MLNs)
   - Temporal logic for time-indexed facts
   - Modal logic for beliefs, obligations

3. **Automated Theorem Proving**
   - Integration with Coq, Lean, or Isabelle
   - Formal proof generation
   - Proof checking

4. **Contradiction Resolution**
   - Paraconsistent logic support
   - Conflict detection
   - Source credibility weighting

5. **Ground Truth Oracles**
   - External knowledge base integration
   - Fact-checking API connections
   - Expert system validation

### Demonstrations

Run the demonstrations to see the system in action:

```bash
# Basic neuro-symbolic reasoning
python neuro_symbolic_demo.py

# Full integration with Agent framework
python neuro_symbolic_integration.py

# Rigorous logic features (addresses all edge cases)
python rigorous_logic_demo.py
```

### References

This implementation addresses challenges identified in:

- Symbol Grounding Problem (Harnad, 1990)
- Neuro-Symbolic AI (Garcez et al., 2019)
- Epistemic Logic (Hintikka, 1962)
- Fallacy Detection (Walton, 2010)
- Confidence Propagation (Pearl, 1988)

### Contributing

When extending this system:

1. ✅ Add tests for new logic patterns
2. ✅ Document assumptions explicitly
3. ✅ Separate validity from soundness
4. ✅ Make confidence calculations explicit
5. ✅ Provide unparseable fragment handling
