"""Sign-in is two steps for every account: the password (login/register)
returns a short-lived mfa token, and only a second factor turns that into
an access token. First sign-in enrols an authenticator app."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import mfa
from app.auth.dependencies import current_user, require_role
from app.auth.security import (
    hash_password,
    password_exceeds_limit,
    verify_password_timing_safe,
)
from app.auth.tokens import (
    TokenError,
    create_access_token,
    create_mfa_token,
    decode_mfa_token,
)
from app.config import get_settings
from app.db import get_db
from app.domain import clock
from app.domain.audit import write_audit
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import (
    LoginRequest,
    MfaChallenge,
    MfaCodeRequest,
    MfaEnabledResponse,
    MfaSetupResponse,
    MfaTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_BAD_MFA_TOKEN = HTTPException(
    status.HTTP_401_UNAUTHORIZED, detail="Your sign-in expired. Enter your email and password again."
)


def _challenge(user: User) -> MfaChallenge:
    return MfaChallenge(
        mfa_token=create_mfa_token(user_id=user.id),
        mfa="verify" if user.totp_enabled_at is not None else "enroll",
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id=user.id, role=user.role), user=UserOut.model_validate(user)
    )


async def _user_for_mfa_token(session: AsyncSession, token: str) -> User:
    """The token's user, row-locked so concurrent guesses are counted one at
    a time, and refused while locked out."""
    try:
        payload = decode_mfa_token(token)
    except TokenError as exc:
        raise _BAD_MFA_TOKEN from exc
    user = await session.scalar(select(User).where(User.id == int(payload["sub"])).with_for_update())
    if user is None:
        raise _BAD_MFA_TOKEN
    if user.mfa_locked_until is not None and user.mfa_locked_until > clock.now():
        await session.commit()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many wrong codes. Wait {get_settings().MFA_LOCKOUT_MINUTES} minutes, then try again.",
        )
    return user


async def _wrong_code(session: AsyncSession, user: User) -> HTTPException:
    settings = get_settings()
    user.mfa_failed_attempts += 1
    if user.mfa_failed_attempts >= settings.MFA_MAX_FAILED_ATTEMPTS:
        user.mfa_failed_attempts = 0
        user.mfa_locked_until = clock.now() + timedelta(minutes=settings.MFA_LOCKOUT_MINUTES)
    await session.commit()
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="That code isn't right. Try the current one.")


async def _wrong_setup_code(session: AsyncSession) -> HTTPException:
    """/2fa/enable's wrong-code path never counts towards the lockout: the
    account isn't enrolled yet, so nobody who reaches this endpoint could
    instead just enrol their own device with a fresh secret (no code
    guessing needed), and locking a real user out here has no self-service
    recovery (re-registering the same email 409s)."""
    await session.commit()
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail="That code isn't right. Try the current one.")


def _accept_code(user: User, step: int | None = None) -> None:
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    if step is not None:
        user.totp_last_step = step


@router.post("/register", response_model=MfaChallenge, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)) -> MfaChallenge:
    # Public registration always creates an end_user; agent/admin accounts are
    # provisioned by an admin, never through this endpoint.
    user = User(
        email=body.email,
        name=body.name,
        role=UserRole.end_user,
        team=None,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # The unique constraint is the real guard against two concurrent
        # registrations for one email; answer 409, not 500.
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    await session.refresh(user)
    return _challenge(user)


@router.post("/login", response_model=MfaChallenge)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> MfaChallenge:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    # bcrypt raises ValueError past 72 bytes rather than just comparing
    # wrong; no real password is this long, so reject without hashing.
    if password_exceeds_limit(body.password):
        raise invalid

    user = await session.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password_timing_safe(body.password, user.password_hash if user else None)
    if user is None or not password_ok:
        raise invalid
    return _challenge(user)


@router.post("/2fa/setup", response_model=MfaSetupResponse)
async def setup_2fa(body: MfaTokenRequest, session: AsyncSession = Depends(get_db)) -> MfaSetupResponse:
    """A fresh secret for an account that hasn't enrolled yet. Refused once
    2FA is on, so a stolen password can't re-enrol someone's account."""
    user = await _user_for_mfa_token(session, body.mfa_token)
    if user.totp_enabled_at is not None:
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Two-step verification is already set up")
    user.totp_secret = mfa.new_secret()
    await session.commit()
    uri = mfa.provisioning_uri(user.totp_secret, email=user.email, issuer=get_settings().TOTP_ISSUER)
    return MfaSetupResponse(secret=user.totp_secret, otpauth_uri=uri, qr_svg_data_uri=mfa.qr_svg_data_uri(uri))


@router.post("/2fa/enable", response_model=MfaEnabledResponse)
async def enable_2fa(body: MfaCodeRequest, session: AsyncSession = Depends(get_db)) -> MfaEnabledResponse:
    user = await _user_for_mfa_token(session, body.mfa_token)
    if user.totp_enabled_at is not None:
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Two-step verification is already set up")
    if user.totp_secret is None:
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Start two-step verification setup first")

    step = mfa.match_totp(user.totp_secret, body.code, last_step=user.totp_last_step)
    if step is None:
        raise await _wrong_setup_code(session)

    _accept_code(user, step)
    # Real time, not domain.clock: it's compared with access tokens' `iat`.
    user.totp_enabled_at = datetime.now(UTC)
    codes = mfa.new_recovery_codes(get_settings().MFA_RECOVERY_CODE_COUNT)
    user.recovery_code_hashes = [mfa.hash_recovery_code(c) for c in codes]
    await write_audit(
        session, entity_type="user", entity_id=user.id, actor_id=user.id, action="user.2fa_enabled", diff=None
    )
    await session.commit()
    await session.refresh(user)
    return MfaEnabledResponse(**_token_response(user).model_dump(), recovery_codes=codes)


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(body: MfaCodeRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await _user_for_mfa_token(session, body.mfa_token)
    if user.totp_enabled_at is None or user.totp_secret is None:
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Set up two-step verification first")

    step = mfa.match_totp(user.totp_secret, body.code, last_step=user.totp_last_step)
    if step is not None:
        _accept_code(user, step)
    elif mfa.looks_like_recovery_code(body.code) and (
        mfa.hash_recovery_code(body.code) in user.recovery_code_hashes
    ):
        used = mfa.hash_recovery_code(body.code)
        # A new list (not in-place), so SQLAlchemy sees the change.
        user.recovery_code_hashes = [h for h in user.recovery_code_hashes if h != used]
        _accept_code(user)
        await write_audit(
            session, entity_type="user", entity_id=user.id, actor_id=user.id,
            action="user.recovery_code_used", diff={"remaining": len(user.recovery_code_hashes)},
        )
    else:
        raise await _wrong_code(session, user)

    await session.commit()
    await session.refresh(user)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/_probe/agent-only")
async def agent_only_probe(user: User = Depends(require_role(UserRole.agent, UserRole.admin))) -> dict:
    """A small role-gated route for the auth tests."""
    return {"ok": True, "role": user.role.value}
