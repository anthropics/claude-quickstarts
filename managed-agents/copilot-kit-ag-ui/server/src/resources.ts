/**
 * Which agent and environment the runtime talks to.
 *
 * `ant apply agents environments`, run from the quickstart root, creates both
 * from agents/ and environments/ and records their IDs, and the agent's
 * version, in claude-lock.json there. The server reads that file. Deployment
 * platforms without a persistent checkout (Vercel, Netlify, containers built
 * from a clean tree) can't ship the lockfile, so ANTHROPIC_ENVIRONMENT_ID,
 * ANTHROPIC_AGENT_ID and ANTHROPIC_AGENT_VERSION stand in for it when it is
 * absent. All three or none: a partial set is a deploy-config mistake.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
export const LOCKFILE_PATH = path.resolve(here, '../../claude-lock.json');

const AGENT_KEY = './agents/financial-assistant.md';
const ENVIRONMENT_KEY = './environments/financial-assistant.yaml';

export interface AgentIds {
  environmentId: string;
  agentId: string;
  agentVersion: number;
}

type Lockfile = { resources?: Record<string, { id?: string; version?: string }> };

export function loadAgentIds(): AgentIds {
  if (fs.existsSync(LOCKFILE_PATH)) {
    const lock = JSON.parse(fs.readFileSync(LOCKFILE_PATH, 'utf8')) as Lockfile;
    const agent = lock.resources?.[AGENT_KEY];
    const environment = lock.resources?.[ENVIRONMENT_KEY];
    if (!agent?.id || !agent.version || !environment?.id) {
      // apply records each resource as soon as it exists, so a run that
      // stopped partway leaves a lockfile with one of the two missing.
      throw new Error(
        `${LOCKFILE_PATH} is missing the agent or the environment: ` +
          'run `ant apply agents environments` again from the quickstart root and read its output.',
      );
    }
    return { environmentId: environment.id, agentId: agent.id, agentVersion: Number(agent.version) };
  }

  const { ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_AGENT_ID, ANTHROPIC_AGENT_VERSION } = process.env;
  const envVars = { ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_AGENT_ID, ANTHROPIC_AGENT_VERSION };
  const missing = Object.keys(envVars).filter((k) => !envVars[k as keyof typeof envVars]);
  if (missing.length === 3) {
    throw new Error(
      'No agent configured: run `ant apply agents environments` from the quickstart root ' +
        '(it writes claude-lock.json), or set ANTHROPIC_ENVIRONMENT_ID, ANTHROPIC_AGENT_ID, ' +
        'and ANTHROPIC_AGENT_VERSION.',
    );
  }
  if (missing.length > 0) {
    throw new Error(`Agent env vars partially set: missing ${missing.join(', ')}.`);
  }
  const agentVersion = Number(ANTHROPIC_AGENT_VERSION);
  if (!Number.isInteger(agentVersion)) {
    throw new Error(`ANTHROPIC_AGENT_VERSION must be an integer, got "${ANTHROPIC_AGENT_VERSION}".`);
  }
  return { environmentId: ANTHROPIC_ENVIRONMENT_ID!, agentId: ANTHROPIC_AGENT_ID!, agentVersion };
}
