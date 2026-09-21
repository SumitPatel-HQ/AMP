"""PostgreSQL-backed persistence: the same protocols, a different storage.

Nothing above the repository boundary depends on this package. See
amis/repositories.py for the protocols these tables and repositories
implement, and docs/adr/0005 for why plan ids carry the scenario id.
"""

from amis.db.repositories import build_repositories

__all__ = ["build_repositories"]
