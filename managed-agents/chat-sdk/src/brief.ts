// Shared between the server (src/card.tsx, src/sessions.ts, the bridge) and
// the browser bundle (web/app.tsx): the "brief ready" card's data shape and
// the formatting both sides must agree on. Keep this module dependency-free
// so esbuild can bundle it into the page.

export type BriefStats = {
  searches: number; // web_search calls this turn
  seconds: number; // wall-clock turn duration
  sessionId: string; // the Managed Agents session behind the conversation
};

// Every session has a live trace view in the Anthropic Console; `default`
// resolves to the session's actual workspace on load.
export function consoleTraceUrl(sessionId: string): string {
  return `https://platform.claude.com/workspaces/default/sessions/${sessionId}`;
}

export function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

// The web fallback the page parses back into a card. The stats are
// bridge-generated, never agent text, and web/app.tsx validates the shape
// again before rendering (see parseBriefStats there).
export function cardFence(stats: BriefStats): string {
  return "```card\n" + JSON.stringify(stats) + "\n```";
}

// One tool call in a turn's kept trace. `hint` is a short extract of the
// tool's input (the search query, the fetched URL); may be empty. Tool
// inputs can quote text from pages the agent read, so the page renders
// hints as plain text only -- never markdown, never a link.
export type ToolCall = {
  name: string;
  hint: string;
  error?: boolean; // the tool_result came back is_error
};

// One label rule for a tool call, shared by the live activity feed and the
// kept trace so the same call reads identically in both.
export function toolLabel(call: ToolCall): string {
  return call.hint ? `${call.name}: ${call.hint}` : call.name;
}

// The page rejects traces above this outright (see parseToolCalls in
// web/app.tsx), so toolsFence below must never emit more. Living here keeps
// the producer and the parser from drifting apart.
export const TOOLS_MAX = 500;

// The trace travels the same way as the card: a fenced block the page
// parses back, posted live at the end of each turn and re-derived from the
// event log on replay -- kept without the server storing anything.
export function toolsFence(tools: ToolCall[]): string {
  const capped =
    tools.length > TOOLS_MAX
      ? [
          ...tools.slice(0, TOOLS_MAX - 1),
          { name: `${tools.length - TOOLS_MAX + 1} more tool calls`, hint: "" },
        ]
      : tools;
  return "```tools\n" + JSON.stringify(capped) + "\n```";
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

// The first message of a conversation becomes the session title; the bridge
// persists it truncated to this and the sidebar mirrors it optimistically.
export const TITLE_MAX = 60;

