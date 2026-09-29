from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Team, UserRole

# bcrypt silently truncates/errors past 72 bytes (raises ValueError in
# bcrypt 5), so this is the real usable limit, not an arbitrary one. A
# character count isn't enough: multi-byte UTF-8 characters take more than
# one byte each.
MAX_PASSWORD_BYTES = 72


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _check_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    team: Team | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MfaChallenge(BaseModel):
    """The password step's answer: no access token until the second factor.
    `enroll` = set up an authenticator first; `verify` = enter a code."""

    mfa_token: str
    mfa: Literal["enroll", "verify"]


class MfaTokenRequest(BaseModel):
    mfa_token: str


class MfaCodeRequest(BaseModel):
    mfa_token: str
    # A 6-digit authenticator code, or (verify only) a recovery code.
    code: str = Field(min_length=1, max_length=32)


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg_data_uri: str


class MfaEnabledResponse(TokenResponse):
    # Shown once; only their hashes are stored.
    recovery_codes: list[str]
