"""add on-chain verification fields for crypto top ups

Revision ID: 0005_top_up_crypto_chain_verification_fields
Revises: 0004_top_up_bybit_sender_uid
Create Date: 2026-03-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_top_up_crypto_chain_verification_fields"
down_revision: Union[str, None] = "0004_top_up_bybit_sender_uid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("top_up_requests", sa.Column("requested_network", sa.String(length=32), nullable=True))
    op.add_column("top_up_requests", sa.Column("requested_token", sa.String(length=64), nullable=True))
    op.add_column("top_up_requests", sa.Column("verified_tx_hash", sa.String(length=255), nullable=True))
    op.add_column("top_up_requests", sa.Column("verified_network", sa.String(length=32), nullable=True))
    op.add_column("top_up_requests", sa.Column("verified_token", sa.String(length=64), nullable=True))
    op.add_column("top_up_requests", sa.Column("verified_amount", sa.Numeric(precision=20, scale=8), nullable=True))
    op.add_column("top_up_requests", sa.Column("verified_recipient", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("top_up_requests", "verified_recipient")
    op.drop_column("top_up_requests", "verified_amount")
    op.drop_column("top_up_requests", "verified_token")
    op.drop_column("top_up_requests", "verified_network")
    op.drop_column("top_up_requests", "verified_tx_hash")
    op.drop_column("top_up_requests", "requested_token")
    op.drop_column("top_up_requests", "requested_network")
