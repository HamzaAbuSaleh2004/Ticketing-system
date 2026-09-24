import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import get_ai_provider
from app.auth.security import hash_password
from app.db import SessionLocal
from app.models import (
    Category,
    KnowledgeBaseArticle,
    SlaPolicy,
    Team,
    TicketPriority,
    User,
    UserRole,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_PASSWORD = "ChangeMe123!"

USERS = [
    {"email": "admin@ticketing.local", "name": "Ada Admin", "role": UserRole.admin, "team": None},
    {"email": "agent1@ticketing.local", "name": "Tara Tier1", "role": UserRole.agent, "team": Team.tier1},
    {"email": "agent2@ticketing.local", "name": "Tom Tier1", "role": UserRole.agent, "team": Team.tier1},
    {"email": "agent3@ticketing.local", "name": "Sasha Senior", "role": UserRole.agent, "team": Team.senior},
    {"email": "user1@ticketing.local", "name": "Uma User", "role": UserRole.end_user, "team": None},
    {"email": "user2@ticketing.local", "name": "Leo Client", "role": UserRole.end_user, "team": None},
]

SLA_POLICIES = [
    {"name": "Urgent", "priority": TicketPriority.urgent, "response_minutes": 15, "resolution_minutes": 4 * 60},
    {"name": "High", "priority": TicketPriority.high, "response_minutes": 60, "resolution_minutes": 8 * 60},
    {"name": "Normal", "priority": TicketPriority.normal, "response_minutes": 4 * 60, "resolution_minutes": 24 * 60},
    {"name": "Low", "priority": TicketPriority.low, "response_minutes": 8 * 60, "resolution_minutes": 72 * 60},
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


async def seed_users(session: AsyncSession) -> None:
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
                password_hash=hash_password(SEED_PASSWORD),
            )
        )
    await session.commit()


async def seed_sla_policies(session: AsyncSession) -> None:
    for p in SLA_POLICIES:
        existing = await session.scalar(select(SlaPolicy).where(SlaPolicy.priority == p["priority"]))
        if existing:
            continue
        session.add(SlaPolicy(**p))
    await session.commit()


async def seed_categories(session: AsyncSession) -> None:
    for c in CATEGORIES:
        existing = await session.scalar(select(Category).where(Category.slug == c["slug"]))
        if existing:
            continue
        session.add(Category(name=c["name"], slug=c["slug"], active=True))
    await session.commit()


async def seed_kb_articles(session: AsyncSession) -> None:
    provider = get_ai_provider()
    for a in KB_ARTICLES:
        existing = await session.scalar(
            select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.slug == a["slug"])
        )
        if existing:
            continue
        [embedding] = await provider.embed([a["body"]])
        session.add(
            KnowledgeBaseArticle(
                slug=a["slug"],
                title=a["title"],
                body=a["body"],
                tags=a["tags"],
                embedding=embedding,
            )
        )
    await session.commit()


async def main() -> None:
    async with SessionLocal() as session:
        await seed_users(session)
        await seed_sla_policies(session)
        await seed_categories(session)
        await seed_kb_articles(session)
    logger.info("seed: complete")


if __name__ == "__main__":
    asyncio.run(main())
