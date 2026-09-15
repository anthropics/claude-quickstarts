import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

const CLAUDE_AGENT_ID = process.env.CLAUDE_AGENT_ID!;
const CLAUDE_ENVIRONMENT_ID = process.env.CLAUDE_ENVIRONMENT_ID!;

export interface SlackMention {
  channel: string;
  thread_ts: string;
  user: string;
  text: string;
  team: string;
}

// Fire-and-forget: create the Managed Agents session, attach routing metadata, send the
// prompt, return. The reply path is handled in managed-agents-webhook.ts when Anthropic
// POSTs `session.status_idled`.
export async function kickoffAgentSession(m: SlackMention) {
  // Stash the Slack routing info on the session. The idle webhook later
  // delivers only a session ID; we read this metadata back to know where to
  // post the reply.
  const session = await client.beta.sessions.create({
    agent: CLAUDE_AGENT_ID,
    environment_id: CLAUDE_ENVIRONMENT_ID,
    metadata: {
      slack_channel: m.channel,
      slack_thread_ts: m.thread_ts,
      slack_team: m.team,
    },
  });

  await client.beta.sessions.events.send(session.id, {
    events: [
      {
        type: "user.message",
        content: [{ type: "text", text: m.text || "Hello! How can I help?" }],
      },
    ],
  });

  console.log(
    `[agent] kickoff slack=${m.channel}/${m.thread_ts} claude=${session.id}`,
  );
}
