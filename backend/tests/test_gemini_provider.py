import json
import math

import httpx
import pytest

from app.ai.gemini import GeminiError, GeminiProvider
from app.config import Settings
from app.schemas.ai import CategoryOption, KbContext

CATS = [CategoryOption(slug="billing", name="Billing"), CategoryOption(slug="other", name="Other")]


def _settings(**overrides) -> Settings:
    return Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_TRIAGE_MODEL="triage-model",
        GEMINI_ANSWER_MODEL="answer-model",
        GEMINI_EMBED_MODEL="embed-model",
        EMBED_DIM=4,
        GEMINI_RETRY_BACKOFF_SECONDS=0,
        **overrides,
    )


def _provider(handler, **overrides) -> tuple[GeminiProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request, len(seen))

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    return GeminiProvider(_settings(**overrides), client=client), seen


def _generate_reply(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]})


TRIAGE_OK = {
    "category": "billing",
    "priority": "high",
    "one_line_summary": "Charged twice for March",
    "suggested_response_draft": "Thanks, looking into the double charge now.",
}


async def test_triage_request_shape():
    provider, seen = _provider(lambda req, n: _generate_reply(TRIAGE_OK))
    result = await provider.triage(subject="Double charge", description="Charged twice", categories=CATS)

    assert result.model == "triage-model"
    assert result.suggestion.category == "billing"
    [req] = seen
    assert req.method == "POST"
    assert str(req.url) == "https://generativelanguage.googleapis.com/v1beta/models/triage-model:generateContent"
    assert req.headers["x-goog-api-key"] == "test-key"
    assert "key=" not in str(req.url)
    body = json.loads(req.content)
    assert body["contents"][0]["role"] == "user"
    assert "Charged twice" in body["contents"][0]["parts"][0]["text"]
    assert "untrusted" in body["systemInstruction"]["parts"][0]["text"]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"]["properties"]["category"]["enum"] == ["billing", "other"]


async def test_triage_retries_transient_errors_then_succeeds():
    def handler(req, n):
        return httpx.Response(503, text="overloaded") if n < 3 else _generate_reply(TRIAGE_OK)

    provider, seen = _provider(handler)
    result = await provider.triage(subject="s", description="d", categories=CATS)
    assert len(seen) == 3  # 1 try + 2 retries
    assert result.model == "triage-model"


async def test_triage_falls_back_to_fake_after_exhausting_retries():
    provider, seen = _provider(lambda req, n: httpx.Response(503))
    result = await provider.triage(subject="Invoice", description="refund please", categories=CATS)
    assert len(seen) == 3
    assert result.model == "fake-fallback"
    assert result.suggestion.category == "billing"


async def test_triage_does_not_retry_client_errors_and_falls_back():
    provider, seen = _provider(lambda req, n: httpx.Response(400, json={"error": {"message": "bad"}}))
    result = await provider.triage(subject="s", description="d", categories=CATS)
    assert len(seen) == 1
    assert result.model == "fake-fallback"


@pytest.mark.parametrize(
    "reply",
    [
        _generate_reply({**TRIAGE_OK, "category": "not-a-category"}),
        _generate_reply({**TRIAGE_OK, "priority": "whenever"}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}),
        httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
        httpx.Response(200, text="<html>proxy error</html>"),
    ],
)
async def test_triage_invalid_output_falls_back(reply):
    provider, _ = _provider(lambda req, n: reply)
    result = await provider.triage(subject="s", description="d", categories=CATS)
    assert result.model == "fake-fallback"


async def test_triage_timeout_falls_back():
    def handler(req, n):
        raise httpx.ReadTimeout("slow", request=req)

    provider, seen = _provider(handler)
    result = await provider.triage(subject="s", description="d", categories=CATS)
    assert len(seen) == 3
    assert result.model == "fake-fallback"


async def test_embed_request_shape_and_normalisation():
    def handler(req, n):
        return httpx.Response(200, json={"embeddings": [{"values": [3, 0, 4, 0]}, {"values": [1, 1, 1, 1]}]})

    provider, seen = _provider(handler)
    vectors = await provider.embed(["doc one", "doc two"], task="document")

    [req] = seen
    assert str(req.url).endswith("/models/embed-model:batchEmbedContents")
    body = json.loads(req.content)
    assert body["requests"][0] == {
        "model": "models/embed-model",
        "content": {"parts": [{"text": "doc one"}]},
        "embedContentConfig": {"taskType": "RETRIEVAL_DOCUMENT", "outputDimensionality": 4},
    }
    assert vectors[0] == [0.6, 0.0, 0.8, 0.0]
    assert all(math.isclose(sum(v * v for v in vec), 1.0) for vec in vectors)
    assert provider.EMBEDDING_MODEL_ID == "embed-model@4"


async def test_embed_query_task_type():
    provider, seen = _provider(lambda req, n: httpx.Response(200, json={"embeddings": [{"values": [1, 0, 0, 0]}]}))
    await provider.embed(["q"], task="query")
    assert json.loads(seen[0].content)["requests"][0]["embedContentConfig"]["taskType"] == "RETRIEVAL_QUERY"


async def test_embed_dimension_mismatch_raises_instead_of_falling_back():
    # A fake vector would silently mix vector spaces, so embedding never falls back.
    provider, _ = _provider(lambda req, n: httpx.Response(200, json={"embeddings": [{"values": [1, 0]}]}))
    with pytest.raises(GeminiError):
        await provider.embed(["q"], task="query")


async def test_answer_request_numbers_articles_and_falls_back_on_failure():
    articles = [KbContext(id=7, title="Reset", body="Select Forgot password.")]
    provider, seen = _provider(
        lambda req, n: _generate_reply({"answer": "Select Forgot password [7].", "cited_article_ids": [7]})
    )
    result = await provider.answer(question="forgot password", articles=articles)
    assert result.cited_article_ids == [7]
    assert str(seen[0].url).endswith("/models/answer-model:generateContent")
    assert "[7] Reset" in json.loads(seen[0].content)["contents"][0]["parts"][0]["text"]

    failing, _ = _provider(lambda req, n: httpx.Response(500))
    fallback = await failing.answer(question="forgot password", articles=articles)
    assert fallback.cited_article_ids == [7]


def test_provider_selection():
    from app.ai.fake import FakeProvider

    assert Settings(AI_PROVIDER="auto", GEMINI_API_KEY=None).use_gemini is False
    assert Settings(AI_PROVIDER="auto", GEMINI_API_KEY="k").use_gemini is True
    assert Settings(AI_PROVIDER="fake", GEMINI_API_KEY="k").use_gemini is False
    assert Settings(AI_PROVIDER="gemini", GEMINI_API_KEY=None).use_gemini is False
    with pytest.raises(ValueError):
        GeminiProvider(Settings(GEMINI_API_KEY=None))
    assert FakeProvider.EMBEDDING_MODEL_ID != "embed-model@4"


async def test_interactive_calls_use_the_short_budget():
    timeouts: list = []

    def handler(req, n):
        timeouts.append(req.extensions["timeout"]["read"])
        return httpx.Response(503)

    provider, seen = _provider(handler, GEMINI_INTERACTIVE_TIMEOUT_SECONDS=3, GEMINI_INTERACTIVE_MAX_RETRIES=1)
    with pytest.raises(GeminiError):
        await provider.embed(["q"], task="query")
    assert len(seen) == 2 and timeouts == [3, 3]

    await provider.answer(question="q", articles=[KbContext(id=1, title="t", body="b.")])
    assert len(seen) == 4

    timeouts.clear()
    await provider.triage(subject="s", description="d", categories=CATS)
    assert timeouts == [20, 20, 20]
