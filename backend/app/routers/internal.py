"""Cloud Scheduler's replacement for the worker's while-True loop in prod:
Scheduler calls this over HTTPS on a cron schedule instead. Auth is a
Google-signed OIDC token (Scheduler's own "add an OIDC token" HTTP target
option), verified two ways: the standard signature/expiry/issuer check
(`google.oauth2.id_token.verify_oauth2_token`, which raises on a forged or
expired token) and then, explicitly, that the token's audience is this exact
service and its `email` claim is the one service account allowed to call it
— so a validly-signed token for some *other* Cloud Run service can't be
replayed here."""

import logging

from fastapi import APIRouter, Header, HTTPException, status

from app.config import get_settings
from app.domain import clock
from app.worker import run_sweeps_once

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)


def _verify_scheduler_token(authorization: str | None) -> None:
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")

    # Imported lazily: these packages are only needed in prod, and importing
    # google.auth.transport.requests opens no sockets by itself, but keeping
    # it out of the module's top-level import list keeps a plain local
    # `docker compose up` from needing them installed just to boot the API
    # when nothing ever calls this endpoint.
    from google.auth import exceptions as google_exceptions
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.SWEEP_AUDIENCE
        )
    except (google_exceptions.TransportError, google_exceptions.TimeoutError) as exc:
        # Couldn't even reach Google to check the token (egress hiccup,
        # fetching its public certs timed out, ...) — the token itself is
        # neither confirmed nor refuted, so this isn't the same thing as an
        # invalid token: a 503 tells Scheduler's own retry to try again,
        # rather than logging it identically to an actual forged caller.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not verify token") from exc
    except Exception as exc:
        # verify_oauth2_token raises a plain ValueError for most failures
        # (bad signature, expired, wrong audience) and GoogleAuthError for a
        # bad issuer; either way the token itself is untrusted, so it's a 401.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if claims.get("email") != settings.SWEEP_INVOKER_EMAIL:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Unrecognised caller")


@router.post("/sweeps")
async def run_sweeps(authorization: str | None = Header(default=None)) -> dict[str, list[int]]:
    _verify_scheduler_token(authorization)
    return await run_sweeps_once(clock.now())
