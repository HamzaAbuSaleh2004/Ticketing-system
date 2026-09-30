from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    actor_id: int | None,
    action: str,
    diff: dict | None = None,
) -> None:
    """actor_id=None means the system (a worker sweep, the demo seeder) —
    never a system user row."""
    session.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            diff_json=diff,
        )
    )
