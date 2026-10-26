"""body tracking: weight, measurements, user-reported soreness

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('body_weight',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('weight_kg', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'entry_date', name='uq_body_weight_user_date')
    )
    op.create_index('ix_body_weight_user_id', 'body_weight', ['user_id'], unique=False)
    op.create_table('body_measurement',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('waist_cm', sa.Float(), nullable=True),
    sa.Column('chest_cm', sa.Float(), nullable=True),
    sa.Column('hips_cm', sa.Float(), nullable=True),
    sa.Column('biceps_cm', sa.Float(), nullable=True),
    sa.Column('thigh_cm', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'entry_date', name='uq_body_measurement_user_date')
    )
    op.create_index('ix_body_measurement_user_id', 'body_measurement', ['user_id'], unique=False)
    op.create_table('soreness_rating',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('muscle_group', sa.String(length=16), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'muscle_group', name='uq_soreness_user_group')
    )
    op.create_index('ix_soreness_rating_user_id', 'soreness_rating', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_soreness_rating_user_id', table_name='soreness_rating')
    op.drop_table('soreness_rating')
    op.drop_index('ix_body_measurement_user_id', table_name='body_measurement')
    op.drop_table('body_measurement')
    op.drop_index('ix_body_weight_user_id', table_name='body_weight')
    op.drop_table('body_weight')
