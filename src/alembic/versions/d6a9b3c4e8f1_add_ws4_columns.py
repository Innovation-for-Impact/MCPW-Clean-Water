"""add WS4 columns: priority, legal_citation on rules; jurisdiction_scope, notes on contacts

Revision ID: d6a9b3c4e8f1
Revises: c5f8d2a1e7b3
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd6a9b3c4e8f1'
down_revision: Union[str, Sequence[str]] = 'c5f8d2a1e7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rules', sa.Column('priority', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('rules', sa.Column('legal_citation', sa.Text(), nullable=True))
    op.add_column('contacts', sa.Column('jurisdiction_scope', sa.String(50), nullable=True))
    op.add_column('contacts', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'notes')
    op.drop_column('contacts', 'jurisdiction_scope')
    op.drop_column('rules', 'legal_citation')
    op.drop_column('rules', 'priority')
