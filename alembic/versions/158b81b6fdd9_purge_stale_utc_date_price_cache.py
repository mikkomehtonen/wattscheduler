"""purge stale utc-date price cache

Revision ID: 158b81b6fdd9
Revises: 85b2dda37215
Create Date: 2026-07-01 16:41:00.466258

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '158b81b6fdd9'
down_revision: Union[str, Sequence[str], None] = '85b2dda37215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Purge stale UTC-date keyed price cache.

    CachedPriceProvider now keys buckets by Europe/Helsinki calendar date.
    Old rows keyed by UTC date are orphaned and must be removed so the cache
    repopulates with complete Helsinki-day buckets on the next request.
    """
    op.execute("DELETE FROM price_points")


def downgrade() -> None:
    """Downgrade schema."""
    # Cache data is regenerable from the Spot-Hinta API and cannot be restored.
    pass
