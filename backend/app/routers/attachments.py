from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.config import get_settings
from app.db import get_db
from app.models import Attachment, Ticket, TicketComment, User
from app.models.enums import UserRole

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    row = (
        await session.execute(
            select(Attachment, Ticket.requester_id, TicketComment.is_internal_note)
            .join(Ticket, Ticket.id == Attachment.ticket_id)
            .outerjoin(TicketComment, TicketComment.id == Attachment.comment_id)
            .where(Attachment.id == attachment_id)
        )
    ).first()
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    if row is None:
        raise not_found
    attachment, requester_id, is_internal_note = row
    # Same scoping as the ticket detail: an end user only sees their own
    # tickets, and never an internal note's attachments. 404, not 403.
    if user.role == UserRole.end_user and (requester_id != user.id or is_internal_note):
        raise not_found

    path = Path(attachment.file_path).resolve()
    if not path.is_relative_to(Path(get_settings().ATTACHMENTS_DIR).resolve()) or not path.is_file():
        raise not_found
    # FileResponse with a filename sends Content-Disposition: attachment, so
    # the browser downloads instead of rendering (no inline HTML/PDF from us).
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )
