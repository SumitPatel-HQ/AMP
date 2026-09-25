# How to Run AMIS

## Backend

```powershell
cd D:\LearningHub\CollegeProjects\AMP
.\.venv\Scripts\Activate.ps1
uvicorn amis.main:app --reload
```

Backend runs at http://127.0.0.1:8000

The backend reads its orbital catalogue and Sun ephemeris from `amis/data`. It does not fetch them while serving requests. `GET /examples` includes a four-day orbital mission near the bundled 2026-09-25 element epoch. New orbital missions must stay within 14 days of their element epoch and, when daylight filtering is enabled, inside the ephemeris excerpt (2026-09-20 through 2026-10-15).

To refresh the developer catalogue, run `python -m scripts.fetch_orbital_elements` from the repository root. Review the dated JSON and manifest hashes before committing them. The published orbit is real; pointing and resource settings are assumptions for a hypothetical agile imager.

## Frontend

In a separate terminal:

```powershell
cd D:\LearningHub\CollegeProjects\AMP\frontend
npm install   # first time only
npm run dev
```

Frontend runs at http://localhost:5173

> The frontend fetches the OpenAPI schema from the backend on startup, so the backend must be running first.
