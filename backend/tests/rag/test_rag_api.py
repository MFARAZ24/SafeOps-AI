import pytest
from fastapi.testclient import TestClient

import app.api.routes.rag as rag_route
from app.main import app
from app.rag.schemas import (
    RAGSearchResponse,
    RAGSearchResult,
    RetrievalDetails,
    RetrieverType,
)
from app.rag.vector_store import (
    VectorIndexError,
)

client = TestClient(app)


def make_response(
    *,
    include_content: bool = True,
) -> RAGSearchResponse:
    """Create a representative RAG API response."""

    return RAGSearchResponse(
        query=(
            "Recommendation memory "
            "keeps increasing"
        ),
        retriever=RetrieverType.HYBRID,
        top_k=3,
        result_count=1,
        elapsed_ms=12.5,
        results=[
            RAGSearchResult(
                rank=1,
                document_id="RB-002",
                chunk_id="RB-002-C003",
                title=(
                    "Memory Exhaustion and "
                    "Continuous Memory Growth Runbook"
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
                score=0.0364,
                score_type=(
                    "reciprocal_rank_fusion"
                ),
                content=(
                    "Investigate allocation growth "
                    "and cache behavior."
                    if include_content
                    else None
                ),
                details=RetrievalDetails(
                    vector_rank=1,
                    vector_score=0.77,
                    vectorless_rank=1,
                    vectorless_score=48.0,
                    safety_boost=0.0,
                ),
            )
        ],
    )


def test_rag_search_returns_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint should return structured retrieval results."""

    def fake_search(
        query: str,
        **kwargs: object,
    ) -> RAGSearchResponse:
        assert query == (
            "Recommendation memory "
            "keeps increasing"
        )

        assert kwargs["retriever"] == (
            RetrieverType.HYBRID
        )

        assert kwargs["top_k"] == 3

        return make_response()

    monkeypatch.setattr(
        rag_route,
        "search_knowledge",
        fake_search,
    )

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": (
                "Recommendation memory "
                "keeps increasing"
            ),
            "retriever": "hybrid",
            "top_k": 3,
            "include_content": True,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["retriever"] == "hybrid"

    assert payload["result_count"] == 1

    assert (
        payload["results"][0][
            "document_id"
        ]
        == "RB-002"
    )

    assert (
        payload["results"][0][
            "score_type"
        ]
        == "reciprocal_rank_fusion"
    )


def test_rag_search_uses_hybrid_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hybrid retrieval should be the API default."""

    selected_retriever = None

    def fake_search(
        query: str,
        **kwargs: object,
    ) -> RAGSearchResponse:
        nonlocal selected_retriever

        selected_retriever = kwargs[
            "retriever"
        ]

        return make_response()

    monkeypatch.setattr(
        rag_route,
        "search_knowledge",
        fake_search,
    )

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": (
                "Recommendation memory "
                "keeps increasing"
            ),
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    assert selected_retriever == (
        RetrieverType.HYBRID
    )


def test_rag_search_rejects_invalid_retriever() -> None:
    """Unsupported retriever names should fail validation."""

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": "Checkout is slow",
            "retriever": "unknown",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "top_k",
    [
        0,
        11,
    ],
)
def test_rag_search_validates_top_k(
    top_k: int,
) -> None:
    """Top K should remain within the declared API bounds."""

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": "Checkout is slow",
            "top_k": top_k,
        },
    )

    assert response.status_code == 422


def test_rag_search_rejects_whitespace_query() -> None:
    """Whitespace-only input should return a client error."""

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": "   ",
            "retriever": "vectorless",
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Search query cannot be empty."
    )


def test_rag_search_reports_missing_vector_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable vector storage should return HTTP 503."""

    def unavailable_search(
        query: str,
        **kwargs: object,
    ) -> RAGSearchResponse:
        raise VectorIndexError(
            "Vector index is missing."
        )

    monkeypatch.setattr(
        rag_route,
        "search_knowledge",
        unavailable_search,
    )

    response = client.post(
        "/api/v1/rag/search",
        json={
            "query": "Checkout is slow",
            "retriever": "vector",
        },
    )

    assert response.status_code == 503

    assert "vector index" in (
        response.json()["detail"].lower()
    )