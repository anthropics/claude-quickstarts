/**
 * Generative-UI tools: custom (client-rendered) tools declared on the managed
 * agent. The agent calls one of these with the numbers it wants to show; the
 * bridge forwards the call to the browser as AG-UI TOOL_CALL events, CopilotKit
 * renders it with an interactive React component (see web/src/viz), and the
 * bridge immediately acks the session so the turn keeps flowing.
 */

export const VIZ_TOOL_NAMES = [
  'show_payoff_timeline',
  'show_growth_projection',
  'show_budget_breakdown',
  'show_comparison',
] as const;

export type VizToolName = (typeof VIZ_TOOL_NAMES)[number];

export const isVizTool = (name: string): name is VizToolName =>
  (VIZ_TOOL_NAMES as readonly string[]).includes(name);

export const vizToolDefinitions = [
  {
    type: 'custom' as const,
    name: 'show_payoff_timeline',
    description:
      'Render an interactive debt-payoff chart in the chat: remaining balance by month, ' +
      'payoff date, and total interest, with a payment slider the user can drag to explore ' +
      '"what if I paid more". Use whenever you discuss paying down a specific debt. ' +
      'Pass a comparisonPayment to contrast two plans (e.g. minimum vs aggressive).',
    input_schema: {
      type: 'object' as const,
      properties: {
        title: { type: 'string', description: 'Short chart title, e.g. "Credit card payoff"' },
        principal: { type: 'number', exclusiveMinimum: 0, description: 'Current balance in dollars' },
        aprPercent: { type: 'number', minimum: 0, maximum: 100, description: 'Annual interest rate, e.g. 22 for 22% APR' },
        monthlyPayment: { type: 'number', exclusiveMinimum: 0, description: 'Planned monthly payment in dollars' },
        comparisonPayment: {
          type: 'number',
          exclusiveMinimum: 0,
          description: 'Optional second payment amount to compare against',
        },
      },
      required: ['title', 'principal', 'aprPercent', 'monthlyPayment'],
    },
  },
  {
    type: 'custom' as const,
    name: 'show_growth_projection',
    description:
      'Render an interactive compound-growth chart in the chat: projected value over the ' +
      'years versus total contributed, with sliders for monthly contribution and return rate. ' +
      'Use whenever you discuss investing, retirement pace, or "what will this grow to".',
    input_schema: {
      type: 'object' as const,
      properties: {
        title: { type: 'string', description: 'Short chart title, e.g. "Roth IRA at 7%"' },
        initialAmount: { type: 'number', minimum: 0, description: 'Starting balance in dollars' },
        monthlyContribution: { type: 'number', minimum: 0, description: 'Monthly contribution in dollars' },
        annualReturnPercent: { type: 'number', minimum: 0, maximum: 30, description: 'Assumed annual return, e.g. 7' },
        years: { type: 'integer', minimum: 1, maximum: 50, description: 'Projection horizon in years' },
      },
      required: ['title', 'initialAmount', 'monthlyContribution', 'annualReturnPercent', 'years'],
    },
  },
  {
    type: 'custom' as const,
    name: 'show_budget_breakdown',
    description:
      'Render a budget bar chart in the chat: each spending category as a share of monthly ' +
      'income, with anything unallocated shown as a remainder. Use when reviewing how ' +
      "someone's income is divided or proposing a budget.",
    input_schema: {
      type: 'object' as const,
      properties: {
        title: { type: 'string', description: 'Short chart title, e.g. "Monthly budget"' },
        monthlyIncome: { type: 'number', exclusiveMinimum: 0, description: 'Monthly take-home income in dollars' },
        items: {
          type: 'array',
          description: 'Spending categories; keep to at most 8',
          items: {
            type: 'object',
            properties: {
              category: { type: 'string', description: 'Category name, e.g. "Rent"' },
              amount: { type: 'number', description: 'Monthly dollars' },
            },
            required: ['category', 'amount'],
          },
        },
      },
      required: ['title', 'monthlyIncome', 'items'],
    },
  },
  {
    type: 'custom' as const,
    name: 'show_comparison',
    description:
      'Render a small bar comparison of 2-5 scenarios in the chat, e.g. total interest under ' +
      'avalanche vs snowball, or renting vs buying over five years. Use when the point is ' +
      '"option A vs option B" and a number captures each option.',
    input_schema: {
      type: 'object' as const,
      properties: {
        title: { type: 'string', description: 'Short chart title' },
        unit: {
          type: 'string',
          enum: ['dollars', 'months', 'percent'],
          description: 'Unit of the values',
        },
        options: {
          type: 'array',
          description: '2-5 scenarios to compare',
          items: {
            type: 'object',
            properties: {
              label: { type: 'string', description: 'Scenario name' },
              value: { type: 'number', description: 'The number to compare' },
              note: { type: 'string', description: 'Optional one-line note' },
            },
            required: ['label', 'value'],
          },
        },
      },
      required: ['title', 'unit', 'options'],
    },
  },
];
