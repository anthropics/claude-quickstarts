# HRCore Platform

Production-grade rebuild of the HR platform originally prototyped in
`hr-app/mvp`. See `hr-app/SPECIFICATION.md` / `hr-app/SPRINT_BACKLOG.md` for
the full product spec, `docs/adr/0001-stack-decisions.md` for why this stack
was chosen, and the root `hr-app/README.md` (written in M11) for an accurate,
phase-by-phase status of what's built vs. pending.

## Structure

- `apps/web` — Next.js 15 web app
- `apps/api` — Fastify API
- `apps/mobile` — Expo/React Native mobile app
- `packages/db` — Drizzle schema, migrations, multi-tenant provisioning
- `packages/ui` — shared design system
- `packages/config` — shared TypeScript/ESLint config

## Local development

```bash
cp .env.example .env   # fill in real values as they become available
docker compose up -d postgres redis   # or run local Postgres 16 / Redis directly
npm install
npm run db:migrate
npm run db:seed
npm run dev
```

## Commands

- `npm run build` / `npm run lint` / `npm run typecheck` / `npm run test` — run across every workspace via Turborepo
- `npm run db:generate` / `npm run db:migrate` / `npm run db:seed` — data layer tasks (see `packages/db`)
