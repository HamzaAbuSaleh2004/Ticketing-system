"""Security headers on every response. Harmless on today's JSON-only API
responses (CSP only takes effect on the response that delivers the HTML
document), and load-bearing once Phase 15's unified app also serves the
SPA's index.html from this same FastAPI app."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# self plus data: images (the 2FA setup QR code is an inline SVG data URI)
# and the self-hosted fonts; MUI/emotion inject <style> tags at runtime with
# no nonce, hence style-src 'unsafe-inline' (script-src stays strict).
# font-src needs data: too: verified against the actual `npm run build`
# output (not just assumed) that @fontsource-variable's CSS inlines some
# unicode-range subsets as base64 data: URIs alongside the separate static
# .woff2 files, and 'self' alone left the console full of blocked-font
# errors (Playwright against a local static server with these exact headers).
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = _CSP
        return response
