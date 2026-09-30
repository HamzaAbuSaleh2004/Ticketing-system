"""TOTP two-factor authentication (RFC 6238: 6 digits, 30 s steps, SHA-1,
which is what Google/Microsoft Authenticator and 1Password expect).

Codes are checked against real wall-clock time (not `domain.clock`, which
tests freeze for lifecycle timing), one step either side for clock drift,
and a step is never accepted twice for the same user.
"""

import hashlib
import hmac
import secrets
import time

import pyotp
import segno

STEP_SECONDS = 30
_DRIFT_STEPS = 1
# No i/l/o/0/1/8/9, so a recovery code can't be misread when typed back in.
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz234567"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, email: str, issuer: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def qr_svg_data_uri(uri: str) -> str:
    """A data: URI, so the page shows it as an <img> (no markup injected).
    Black on white with a quiet zone whatever the page theme: scanners need it."""
    return segno.make(uri, error="m").svg_data_uri(scale=6, border=4, dark="#000", light="#fff")


def match_totp(secret: str, code: str, *, last_step: int | None, now: float | None = None) -> int | None:
    """The time step `code` belongs to, or None if it's wrong or that step
    (or a later one) was already used."""
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // STEP_SECONDS)
    totp = pyotp.TOTP(secret)
    for step in range(current - _DRIFT_STEPS, current + _DRIFT_STEPS + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * STEP_SECONDS), code):
            return step
    return None


def new_recovery_codes(count: int) -> list[str]:
    """Shown to the user once, as `xxxxx-xxxxx` (about 48 bits each)."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def hash_recovery_code(code: str) -> str:
    # High-entropy random codes, so a fast hash is enough (unlike passwords).
    normalized = code.strip().lower().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def looks_like_recovery_code(code: str) -> bool:
    return len(code.strip().replace("-", "").replace(" ", "")) == 10
