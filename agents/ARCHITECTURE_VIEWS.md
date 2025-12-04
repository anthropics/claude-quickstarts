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
