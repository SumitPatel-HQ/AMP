# How to Run AMIS

## Backend

```powershell
cd D:\LearningHub\CollegeProjects\AMP
.\.venv\Scripts\Activate.ps1
uvicorn amis.main:app --reload
```

Backend runs at http://127.0.0.1:8000

## Frontend

In a separate terminal:

```powershell
cd D:\LearningHub\CollegeProjects\AMP\frontend
npm install   # first time only
npm run dev
```

Frontend runs at http://localhost:5173

> The frontend fetches the OpenAPI schema from the backend on startup, so the backend must be running first.
