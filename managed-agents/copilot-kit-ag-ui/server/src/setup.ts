/**
 * ONE-TIME SETUP — run `npm run setup`, then start the server.
 *
 * Managed agents are persistent, versioned resources: create them once, store
 * the IDs, and reference them on every session. This script provisions a
 * cloud environment and a single financial-assistant agent on claude-fable-5.
 *
 * IDs land in agent-ids.json at the repo root (gitignored). Re-running with
 * --force re-provisions and overwrites the file.
 */
import Anthropic from '@anthropic-ai/sdk';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { vizToolDefinitions } from './vizTools.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
export const AGENT_IDS_PATH = path.resolve(here, '../../agent-ids.json');

export interface AgentIds {
  environmentId: string;
  agentId: string;
  agentVersion: number;
}

const MODEL = 'claude-fable-5';

const ASSISTANT_SYSTEM = `You are a careful, plain-spoken personal finance assistant. Your job is
to help people review their personal finances, brainstorm ideas, and think through best
practices for planning their future.

How you work:
- Start by understanding their picture. When someone shares income, spending, debts, savings,
  or goals, reflect a short summary back so they can correct you, then work from it. If key
  numbers are missing, ask for the one or two that matter most rather than a long intake form.
- Review, then brainstorm. Point out what already looks healthy, where the risks or gaps are
  (emergency fund, high-interest debt, retirement pace, insurance), and then offer a handful
  of distinct ideas or trade-offs to consider, not a single prescription. Frame options as
  "many people in this situation weigh X against Y."
- Think in horizons: this year, the next five years, and retirement. Best practices worth
  reaching for when relevant: pay-yourself-first budgeting, debt-avalanche vs snowball,
  employer-match capture, tax-advantaged account ordering, and keeping investing boring.
- Use web_search when current data would change the answer (rates, limits, recent policy
  changes) rather than answering from memory, and say when figures are as-of a date.
- Use bash and files in your workspace for quick calculations (compound interest, payoff
  timelines, scenario tables). Show the numbers, not the code.
- Show, don't just tell. You have interactive visual tools that render live in the chat:
  show_payoff_timeline (debt payoff with a what-if payment slider), show_growth_projection
  (compound growth with contribution/return sliders), show_budget_breakdown (income vs
  spending bars), and show_comparison (scenario A vs B bars). Whenever a concept has numbers
  behind it, call the matching visual with those numbers, then keep your prose short and let
  the visual carry the explanation. One or two visuals per reply, placed where they help most.
- You provide educational guidance, not personalized investment advice. When a decision
  depends on someone's full financial picture (taxes, jurisdiction, risk tolerance), say what
  generally applies and note what a licensed professional would need to know. Keep answers
  tight; one short disclaimer at most, and only where genuinely warranted.`;

function printEnvExports(ids: AgentIds) {
  console.log('Deploying somewhere without agent-ids.json? Set these instead:');
  console.log(`  ANTHROPIC_ENVIRONMENT_ID=${ids.environmentId}`);
  console.log(`  ANTHROPIC_AGENT_ID=${ids.agentId}`);
  console.log(`  ANTHROPIC_AGENT_VERSION=${ids.agentVersion}`);
}

async function main() {
  const force = process.argv.includes('--force');
  if (fs.existsSync(AGENT_IDS_PATH) && !force) {
    console.log(`agent-ids.json already exists — agents are reusable, not per-run.`);
    console.log(`Re-run with --force to re-provision.\n`);
    printEnvExports(JSON.parse(fs.readFileSync(AGENT_IDS_PATH, 'utf8')) as AgentIds);
    return;
  }

  // Zero-arg client: resolves ANTHROPIC_API_KEY or an `ant auth login` profile.
  const client = new Anthropic();

  // The chat endpoint that fronts this agent is unauthenticated in the demo, so
  // keep the blast radius small: the container gets no outbound network (bash
  // and files still work for calculations), and web_fetch stays off because
  // arbitrary URL fetches are the classic prompt-injection + exfil channel.
  // web_search stays on for current rates and limits.
  console.log('Creating environment…');
  const environment = await client.beta.environments.create({
    name: `financial-assistant-demo-${Date.now().toString(36)}`,
    config: {
      type: 'cloud',
      networking: {
        type: 'limited',
        allowed_hosts: [],
        allow_package_managers: false,
        allow_mcp_servers: false,
      },
    },
  });
  console.log(`  environment ${environment.id}`);

  console.log('Creating agent…');
  const agent = await client.beta.agents.create({
    name: 'financial-assistant',
    model: MODEL,
    system: ASSISTANT_SYSTEM,
    tools: [
      {
        type: 'agent_toolset_20260401',
        configs: [{ name: 'web_fetch', enabled: false }],
      },
      ...vizToolDefinitions,
    ],
  });
  console.log(`  financial-assistant ${agent.id} (version ${agent.version})`);

  const ids: AgentIds = {
    environmentId: environment.id,
    agentId: agent.id,
    agentVersion: agent.version,
  };
  fs.writeFileSync(AGENT_IDS_PATH, JSON.stringify(ids, null, 2) + '\n');
  console.log(`\nWrote ${AGENT_IDS_PATH}`);
  console.log('Setup complete. Start the demo with: npm run dev\n');
  printEnvExports(ids);
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

export function loadAgentIds(): AgentIds {
  // Env vars first — deployment platforms without a persistent disk (Vercel,
  // Netlify, containers built from a clean checkout) can't ship agent-ids.json.
  const { ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_AGENT_ID, ANTHROPIC_AGENT_VERSION } = process.env;
  const envVars = {
    ANTHROPIC_ENVIRONMENT_ID,
    ANTHROPIC_AGENT_ID,
    ANTHROPIC_AGENT_VERSION,
  };
  const missing = Object.keys(envVars).filter((k) => !envVars[k as keyof typeof envVars]);
  if (missing.length > 0 && missing.length < 3) {
    // A partial set is a deploy-config mistake, not a fallback case.
    throw new Error(`Agent env vars partially set: missing ${missing.join(', ')}.`);
  }
  if (ANTHROPIC_ENVIRONMENT_ID && ANTHROPIC_AGENT_ID && ANTHROPIC_AGENT_VERSION) {
    const agentVersion = Number(ANTHROPIC_AGENT_VERSION);
    if (!Number.isInteger(agentVersion)) {
      throw new Error(`ANTHROPIC_AGENT_VERSION must be an integer, got "${ANTHROPIC_AGENT_VERSION}".`);
    }
    return {
      environmentId: ANTHROPIC_ENVIRONMENT_ID,
      agentId: ANTHROPIC_AGENT_ID,
      agentVersion,
    };
  }
  if (!fs.existsSync(AGENT_IDS_PATH)) {
    throw new Error(
      'No agent configured — run `npm run setup` first, or set ' +
        'ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_AGENT_ID, and ANTHROPIC_AGENT_VERSION.',
    );
  }
  return JSON.parse(fs.readFileSync(AGENT_IDS_PATH, 'utf8')) as AgentIds;
}
