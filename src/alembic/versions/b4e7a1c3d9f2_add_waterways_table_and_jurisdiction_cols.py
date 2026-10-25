"""add waterways table and jurisdiction source columns

Revision ID: b4e7a1c3d9f2
Revises: 786cb4e495c4
Create Date: 2026-10-22 17:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4e7a1c3d9f2'
down_revision: Union[str, Sequence[str]] = '786cb4e495c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add waterways table, jurisdiction source columns, and spatial indexes."""
    # --- waterways table ---
    op.create_table(
        'waterways',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('nhd_comid', sa.BigInteger(), nullable=False),
        sa.Column('flow_direction', sa.String(length=10), nullable=True),
        sa.Column('downstream_comid', sa.BigInteger(), nullable=True),
        sa.Column(
            'geometry',
            geoalchemy2.types.Geography(
                geometry_type='LINESTRING', srid=4326, dimension=2,
                from_text='ST_GeogFromText', name='geography', nullable=False,
            ),
            nullable=False,
        ),
        sa.Column('has_beach_downstream', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_intake_downstream', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nhd_comid'),
    )

    # --- new columns on jurisdictions ---
    op.add_column('jurisdictions', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('jurisdictions', sa.Column('last_updated', sa.Date(), nullable=True))

    # --- spatial indexes ---
    op.create_index('idx_waterways_geom', 'waterways', ['geometry'], postgresql_using='gist')
    op.create_index('idx_jurisdictions_geom', 'jurisdictions', ['geometry'], postgresql_using='gist')
    op.create_index('idx_jurisdictions_layer', 'jurisdictions', ['layer'])


def downgrade() -> None:
    """Remove waterways table, jurisdiction source columns, and spatial indexes."""
    op.drop_index('idx_jurisdictions_layer', table_name='jurisdictions')
    op.drop_index('idx_jurisdictions_geom', table_name='jurisdictions')
    op.drop_index('idx_waterways_geom', table_name='waterways')
    op.drop_column('jurisdictions', 'last_updated')
    op.drop_column('jurisdictions', 'source_url')
    op.drop_table('waterways')
