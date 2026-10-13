"""Unique constraint company_id and internal_id

Revision ID: c3f89e41b212
Revises: 617cdc1ada8d
Create Date: 2026-10-13 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f89e41b212"
down_revision: str | Sequence[str] | None = "617cdc1ada8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: replace global internal_id unique constraint with compound (company_id, internal_id)."""
    with op.batch_alter_table("expeditions", schema=None) as batch_op:
        batch_op.drop_index("ix_expeditions_internal_id")
        batch_op.create_index(
            "ix_expeditions_internal_id", ["internal_id"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_expeditions_company_internal_id", ["company_id", "internal_id"]
        )


def downgrade() -> None:
    """Downgrade schema: restore global internal_id unique constraint."""
    with op.batch_alter_table("expeditions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_expeditions_company_internal_id", type_="unique")
        batch_op.drop_index("ix_expeditions_internal_id")
        batch_op.create_index(
            "ix_expeditions_internal_id", ["internal_id"], unique=True
        )
