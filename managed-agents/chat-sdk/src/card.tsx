/** @jsxImportSource chat */
// The "brief ready" card: one Chat SDK JSX card posted after each research
// turn. On adapters with native cards (Slack Block Kit, Teams Adaptive
// Cards) the JSX below renders as a real card. The web adapter has no card
// renderer in v1 -- it sends `fallbackText` instead -- so the fallback is a
// fenced ```card block carrying the same stats as JSON, and web/app.tsx
// renders that fence as a styled card. One post, both surfaces.

import type { PostableCard } from "chat";
import { Actions, Card, LinkButton, toCardElement } from "chat";
import { cardFence, consoleTraceUrl, formatDuration, type BriefStats } from "./brief";

export type { BriefStats };

export function briefCard(stats: BriefStats): PostableCard {
  // toCardElement narrows JSX to a card and is null only for non-card JSX,
  // which this literal never is.
  const card = toCardElement(
    <Card
      title="Brief ready"
      subtitle={`${stats.searches} web search${stats.searches === 1 ? "" : "es"} · ${formatDuration(stats.seconds)}`}
    >
      <Actions>
        <LinkButton url={consoleTraceUrl(stats.sessionId)} label="Open session trace" />
      </Actions>
    </Card>,
  );
  if (!card) throw new Error("briefCard JSX did not produce a card element");
  return { card, fallbackText: cardFence(stats) };
}
