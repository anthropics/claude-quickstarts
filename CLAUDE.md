# CLAUDE.md — Anthropic Quickstarts

This file provides guidance for AI assistants (Claude Code and similar tools) working with this repository.

## Repository Overview

This is a monorepo containing three independent quickstart demo projects that showcase different Claude API capabilities. Each project lives in its own subdirectory and has its own dependencies and setup.

```
anthropic-quickstarts/
├── customer-support-agent/   # Next.js 14 customer support chat with RAG
├── financial-data-analyst/   # Next.js 14 financial data analysis + charting
├── computer-use-demo/        # Python/Streamlit computer use agent
├── pyproject.toml            # Root Python config (Pyright venv path)
└── README.md
```

The projects are **not** linked (no workspaces, no shared packages). Work in each subdirectory independently.

---

## Project 1: customer-support-agent

**Path:** `customer-support-agent/`
**Stack:** Next.js 14, React 18, TypeScript 5, Tailwind CSS, shadcn/ui

### Purpose
An AI customer support chatbot powered by Claude with Amazon Bedrock RAG (Retrieval-Augmented Generation). Retrieves context from a Bedrock Knowledge Base, detects user mood, suggests follow-up questions, and can redirect users to human agents.

### Directory Layout
```
customer-support-agent/
├── app/
│   ├── api/chat/route.ts        # Main API endpoint — Claude + RAG logic
│   ├── lib/
│   │   ├── utils.ts             # Bedrock client + retrieveContext() + cn()
│   │   └── customer_support_categories.json
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ChatArea.tsx             # Main chat UI — knowledge base + model selection
│   ├── LeftSidebar.tsx
│   ├── RightSidebar.tsx
│   ├── TopNavBar.tsx
│   ├── FullSourceModal.tsx
│   ├── theme-provider.tsx
│   └── ui/                      # shadcn/ui primitives (avatar, button, etc.)
├── lib/utils.ts                 # cn() helper
├── config.ts                    # Sidebar inclusion via env vars
├── styles/                      # Theme definitions
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### Key Files
- `app/api/chat/route.ts` — POST handler: calls Bedrock RAG, builds system prompt, calls Claude, validates response with Zod
- `app/lib/utils.ts` — `retrieveContext()` using AWS Bedrock Agent Runtime; `cn()` utility
- `components/ChatArea.tsx` — Defines `knowledgeBases` and `models` arrays; controls conversation state
- `config.ts` — `NEXT_PUBLIC_INCLUDE_LEFT_SIDEBAR` / `NEXT_PUBLIC_INCLUDE_RIGHT_SIDEBAR` flags

### Environment Variables (`.env.local`)
```
ANTHROPIC_API_KEY=         # Required
BAWS_ACCESS_KEY_ID=        # AWS access key (note: 'B' prefix avoids Amplify restriction)
BAWS_SECRET_ACCESS_KEY=    # AWS secret key
```

### NPM Scripts
```bash
npm run dev           # Full app (both sidebars)
npm run dev:left      # Left sidebar only
npm run dev:right     # Right sidebar only
npm run dev:chat      # Chat area only (no sidebars)
npm run build         # Production build (full)
npm run build:left    # Production build (left sidebar only)
npm run build:right   # Production build (right sidebar only)
npm run build:chat    # Production build (chat only)
npm run lint          # ESLint (eslint-config-next)
npm run start         # Start production server
```

### API Response Schema (Zod-validated)
```typescript
{
  response: string,
  thinking: string,
  user_mood: "positive" | "neutral" | "negative" | "curious" | "frustrated" | "confused",
  suggested_questions: string[],
  debug: { context_used: boolean },
  matched_categories?: string[],
  redirect_to_agent?: { should_redirect: boolean, reason?: string }
}
```
Claude is prompted to return JSON directly (prefill technique: `"{"` is prepended to the assistant turn).

---

## Project 2: financial-data-analyst

**Path:** `financial-data-analyst/`
**Stack:** Next.js 14, React 18, TypeScript 5, Tailwind CSS, shadcn/ui, Recharts, PDF.js

### Purpose
A financial data analyst chatbot. Users upload financial documents (text, CSV, PDF, images) and ask questions. Claude uses the `generate_graph_data` tool to produce structured chart data rendered by Recharts.

### Directory Layout
```
financial-data-analyst/
├── app/
│   ├── api/finance/route.ts     # Edge API: handles file data, calls Claude with tool
│   ├── finance/page.tsx         # Main chat page
│   ├── layout.tsx
│   ├── page.tsx                 # Redirect to /finance
│   └── globals.css
├── components/
│   ├── ChartRenderer.tsx        # Renders Recharts charts from Claude tool output
│   ├── FilePreview.tsx          # File upload preview
│   ├── TopNavBar.tsx
│   ├── theme-provider.tsx
│   └── ui/                      # shadcn/ui primitives
├── hooks/                       # React hooks
├── lib/utils.ts                 # cn() helper
├── types/                       # TypeScript type definitions (ChartData, etc.)
├── utils/fileHandling.ts        # File-to-base64 conversion utilities
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### Key Files
- `app/api/finance/route.ts` — Edge runtime POST handler; defines `generate_graph_data` tool schema; converts file uploads to base64; calls Claude with `tool_choice: auto`
- `components/ChartRenderer.tsx` — Renders bar, multiBar, line, area, stackedArea, pie charts
- `utils/fileHandling.ts` — Converts uploaded files to base64 for Claude's vision/document API
- `types/` — `ChartData` type and related chart type definitions

### Environment Variables (`.env.local`)
```
ANTHROPIC_API_KEY=    # Required
```

### Supported File Types
- Text/code: `.txt`, `.md`, `.html`, `.py`, `.csv`, etc.
- PDF (text-based, not scanned)
- Images

### Chart Types (tool output)
`bar` | `multiBar` | `line` | `area` | `stackedArea` | `pie`

### NPM Scripts
```bash
npm run dev    # Development server (localhost:3000)
npm run build  # Production build
npm run start  # Production server
npm run lint   # ESLint
```

### API Route Notes
- Uses **Edge Runtime** (`export const runtime = "edge"`)
- `generate_graph_data` tool assigns sequential CSS chart colors: `hsl(var(--chart-1))` etc.
- Pie chart data is normalized to `{ segment, value }` keys before returning

---

## Project 3: computer-use-demo

**Path:** `computer-use-demo/`
**Stack:** Python 3.12, Streamlit, Anthropic SDK (beta computer-use), Docker

### Purpose
A Docker-based agent that lets Claude control a virtual desktop (Ubuntu) using computer use beta tools: screenshot, mouse/keyboard control, bash execution, and file editing. Supports Anthropic API, AWS Bedrock, and Google Vertex AI providers.

### Directory Layout
```
computer-use-demo/
├── computer_use_demo/
│   ├── loop.py           # Core agentic sampling loop
│   ├── streamlit.py      # Streamlit UI entrypoint
│   ├── tools/
│   │   ├── base.py       # BaseAnthropicTool, ToolResult, CLIResult, ToolError
│   │   ├── bash.py       # BashTool
│   │   ├── computer.py   # ComputerTool (screenshots, mouse, keyboard)
│   │   ├── edit.py       # EditTool (str_replace_editor)
│   │   ├── collection.py # ToolCollection
│   │   └── run.py        # Tool runner utilities
│   └── __init__.py
├── tests/
│   ├── conftest.py
│   ├── loop_test.py
│   ├── streamlit_test.py
│   └── tools/
│       ├── bash_test.py
│       ├── computer_test.py
│       └── edit_test.py
├── image/                # Docker image assets
├── Dockerfile
├── setup.sh              # Dev environment setup (creates .venv)
├── dev-requirements.txt  # ruff, pytest, pytest-asyncio + runtime deps
├── pyproject.toml        # pytest config + Pyright config
└── ruff.toml             # Ruff linter config
```

### Setup (local development)
```bash
cd computer-use-demo
./setup.sh          # Creates .venv, installs deps, sets up pre-commit
source .venv/bin/activate
```
**Requirements:** Python ≤3.12, Rust/Cargo (required by a transitive dependency)

### Running
```bash
# Via Docker (recommended)
export ANTHROPIC_API_KEY=your_key
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -p 5900:5900 -p 8501:8501 -p 6080:6080 -p 8080:8080 \
    -it ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest

# Local Streamlit (development)
streamlit run computer_use_demo/streamlit.py
```

### Testing
```bash
pytest                  # Run all tests
pytest tests/tools/     # Run tool-specific tests
```
Tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).

### Linting / Formatting
```bash
ruff check .            # Lint
ruff check --fix .      # Lint + auto-fix
ruff format .           # Format
```

### Ruff Config (`ruff.toml`)
- Selected rules: `A`, `ASYNC`, `B`, `E`, `F`, `I`, `PIE`, `RUF200`, `T20`, `UP`, `W`
- Ignored: `E501` (line length), `ASYNC230`
- isort: `combine-as-imports = true`
- `.venv` excluded

### Environment Variables
```
ANTHROPIC_API_KEY=    # Required for Anthropic provider
API_PROVIDER=         # "anthropic" (default) | "bedrock" | "vertex"
# Bedrock: AWS_PROFILE or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_REGION
# Vertex: CLOUD_ML_REGION + ANTHROPIC_VERTEX_PROJECT_ID
```

### API Provider Support
| Provider | Client | Notes |
|---|---|---|
| `anthropic` | `Anthropic` | Prompt caching enabled automatically |
| `bedrock` | `AnthropicBedrock` | Requires AWS credentials |
| `vertex` | `AnthropicVertex` | Requires GCP credentials |

### Key Architecture: `sampling_loop`
```python
async def sampling_loop(*, model, provider, messages, output_callback,
                         tool_output_callback, api_response_callback, ...)
```
- Agentic loop: calls Claude → executes tool use → feeds results back → repeats until no tool calls
- Uses `computer-use-2024-10-22` beta flag
- Anthropic provider additionally uses `prompt-caching-2024-07-31` beta flag
- Image truncation: keeps only N most recent screenshots (cache-friendly chunked removal)

### Tool Base Classes
```python
class BaseAnthropicTool(ABC):
    def __call__(self, **kwargs) -> Any: ...
    def to_params(self) -> BetaToolUnionParam: ...

@dataclass(kw_only=True, frozen=True)
class ToolResult:
    output: str | None
    error: str | None
    base64_image: str | None
    system: str | None
```

---

## Common Conventions Across TypeScript Projects

### Class Name Utilities
Both Next.js projects use the same `cn()` pattern:
```typescript
// lib/utils.ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### shadcn/ui Components
UI components in `components/ui/` are shadcn/ui primitives built on Radix UI. Modify them directly; they are not installed from a package registry.

### Next.js App Router
- All routes use the App Router (`app/` directory)
- API routes: `app/api/[name]/route.ts`, export named `POST`/`GET` functions
- `"use client"` directive for interactive React components

### TypeScript Patterns
- Strict TypeScript (tsconfig extends Next.js defaults)
- Zod used in `customer-support-agent` for runtime API response validation
- No `any` casts unless necessary for third-party SDK interop
- Types colocated with usage or in `types/` directory

### Styling
- Tailwind CSS 3 utility classes
- CSS variables for theming (dark/light mode via `next-themes`)
- Chart colors: `hsl(var(--chart-1))` through `hsl(var(--chart-5))`

---

## CI/CD

CI runs only on changes to `computer-use-demo/` or `.github/` paths.

### GitHub Actions Workflows (`.github/workflows/`)

| Workflow | Trigger | Jobs |
|---|---|---|
| `tests.yaml` | PR / push to main | `ruff` (lint), `pyright` (type check), `pytest` (unit tests) |
| `build.yaml` | PR / push to main | Docker build for AMD64 + ARM64, push to `ghcr.io/anthropics/anthropic-quickstarts` |
| `reusable_build_step.yaml` | Called by `build.yaml` | Reusable Docker build step |

Docker image tags:
- `computer-use-demo-{SHORT_SHA}` — every push
- `computer-use-demo-latest` — main branch only

### Pre-commit Hooks (`.pre-commit-config.yaml`)
Applies only to `computer-use-demo/` files, runs on `pre-commit` and `pre-push` stages:
1. `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`
2. `ruff --fix-only` — auto-fix lint errors
3. `ruff format` — format code
4. `ruff` — final lint pass
5. `pyright` — type checking

---

## Git Workflow

---

## Important Notes for AI Assistants

1. **No shared build system** — Each project is entirely self-contained. `npm install` must be run inside each Next.js project directory separately. The Python project uses its own `.venv`.

2. **No test setup in TypeScript projects** — Neither `customer-support-agent` nor `financial-data-analyst` has test scripts. Only `computer-use-demo` has tests.

3. **AWS credential naming** — `customer-support-agent` uses `BAWS_ACCESS_KEY_ID` and `BAWS_SECRET_ACCESS_KEY` (with a `B` prefix) to work around AWS Amplify's restriction on environment variables starting with `AWS_`.

4. **computer-use-demo requires Python ≤3.12** — The `setup.sh` script will exit with an error on Python 3.13+.

5. **computer-use-demo requires Rust/Cargo** — A transitive Python dependency requires Rust to build.

6. **Edge Runtime in financial-data-analyst** — The finance API route runs on Vercel's edge runtime. Avoid Node.js-only APIs in that file.

7. **Beta APIs** — `computer-use-demo` uses `anthropic.beta.messages` with beta flags. These APIs may change; check `loop.py` for the current flag strings.

8. **Prototype disclaimer** — All projects are prototypes/demos, not production-ready. They may lack comprehensive error handling, security hardening, and test coverage expected in production code.
