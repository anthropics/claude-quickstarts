# Safety Guardrails Quickstart

Add real-time safety scanning to Claude API calls — detect prompt injection, PII leaks, harmful content, and dangerous tool calls before they reach your users.

## What This Demonstrates

- **Input scanning** — Block prompt injection and harmful content before sending to Claude
- **Output scanning** — Detect PII and hallucination signals in Claude's responses
- **PII redaction** — Automatically redact emails, SSNs, and API keys
- **Tool-use safety** — Scan tool arguments in agentic workflows before execution
- **Policy configuration** — Customize scanning rules via YAML

## Setup

```bash
cd safety-guardrails
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-api-key"
```

## Run

```bash
# Basic: input/output scanning with Claude
python main.py

# Interactive: try your own inputs
python main.py --interactive
```

## How It Works

The quickstart wraps Claude API calls with a safety scanning layer:

```python
from anthropic import Anthropic
from sentinel import SentinelGuard

guard = SentinelGuard.default()
client = Anthropic()

# Scan user input before sending to Claude
user_input = "Tell me about machine learning"
scan = guard.scan(user_input)

if scan.blocked:
    print(f"Blocked: {scan.risk.value} risk — {scan.findings[0].description}")
else:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": user_input}],
    )
    # Scan output for PII before showing to user
    output_scan = guard.scan(response.content[0].text)
    print(output_scan.redacted_text or response.content[0].text)
```

## Examples in `main.py`

1. **Safe input** — passes through to Claude normally
2. **Prompt injection** — blocked before reaching Claude
3. **PII in output** — redacted automatically
4. **Tool-use safety** — dangerous tool calls blocked
5. **Multilingual injection** — detected in 12 languages

## Key Properties

- ~0.05ms scan latency (regex-based, no GPU)
- Single dependency (`regex`)
- 530-case benchmark at 100% accuracy
- Works with any LLM provider (Claude, OpenAI, etc.)
