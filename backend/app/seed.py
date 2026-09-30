import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Category,
    KnowledgeBaseArticle,
    Organization,
    OrganizationKind,
    Team,
    User,
    UserRole,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_PASSWORD = "ChangeMe123!"
# Local demo accounts come with 2FA already set up on this published secret
# (add it to an authenticator app, see README), like their published
# password. Neither is ever used in prod, where no demo accounts are created.
DEMO_TOTP_SECRET = "LIVERXDEMOTOTPSECRETFORLOCALONLY"

USERS = [
    {"email": "admin@ticketing.demo", "name": "Ada Admin", "role": UserRole.admin, "team": None, "organization": None},
    {"email": "agent1@ticketing.demo", "name": "Tara Tier1", "role": UserRole.agent, "team": Team.tier1, "organization": None},
    {"email": "agent2@ticketing.demo", "name": "Tom Tier1", "role": UserRole.agent, "team": Team.tier1, "organization": None},
    {"email": "agent3@ticketing.demo", "name": "Sasha Senior", "role": UserRole.agent, "team": Team.senior, "organization": None},
    {"email": "user1@ticketing.demo", "name": "Uma User", "role": UserRole.end_user, "team": None,
     "organization": "Meridian Retail Group"},
    {"email": "user2@ticketing.demo", "name": "Leo Client", "role": UserRole.end_user, "team": None,
     "organization": "Ministry of Public Works"},
]

# Phase 12 addition: which organisation each ticket's customer belongs to.
# Realistic company + government mix; only the first two are used by the
# seeded demo end users (above), the other two exist so the org picker and
# filter aren't a one-item list.
ORGANIZATIONS = [
    {"name": "Meridian Retail Group", "kind": OrganizationKind.company},
    {"name": "Ministry of Public Works", "kind": OrganizationKind.government},
    {"name": "Harborline Logistics", "kind": OrganizationKind.company},
    {"name": "City Transit Authority", "kind": OrganizationKind.government},
]

CATEGORIES = [
    {"name": "Account & login", "slug": "account-login"},
    {"name": "Billing", "slug": "billing"},
    {"name": "Technical issue", "slug": "technical-issue"},
    {"name": "Data & privacy", "slug": "data-privacy"},
    {"name": "Other", "slug": "other"},
]

KB_ARTICLES = [
    {
        "slug": "resetting-your-password",
        "title": "Resetting your password",
        "tags": ["password", "login", "account"],
        "body": (
            "If you're locked out of your account, go to the sign-in page and select "
            "'Forgot password'. Enter the email address on your account and we'll send a "
            "reset link that's valid for 30 minutes. Opening the link takes you to a form "
            "where you can set a new password; it must be at least 10 characters and include "
            "a number. Once it's saved, you'll be signed out of any other active sessions for "
            "security, so you'll need to sign back in on other devices. If the reset email "
            "doesn't arrive within a few minutes, check your spam folder before requesting "
            "another one — requesting too many resets in a short window will temporarily "
            "rate-limit the address. If you no longer have access to the email on file, "
            "contact support and we'll verify your identity manually."
        ),
    },
    {
        "slug": "understanding-your-monthly-invoice",
        "title": "Understanding your monthly invoice",
        "tags": ["billing", "invoice", "payment"],
        "body": (
            "Your invoice is generated on the same day each month, based on your original "
            "signup date, and covers usage for the prior billing period. Each line item maps "
            "to a plan or add-on you had active during that period; partial months are "
            "prorated automatically when you upgrade, downgrade, or cancel mid-cycle. Taxes "
            "are calculated based on the billing address on your account, so keep it current "
            "if you move. You can view or download any past invoice as a PDF from the Billing "
            "tab. If a charge looks unfamiliar, check whether a teammate added a seat or "
            "add-on during the period before contacting support — the invoice's itemized "
            "breakdown usually explains it. Failed payments are retried automatically over "
            "several days before the account is restricted."
        ),
    },
    {
        "slug": "troubleshooting-slow-load-times",
        "title": "Troubleshooting slow load times and error screens",
        "tags": ["performance", "errors", "troubleshooting"],
        "body": (
            "If pages are loading slowly or you're seeing error screens, start with a hard "
            "refresh (Ctrl/Cmd+Shift+R) to rule out a stale cached version. Next, try an "
            "incognito/private window — if the problem disappears there, a browser extension "
            "is likely interfering, so disable extensions one at a time to find the culprit. "
            "Persistent errors that include a reference code should be reported to support "
            "along with that code, since it points us to the exact failed request in our "
            "logs. Slowness that's specific to one network (e.g. a corporate VPN) is usually "
            "a routing issue on that network rather than on our end — try a different network "
            "to confirm. We also publish real-time incident status; check there first before "
            "opening a ticket if many users seem affected at once."
        ),
    },
    {
        "slug": "how-we-handle-your-data",
        "title": "How we handle and protect your data",
        "tags": ["privacy", "security", "data"],
        "body": (
            "We collect only the data needed to operate your account: profile details you "
            "provide, ticket and message content, and basic usage logs for security and "
            "reliability. Data is encrypted in transit and at rest, and access inside our "
            "systems is limited to staff who need it to do their job, with every access "
            "logged. We never sell customer data, and we don't share it with third parties "
            "except the infrastructure providers required to run the service (under contracts "
            "that bind them to the same protections). You can request a full export or "
            "deletion of your data at any time from Account Settings, or by asking support; "
            "deletion requests are processed within 30 days except where we're required to "
            "retain certain records for legal or billing reasons, which we'll explain if it "
            "applies to you."
        ),
    },
    {
        "slug": "contacting-support-what-to-expect",
        "title": "Contacting support and what to expect",
        "tags": ["support", "response-time", "general"],
        "body": (
            "You can reach support by submitting a request from this portal; there's no need "
            "to email separately. Every request gets an automatic priority based on its "
            "content, which determines our target response time — urgent issues (e.g. you're "
            "fully locked out or billed incorrectly) get the fastest response, while general "
            "questions are handled on a normal queue. You'll get a reply from a real person, "
            "not just an automated acknowledgment, and you can keep adding details to your "
            "request at any time by replying — this doesn't create a new ticket unless the "
            "original one has already been closed. Once an agent marks a request resolved, "
            "it stays open for you to reply for a few more days in case the issue resurfaces; "
            "after that, a new reply starts a fresh linked request instead."
        ),
    },
]


async def seed_organizations(session: AsyncSession) -> None:
    for o in ORGANIZATIONS:
        existing = await session.scalar(select(Organization).where(Organization.name == o["name"]))
        if existing:
            continue
        session.add(Organization(name=o["name"], kind=o["kind"], active=True))
    await session.commit()


async def seed_users(session: AsyncSession) -> None:
    # The demo accounts share a published password: never create them in prod.
    if get_settings().ENV == "prod":
        logger.info("seed: ENV=prod, skipping the demo accounts")
        return
    org_ids = {o.name: o.id for o in await session.scalars(select(Organization))}
    for u in USERS:
        existing = await session.scalar(select(User).where(User.email == u["email"]))
        if existing:
            continue
        session.add(
            User(
                email=u["email"],
                name=u["name"],
                role=u["role"],
                team=u["team"],
                organization_id=org_ids.get(u["organization"]) if u["organization"] else None,
                password_hash=hash_password(SEED_PASSWORD),
                totp_secret=DEMO_TOTP_SECRET,
                # Real time: it's compared with access tokens' `iat`.
                totp_enabled_at=datetime.now(UTC),
            )
        )
    await session.commit()


async def seed_categories(session: AsyncSession) -> None:
    for c in CATEGORIES:
        existing = await session.scalar(select(Category).where(Category.slug == c["slug"]))
        if existing:
            continue
        session.add(Category(name=c["name"], slug=c["slug"], active=True))
    await session.commit()


async def seed_kb_articles(session: AsyncSession) -> None:
    existing = set(await session.scalars(select(KnowledgeBaseArticle.slug)))
    for a in KB_ARTICLES:
        if a["slug"] not in existing:
            session.add(KnowledgeBaseArticle(slug=a["slug"], title=a["title"], body=a["body"], tags=a["tags"]))
    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed_organizations(session)
        await seed_users(session)
        await seed_categories(session)
        await seed_kb_articles(session)
        settings = get_settings()
        if settings.seed_demo:
            from app.seed_demo import seed_demo_tickets

            created = await seed_demo_tickets(session, settings.DEMO_DATA_PATH)
            if created:
                logger.info("seed: added %d demo tickets", created)
    logger.info("seed: complete")


if __name__ == "__main__":
    asyncio.run(main())
