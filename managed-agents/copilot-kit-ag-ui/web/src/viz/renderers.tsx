/**
 * Generative UI wiring: register a React renderer for each visual tool the
 * managed agent can call. CopilotKit matches TOOL_CALL events by name and
 * mounts the component inline in the transcript. The zod schemas type each
 * renderer's props; they are not enforced at render time, so the components
 * guard the values they use.
 */
import React from 'react';
import { useRenderTool } from '@copilotkit/react-core/v2';
import { z } from 'zod';
import { PayoffTimeline } from './PayoffTimeline';
import { GrowthProjection } from './GrowthProjection';
import { BudgetBreakdown } from './BudgetBreakdown';
import { Comparison } from './Comparison';
import { ToolActivity } from './ToolActivity';

// The tool schemas the agent sees (vizTools.ts) carry the numeric bounds;
// these zod shapes only type the render props. The components clamp and
// guard defensively, so an out-of-range value still renders sensibly.
const payoffSchema = z.object({
  title: z.string(),
  principal: z.number().positive(),
  aprPercent: z.number().min(0),
  monthlyPayment: z.number().positive(),
  comparisonPayment: z.number().positive().optional(),
});

const growthSchema = z.object({
  title: z.string(),
  initialAmount: z.number().min(0),
  monthlyContribution: z.number().min(0),
  annualReturnPercent: z.number().min(0),
  years: z.number().min(1),
});

const budgetSchema = z.object({
  title: z.string(),
  monthlyIncome: z.number().positive(),
  items: z.array(z.object({ category: z.string(), amount: z.number() })),
});

const comparisonSchema = z.object({
  title: z.string(),
  unit: z.enum(['dollars', 'months', 'percent']),
  options: z.array(z.object({ label: z.string(), value: z.number(), note: z.string().optional() })),
});

const Placeholder: React.FC<{ label: string }> = ({ label }) => (
  <div className="viz-card viz-loading">{label}</div>
);

/** Mount once inside CopilotKitProvider; renders nothing itself. */
export const VizToolRenderers: React.FC = () => {
  useRenderTool(
    {
      name: 'show_payoff_timeline',
      parameters: payoffSchema,
      render: (props) =>
        props.status === 'inProgress' ?
          <Placeholder label="Building payoff timeline…" />
        : <PayoffTimeline {...props.parameters} />,
    },
    [],
  );

  useRenderTool(
    {
      name: 'show_growth_projection',
      parameters: growthSchema,
      render: (props) =>
        props.status === 'inProgress' ?
          <Placeholder label="Building growth projection…" />
        : <GrowthProjection {...props.parameters} />,
    },
    [],
  );

  useRenderTool(
    {
      name: 'show_budget_breakdown',
      parameters: budgetSchema,
      render: (props) =>
        props.status === 'inProgress' ?
          <Placeholder label="Building budget breakdown…" />
        : <BudgetBreakdown {...props.parameters} />,
    },
    [],
  );

  useRenderTool(
    {
      name: 'show_comparison',
      parameters: comparisonSchema,
      render: (props) =>
        props.status === 'inProgress' ?
          <Placeholder label="Building comparison…" />
        : <Comparison {...props.parameters} />,
    },
    [],
  );

  // Wildcard fallback: every other tool call (bash, web_search, file ops)
  // renders as a compact expandable activity row instead of disappearing.
  useRenderTool(
    {
      name: '*',
      render: (props) => (
        <ToolActivity
          name={props.name}
          status={props.status}
          args={props.parameters as Record<string, unknown> | undefined}
          result={typeof props.result === 'string' ? props.result : undefined}
        />
      ),
    },
    [],
  );

  return null;
};
