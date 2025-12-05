# Agent Architecture Views

Visual summaries of the current and intended agent stack. These reflect the existing code (reasoning agent, decision model, planner with preconditions/effects, memory, critic/hallucination guard) and the planned integration noted in the roadmap.

## End-to-End Reasoning Flow

```mermaid
flowchart LR
    Q(Query) --> P(Parse/Ground)
    P --> KB[(Knowledge Base)]
    KB -->|facts| R(Reasoning Chain)
    R --> FA(Formal Argument)
    FA --> VAL(Validation + Contradiction Check)
    VAL --> HG(Hallucination Guard)
    R --> DEC(Decision Model)
    DEC --> PLAN(Planner/Executor)
    PLAN --> TOOLS{{Tools}}
    TOOLS --> PLAN
    PLAN --> STATE[(Plan State)]
    STATE --> DEC
    HG --> OUT(Answer + Warnings)
    DEC --> OUT
```

## Decision Model Scoring Pipeline

```mermaid
flowchart TD
    A(Options) --> B(Hard Constraints Check)
    B -->|blocked| W[Warnings/No options]
    B -->|pass| C(Score: value - cost - risk)
    C --> D(Apply soft penalties)
    D --> E(Citation/Contradiction penalties)
    E --> F(Risk gate warnings)
    F --> G(Sort & Select)
    G --> H(Output: ranked options + warnings)
```

## Planner with Preconditions/Effects and State

```mermaid
flowchart LR
    PLAN[Plan Steps] -->|priority| READY{Ready Steps}
    READY -->|preconditions met| EXEC[Execute Step]
    EXEC --> TOOL{{Tool / Reasoning / Decision}}
    TOOL --> RESULT[Result]
    RESULT --> STATE[(State Effects)]
    STATE --> READY
    EXEC --> WARN[Warnings/Errors]
    WARN --> REPLAN[Retry/Recovery/Replan]
```

## Validation, Critic, and Hallucination Guard

```mermaid
flowchart LR
    CHAIN(Reasoning Chain) --> ARG(Formal Argument)
    ARG --> VAL(Validate + Contradiction Detect)
    VAL --> CRIT(Critic/Debate - planned)
    CRIT --> HG(Hallucination Guard)
    HG --> OUT(Conclusion + Adjusted Confidence + Warnings)
```

## WG Alignment (Future Intent)

```mermaid
flowchart TD
    SHARED[Shared Agent Logic & Config (future package)]
    SHARED --> QS[Quickstarts Agents]
    SHARED --> WGBE[WG Local Backend (planned)]
    WGBE --> WGFE[WG Front-End]
    WGFE --> USERS(Users/Tests)
```

## Sequence Diagrams

### Reasoning with Validation and Guard

```mermaid
sequenceDiagram
    participant User
    participant Parser
    participant KB
    participant Reasoner
    participant Validator
    participant Guard
    User->>Parser: query
    Parser-->>Reasoner: parse/grounded query
    Reasoner->>KB: fetch relevant facts
    KB-->>Reasoner: facts
    Reasoner->>Validator: formal argument
    Validator-->>Guard: validation + contradictions
    Guard-->>User: conclusion + adjusted confidence + warnings
```

### Planner Execution with Failure/Recovery

```mermaid
sequenceDiagram
    participant Planner
    participant Executor
    participant Tool
    participant State
    Planner->>Executor: prioritized ready steps
    Executor->>Tool: execute step
    Tool-->>Executor: success or error
    Executor-->>State: apply effects (on success)
    Executor-->>Planner: warn/replan (on failure)
    Planner-->>Executor: recovery/retry steps
```

### Decision Scoring with Constraints/Risk

```mermaid
sequenceDiagram
    participant DecisionModel
    participant Constraints
    participant Critic
    DecisionModel->>Constraints: check hard/soft rules
    DecisionModel-->>DecisionModel: apply value/cost/risk math
    DecisionModel-->>DecisionModel: apply citation/contradiction penalties
    DecisionModel-->>Critic: (high-risk) request extra scrutiny
    DecisionModel-->>DecisionModel: rank options + warnings
```

## State Transitions

### Plan Step States

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> IN_PROGRESS
    IN_PROGRESS --> COMPLETED
    IN_PROGRESS --> FAILED
    FAILED --> PENDING : retry
    FAILED --> BLOCKED : no recovery
    PENDING --> SKIPPED
```

### Validation/Guard States

```mermaid
stateDiagram-v2
    [*] --> RAW
    RAW --> VALIDATED : KB check
    VALIDATED --> CONTRADICTED : conflicts found
    VALIDATED --> GUARDED : guard adjusts confidence
    GUARDED --> OUTPUT
    CONTRADICTED --> GUARDED
```
