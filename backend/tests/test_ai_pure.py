from app.ai.fake import fake_answer, fake_triage
from app.ai.schema import gemini_response_schema
from app.domain.grounding import ground_citations
from app.schemas.ai import CategoryOption, GroundedAnswer, KbContext, TriageSuggestion
from app.seed import CATEGORIES

CATS = [CategoryOption(slug=c["slug"], name=c["name"]) for c in CATEGORIES]


def test_triage_schema_is_gemini_openapi_subset_with_injected_category_enum():
    schema = gemini_response_schema(TriageSuggestion, enums={"category": ["billing", "other"]})
    assert schema["type"] == "OBJECT"
    assert schema["required"] == ["category", "priority", "one_line_summary", "suggested_response_draft"]
    assert schema["propertyOrdering"] == schema["required"]
    assert schema["properties"]["category"] == {
        "type": "STRING",
        "description": TriageSuggestion.model_fields["category"].description,
        "enum": ["billing", "other"],
    }
    # The TicketPriority $ref is inlined as a string enum.
    assert schema["properties"]["priority"]["type"] == "STRING"
    assert schema["properties"]["priority"]["enum"] == ["low", "normal", "high", "urgent"]
    flat = str(schema)
    for unsupported in ("$ref", "$defs", "title", "maxLength"):
        assert unsupported not in flat


def test_answer_schema_array_items():
    schema = gemini_response_schema(GroundedAnswer)
    assert schema["properties"]["cited_article_ids"] == {
        "type": "ARRAY",
        "description": GroundedAnswer.model_fields["cited_article_ids"].description,
        "items": {"type": "INTEGER"},
    }


def test_ground_citations_renumbers_ids_to_source_order():
    answer, sources = ground_citations("Do X [20]. Then Y [10]. Again X [20].", [20, 10], [10, 20, 30])
    assert sources == [20, 10]
    assert answer == "Do X [1]. Then Y [2]. Again X [1]."


def test_ground_citations_drops_ids_and_markers_outside_retrieved_set():
    answer, sources = ground_citations("Fact [10]. Invented [7].", [10, 999], [10, 20])
    assert sources == [10]
    assert answer == "Fact [1]. Invented."


def test_ground_citations_small_ids_are_never_read_as_positions():
    # Article ids 1 and 3 are retrieved; "[1]" means article id 1, not "the first article".
    answer, sources = ground_citations("From the invoice article [3].", [3], [7, 1, 3])
    assert (answer, sources) == ("From the invoice article [1].", [3])


def test_ground_citations_grouped_markers():
    answer, sources = ground_citations("Reset it in Settings [12, 7; 99].", [], [7, 12])
    assert sources == [12, 7]
    assert answer == "Reset it in Settings [1] [2]."


def test_ground_citations_keeps_cited_id_without_marker():
    answer, sources = ground_citations("A plain answer.", [20], [10, 20])
    assert (answer, sources) == ("A plain answer.", [20])


def test_ground_citations_ungrounded_or_empty_answer_is_none():
    assert ground_citations("Unsupported claim.", [], [10]) == (None, [])
    assert ground_citations("Only a bogus id [999].", [999], [10]) == (None, [])
    assert ground_citations("   ", [10], [10]) == (None, [])


def test_long_summary_is_truncated_not_rejected():
    s = TriageSuggestion(
        category="billing", priority="high", one_line_summary="word " * 80, suggested_response_draft="Hi"
    )
    assert len(s.one_line_summary) == 200
    assert s.one_line_summary.endswith("...")


def test_fake_triage_keywords():
    s = fake_triage(subject="Locked out", description="I can't log in, urgent!", categories=CATS)
    assert (s.category, s.priority.value) == ("account-login", "urgent")

    s = fake_triage(subject="Invoice question", description="How do I download last month's invoice?", categories=CATS)
    assert (s.category, s.priority.value) == ("billing", "low")

    s = fake_triage(subject="Hi", description="Just saying thanks", categories=CATS)
    assert (s.category, s.priority.value) == ("other", "normal")


def test_fake_triage_only_picks_allowed_categories():
    only_other = [CategoryOption(slug="other", name="Other")]
    s = fake_triage(subject="Password reset", description="forgot my password", categories=only_other)
    assert s.category == "other"
    only_billing = [CategoryOption(slug="billing", name="Billing")]
    assert fake_triage(subject="Hi", description="thanks", categories=only_billing).category == "billing"
    # No active categories at all doesn't crash triage.
    assert fake_triage(subject="Hi", description="thanks", categories=[]).category == "other"


def test_fake_answer_is_extractive_and_cites_top_article():
    articles = [
        KbContext(id=5, title="Reset", body="Go to sign in. Select Forgot password to get a link. Links last 30 minutes."),
        KbContext(id=6, title="Other", body="Unrelated."),
    ]
    result = fake_answer(question="forgot password link", articles=articles)
    assert result.cited_article_ids == [5]
    assert result.answer.endswith("[5]")
    assert "Forgot password" in result.answer
