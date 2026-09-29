"""attachment file_path relative to attachments dir

Revision ID: a0187af77fe7
Revises: 21bb89cebd7d
Create Date: 2026-09-29 15:51:41.664032

Data-only: no column/type change. `attachments.file_path` held an absolute
path under ATTACHMENTS_DIR; Phase 16's Storage protocol treats it as a
backend-relative key instead (so the same column works unchanged for the
GCS backend, whose keys were never absolute paths to begin with). Rows
already written with an absolute path under the *current* ATTACHMENTS_DIR
get that prefix stripped; anything else (already relative, or under some
other historical directory) is left as-is rather than guessed at.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import get_settings

# revision identifiers, used by Alembic.
revision: str = 'a0187af77fe7'
down_revision: Union[str, None] = '21bb89cebd7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    base = get_settings().ATTACHMENTS_DIR.rstrip("/") + "/"
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE attachments SET file_path = substring(file_path from CAST(:n AS integer)) "
            "WHERE file_path LIKE :pattern"
        ),
        {"n": len(base) + 1, "pattern": base + "%"},
    )


def downgrade() -> None:
    base = get_settings().ATTACHMENTS_DIR.rstrip("/") + "/"
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE attachments SET file_path = :base || file_path "
            "WHERE file_path NOT LIKE '/%'"
        ),
        {"base": base},
    )
