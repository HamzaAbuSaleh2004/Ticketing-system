"""restore SLA, per-organisation

PLAN.md Phase 22: SLA tracking is restored (Phase 19 removed it), with one
real change over the old design — an organisation can override its own
response/resolution minutes per priority; a ticket with no override uses the
same global defaults as before. `pending`'s pause semantics are unaffected:
it already exists post-Phase-19, so this only re-adds the ticket columns
that `enter_pending`/`leave_pending` write to.

`sla_policies` gains a nullable `organization_id`. A plain
UNIQUE(organization_id, priority) wouldn't stop duplicate global-default
rows, since Postgres treats every NULL as distinct — two partial unique
indexes instead: one default per priority, one override per (organisation,
priority).

Revision ID: b7c9a1d34e56
Revises: a3d8e6f1b207
Create Date: 2026-09-30 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7c9a1d34e56'
down_revision: Union[str, None] = 'a3d8e6f1b207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ticket_priority already exists (created by the initial migration for
    # tickets.priority, and never dropped) - reference it, don't recreate it.
    ticket_priority = postgresql.ENUM(
        'low', 'normal', 'high', 'urgent', name='ticket_priority', create_type=False
    )
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('priority', ticket_priority, nullable=False),
        sa.Column('response_minutes', sa.Integer(), nullable=False),
        sa.Column('resolution_minutes', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_sla_policies_organization_id'), 'sla_policies', ['organization_id'], unique=False
    )
    op.create_index(
        'uq_sla_policies_global_priority', 'sla_policies', ['priority'],
        unique=True, postgresql_where=sa.text('organization_id IS NULL'),
    )
    op.create_index(
        'uq_sla_policies_org_priority', 'sla_policies', ['organization_id', 'priority'],
        unique=True, postgresql_where=sa.text('organization_id IS NOT NULL'),
    )

    op.add_column('tickets', sa.Column('sla_response_due', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('sla_resolution_due', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('sla_paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('sla_paused_total_seconds', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('tickets', 'sla_paused_total_seconds', server_default=None)


def downgrade() -> None:
    op.drop_column('tickets', 'sla_paused_total_seconds')
    op.drop_column('tickets', 'sla_paused_at')
    op.drop_column('tickets', 'sla_resolution_due')
    op.drop_column('tickets', 'sla_response_due')

    op.drop_index('uq_sla_policies_org_priority', table_name='sla_policies')
    op.drop_index('uq_sla_policies_global_priority', table_name='sla_policies')
    op.drop_index(op.f('ix_sla_policies_organization_id'), table_name='sla_policies')
    op.drop_table('sla_policies')
