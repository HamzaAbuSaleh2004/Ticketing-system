"""Caps request bodies before FastAPI parses them. Multipart parsing (and so
spooling an upload to disk) happens before route dependencies such as auth
run, so without this an anonymous client could fill the disk with one
oversized upload. Counts streamed bytes, so a missing or false
Content-Length doesn't bypass it."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings

# Room for multipart boundaries and form fields around the largest file.
_OVERHEAD = 64 * 1024


class _TooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().ATTACHMENT_MAX_BYTES + _OVERHEAD
        too_large = JSONResponse({"detail": "Request body too large"}, status_code=413)

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await too_large(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await too_large(scope, receive, send)
