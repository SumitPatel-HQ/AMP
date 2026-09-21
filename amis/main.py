"""ASGI entrypoint: ``uvicorn amis.main:app``.

Wires PostgreSQL behind the repository protocols when
``AMIS_DATABASE_URL`` is set (see amis/config.py and amis/db/), and
falls back to the in-memory repositories otherwise, so the core
workflow and the test suite still need no database and no API key.
Run the Alembic migrations against the target database before
starting this: see migrations/README.md.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import create_engine

from amis.api import create_app
from amis.config import get_database_url


def build_app() -> FastAPI:
    database_url = get_database_url()
    if database_url is None:
        return create_app()

    from amis.db import build_repositories

    engine = create_engine(database_url)
    return create_app(build_repositories(engine))


app = build_app()
