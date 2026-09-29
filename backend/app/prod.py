"""The single production entry point (Dockerfile.prod's CMD): the API,
mounted at /api exactly as the dev proxy already does (frontend/vite.config.ts
strips the same prefix), plus the built SPA served from ./static with an
index.html fallback for client-side routes. Migrations are deliberately not
run here — that's a separate Cloud Run job step (or, for prod-local, the
`migrate` one-off service in docker-compose.prod-local.yml) — so a bad
migration can't block every running instance from even booting."""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse, Response

from app.main import app as api_app
from app.security_headers import SecurityHeadersMiddleware

STATIC_DIR = (Path(__file__).resolve().parent.parent / "static").resolve()
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="Ticketing Portal")
# Security headers apply to the SPA document too (that's the whole point of
# a page-level CSP) — api_app already has its own copy for its responses.
app.add_middleware(SecurityHeadersMiddleware)
# Everything under /api goes to the existing app unchanged, prefix stripped,
# same as the dev Vite proxy — api_app's own health check stays at /api/health.
app.mount("/api", api_app)


@app.get("/{full_path:path}")
async def spa(full_path: str) -> Response:
    candidate = (STATIC_DIR / full_path).resolve() if full_path else None
    if candidate is not None and candidate.is_relative_to(STATIC_DIR) and candidate.is_file():
        # Hashed build assets (frontend/vite.config.ts's default output
        # naming) are safe to cache forever; anything else at a literal path
        # (favicon.png, the manifest) gets a short, ordinary cache instead.
        cache = "public, max-age=31536000, immutable" if full_path.startswith("assets/") else "public, max-age=3600"
        return FileResponse(candidate, headers={"Cache-Control": cache})
    # No matching file: either the SPA shell itself, or a client-side route
    # (e.g. /agent/tickets/1) that only React Router knows about — either
    # way, index.html, never cached, so a new deploy is visible immediately.
    return FileResponse(INDEX_HTML, headers={"Cache-Control": "no-cache"})
