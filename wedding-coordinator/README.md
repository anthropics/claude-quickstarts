# Wedding Coordinator

An elite VIP wedding coordinator and crisis manager, powered by Claude. This project demonstrates how to turn a detailed persona system prompt into a small production-shaped Next.js app: a parameter intake form feeds a wedding's date, venue, budget, guest count, style, and priorities into the system prompt, and a streaming chat interface renders Claude's plan — including Markdown tables for the budget breakdown and day-of timeline.

The assistant's persona, tone, and task list are entirely in Czech (its target audience), so the UI and default conversation are Czech as well.

## What it demonstrates

- **Parameterized system prompts** — `lib/system-prompt.ts` fills a persona template's placeholders from structured user input instead of hardcoding a single prompt.
- **Streaming responses** — `app/api/chat/route.ts` uses `client.messages.stream()` and pipes text chunks straight into a `ReadableStream`, so the browser renders Claude's answer as it's generated.
- **Markdown-first output** — the system prompt asks Claude to answer with Markdown tables (budget breakdown, day-of schedule) and bullet checklists, rendered client-side with `react-markdown` + `remark-gfm`.

## Setup & Development

1. Install dependencies:

   ```bash
   npm install
   ```

2. Configure your API key:

   ```bash
   cp .env.example .env.local
   ```

   Then edit `.env.local` and set `ANTHROPIC_API_KEY` to your key from [console.anthropic.com](https://console.anthropic.com). `ANTHROPIC_MODEL` is optional and defaults to `claude-sonnet-5`.

3. Run the dev server:

   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000), fill in the wedding parameters (or leave them blank — the coordinator will ask), and submit to start the conversation.

## Project structure

```
app/
  api/chat/route.ts   # Streaming Claude endpoint
  page.tsx            # Switches between the intake form and the chat view
  layout.tsx, globals.css
components/
  WeddingParamsForm.tsx  # Captures date, venue, budget, guest count, style, priorities
  ChatWindow.tsx         # Streaming chat UI with Markdown rendering
lib/
  system-prompt.ts    # Persona prompt template + placeholder substitution
  utils.ts
types/
  wedding.ts
```

## Customizing

- Edit the persona prompt in `lib/system-prompt.ts` to change the coordinator's tone, task list, or output format.
- Add or remove intake fields by editing `FIELDS` in `components/WeddingParamsForm.tsx` and the corresponding `WeddingParams` type in `types/wedding.ts`.
