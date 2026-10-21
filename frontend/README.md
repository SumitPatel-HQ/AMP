# AMIS Mission Dashboard

Web-based mission control console for the AMIS satellite planning simulator.

## Tech Stack

- **Framework**: React 19, TypeScript, Vite 8
- **Styling**: Tailwind CSS v4
- **Visualization**: MapLibre GL + deck.gl (WebGL orbit tracking & targets)
- **Timeline**: vis-timeline (Gantt-style satellite schedule)
- **API Client**: openapi-fetch (auto-generated typed client from FastAPI backend)
- **Testing & Quality**: Vitest, React Testing Library, Oxlint

---

## Getting Started

> **Prerequisite**: Start the backend first (`uvicorn amis.main:app`) so OpenAPI types can be generated.

```powershell
cd frontend
npm install
npm run dev
```

Dashboard runs at: `http://localhost:5173`

---

## Configuration (`.env`)

Copy `.env.example` to `.env` to customize the backend URL:

```env
VITE_AMIS_API_URL=http://127.0.0.1:8000
```

---

## Available Scripts

| Command | Action |
| :--- | :--- |
| `npm run dev` | Auto-generates API types and starts Vite dev server |
| `npm run build` | Regenerates API types, typechecks, and builds to `/dist` |
| `npm run generate:api` | Manually regenerates `src/api/schema.ts` from `/openapi.json` |
| `npm test` | Runs unit/integration test suite with Vitest |
| `npm run lint` | Runs fast code quality checks using Oxlint |
| `npm run preview` | Locally previews production build |

---

## Docker

Build and run with Nginx:

```powershell
# Run just the frontend container (:8080)
docker compose up --build web
```
