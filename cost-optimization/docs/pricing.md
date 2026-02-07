# Claude API Pricing Reference

> Last updated: January 2026

## Model Pricing

| Model | Input | Output | Batch Input | Batch Output |
|-------|-------|--------|-------------|--------------|
| Claude Opus 4.5 | $15/MTok | $75/MTok | $7.50/MTok | $37.50/MTok |
| Claude Sonnet 4.5 | $3/MTok | $15/MTok | $1.50/MTok | $7.50/MTok |
| Claude Haiku 4.5 | $1/MTok | $5/MTok | $0.50/MTok | $2.50/MTok |

*MTok = Million Tokens*

## Prompt Caching Pricing

Prompt caching pricing varies by model:

### Claude Sonnet 4.5
| Type | Price | vs Normal |
|------|-------|-----------|
| Normal input | $3/MTok | Baseline |
| Cache write | $3.75/MTok | +25% (one-time) |
| **Cache read** | **$0.30/MTok** | **-90%** |

### Claude Opus 4.5
| Type | Price | vs Normal |
|------|-------|-----------|
| Normal input | $15/MTok | Baseline |
| Cache write | $18.75/MTok | +25% (one-time) |
| **Cache read** | **$1.50/MTok** | **-90%** |

### Claude Haiku 4.5
| Type | Price | vs Normal |
|------|-------|-----------|
| Normal input | $1/MTok | Baseline |
| Cache write | $1.25/MTok | +25% (one-time) |
| **Cache read** | **$0.10/MTok** | **-90%** |

## Extended Thinking Pricing

Extended thinking tokens are charged at input token rates:

| Model | Input/Thinking | Output |
|-------|----------------|--------|
| Sonnet 4.5 | $3/MTok | $15/MTok |
| Opus 4.5 | $15/MTok | $75/MTok |

## Batch API Details

- **Discount**: 50% off standard pricing
- **Processing time**: Up to 24 hours (usually <1 hour)
- **Results retention**: 29 days
- **Limits**: 100,000 requests or 256MB per batch

## Cache Details

### Minimum Token Requirements
| Model | Minimum Tokens |
|-------|---------------|
| Claude Sonnet 4.5 | 1,024 tokens |
| Claude Haiku 4.5 | 2,048 tokens |
| Claude Opus 4.5 | 1,024 tokens |

### Cache Lifetime
- **Standard**: 5 minutes (refreshes on each use)
- **Extended**: 1 hour (available for additional cost)

## Cost Calculation Examples

### Example 1: Single API Call (Sonnet 4.5)
```
Input: 1,000 tokens × $3/MTok = $0.003
Output: 500 tokens × $15/MTok = $0.0075
Total: $0.0105
```

### Example 2: Batch Processing (Sonnet 4.5)
```
Input: 1,000 tokens × $1.50/MTok = $0.0015
Output: 500 tokens × $7.50/MTok = $0.00375
Total: $0.00525 (50% savings)
```

### Example 3: Cached Conversation (Sonnet 4.5)
```
First call:
  - System (2000 tokens, cache write): 2,000 × $3.75/MTok = $0.0075
  - User (100 tokens): 100 × $3/MTok = $0.0003
  - Output (500 tokens): 500 × $15/MTok = $0.0075
  Total: $0.0153

Subsequent calls (cache hit):
  - System (2000 tokens, cache read): 2,000 × $0.30/MTok = $0.0006
  - User (100 tokens): 100 × $3/MTok = $0.0003
  - Output (500 tokens): 500 × $15/MTok = $0.0075
  Total: $0.0084 (45% savings)
```

## Official Resources

- [Anthropic Pricing Page](https://www.anthropic.com/pricing)
- [API Documentation](https://docs.anthropic.com/)
- [Batch Processing Guide](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing)
- [Prompt Caching Guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Extended Thinking Guide](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
