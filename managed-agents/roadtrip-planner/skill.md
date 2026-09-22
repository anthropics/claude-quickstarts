# Setup walkthrough

Work top to bottom. Every step has a verification before the next one starts.

## 1. Keys

| key | where | notes |
|---|---|---|
| Anthropic auth | `ant auth login`, or an API key from <https://platform.claude.com/> | the CLI and the app share the login. With a key, uncomment `ANTHROPIC_API_KEY` in `.env`. The org needs Managed Agents access |
| `NATIONAL_PARK_SERVICE_API_KEY` | <https://www.nps.gov/subjects/developer/get-started.htm> | free, emailed instantly |
| `WINDY_API_KEY` | <https://api.windy.com/point-forecast/docs> | free tier, point-forecast product |

```bash
cp .env.example .env   # then fill in the two vendor keys
```

Verify the vendor keys from your own machine before involving the sandbox:

```bash
set -a; . ./.env; set +a
curl -sS "https://developer.nps.gov/api/v1/alerts?parkCode=acad&limit=1" -H "X-Api-Key: $NATIONAL_PARK_SERVICE_API_KEY" | head -c 300
curl -sS -X POST "https://api.windy.com/api/point-forecast/v2" \
  -H "Content-Type: application/json" \
  -d '{"lat":44.35,"lon":-68.21,"model":"gfs","parameters":["temp"],"levels":["surface"],"key":"'"$WINDY_API_KEY"'"}' | head -c 300
```

Both return JSON. A 403 here is a key problem, not a quickstart problem.

## 2. Provision

```bash
npm install
./agents/setup.sh
```

`ant apply` (which setup runs with `--yes`; needs `ant` 1.34 or later and `jq`) creates the environment (networking limited to `developer.nps.gov` and `api.windy.com`), the vault, the reviewer agent (Opus, review-only prompt), and the planner agent (bash on, `web_search`/`web_fetch` off, a `multiagent` coordinator roster naming the reviewer's file), and records their IDs in `claude-lock.json`. Then setup adds two `environment_variable` credentials to the vault with the `injection_location` each vendor documents hardcoded (NPS: header, Windy: body).

`ant apply` records each resource in the lockfile as soon as it exists, so a run that fails partway picks up where it stopped. Re-running after a full run applies edits to the vault, environment, and both agents from their files. An agent update is a new version that new trips pick up, and a reviewer update also re-pins the planner's roster. The two credentials are created once and then left alone, so a flip from README step 2 survives a re-run.

Verify: `claude-lock.json` lists four resources, and `ant beta:agents retrieve --agent-id "$(jq -r '.resources["./agents/roadtrip-planner.md"].id' claude-lock.json)" --transform multiagent` shows the reviewer's ID and version in the roster.

## 3. Run

```bash
npm run dev
```

Open <http://localhost:3000>. The page creates one session per browser on load (cookie `roadtrip_planner_session_id`), so the sandbox is warm before the first question. Then do the four steps in [README.md](./README.md#four-things-to-do-with-it), in order. Step 2 is the vault story and it only lands after a real conversation exists. Step 3 is the `agent_with_overrides` model picker. Step 4 is the multi-agent review: it needs a full itinerary ask, not a one-fact question.

## Gotchas

### The cookie is input, so every route checks it

The session ID in the cookie goes straight into an API path, and the server's Anthropic credentials can read every session in the workspace. `ownedSession()` in `src/lib/client.ts` is why a pasted ID from another app gets a 403: the session has to resolve, belong to the planner agent in `claude-lock.json`, and still be live. The reviewer's agent ID is never accepted. Its threads live inside the planner's sessions and are not addressable from the browser.

### The IDs live in `claude-lock.json`, not `.env`

The app reads the planner, environment, and vault IDs from `claude-lock.json` (`src/lib/resources.ts`), which `ant apply` writes beside `package.json` when setup runs it from this directory. `CLAUDE_AGENT_ID` and friends in `.env`, `.env.local`, or your shell count only where the lockfile has no entry, so IDs left over from an older copy of this app cannot point it at archived resources. Delete them anyway to avoid confusion. Setup refuses a vendor key with quotes or spaces in it, because the key is interpolated into a YAML body.

## Debugging

| symptom | cause | fix |
|---|---|---|
| `./agents/setup.sh` 404s on `/v1/environments` or `/v1/vaults` | org not enrolled in Managed Agents | request access, or switch orgs |
| `./agents/setup.sh` stops with 409 on the environment | environment names are unique per workspace and `quickstart-roadtrip-planner-env` already exists there (an earlier run of this quickstart's old setup, usually); `ant apply` can't adopt it | change `name` in `environments/roadtrip-planner.yaml` and re-run, or archive the old environment in the Console first |
| `tsc` rejects `event_deltas`, `injection_location`, or the `lib/sessions/accumulate` import | installed SDK predates the 2026-07-01 Managed Agents update | upgrade `@anthropic-ai/sdk` |
| replies arrive whole, no token-by-token rendering | the org's streaming gate is closed (`event_deltas` is silently ignored when ungated), or an older SDK's stream parser drops the `event_start` / `event_delta` events it does not recognize | confirm the org is enrolled in the update, and upgrade `@anthropic-ai/sdk` |
| picking a model 400s with "Agent must be a non-empty Agent ID or agent_reference" (or the older "Extra inputs are not permitted") | the org's gate for `agent_with_overrides` is not open yet (a closed gate rejects the selector as an unknown agent shape) | use the default model until the org is enrolled in the update |
| picking a model 400s with `model must be one of: ...` | the request named a model that is not in `src/lib/models.ts` | add it to that list. The picker and the server check share it |
| picking a model 400s with `agent_field_not_overridable` | the selector carried a key that is not overridable (the gate is open, and only `model`, `system`, `tools`, `mcp_servers`, `skills` may be overridden) | only happens if you edited the `sessions.create` call in `src/app/api/session/route.ts`: remove the extra key |
| boot screen says `No agent ID` (or environment, vault) | no `claude-lock.json` beside `package.json`: setup has not run here, or its `ant apply` stopped partway | run `./agents/setup.sh` and read its output, restart `npm run dev` |
| `./agents/setup.sh` prints `refusing to apply` | a resource in `claude-lock.json` was changed, archived, or deleted in the Console | the plan says which and why; `ant apply --force agents environments vaults` overwrites the edit or creates a replacement, then re-run setup |
| the stream, chat, or stop button answers 403 | the cookie names a session this app's planner did not create, or one that was archived | reload. `/api/session` issues a fresh one |
| events arrive only in end-of-turn bursts | a proxy is buffering the SSE response | use `next dev` directly on localhost first |
| the rail shows `session.error` `model_overloaded_error`, then the turn ends with no reply | the API was overloaded and the session's retries ran out | send the message again, or pick another model for the next trip |
| answer cites no tool calls | the agent answered from priors | the prompt demands API evidence per claim. If you weakened it, restore `agents/roadtrip-planner.md` and re-run `./agents/setup.sh` |
| itinerary arrives with no review handoff (no thread events in the rail) | the question was small enough that the prompt's "skip the review" branch applied, or the planner's roster is empty | ask for a full multi-day itinerary. Check the roster with the `ant beta:agents retrieve` call in step 2 |
| `./agents/setup.sh` 400s creating the planner, naming `multiagent` | the org is not enrolled in the Managed Agents update that ships coordinator rosters | delete the `multiagent` block in `agents/roadtrip-planner.md` for a single-agent copy until the org is enrolled |
| every NPS call 403s with header injection on | the National Park Service key itself is bad | re-run the step 1 curl from your machine |
| `session.error` `credential_host_unreachable_error` | the credential allows a host the environment's networking does not | both `allowed_hosts` lists must name the vendor host |
| the chat resets to an empty trip after a teardown | the cookie pointed at an archived session, so a fresh one was created | expected: archived sessions cannot take another message |

## Reset

```bash
./agents/teardown.sh   # archive sessions, both agents, the vault with its credentials, the environment, then remove claude-lock.json
./agents/setup.sh      # provision a fresh copy
```

Teardown interrupts a session that is still running, waits up to 20 seconds for it to go idle, and archives it. It is safe to re-run: an entry stays in `claude-lock.json` only while its archive keeps failing. If a session will not archive, the planner's entry stays too, because listing by that ID is how the next run finds the session.
