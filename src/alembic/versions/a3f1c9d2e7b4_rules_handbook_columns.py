"""rules: priority, citation, handbook and drain-context columns

Revision ID: a3f1c9d2e7b4
Revises: 786cb4e495c4
Create Date: 2026-10-15 18:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d2e7b4'
down_revision: Union[str, Sequence[str], None] = '786cb4e495c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    sa.Column('legal_citation', sa.Text(), nullable=True),
    sa.Column('priority', sa.Integer(), server_default='100', nullable=False),
    sa.Column('drain_tier', sa.String(length=5), nullable=True),
    sa.Column('drain_id', sa.String(length=100), nullable=True),
    sa.Column('conveyance_owner', sa.String(length=30), nullable=True),
    sa.Column('conveyance_type', sa.String(length=20), nullable=True),
    sa.Column('hazard_class', sa.String(length=30), nullable=True),
    sa.Column('after_hours', sa.Boolean(), nullable=True),
    sa.Column('immediate_threat', sa.Boolean(), nullable=True),
    sa.Column('action_type', sa.String(length=20), server_default='notify', nullable=False),
    sa.Column('action', sa.Text(), nullable=True),
    sa.Column('handbook_ref', sa.String(length=50), nullable=True),
]


def upgrade() -> None:
    """Upgrade schema."""
    for col in _COLUMNS:
        op.add_column('rules', col)


def downgrade() -> None:
    """Downgrade schema."""
    for col in reversed(_COLUMNS):
        op.drop_column('rules', col.name)
