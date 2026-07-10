/**
 * Transcript detail for the agent's built-in tool use and thinking.
 *
 * ToolActivity is the wildcard tool-call renderer: any tool without an exact
 * name match (bash, web_search, web_fetch, read, write, edit, glob, grep)
 * shows up as a compact row with a per-tool summary and a collapsible
 * args/result view. ThinkingActivity and SessionTraceActivity render the
 * activity messages the bridge emits for thinking spans and the Console
 * trace link.
 */
import React from 'react';

const TOOL_ICON: Record<string, string> = {
  bash: '❯',
  web_search: '🔎',
  web_fetch: '⇣',
  read: '📄',
  write: '✎',
  edit: '✎',
  glob: '❉',
  grep: '❉',
};

/** Human summary of the interesting argument per tool. */
const summarize = (name: string, args: Record<string, unknown> | undefined): string => {
  if (!args) return '';
  const pick = (...keys: string[]) => {
    for (const key of keys) {
      const v = args[key];
      if (typeof v === 'string' && v) return v;
    }
    return '';
  };
  switch (name) {
    case 'bash':
      return pick('command');
    case 'web_search':
      return pick('query');
    case 'web_fetch':
      return pick('url');
    case 'read':
    case 'write':
    case 'edit':
      return pick('file_path', 'path');
    case 'glob':
    case 'grep':
      return pick('pattern');
    default: {
      const first = Object.values(args).find((v) => typeof v === 'string' && v);
      return typeof first === 'string' ? first : '';
    }
  }
};

export interface ToolActivityProps {
  name: string;
  status: 'inProgress' | 'executing' | 'complete';
  args?: Record<string, unknown>;
  result?: string;
}

export const ToolActivity: React.FC<ToolActivityProps> = ({ name, status, args, result }) => {
  const summary = summarize(name, args);
  const running = status !== 'complete';
  return (
    <details className="tool-activity">
      <summary>
        <span className={`tool-activity-dot${running ? ' running' : ''}`} />
        <span className="tool-activity-icon">{TOOL_ICON[name] ?? '⚙'}</span>
        <span className="tool-activity-name">{name}</span>
        {summary ? <code className="tool-activity-summary">{summary}</code> : null}
      </summary>
      <div className="tool-activity-body">
        {args && Object.keys(args).length > 0 && (
          <pre className="tool-activity-pre">{JSON.stringify(args, null, 2)}</pre>
        )}
        {result ? (
          <pre className="tool-activity-pre tool-activity-result">{result}</pre>
        ) : (
          <p className="tool-activity-pending">{running ? 'running…' : 'no output'}</p>
        )}
      </div>
    </details>
  );
};

export const ThinkingActivity: React.FC<{ content: { state?: string } }> = ({ content }) => (
  <div className={`thinking-activity${content.state === 'thinking' ? ' active' : ''}`}>
    <span className="thinking-activity-glyph">✦</span>
    {content.state === 'thinking' ? 'Thinking…' : 'Thought for a moment'}
  </div>
);

export const SessionTraceActivity: React.FC<{ content: { url?: string; sessionId?: string } }> = ({
  content,
}) =>
  content.url ? (
    <div className="trace-activity">
      Managed Agents session <code>{content.sessionId}</code> ·{' '}
      <a href={content.url} target="_blank" rel="noreferrer">
        open the full trace in Console
      </a>{' '}
      (every tool call and thinking span)
    </div>
  ) : null;
