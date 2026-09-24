"""Live Gemini smoke test: one triage + one KB query per seeded article topic.

    docker compose exec api python scripts/smoke_gemini.py

Needs GEMINI_API_KEY in .env (and the api restarted after adding it, so the
seed re-embeds the KB with Gemini). Exits non-zero if any call fell back to
the fake or returned no grounded answer.
"""

import asyncio
import sys

from httpx import ASGITransport, AsyncClient

from app.ai import get_ai_provider
from app.ai.gemini import GeminiProvider
from app.config import get_settings
from app.schemas.ai import CategoryOption
from app.seed import CATEGORIES, SEED_PASSWORD

KB_QUERIES = [
    ("I forgot my password and the reset email never came", "resetting-your-password"),
    ("Why is there a prorated line on my bill this month?", "understanding-your-monthly-invoice"),
    ("Can I get all my personal data deleted?", "how-we-handle-your-data"),
]


async def main() -> int:
    settings = get_settings()
    provider = get_ai_provider()
    if not isinstance(provider, GeminiProvider):
        print("GEMINI_API_KEY is not set (or AI_PROVIDER=fake): nothing to smoke-test.")
        return 2
    print(f"triage model: {settings.GEMINI_TRIAGE_MODEL}  answer model: {settings.GEMINI_ANSWER_MODEL}  "
          f"embed model: {provider.EMBEDDING_MODEL_ID}")
    ok = True

    result = await provider.triage(
        subject="Charged twice and now locked out",
        description="My card was charged twice for March and since then I can't sign in at all. Please help!",
        categories=[CategoryOption(slug=c["slug"], name=c["name"]) for c in CATEGORIES],
    )
    print("\n== triage ==")
    print(f"model: {result.model}")
    print(result.suggestion.model_dump_json(indent=2))
    ok &= result.model == settings.GEMINI_TRIAGE_MODEL

    from app.ai import gemini as gemini_module
    from app.main import app

    def no_fallback(**_kwargs):
        raise RuntimeError("Gemini grounded answer failed and fell back to the fake (see warning above)")

    # A silent fallback would make the KB check pass without Gemini answering.
    gemini_module.fake_answer = no_fallback

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://smoke") as client:
        login = await client.post("/auth/login", json={"email": "user1@ticketing.demo", "password": SEED_PASSWORD})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for query, expected_slug in KB_QUERIES:
            resp = await client.get("/kb/search", params={"q": query}, headers=headers)
            body = resp.json()
            slugs = [s["slug"] for s in body.get("sources", [])]
            print(f"\n== kb: {query!r} ==  (HTTP {resp.status_code})")
            print(f"answer: {body.get('answer')}")
            print(f"sources: {slugs}")
            ok &= resp.status_code == 200 and bool(body.get("answer")) and expected_slug in slugs

    print("\nSMOKE PASSED" if ok else "\nSMOKE FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
