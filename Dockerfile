FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY amis ./amis
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir ".[postgres]"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn amis.main:app --host 0.0.0.0 --port 8000"]
