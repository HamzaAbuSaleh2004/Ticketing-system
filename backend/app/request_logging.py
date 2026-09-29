"""One JSON line per request, so Cloud Logging (which parses stdout/stderr as
JSON when the container writes valid JSON lines) can filter and query them.
Never logs tokens, codes or passwords: only method, path, status, latency
and the caller's user id (set by `current_user`, never decoded here)."""

import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            # An unhandled exception downstream is exactly the request most
            # worth a log line for, and call_next re-raises it before this
            # middleware would otherwise ever get to log — so this runs on
            # every exit, not just the success path.
            latency_ms = round((time.monotonic() - started) * 1000, 1)
            logger.info(
                json.dumps(
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "latency_ms": latency_ms,
                        "user_id": getattr(request.state, "user_id", None),
                    }
                )
            )
