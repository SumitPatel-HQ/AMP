# AMIS mission dashboard

The dashboard loads the canonical demo scenario, creates its initial mission plan, and shows the plan beside the current mission state. It uses Vite, React, TypeScript, Tailwind CSS, and a `vis-timeline` mission timeline.

The mission map draws on a MapLibre GL vector basemap with a deck.gl overlay for targets, the plan sequence, event rings, and the satellite position inferred from the plan. The basemap loads OpenFreeMap's dark style, falls back to CARTO Dark Matter, and finally to an offline land outline bundled with the app, so the map still draws without network access. MapLibre and deck.gl load lazily when the map mounts. The map needs WebGL.

## Run locally

Start the API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn amis.main:app --reload
```

Then start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend uses `http://127.0.0.1:8000` by default. Copy `.env.example` to `.env` to set a different API URL. `npm run dev` regenerates the API types before Vite starts.

## Generate API types

With the API running, regenerate `src/api/schema.ts` from its live OpenAPI document:

```powershell
npm run generate:api
```

Set `AMIS_API_URL` if the API is not running at the default address. `npm run build` also regenerates the file before typechecking. Application types come from the generated file. Do not edit it by hand.

## Checks

```powershell
npm test
npm run lint
npm run build
```

From the repository root, `docker compose up --build` starts PostgreSQL, the API at port 8000, and the dashboard at port 8080.
