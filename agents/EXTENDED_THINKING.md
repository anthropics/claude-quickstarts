# 🧠 Extended Thinking Integration

**Multi-layer chain-of-thought reasoning for Watson Glaser TIS and Agent systems**

This integration brings Watson Glaser Test of Inference and Suggestions (TIS) extended thinking capabilities to the agent framework, enabling deep, systematic reasoning with confidence assessment and consensus synthesis.

## 🎯 Overview

Extended Thinking provides:

- **6-step chain-of-thought reasoning** process
- **4-layer multi-perspective analysis** (Perception, Reasoning, Evaluation, Meta-Learning)
- **Watson Glaser critical thinking** templates
- **Curriculum-based complexity gating**
- **History tracking and pattern learning**
- **Seamless agent integration**

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Extended Thinking Tool                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Step 1: Question Analysis                              │
│           ↓                                              │
│  Step 2: Key Concept Identification                     │
│           ↓                                              │
│  Step 3: Multi-Layer Analysis (4 layers)                │
│           ├─→ Layer 1: Perception                       │
│           ├─→ Layer 2: Reasoning                        │
│           ├─→ Layer 3: Evaluation                       │
│           └─→ Layer 4: Meta-Learning                    │
│           ↓                                              │
│  Step 4: Strategy Selection                             │
│           ↓                                              │
│  Step 5: Option Evaluation (if applicable)              │
│           ↓                                              │
│  Step 6: Consensus Synthesis                            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Basic Usage

```python
from tools.extended_thinking import ExtendedThinkingTool

# Create tool
et_tool = ExtendedThinkingTool(layers=4, verbose=True)

# Analyze a question
result = et_tool.execute(
    query="Should we adopt this new technology?",
    context="Budget: $50k, Timeline: 3 months",
    options=[
        "Adopt immediately",
        "Pilot test first",
        "Delay decision",
        "Reject proposal"
    ],
    depth=3  # 1-5, higher = deeper thinking
)

print(f"Confidence: {result['confidence']:.1%}")
print(f"Recommendation: {result['recommendation']}")
```

### Watson Glaser Critical Thinking

```python
from tools.extended_thinking import WatsonGlaserThinkingTool

# Create specialized tool
wg_tool = WatsonGlaserThinkingTool(verbose=True)

# Critical thinking query
result = wg_tool.execute(
    query="""
    All AI systems require training data.
    This is an AI system.
    Therefore, this requires training data.
    Is this reasoning valid?
    """,
    options=["Yes, sound logic", "No, invalid premise", "Cannot determine"],
    depth=3
)

# Unlock higher complexity with accuracy
unlock_msg = wg_tool.unlock_complexity(accuracy=0.85)
if unlock_msg:
    print(unlock_msg)  # "🎓 Unlocked Complexity Level 3 (Advanced)!"
```

### Agent Integration

```python
from agent import Agent
from tools.extended_thinking import ExtendedThinkingTool

# Create tool
et_tool = ExtendedThinkingTool(layers=4)

# Add to agent
agent = Agent(
    name="Critical Thinker",
    tools=[et_tool.get_schema()]
)

# Agent can now invoke extended_thinking during conversations
# Claude will automatically use the tool for complex reasoning tasks
```

## 📊 Features

### 1. Six-Step Thinking Process

Each query goes through:

1. **Question Analysis**: Identify type (assumptions, inferences, deductions, etc.) and complexity
2. **Key Concepts**: Extract domain-specific concepts (logic, causation, evidence, etc.)
3. **Multi-Layer Analysis**: Analyze from 4 specialized perspectives
4. **Strategy Selection**: Choose optimal reasoning strategies (analytical, eliminative, etc.)
5. **Option Evaluation**: Score each option using selected strategies
6. **Consensus Synthesis**: Combine insights and generate recommendation

### 2. Multi-Layer Analysis

Four specialized layers provide different perspectives:

| Layer | Name | Focus | Specialization |
|-------|------|-------|----------------|
| 1 | Perception | Pattern Recognition | Identifies structures and key elements |
| 2 | Reasoning | Logical Inference | Applies deductive/inductive reasoning |
| 3 | Evaluation | Critical Assessment | Evaluates evidence and argument validity |
| 4 | Meta-Learning | Strategy Optimization | Coordinates insights and improves over time |

### 3. Reasoning Strategies

Six core strategies with adaptive weighting:

- **Analytical** (0.8): Break down into components
- **Comparative** (0.75): Compare with similar cases  
- **Eliminative** (0.85): Eliminate impossible options
- **Constructive** (0.7): Build from first principles
- **Probabilistic** (0.72): Assess likelihood
- **Counterfactual** (0.68): Consider alternatives

### 4. Curriculum Learning

Watson Glaser tool unlocks complexity progressively:

- **Level 1** (Novice): Basic patterns, simple templates
- **Level 2** (Intermediate): 70%+ accuracy required
- **Level 3** (Advanced): 80%+ accuracy required  
- **Level 4** (Expert): 90%+ accuracy required

### 5. History & Pattern Learning

The tool maintains thinking history:

```python
# Get history summary
summary = et_tool.get_history_summary()

print(f"Total queries: {summary['total_queries']}")
print(f"Avg confidence: {summary['avg_confidence']:.1%}")
print(f"Recent: {summary['recent_queries']}")
```

## 📈 Output Structure

```python
{
    "thinking_chain": [
        {
            "step": 1,
            "name": "Question Analysis",
            "content": "Question type: inferences, Complexity: 3/5",
            "details": {...}
        },
        # ... 6 steps total
    ],
    "key_insights": [
        "Question type: inferences, Complexity: 3/5",
        "Consensus confidence: 82.5%"
    ],
    "confidence": 0.825,
    "recommendation": "Option B: Pilot test first",
    "reasoning_depth": 3,
    "meta_analysis": {
        "total_steps": 6,
        "analysis_depth": 2,
        "decision_quality": "high"
    }
}
```

## 🔧 Configuration

### Thinking Depth

Control analysis depth (1-5):

- **Depth 1**: Quick analysis, 2-3 layers
- **Depth 3**: Standard analysis, all 4 layers (default)
- **Depth 5**: Maximum depth, extended evaluation

### Verbose Mode

Enable detailed output:

```python
et_tool = ExtendedThinkingTool(verbose=True)
# Prints full thinking process to console
```

### Layer Count

Adjust number of analysis layers:

```python
et_tool = ExtendedThinkingTool(layers=2)  # Lighter, faster
et_tool = ExtendedThinkingTool(layers=4)  # Standard (recommended)
```

## 📚 Examples

### Example 1: Technology Decision

```python
query = """
Should we migrate from Python/Django to Node.js/Express?
- Team: 5 developers (mostly Python experience)
- Timeline: 3 months
- Budget: $50k
- Current system: stable, but scaling issues
"""

options = [
    "Migrate fully now",
    "Gradual migration",
    "Stay with Python",
    "Need more research"
]

result = et_tool.execute(query=query, options=options, depth=4)
# → "Gradual migration" with 78% confidence
```

### Example 2: Critical Thinking

```python
query = """
A study of 50 users found our app "very useful".
How strong is this evidence for widespread usefulness?
"""

options = [
    "Very strong - proves universal usefulness",
    "Moderate - limited sample, potential bias",
    "Conclusive - 50 is a large number",
    "Weak - only because it's qualitative"
]

result = wg_tool.execute(query=query, options=options, depth=3)
# → "Moderate - limited sample, potential bias" with 85% confidence
```

### Example 3: Multi-Query Pattern Learning

```python
queries = [
    "Should we invest in AI research?",
    "Is remote work more productive?",
    "Should we expand internationally?"
]

for query in queries:
    result = et_tool.execute(query=query, depth=2)
    print(f"{query} → {result['confidence']:.1%}")

# Tool learns patterns across queries
summary = et_tool.get_history_summary()
```

## 🔗 Integration with 4-Layer Architecture

The enhanced `four_layer.html` now includes extended thinking:

```javascript
// Each layer has extendedThinking() method
const chain = layer.extendedThinking(question);

// 6-step process per layer:
// 1. Layer-specific perception
// 2. Concept identification  
// 3. Strategy selection
// 4. Option evaluation
// 5. Layer integration
// 6. Decision making

// Consensus synthesis across all 4 layers
const consensus = this.calculateConsensus(results);
```

**Key improvements:**

- ✅ Layer-specialized reasoning chains
- ✅ Per-layer strategy selection and weighting
- ✅ Multi-perspective option evaluation
- ✅ Cross-layer consensus synthesis
- ✅ Enhanced pattern storage

## 🎓 Watson Glaser Integration

The system includes Watson Glaser critical thinking templates:

### Question Types

1. **Assumptions**: What is taken for granted?
2. **Inferences**: What can be concluded?
3. **Deductions**: What must be true?
4. **Interpretations**: What is the meaning?
5. **Evaluations**: How strong is the evidence?

### Cognitive Templates

```python
cognitive_templates = {
    "assumptions": [
        {"pattern": "implies", "weight": 0.8, "complexity": 1},
        {"pattern": "presupposes", "weight": 0.85, "complexity": 2},
        {"pattern": "takes for granted", "weight": 0.75, "complexity": 1}
    ],
    "inferences": [
        {"pattern": "follows logically", "weight": 0.85, "complexity": 1},
        {"pattern": "can be concluded", "weight": 0.8, "complexity": 1}
    ]
}
```

## 📊 Performance Considerations

### Speed vs Depth Trade-offs

| Depth | Layers | Avg Time | Use Case |
|-------|--------|----------|----------|
| 1 | 2 | ~100ms | Quick decisions |
| 3 | 4 | ~250ms | Standard analysis (recommended) |
| 5 | 4 | ~400ms | Complex problems requiring deep thought |

### Memory Usage

- Tool instance: ~50KB
- History per query: ~5-10KB
- Full history (100 queries): ~500KB-1MB

## 🧪 Testing

Run the demo:

```bash
cd agents
python extended_thinking_demo.py
```

Or use the Jupyter notebook:

```bash
jupyter notebook extended_thinking_integration.ipynb
```

## 🔄 Comparison with Previous System

| Feature | Previous | Enhanced |
|---------|----------|----------|
| Thinking steps | 1 (basic) | 6 (extended chain) |
| Analysis layers | 1 | 4 (specialized) |
| Strategy selection | Random | Adaptive, weighted |
| Option evaluation | Single score | Multi-strategy breakdown |
| Confidence | Basic | Multi-layer consensus |
| History tracking | None | Full history with patterns |
| Curriculum learning | None | Progressive complexity gating |

## 📖 API Reference

### ExtendedThinkingTool

```python
ExtendedThinkingTool(
    layers: int = 4,        # Number of analysis layers
    verbose: bool = False   # Print detailed output
)
```

**Methods:**

- `get_schema()` → Tool schema for agent integration
- `execute(query, context, options, depth)` → Run extended thinking
- `get_history_summary()` → Get thinking history stats

### WatsonGlaserThinkingTool

```python
WatsonGlaserThinkingTool(
    layers: int = 4,
    verbose: bool = False
)
```

**Additional methods:**

- `unlock_complexity(accuracy)` → Unlock higher complexity levels
- Same interface as ExtendedThinkingTool

## 🛣️ Roadmap

- [ ] Add visual thinking chain renderer
- [ ] Implement cross-agent consensus
- [ ] Add more cognitive templates
- [ ] Real-time collaboration between agents
- [ ] Export thinking chains to knowledge base
- [ ] Interactive complexity adjustment
- [ ] Performance profiling dashboard

## 🤝 Contributing

See main [CLAUDE.md](../CLAUDE.md) for contribution guidelines.

## 📄 License

MIT License - see [LICENSE](../LICENSE)

---

**Built with:** Python 3.11+ | Anthropic Claude | Watson Glaser Critical Thinking Framework

**Status:** ✅ Production Ready | 🧪 Actively Developed
