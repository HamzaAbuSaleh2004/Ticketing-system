"""ticket collaborators

PLAN.md Phase 20: a ticket can have multiple agents. `tickets.assignee_id`
stays the single primary owner (escalation, least-loaded-senior assignment,
the active-ticket load count, and audit diffs all key off it alone,
unchanged). This adds `ticket_collaborators`, a many-to-many join table for
any number of additional agents who can see and work the ticket alongside
the primary, with no effect on escalation or load-balancing.

Revision ID: a3d8e6f1b207
Revises: f2a6d4b8c913
Create Date: 2026-09-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3d8e6f1b207'
down_revision: Union[str, None] = 'f2a6d4b8c913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ticket_collaborators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticket_id', 'user_id', name='uq_ticket_collaborators_ticket_user'),
    )
    op.create_index(op.f('ix_ticket_collaborators_ticket_id'), 'ticket_collaborators', ['ticket_id'], unique=False)
    op.create_index(op.f('ix_ticket_collaborators_user_id'), 'ticket_collaborators', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ticket_collaborators_user_id'), table_name='ticket_collaborators')
    op.drop_index(op.f('ix_ticket_collaborators_ticket_id'), table_name='ticket_collaborators')
    op.drop_table('ticket_collaborators')
