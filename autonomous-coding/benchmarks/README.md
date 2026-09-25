# Autonomous Coding Tool Benchmarks

Standardized benchmark suite for comparing autonomous coding tools.

## Benchmark Tiers

| Tier | Complexity | Description | Expected Time |
|------|------------|-------------|---------------|
| **T1** | Trivial | Single file, one function (email validator) | <5 min |
| **T2** | Simple | 2-3 files, single feature (todo CLI) | <15 min |
| **T3** | Medium | Multi-component with auth (REST API) | <30 min |
| **T4** | Complex | Full-stack with analytics (URL shortener) | <60 min |

## Supported Tools

- **junior** - Minimal two-agent harness (this repo)
- **claudiomiro** - 9-step DAG-parallel pipeline
- **codemachine** - Multi-agent workflow orchestration
- **roma** - Recursive hierarchical decomposition

## Quick Start

```bash
# Check which tools are available
python run_benchmark.py --list-tools

# Run T2 benchmark on junior
python run_benchmark.py --tier t2 --tools junior

# Run all tiers on multiple tools
python run_benchmark.py --tier all --tools junior,claudiomiro

# Evaluate results
python evaluate.py
```

## Scoring Methodology

| Metric | Weight | Description |
|--------|--------|-------------|
| **Completeness** | 30% | Expected files created |
| **Correctness** | 25% | Tests passing + coverage |
| **Efficiency** | 20% | Time taken vs expected |
| **Quality** | 15% | Lint errors (ruff) |
| **Autonomy** | 10% | Completion without intervention |

## Directory Structure

```
benchmarks/
├── t1_email_validator/
│   └── spec.txt          # Specification file
├── t2_todo_cli/
│   └── spec.txt
├── t3_rest_api/
│   └── spec.txt
├── t4_url_shortener/
│   └── spec.txt
├── results/              # Output directory
│   ├── junior/
│   │   ├── t1_email_validator/
│   │   │   ├── metrics.json
│   │   │   └── ... (generated code)
│   │   └── t2_todo_cli/
│   └── claudiomiro/
├── run_benchmark.py      # Main runner
├── evaluate.py           # Scoring script
└── README.md
```

## Example Output

```
COMPARISON TABLE
================================================================================

Tool            Tier                 Complete   Correct    Efficient  Quality    OVERALL
------------------------------------------------------------------------------------------------
junior          t2_todo_cli          100.0      85.0       90.0       100.0      93.0
claudiomiro     t2_todo_cli          100.0      90.0       75.0       95.0       90.0
```

## Adding New Tools

1. Add configuration to `TOOL_CONFIGS` in `run_benchmark.py`:

```python
TOOL_CONFIGS["newtool"] = {
    "command": "newtool run --spec {spec} --output {output}",
    "max_iterations": {"t1": 3, "t2": 5, "t3": 10, "t4": 15},
    "requires": ["newtool"],
}
```

2. Add to `TOOLS` list
3. Run benchmarks

## Notes

- Each tool runs in isolation with fresh output directory
- Results are cached; use `--force` to rerun
- Timeout is 1 hour per benchmark
- Scoring requires `uv`, `pytest`, and `ruff` available
