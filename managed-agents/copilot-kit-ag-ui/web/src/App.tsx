import React from 'react';
import { CopilotKitProvider, CopilotChat } from '@copilotkit/react-core/v2';
import { z } from 'zod';
import { VizToolRenderers } from './viz/renderers';
import { ThinkingActivity, SessionTraceActivity } from './viz/ToolActivity';

const activityRenderers = [
  {
    activityType: 'thinking',
    content: z.object({ state: z.string().optional() }),
    render: ThinkingActivity,
  },
  {
    activityType: 'session_trace',
    content: z.object({ url: z.string().optional(), sessionId: z.string().optional() }),
    render: SessionTraceActivity,
  },
];

export const App: React.FC = () => (
  <CopilotKitProvider runtimeUrl="/api/copilotkit" renderActivityMessages={activityRenderers}>
    <VizToolRenderers />
    <div className="app">
      <header>
        <h1>
          Financial advisor{' '}
          <span className="header-dim">· Claude Managed Agents × CopilotKit</span>
        </h1>
        <p>A helpful personal finance agent to bounce ideas off of.</p>
      </header>
      <div className="chat-shell">
        <CopilotChat
          agentId="financial-advisor"
          labels={{
            chatInputPlaceholder:
              'Share your financial picture or ask about planning for the future…',
          }}
        />
      </div>
    </div>
  </CopilotKitProvider>
);
