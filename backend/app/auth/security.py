import bcrypt

MAX_PASSWORD_BYTES = 72

# A fixed, valid hash with no matching password, checked when a login's email
# doesn't exist so the request still pays bcrypt's cost. Otherwise a missing
# account returns faster than a wrong password on a real one, which leaks
# which emails are registered via response timing.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt()).decode("utf-8")


def password_exceeds_limit(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def verify_password_timing_safe(password: str, password_hash: str | None) -> bool:
    """Like verify_password, but always runs bcrypt even when there's no
    real hash to check against (password_hash is None), so a login for an
    unknown email takes as long as one for a known email with a wrong
    password."""
    return bcrypt.checkpw(password.encode("utf-8"), (password_hash or _DUMMY_HASH).encode("utf-8"))
