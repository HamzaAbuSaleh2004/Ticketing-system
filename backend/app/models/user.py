from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import Team, UserRole, team_enum, user_role_enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)
    team: Mapped[Team | None] = mapped_column(team_enum, nullable=True)
    # Phase 12 addition: only meaningful for end_user accounts, like `team`
    # is only meaningful for agents; cleared when the role becomes staff.
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Two-factor authentication (TOTP), mandatory for every account.
    # `totp_secret` is set at enrolment and only counts once `totp_enabled_at`
    # is set (the first code was confirmed). Access tokens issued before
    # `totp_enabled_at` are rejected, so a reset + re-enrolment ends old sessions.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The last accepted TOTP time step: a code is never accepted twice.
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # SHA-256 hashes of the unused single-use recovery codes.
    recovery_code_hashes: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), nullable=False, default=list, server_default="{}"
    )
    mfa_failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mfa_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def two_factor_enabled(self) -> bool:
        return self.totp_enabled_at is not None
