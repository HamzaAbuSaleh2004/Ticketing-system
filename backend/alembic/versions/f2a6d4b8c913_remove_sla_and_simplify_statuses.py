"""remove SLA and simplify statuses

PLAN.md Phase 19: SLA tracking is removed from the product entirely (no due
dates, no pause/resume, no SLA-risk auto-escalation sweep, no SLA policy
admin tab). The 7-value ticket lifecycle collapses to 5: `new` and `triaged`
fold into `open` (the sole starting point); `in_progress`, `pending`,
`resolved` and `closed` are unchanged.

This app was deployed once already (Phase 17, to a Cloud SQL instance with
only seed/demo data — Phase 18's go-live walkthrough never ran), so this is
a new revision rather than an edit to the already-applied initial migration.

Downgrade is lossy: it restores the SLA columns/table and the wider enum,
but can't recover which of `open`/`new`/`triaged` a ticket originally was
(they're all `open` now), nor any SLA due dates or pause history.

Revision ID: f2a6d4b8c913
Revises: a0187af77fe7
Create Date: 2026-09-30 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f2a6d4b8c913'
down_revision: Union[str, None] = 'a0187af77fe7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fold new/triaged into open while the enum still allows it.
    op.execute("UPDATE tickets SET status = 'open' WHERE status IN ('new', 'triaged')")

    # Narrow the ticket_status enum from 7 values to 5: create-cast-drop-rename,
    # since Postgres can't drop enum values directly.
    op.execute("ALTER TYPE ticket_status RENAME TO ticket_status_old")
    new_status = postgresql.ENUM('open', 'in_progress', 'pending', 'resolved', 'closed', name='ticket_status')
    new_status.create(op.get_bind())
    op.execute(
        "ALTER TABLE tickets ALTER COLUMN status TYPE ticket_status USING status::text::ticket_status"
    )
    op.execute("DROP TYPE ticket_status_old")

    op.drop_column('tickets', 'sla_response_due')
    op.drop_column('tickets', 'sla_resolution_due')
    op.drop_column('tickets', 'sla_paused_at')
    op.drop_column('tickets', 'sla_paused_total_seconds')
    op.drop_table('sla_policies')


def downgrade() -> None:
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='ticket_priority'), nullable=False),
        sa.Column('response_minutes', sa.Integer(), nullable=False),
        sa.Column('resolution_minutes', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('priority'),
    )
    op.add_column('tickets', sa.Column('sla_paused_total_seconds', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('tickets', 'sla_paused_total_seconds', server_default=None)
    op.add_column('tickets', sa.Column('sla_paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('sla_resolution_due', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tickets', sa.Column('sla_response_due', sa.DateTime(timezone=True), nullable=True))

    op.execute("ALTER TYPE ticket_status RENAME TO ticket_status_new")
    old_status = postgresql.ENUM(
        'new', 'triaged', 'open', 'in_progress', 'pending', 'resolved', 'closed', name='ticket_status'
    )
    old_status.create(op.get_bind())
    op.execute(
        "ALTER TABLE tickets ALTER COLUMN status TYPE ticket_status USING status::text::ticket_status"
    )
    op.execute("DROP TYPE ticket_status_new")
