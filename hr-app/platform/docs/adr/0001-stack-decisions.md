# ADR 0001: Production Stack Decisions

Date: 2026-07-19
Status: Accepted

## Context

`hr-app/mvp` (PR #1) shipped a working single-process Next.js 14 + SQLite MVP
covering Phases 1-3 of `hr-app/SPECIFICATION.md`. It is being promoted to a
production-billed application and extended to all 6 phases of the spec. The
spec (§3) called for a specific stack that the MVP deliberately simplified
away from to move fast. This ADR records the decisions made in adopting the
originally-specified stack for `hr-app/platform`.

## Decisions

| Layer | Choice | Rationale |
|---|---|---|
| Monorepo | Turborepo, `apps/{web,api,mobile}` + `packages/{db,ui,config}` | Matches spec S1-1 exactly; lets web/api/mobile share the db and UI packages without publishing. |
| Database | PostgreSQL 16, schema-per-tenant (`platform` + `tenant_<id>`) | Matches spec §3.3. Schema-per-tenant gives strong isolation with simpler backup/restore-per-tenant than row-per-tenant, at the cost of per-tenant migration fan-out (mitigated by the migration runner in `packages/db`). |
| ORM | Drizzle | Spec left Drizzle vs. Prisma open (S1-10). Drizzle chosen for first-class raw SQL escape hatches, which the tenant-provisioning script and RLS policy definitions need. |
| Auth | Clerk | Matches spec S1-5/S1-6. Replaces the MVP's hand-rolled JWT+cookie system, which had two known issues (a duplicated dev-secret fallback across `auth.ts`/`session.ts`, and uniform demo passwords in seed data) — both are eliminated by construction since Clerk owns credential issuance and MFA. |
| RBAC | 8 base roles (spec §3.4) + custom roles/permissions | Replaces the MVP's flat 4-role (`admin`/`hr`/`manager`/`employee`) ad hoc per-route checks. |
| API framework | Fastify + Zod (`fastify-type-provider-zod`) | Matches spec S1-9. Zod schemas are a mechanical port of the MVP's hand-rolled `_lib/validation.ts` files, which already returned Zod-shaped discriminated unions. |
| Jobs | BullMQ + Redis | Matches spec. Replaces `lib/jobs.ts`'s in-process `setInterval` scheduler; the MVP's `job_runs(job_name, period_key)` idempotency table maps directly onto BullMQ repeatable-job dedup keys. |
| File storage | S3 (`@aws-sdk/client-s3`, presigned URLs) | Matches spec. The MVP's `lib/uploads.ts` already documented itself as "swap the fs calls for S3/R2 later without touching callers" — the `saveUpload`/`readStoredFile` interface is preserved. |
| Search | Adapter interface; Postgres full-text search (default) + Meilisearch (optional) | Spec calls for Meilisearch (S2-11). No Meilisearch binary is available in the current build sandbox and no fetch path is guaranteed, so the default adapter uses Postgres `tsvector`/`tsquery` (zero extra infra) and a Meilisearch adapter is implemented behind the same interface, selected via `SEARCH_PROVIDER` env var, for environments that provision it. |
| Mobile | Expo (managed workflow) | Resolves spec open question #3 (S1-11: "Expo managed vs bare workflow"). Managed workflow chosen — the Phase 5 feature set (biometric unlock, GPS/geofence, push, camera, offline cache) is fully supported by Expo SDK 52 without ejecting, and it removes native build maintenance burden. |
| AI | Anthropic Claude API — `claude-fable-5` (complex reasoning) and `claude-haiku-4-5` (high-volume) | Matches spec Module 20 exactly. |
| CI/CD | GitHub Actions (`.github/workflows/hr-app-platform-ci.yaml`) + Docker Compose for local dev | Matches spec. Kubernetes manifests are added in M10 (Phase 6 launch-readiness) as artifacts; no live cluster is provisioned by this build. |

## Known sandbox constraints

This monorepo is being built inside a sandboxed session with no live Clerk
app, AWS account, managed Postgres, Slack/Teams app registration, DocuSign
account, Okta/Azure AD tenant, or Kubernetes cluster. Every external-provider
integration is written as complete, real code behind an env-configured
provider interface (see each integration's `.env.example` entries), but is
**not verified against the live third-party service** until real credentials
are supplied. Local Postgres 16 and Redis run in-container for dev/test via
`docker-compose.yml`. This is tracked per-module in the milestone status
table in `hr-app/README.md`.

## Consequences

- Every module from the MVP needs porting (schema, validation, business
  logic, routes, UI) rather than a lift-and-shift — the MVP's engines
  (payroll, leave, time, performance) port nearly verbatim since they were
  already framework-free pure functions with unit tests; everything else
  (auth, routing, UI, validation wiring) is rewritten against the new stack.
- The MVP (`hr-app/mvp`) is retained, untouched, as a historical/reference
  implementation and is superseded by `hr-app/platform` going forward.
