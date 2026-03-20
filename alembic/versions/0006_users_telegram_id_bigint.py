"""ensure users.telegram_id uses bigint for PostgreSQL

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "users",
            "telegram_id",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            postgresql_using="telegram_id::bigint",
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "users",
            "telegram_id",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            postgresql_using="telegram_id::integer",
            existing_nullable=False,
        )
