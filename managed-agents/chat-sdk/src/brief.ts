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

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

// The first message of a conversation becomes the session title; the bridge
// persists it truncated to this and the sidebar mirrors it optimistically.
export const TITLE_MAX = 60;

