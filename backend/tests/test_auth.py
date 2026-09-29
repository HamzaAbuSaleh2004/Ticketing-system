import time
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from sqlalchemy import select

from app.auth import mfa
from app.auth.tokens import create_access_token, create_mfa_token
from app.config import get_settings
from app.models import AuditLog, User
from app.models.enums import Team, UserRole
from tests.helpers import (
    TEST_TOTP_SECRET,
    auth,
    create_user,
    enroll,
    freeze,
    login,
    register,
    register_full,
)


async def _password_step(client, email, password="Secret123!") -> dict:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _code(secret: str = TEST_TOTP_SECRET, steps_from_now: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + steps_from_now * mfa.STEP_SECONDS)


# --- password step -----------------------------------------------------------


async def test_register_creates_end_user_that_must_enrol(client):
    resp = await client.post(
        "/auth/register", json={"email": "new@example.com", "password": "Password123!", "name": "New User"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["mfa"] == "enroll"
    assert "access_token" not in body

    enabled = await enroll(client, body["mfa_token"])
    assert enabled["user"]["role"] == "end_user"
    me = await client.get("/auth/me", headers=auth(enabled["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


async def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "Password123!", "name": "Dup"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_success_needs_a_code_then_gives_a_token(client, db_session):
    await create_user(db_session, email="agent@example.com", role=UserRole.agent, team=Team.tier1)
    step = await _password_step(client, "agent@example.com")
    assert step["mfa"] == "verify"
    assert "access_token" not in step
    verified = await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": _code()})
    assert verified.status_code == 200
    assert verified.json()["user"]["role"] == "agent"


async def test_login_wrong_password_fails(client, db_session):
    await create_user(db_session, email="agent2@example.com", role=UserRole.agent)
    resp = await client.post("/auth/login", json={"email": "agent2@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_unknown_email_fails(client):
    resp = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


async def test_probe_denies_end_user(client):
    token = await register(client, "enduser@example.com")
    resp = await client.get("/auth/_probe/agent-only", headers=auth(token))
    assert resp.status_code == 403


async def test_probe_allows_agent(client, db_session):
    await create_user(db_session, email="agent3@example.com", role=UserRole.agent)
    token = await login(client, "agent3@example.com")
    resp = await client.get("/auth/_probe/agent-only", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "role": "agent"}


async def test_missing_token_is_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_tampered_token_is_401(client):
    token = await register(client, "tamper@example.com")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    resp = await client.get("/auth/me", headers=auth(tampered))
    assert resp.status_code == 401


async def test_register_password_over_72_bytes_is_422(client):
    resp = await client.post(
        "/auth/register", json={"email": "toolong@example.com", "password": "a" * 73, "name": "Too Long"}
    )
    assert resp.status_code == 422


async def test_register_password_over_72_utf8_bytes_is_422(client):
    # 25 codepoints but each is 3 bytes in UTF-8, well over the 72-byte limit.
    resp = await client.post(
        "/auth/register", json={"email": "multibyte@example.com", "password": "€" * 25, "name": "Multibyte"}
    )
    assert resp.status_code == 422


async def test_login_password_over_72_bytes_is_401_not_500(client):
    resp = await client.post("/auth/login", json={"email": "whoever@example.com", "password": "a" * 100})
    assert resp.status_code == 401


async def test_register_and_login_email_case_insensitive(client):
    body = await register_full(client, "Mixed.Case@Example.com")
    assert body["user"]["email"] == "mixed.case@example.com"
    login_resp = await client.post(
        "/auth/login", json={"email": "  MIXED.CASE@EXAMPLE.COM  ", "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["mfa"] == "verify"


async def test_register_duplicate_email_different_case_conflicts(client):
    await client.post(
        "/auth/register", json={"email": "casedup@example.com", "password": "Password123!", "name": "Case Dup"}
    )
    second = await client.post(
        "/auth/register", json={"email": "CaseDup@Example.com", "password": "Password123!", "name": "Case Dup 2"}
    )
    assert second.status_code == 409


async def test_expired_token_is_401(client, db_session):
    user = await create_user(db_session, email="expired@example.com", role=UserRole.end_user)
    settings = get_settings()
    expired_token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "typ": "access", "iat": 0, "exp": 1},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp = await client.get("/auth/me", headers=auth(expired_token))
    assert resp.status_code == 401


async def test_tokens_without_exp_sub_or_typ_are_rejected(client, db_session):
    user = await create_user(db_session, email="noexp@example.com", role=UserRole.end_user)
    settings = get_settings()
    now = int(time.time())
    full = {"sub": str(user.id), "role": "end_user", "typ": "access", "iat": now, "exp": now + 600}
    for missing in ("exp", "sub", "typ"):
        claims = {k: v for k, v in full.items() if k != missing}
        token = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        assert (await client.get("/auth/me", headers=auth(token))).status_code == 401, missing


# --- two-factor authentication ------------------------------------------------


async def test_mfa_token_is_not_an_access_token(client, db_session):
    user = await create_user(db_session, email="mfa-only@example.com", role=UserRole.agent)
    resp = await client.get("/auth/me", headers=auth(create_mfa_token(user_id=user.id)))
    assert resp.status_code == 401


async def test_access_token_is_not_an_mfa_token(client, db_session):
    user = await create_user(db_session, email="swap@example.com", role=UserRole.agent)
    access = create_access_token(user_id=user.id, role=user.role)
    resp = await client.post("/auth/2fa/verify", json={"mfa_token": access, "code": _code()})
    assert resp.status_code == 401


async def test_account_without_2fa_cant_use_an_access_token(client, db_session):
    """Defence in depth: even a validly signed access token is refused for an
    account that hasn't finished enrolling."""
    user = await create_user(db_session, email="half@example.com", role=UserRole.agent, two_factor=False)
    token = create_access_token(user_id=user.id, role=user.role)
    assert (await client.get("/auth/me", headers=auth(token))).status_code == 401


async def test_enrolment_rejects_a_wrong_code_then_accepts_the_right_one(client):
    resp = await client.post(
        "/auth/register", json={"email": "enrol@example.com", "password": "Password123!", "name": "Enrol"}
    )
    mfa_token = resp.json()["mfa_token"]
    setup = (await client.post("/auth/2fa/setup", json={"mfa_token": mfa_token})).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert "secret=" + setup["secret"] in setup["otpauth_uri"]
    assert setup["qr_svg_data_uri"].startswith("data:image/svg+xml")

    wrong = await client.post("/auth/2fa/enable", json={"mfa_token": mfa_token, "code": "000000"})
    assert wrong.status_code == 401
    ok = await client.post("/auth/2fa/enable", json={"mfa_token": mfa_token, "code": _code(setup["secret"])})
    assert ok.status_code == 200
    codes = ok.json()["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10


async def test_many_wrong_enrolment_codes_never_lock_the_account(client, db_session, monkeypatch):
    """Unlike /2fa/verify, wrong /2fa/enable codes don't count towards the
    lockout: mistyping while setting up an authenticator app for the first
    time must have a self-service way out, since re-registering the same
    email just 409s."""
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    resp = await client.post(
        "/auth/register", json={"email": "fumbles@example.com", "password": "Password123!", "name": "Fumbles"}
    )
    mfa_token = resp.json()["mfa_token"]
    setup = (await client.post("/auth/2fa/setup", json={"mfa_token": mfa_token})).json()
    for _ in range(10):
        wrong = await client.post("/auth/2fa/enable", json={"mfa_token": mfa_token, "code": "000000"})
        assert wrong.status_code == 401
    ok = await client.post("/auth/2fa/enable", json={"mfa_token": mfa_token, "code": _code(setup["secret"])})
    assert ok.status_code == 200


async def test_setup_is_refused_once_2fa_is_on(client, db_session):
    """A stolen password can't re-enrol an account onto the thief's phone."""
    await create_user(db_session, email="enrolled@example.com", role=UserRole.end_user)
    step = await _password_step(client, "enrolled@example.com")
    resp = await client.post("/auth/2fa/setup", json={"mfa_token": step["mfa_token"]})
    assert resp.status_code == 409
    resp = await client.post("/auth/2fa/enable", json={"mfa_token": step["mfa_token"], "code": _code()})
    assert resp.status_code == 409


async def test_verify_before_enrolment_is_refused(client):
    resp = await client.post(
        "/auth/register", json={"email": "early@example.com", "password": "Password123!", "name": "Early"}
    )
    verify = await client.post("/auth/2fa/verify", json={"mfa_token": resp.json()["mfa_token"], "code": "123456"})
    assert verify.status_code == 409


async def test_a_code_works_only_once(client, db_session):
    await create_user(db_session, email="replay@example.com", role=UserRole.agent)
    code = _code()
    first = await _password_step(client, "replay@example.com")
    ok = await client.post("/auth/2fa/verify", json={"mfa_token": first["mfa_token"], "code": code})
    assert ok.status_code == 200
    second = await _password_step(client, "replay@example.com")
    replay = await client.post("/auth/2fa/verify", json={"mfa_token": second["mfa_token"], "code": code})
    assert replay.status_code == 401
    # The next step's code is still fine (one step of drift is allowed).
    nxt = await client.post("/auth/2fa/verify", json={"mfa_token": second["mfa_token"], "code": _code(steps_from_now=1)})
    assert nxt.status_code == 200


async def test_codes_outside_the_drift_window_are_rejected(client, db_session):
    await create_user(db_session, email="drift@example.com", role=UserRole.agent)
    step = await _password_step(client, "drift@example.com")
    for offset in (-3, 3):
        resp = await client.post(
            "/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": _code(steps_from_now=offset)}
        )
        assert resp.status_code == 401, offset


async def test_five_wrong_codes_lock_2fa_for_15_minutes(client, db_session, monkeypatch):
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    await create_user(db_session, email="brute@example.com", role=UserRole.agent)
    step = await _password_step(client, "brute@example.com")
    for _ in range(5):
        resp = await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": "000000"})
        assert resp.status_code == 401
    # Locked: even the right code is refused, without being checked.
    locked = await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": _code()})
    assert locked.status_code == 429

    freeze(monkeypatch, now + timedelta(minutes=15, seconds=1))
    later = await _password_step(client, "brute@example.com")
    ok = await client.post("/auth/2fa/verify", json={"mfa_token": later["mfa_token"], "code": _code()})
    assert ok.status_code == 200


async def test_a_right_code_resets_the_wrong_code_count(client, db_session):
    user = await create_user(db_session, email="reset-count@example.com", role=UserRole.agent)
    step = await _password_step(client, "reset-count@example.com")
    for _ in range(4):
        await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": "000000"})
    ok = await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": _code()})
    assert ok.status_code == 200
    await db_session.refresh(user)
    assert user.mfa_failed_attempts == 0


async def test_recovery_codes_work_once_each(client, db_session):
    body = await register_full(client, "recover@example.com")
    code = body["recovery_codes"][0]
    step = await _password_step(client, "recover@example.com", "Password123!")
    ok = await client.post("/auth/2fa/verify", json={"mfa_token": step["mfa_token"], "code": code.upper()})
    assert ok.status_code == 200

    again = await _password_step(client, "recover@example.com", "Password123!")
    reuse = await client.post("/auth/2fa/verify", json={"mfa_token": again["mfa_token"], "code": code})
    assert reuse.status_code == 401

    user = await db_session.scalar(select(User).where(User.email == "recover@example.com"))
    assert len(user.recovery_code_hashes) == 9
    actions = set(await db_session.scalars(select(AuditLog.action).where(AuditLog.entity_id == user.id)))
    assert {"user.2fa_enabled", "user.recovery_code_used"} <= actions


async def test_expired_mfa_token_is_refused(client, db_session):
    user = await create_user(db_session, email="slow@example.com", role=UserRole.agent)
    settings = get_settings()
    stale = jwt.encode(
        {"sub": str(user.id), "typ": "mfa", "iat": 0, "exp": 1}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    resp = await client.post("/auth/2fa/verify", json={"mfa_token": stale, "code": _code()})
    assert resp.status_code == 401


async def test_admin_reset_2fa_ends_sessions_and_forces_re_enrolment(client, db_session):
    await create_user(db_session, email="root@example.com", name="Root", role=UserRole.admin)
    admin_token = await login(client, "root@example.com")
    body = await register_full(client, "lost-phone@example.com")
    user_token, user_id = body["access_token"], body["user"]["id"]

    users = (await client.get("/users", headers=auth(admin_token))).json()
    assert next(u for u in users if u["id"] == user_id)["two_factor_enabled"] is True

    reset = await client.post(f"/users/{user_id}/reset-2fa", headers=auth(admin_token))
    assert reset.status_code == 200
    assert reset.json()["two_factor_enabled"] is False
    # The old session is dead, and the next sign-in enrols again.
    assert (await client.get("/auth/me", headers=auth(user_token))).status_code == 401
    step = await _password_step(client, "lost-phone@example.com", "Password123!")
    assert step["mfa"] == "enroll"
    re_enrolled = await enroll(client, step["mfa_token"])
    assert (await client.get("/auth/me", headers=auth(re_enrolled["access_token"]))).status_code == 200

    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.2fa_reset", AuditLog.entity_id == user_id)
    )
    assert audit is not None and audit.diff_json["after"] == {"two_factor_enabled": False}


async def test_admin_reset_2fa_rules(client, db_session):
    admin = await create_user(db_session, email="root2@example.com", role=UserRole.admin)
    await create_user(db_session, email="plain-agent@example.com", role=UserRole.agent)
    admin_token = await login(client, "root2@example.com")
    agent_token = await login(client, "plain-agent@example.com")
    assert (await client.post(f"/users/{admin.id}/reset-2fa", headers=auth(admin_token))).status_code == 409
    assert (await client.post("/users/99999/reset-2fa", headers=auth(admin_token))).status_code == 404
    assert (await client.post(f"/users/{admin.id}/reset-2fa", headers=auth(agent_token))).status_code == 403
