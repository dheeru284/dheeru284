# BNIP frontend

Next.js (App Router) + React + TypeScript + Tailwind CSS v4, following shadcn/ui conventions.

```bash
cp .env.example .env.local   # BNIP_API_URL points at the FastAPI backend
npm install
npm run dev                  # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

Pages: `/login`, `/submit` (all submission types), `/submissions/[id]`, `/claims`, `/claims/[id]`
(fact-check result, evidence, critic, searches, stages, audit trail, review form) and `/review`.
Data is fetched server-side with the user's JWT from an httpOnly cookie; mutations are server
actions (`src/app/actions.ts`). React Flow and Recharts arrive in the phases that use them.

shadcn/ui: `components.json` is configured, so `npx shadcn add <component>` works
wherever ui.shadcn.com is reachable. The UI components in `src/components/ui` were
written by hand to the same conventions, because the registry was unreachable from
the build sandbox.

`AGENTS.md` is maintained by Next.js itself; keep it committed.
