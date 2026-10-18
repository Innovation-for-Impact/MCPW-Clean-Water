"""WS3: waterways, drains, drain_segments, response_sites tables + jurisdiction columns

Revision ID: b5d2e8f3a1c6
Revises: a3f1c9d2e7b4
Create Date: 2026-10-15 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b5d2e8f3a1c6'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d2e7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Jurisdictions: add source_url, last_updated, index on layer --
    op.add_column('jurisdictions', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('jurisdictions', sa.Column('last_updated', sa.Date(), nullable=True))
    op.create_index('idx_jurisdictions_layer', 'jurisdictions', ['layer'])

    # -- Waterways --
    op.create_table(
        'waterways',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('nhd_comid', sa.BigInteger(), unique=True, nullable=False),
        sa.Column('flow_direction', sa.String(10), nullable=True),
        sa.Column('downstream_comid', sa.BigInteger(), nullable=True, index=True),
        sa.Column('geometry', geoalchemy2.types.Geography(
            geometry_type='LINESTRING', srid=4326, from_text='ST_GeogFromText',
            name='geography'
        ), nullable=False),
        sa.Column('has_beach_downstream', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('has_intake_downstream', sa.Boolean(), server_default='false', nullable=False),
    )
    op.create_index('idx_waterways_geom', 'waterways', ['geometry'], postgresql_using='gist')

    # -- Drains --
    op.create_table(
        'drains',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('drain_id', sa.String(100), unique=True, nullable=False),
        sa.Column('drain_number', sa.String(20), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tier', sa.String(5), nullable=False),
        sa.Column('conveyance_owner', sa.String(30), nullable=False),
        sa.Column('intercounty', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('upstream_counties', sa.String(255), nullable=True),
        sa.Column('drain_district_id', sa.String(100), nullable=True),
        sa.Column('has_response_plan', sa.Boolean(), server_default='false', nullable=False),
    )

    # -- Drain segments --
    op.create_table(
        'drain_segments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('drain_id', sa.String(100), sa.ForeignKey('drains.drain_id'), nullable=False, index=True),
        sa.Column('segment_id', sa.String(100), unique=True, nullable=False),
        sa.Column('conveyance_type', sa.String(20), nullable=False),
        sa.Column('downstream_segment_id', sa.String(100), nullable=True),
        sa.Column('outlet_nhd_comid', sa.BigInteger(), nullable=True),
        sa.Column('geometry', geoalchemy2.types.Geography(
            geometry_type='LINESTRING', srid=4326, from_text='ST_GeogFromText',
            name='geography'
        ), nullable=False),
    )
    op.create_index('idx_drain_segments_geom', 'drain_segments', ['geometry'], postgresql_using='gist')

    # -- Response sites --
    op.create_table(
        'response_sites',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('drain_id', sa.String(100), sa.ForeignKey('drains.drain_id'), nullable=False, index=True),
        sa.Column('site_order', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('boom_anchor', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('access_notes', sa.Text(), nullable=True),
        sa.Column('access_contact', sa.Text(), nullable=True),
        sa.Column('plan_sheet', sa.String(20), nullable=True),
        sa.Column('geometry', geoalchemy2.types.Geography(
            geometry_type='POINT', srid=4326, from_text='ST_GeogFromText',
            name='geography'
        ), nullable=False),
    )
    op.create_unique_constraint('uq_response_site_drain_order', 'response_sites', ['drain_id', 'site_order'])
    op.create_index('idx_response_sites_geom', 'response_sites', ['geometry'], postgresql_using='gist')


def downgrade() -> None:
    op.drop_constraint('uq_response_site_drain_order', 'response_sites', type_='unique')
    op.drop_table('response_sites')
    op.drop_table('drain_segments')
    op.drop_table('drains')
    op.drop_index('idx_waterways_geom', table_name='waterways')
    op.drop_table('waterways')
    op.drop_index('idx_jurisdictions_layer', table_name='jurisdictions')
    op.drop_column('jurisdictions', 'last_updated')
    op.drop_column('jurisdictions', 'source_url')
