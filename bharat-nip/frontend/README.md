# BNIP frontend

Next.js (App Router) + React + TypeScript + Tailwind CSS v4, following shadcn/ui conventions.

```bash
cp .env.example .env.local   # BNIP_API_URL points at the FastAPI backend
npm install
npm run dev                  # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

Phase 0 shows live backend readiness only. Product screens arrive in Phase 2
(see ../ROADMAP.md). React Flow and Recharts are added in the phases that use them.

shadcn/ui: `components.json` is configured, so `npx shadcn add <component>` works
wherever ui.shadcn.com is reachable. The Phase 0 `badge` and `card` components were
written by hand to the same conventions, because the registry was unreachable from
the build sandbox.

`AGENTS.md` is maintained by Next.js itself; keep it committed.
