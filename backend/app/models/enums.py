import enum

from sqlalchemy import Enum as SAEnum


class UserRole(str, enum.Enum):
    end_user = "end_user"
    agent = "agent"
    admin = "admin"


class Team(str, enum.Enum):
    tier1 = "tier1"
    senior = "senior"


class TicketStatus(str, enum.Enum):
    new = "new"
    triaged = "triaged"
    open = "open"
    in_progress = "in_progress"
    pending = "pending"
    resolved = "resolved"
    closed = "closed"


class TicketPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


# Shared SQLAlchemy Enum instances: reused (not redeclared) across columns so
# each maps to a single Postgres enum type instead of colliding definitions.
user_role_enum = SAEnum(UserRole, name="user_role")
team_enum = SAEnum(Team, name="user_team")
ticket_status_enum = SAEnum(TicketStatus, name="ticket_status")
ticket_priority_enum = SAEnum(TicketPriority, name="ticket_priority")
