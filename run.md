# How to Run AMIS

## Backend

```powershell
python -m venv .venv

.\.venv\Scripts\Activate.ps1

uvicorn amis.main:app --reload
```

Backend runs at http://[IP_ADDRESS]

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

> The frontend fetches the OpenAPI schema from the backend on startup, so the backend must be running first.
