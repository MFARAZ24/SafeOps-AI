import pytest
from langchain_core.messages import AIMessage

import app.rag.answering as answering
from app.rag.schemas import (
    RAGSearchResponse,
    RAGSearchResult,
    RetrievalDetails,
    RetrieverType,
)


class FakeChatModel:
    """Minimal deterministic chat model for unit tests."""

    model_name = "fake-grounded-model"

    def __init__(
        self,
        answer: str,
    ) -> None:
        self.answer = answer
        self.messages = None

    def invoke(
        self,
        messages: object,
    ) -> AIMessage:
        self.messages = messages

        return AIMessage(
            content=self.answer
        )


def make_retrieval() -> RAGSearchResponse:
    """Create representative retrieved evidence."""

    return RAGSearchResponse(
        query="Why is memory growing?",
        retriever=RetrieverType.HYBRID,
        top_k=2,
        result_count=2,
        elapsed_ms=18.5,
        results=[
            RAGSearchResult(
                rank=1,
                document_id="RB-002",
                chunk_id="RB-002-C003",
                title=(
                    "Memory Exhaustion Runbook"
                ),
                document_type="runbook",
                service="recommendation",
                source=(
                    "runbooks/"
                    "memory-exhaustion.md"
                ),
                section=(
                    "Investigation Procedure"
                ),
                score=0.04,
                score_type=(
                    "reciprocal_rank_fusion"
                ),
                content=(
                    "Continuous memory growth may "
                    "indicate retained allocations."
                ),
                details=RetrievalDetails(),
            ),
            RAGSearchResult(
                rank=2,
                document_id="SVC-001",
                chunk_id="SVC-001-C002",
                title=(
                    "Recommendation Service Guide"
                ),
                document_type="service",
                service="recommendation",
                source=(
                    "services/"
                    "recommendation-service.md"
                ),
                section=(
                    "Common Failure Patterns"
                ),
                score=0.03,
                score_type=(
                    "reciprocal_rank_fusion"
                ),
                content=(
                    "Inspect cache growth and "
                    "garbage-collection behavior."
                ),
                details=RetrievalDetails(),
            ),
        ],
    )


def test_extract_citations_preserves_order() -> None:
    """Citation extraction should deduplicate IDs."""

    answer = (
        "Check memory [RB-002], then inspect "
        "the service [SVC-001] [RB-002]."
    )

    assert answering.extract_citation_ids(
        answer
    ) == [
        "RB-002",
        "SVC-001",
    ]


def test_evidence_context_marks_documents() -> None:
    """Evidence should be clearly delimited and identified."""

    context = answering.build_evidence_context(
        make_retrieval()
    )

    assert 'document_id="RB-002"' in context
    assert 'document_id="SVC-001"' in context
    assert "<evidence " in context
    assert "</evidence>" in context


def test_generate_grounded_answer_validates_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieved document citations should be validated."""

    monkeypatch.setattr(
        answering,
        "search_knowledge",
        lambda *args, **kwargs: make_retrieval(),
    )

    fake_model = FakeChatModel(
        
            "Investigate retained allocations [RB-002] "
            "and inspect cache behavior [SVC-001]."
        
    )

    response = (
        answering.generate_grounded_answer(
            "Why is memory growing?",
            model=fake_model,
            include_evidence=True,
        )
    )

    assert response.grounded is True

    assert [
        citation.document_id
        for citation in response.citations
    ] == [
        "RB-002",
        "SVC-001",
    ]

    assert (
        response.unsupported_citation_ids
        == []
    )

    assert response.evidence is not None
    assert len(response.evidence) == 2


def test_unsupported_citation_marks_answer_ungrounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown citations should fail grounding validation."""

    monkeypatch.setattr(
        answering,
        "search_knowledge",
        lambda *args, **kwargs: make_retrieval(),
    )

    fake_model = FakeChatModel(
        
            "Restart the database immediately "
            "[DB-999]."
        
    )

    response = (
        answering.generate_grounded_answer(
            "Why is memory growing?",
            model=fake_model,
        )
    )

    assert response.grounded is False

    assert response.unsupported_citation_ids == [
        "DB-999"
    ]

    assert response.warnings