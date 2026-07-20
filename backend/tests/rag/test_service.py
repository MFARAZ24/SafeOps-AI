import pytest
from langchain_core.documents import Document

import app.rag.service as rag_service
from app.rag.schemas import RetrieverType


def make_document() -> Document:
    """Create a representative retrieval result."""

    return Document(
        page_content=(
            "Investigate allocation growth, "
            "cache behavior, and garbage collection."
        ),
        metadata={
            "document_id": "RB-002",
            "chunk_id": "RB-002-C003",
            "title": (
                "Memory Exhaustion Runbook"
            ),
            "document_type": "runbook",
            "service": "recommendation",
            "source": (
                "runbooks/"
                "memory-exhaustion.md"
            ),
            "heading_1": (
                "Memory Exhaustion Runbook"
            ),
            "heading_2": (
                "Investigation Procedure"
            ),
            "vector_rank": 1,
            "vector_score": 0.81,
            "vectorless_rank": 2,
            "vectorless_score": 42.0,
            "safety_boost": 0.0,
        },
    )


@pytest.mark.parametrize(
    ("retriever", "function_name", "score_type"),
    [
        (
            RetrieverType.VECTOR,
            "search_vector_index",
            "cosine_similarity",
        ),
        (
            RetrieverType.VECTORLESS,
            "search_vectorless",
            "rule_score",
        ),
        (
            RetrieverType.HYBRID,
            "search_hybrid",
            "reciprocal_rank_fusion",
        ),
    ],
)
def test_search_knowledge_supports_all_retrievers(
    monkeypatch: pytest.MonkeyPatch,
    retriever: RetrieverType,
    function_name: str,
    score_type: str,
) -> None:
    """The unified service should support every retriever."""

    document = make_document()

    def fake_search(
        query: str,
        **kwargs: object,
    ) -> list[
        tuple[Document, float]
    ]:
        assert query == (
            "Recommendation memory is growing"
        )

        assert kwargs["top_k"] == 3

        return [
            (
                document,
                0.75,
            )
        ]

    monkeypatch.setattr(
        rag_service,
        function_name,
        fake_search,
    )

    response = (
        rag_service.search_knowledge(
            (
                "Recommendation "
                "memory is growing"
            ),
            retriever=retriever,
            top_k=3,
        )
    )

    assert response.retriever == retriever

    assert response.result_count == 1

    assert response.results[
        0
    ].document_id == "RB-002"

    assert response.results[
        0
    ].section == (
        "Investigation Procedure"
    )

    assert response.results[
        0
    ].score_type == score_type


def test_search_can_exclude_document_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clients may request metadata without full content."""

    monkeypatch.setattr(
        rag_service,
        "search_vectorless",
        lambda query, top_k: [
            (
                make_document(),
                20.0,
            )
        ],
    )

    response = (
        rag_service.search_knowledge(
            "memory growth",
            retriever=(
                RetrieverType.VECTORLESS
            ),
            include_content=False,
        )
    )

    assert (
        response.results[0].content
        is None
    )


def test_search_rejects_empty_query() -> None:
    """The service should reject empty search queries."""

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        rag_service.search_knowledge(
            "   "
        )


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        11,
    ],
)
def test_search_rejects_invalid_top_k(
    top_k: int,
) -> None:
    """The result count must remain within API limits."""

    with pytest.raises(
        ValueError,
        match="between 1 and 10",
    ):
        rag_service.search_knowledge(
            "checkout latency",
            top_k=top_k,
        )