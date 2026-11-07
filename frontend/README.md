# Imbalance price forecast: web viewer

Next.js 16 (App Router), React 19, TypeScript, Recharts, Tailwind 4. Shows the forecast files made by `backend/`.

## Run

```
npm install
npm run dev        # http://localhost:5173
npm test           # Vitest + jsdom
npm run lint       # ESLint, 0 warnings allowed
npm run typecheck
npm run build
```

The forecast files are read from `public/data/` (git-ignored; made by `cd backend && uv run scripts/export_web_data.py`).

## Settings (one `.env` file in the repository root, template `../.env.example`)

- `NEXT_PUBLIC_HIDE_HARNESS`: `true` or `1` removes the Harness tab, panel and the `/harness-api` proxy. Default: shown.
- `NEXT_PUBLIC_DATA_BASE_URL`: where the data JSON is served from. Default `/data`. An external URL must allow cross-origin GET.

Both are inlined at build time: change them, then rebuild or redeploy.

## Folders

- `src/app`: layout and page.
- `src/features/forecast`: the viewer (components, hooks, lib).
- `src/features/harness`: the Harness tab; talks to the local Python server through the `/harness-api` rewrite in `next.config.ts`.
- `src/lib`: shared helpers (`config.ts` for the settings above).
- `src/design-system`: copied design components.
- `test/`: Vitest tests.

## Deploy (GitHub -> Vercel)

Import the repo in Vercel with Root Directory `frontend` and Framework Preset Next.js. Set `NEXT_PUBLIC_HIDE_HARNESS=true`
(and `NEXT_PUBLIC_DATA_BASE_URL` if the data is hosted elsewhere). The data files are not in git (licence), so without a data URL
the hosted page shows a "could not load the forecast" message.
