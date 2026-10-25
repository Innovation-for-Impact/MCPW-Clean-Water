"""add role constraint and performance indexes

Revision ID: c5f8d2a1e7b3
Revises: b4e7a1c3d9f2
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5f8d2a1e7b3'
down_revision: Union[str, Sequence[str]] = 'b4e7a1c3d9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user role constraint and performance indexes."""
    # CheckConstraint on users.role
    op.create_check_constraint(
        'ck_users_valid_role',
        'users',
        "role IN ('admin', 'responder', 'viewer')",
    )

    # Index on waterways.downstream_comid (used in recursive CTE joins)
    op.create_index('idx_waterways_downstream_comid', 'waterways', ['downstream_comid'])

    # Index on rules.jurisdiction_type (used in lookup queries)
    op.create_index('idx_rules_jurisdiction_type', 'rules', ['jurisdiction_type'])


def downgrade() -> None:
    """Remove constraint and indexes."""
    op.drop_index('idx_rules_jurisdiction_type', table_name='rules')
    op.drop_index('idx_waterways_downstream_comid', table_name='waterways')
    op.drop_constraint('ck_users_valid_role', 'users', type_='check')
