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


# Phase 12 addition: which kind of entity an organisation is.
class OrganizationKind(str, enum.Enum):
    company = "company"
    government = "government"


# Phase 12 addition: which side of a ticket's "what's needed" an action item
# belongs to.
class ActionItemSide(str, enum.Enum):
    customer = "customer"
    liverx = "liverx"


# Shared SQLAlchemy Enum instances: reused (not redeclared) across columns so
# each maps to a single Postgres enum type instead of colliding definitions.
user_role_enum = SAEnum(UserRole, name="user_role")
team_enum = SAEnum(Team, name="user_team")
ticket_status_enum = SAEnum(TicketStatus, name="ticket_status")
ticket_priority_enum = SAEnum(TicketPriority, name="ticket_priority")
organization_kind_enum = SAEnum(OrganizationKind, name="organization_kind")
action_item_side_enum = SAEnum(ActionItemSide, name="action_item_side")
