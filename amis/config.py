"""Runtime configuration read from the environment.

No setting here is required: the core workflow and the whole test
suite run with nothing set, backed by in-memory repositories. Setting
``AMIS_DATABASE_URL`` is what switches the REST API over to PostgreSQL.
"""

from __future__ import annotations

import os

DATABASE_URL_ENV_VAR = "AMIS_DATABASE_URL"
CORS_ALLOWED_ORIGINS_ENV_VAR = "AMIS_CORS_ALLOWED_ORIGINS"
DEFAULT_CORS_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
DEFAULT_CORS_ALLOWED_ORIGIN_REGEX = (
    r"^http://(?:localhost|127\.0\.0\.1):\d+$"
)


def get_database_url() -> str | None:
    return os.environ.get(DATABASE_URL_ENV_VAR) or None


def get_cors_allowed_origins() -> tuple[str, ...]:
    raw = os.environ.get(CORS_ALLOWED_ORIGINS_ENV_VAR)
    if raw is None:
        return DEFAULT_CORS_ALLOWED_ORIGINS
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def get_cors_allowed_origin_regex() -> str | None:
    if CORS_ALLOWED_ORIGINS_ENV_VAR in os.environ:
        return None
    return DEFAULT_CORS_ALLOWED_ORIGIN_REGEX
