"use client";

// The tool UI registry. Every entry is `type: "backend"`: Managed Agents runs
// these tools server-side (or, for show_chart, our session controller
// answers them), so assistant-ui only renders them. There's no client
// `execute`, no schema, and no build plugin needed. Anything the agent calls
// that isn't listed here (MCP tools, other custom tools) falls through to
// ToolFallback, which still renders args, result, and the approval gate.

import { defineToolkit, Tools, useAui, type ToolCallMessagePartComponent } from "@assistant-ui/react";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import type { ToolResultPayload } from "@/lib/managed-agents/reducer";
import { BashToolUI } from "./bash";
import { EditToolUI, GlobToolUI, GrepToolUI, ReadToolUI, WriteToolUI } from "./file-tools";
import { ShowChartToolUI } from "./show-chart";
import { WebFetchToolUI, WebSearchToolUI } from "./web-tools";

// display: "standalone" keeps a card out of the collapsible "N tool calls"
// group. Anything that can carry an approval gate must be standalone: an
// Allow/Deny prompt folded inside a collapsed group is a gate nobody sees.
// That is every toolset tool — any of them can be set to always_ask in
// agents/spreadsheet-analyst.md, and each card renders an ApprovalBar for that case. The
// chart is standalone too, since it's the answer, not a step. (Only MCP and
// unknown tools, which fall through to ToolFallback, still group.)
export const toolkit = defineToolkit({
  bash: { type: "backend", display: "standalone", render: BashToolUI },
  web_search: { type: "backend", display: "standalone", render: WebSearchToolUI },
  web_fetch: { type: "backend", display: "standalone", render: WebFetchToolUI },
  read: { type: "backend", display: "standalone", render: ReadToolUI },
  write: { type: "backend", display: "standalone", render: WriteToolUI },
  edit: { type: "backend", display: "standalone", render: EditToolUI },
  glob: { type: "backend", display: "standalone", render: GlobToolUI },
  grep: { type: "backend", display: "standalone", render: GrepToolUI },
  show_chart: {
    type: "backend",
    display: "standalone",
    render: ShowChartToolUI as ToolCallMessagePartComponent,
  },
});

/** Register the toolkit with the runtime. Call once inside the provider. */
export function useManagedAgentsToolkit() {
  return useAui({ tools: Tools({ toolkit }) });
}

// The generic card for everything unregistered: unknown built-ins, MCP
// tools, and custom tools that aren't show_chart. Our reducer stores the
// result as {text, isError, searchResults?}; unwrap it to plain text so the
// stock fallback shows readable output instead of our wrapper object.
export const ManagedAgentsToolFallback: ToolCallMessagePartComponent = (props) => {
  const payload = props.result as ToolResultPayload | undefined;
  const result = payload && typeof payload === "object" && "text" in payload ? payload.text : props.result;
  return <ToolFallback {...props} result={result} isError={payload?.isError ?? props.isError} />;
};
