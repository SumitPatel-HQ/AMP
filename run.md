# How to Run AMIS

AMIS can run in two modes:
1. **In-Memory Mode (Default)**: No database required. All state is kept in memory (great for quick testing and local development).
2. **PostgreSQL Mode**: Uses PostgreSQL for persistent storage and Alembic for database migrations.

---

## 1. Database Setup (PostgreSQL & Migrations)

> *Skip this step if you want to run the backend in in-memory mode without a database.*

### A. Start PostgreSQL

#### Option 1: Using Docker (Recommended)
Start just the PostgreSQL container:
```powershell
docker compose up -d db
```
This runs PostgreSQL on `localhost:5432` with username `amis`, password `amis`, and database `amis`.

#### Option 2: Using Local PostgreSQL
If you have PostgreSQL installed on your machine, create a database and user:
```sql
CREATE USER amis WITH PASSWORD 'amis';
CREATE DATABASE amis OWNER amis;
```

---

### B. Install Database Dependencies

Activate your virtual environment and install the PostgreSQL driver:
```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[postgres]"
```

---

### C. Set Environment Variable & Run Database Migrations

Set the database connection string and apply all Alembic migrations to update the schema:

```powershell
# Set database connection URL
$env:AMIS_DATABASE_URL = "postgresql+psycopg2://amis:amis@localhost:5432/amis"

# Apply all migrations to the latest version
alembic upgrade head
```

#### Useful Database Migration Commands:
- Check current database version:
  ```powershell
  alembic current
  ```
- Rollback one migration:
  ```powershell
  alembic downgrade -1
  ```
- Generate a new migration after model changes:
  ```powershell
  alembic revision --autogenerate -m "description_of_changes"
  ```

---

## 2. Backend

```powershell
python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -e .

# (Optional: set if using PostgreSQL)
# $env:AMIS_DATABASE_URL = "postgresql+psycopg2://amis:amis@localhost:5432/amis"

uvicorn amis.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000` (API docs available at `http://localhost:8000/docs`).

---

## 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

> **Note**: The frontend fetches the OpenAPI schema from the backend on startup, so the backend must be running first.

---

## 4. Run Everything with Docker (Alternative)

To build and start the database, backend, and frontend all together:
```powershell
docker compose up --build
```
- Web UI: `http://localhost:8080`
- API & Docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
