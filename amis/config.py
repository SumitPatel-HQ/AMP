"""Runtime configuration read from the environment.

No setting here is required: the core workflow and the whole test
suite run with nothing set, backed by in-memory repositories. Setting
``AMIS_DATABASE_URL`` is what switches the REST API over to PostgreSQL.
"""

from __future__ import annotations

import os

DATABASE_URL_ENV_VAR = "AMIS_DATABASE_URL"


def get_database_url() -> str | None:
    return os.environ.get(DATABASE_URL_ENV_VAR) or None
