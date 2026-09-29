from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.db import get_db
from app.models import Attachment, Ticket, TicketComment, User
from app.models.enums import UserRole
from app.storage import Storage, get_storage

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Response:
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

    try:
        data = await storage.open(attachment.file_path)
    except FileNotFoundError:
        raise not_found from None

    # A hand-set Content-Disposition (not FileResponse, since GCS has no local
    # path to hand it). HTTP header values are Latin-1 only, so a non-ASCII
    # filename (an Arabic ticket attachment, an emoji, ...) can't just be
    # dropped into `filename="..."` — it has to go through the same
    # ASCII-fallback-plus-RFC-5987 `filename*=` pair FileResponse itself
    # builds, or the header encoding raises and the download 500s instead of
    # sending the file. Quotes are stripped from the fallback so they can't
    # break out of the quoted-string value.
    ascii_filename = attachment.filename.encode("ascii", "replace").decode("ascii").replace('"', "")
    encoded_filename = quote(attachment.filename)
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )
