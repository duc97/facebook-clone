"""add pg_trgm GIN indexes for user search (ILIKE optimisation)

Revision ID: 007
Revises: 006
Create Date: 2026-03-20

Why:  user_search_repo uses ILIKE '%query%' with a leading wildcard on both
      display_name and email.  A leading wildcard makes B-tree indexes
      unusable, forcing a full-table sequential scan on every search request.

Fix:  Enable the pg_trgm extension (if not already present) and add GIN
      trigram indexes on users.display_name and users.email.  The trigram
      operator class supports ILIKE / LIKE patterns at any position, turning
      those scans into fast index lookups.

Backward-compatible: the extension is created with IF NOT EXISTS; the
indexes are created with IF NOT EXISTS so this migration is safe to run
against a database that already has them.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable trigram extension — requires pg_trgm to be available on the
    # server (bundled with the default PostgreSQL contrib package).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram index on display_name — supports ILIKE '%<query>%' lookups.
    # GIN is preferred over GiST here because it has faster reads (at the cost
    # of slightly slower writes), which matches the read-heavy search workload.
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_display_name_trgm
        ON users
        USING gin (display_name gin_trgm_ops)
        """
    )

    # GIN trigram index on email for email-based substring searches.
    op.execute(
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_email_trgm
        ON users
        USING gin (email gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_display_name_trgm")
    # We intentionally do NOT drop the pg_trgm extension on downgrade —
    # other migrations or application code may already depend on it.
