import pytest
from fastapi.testclient import TestClient

import app.api.routes.rag as rag_route
from app.llm.model import ModelConfigurationError
from app.main import app
from app.rag.answer_schemas import (
    AnswerCitation,
    AnswerEvidence,
    RAGAnswerResponse,
)
from app.rag.answering import AnswerGenerationError
from app.rag.schemas import RetrieverType
from app.rag.vector_store import VectorIndexError

client = TestClient(app)


def make_answer_response(
    *,
    include_evidence: bool = False,
) -> RAGAnswerResponse:
    """Create a representative grounded answer response."""

    evidence = None

    if include_evidence:
        evidence = [
            AnswerEvidence(
                rank=1,
                document_id="RB-002",
                chunk_id="RB-002-C003",
                title="Memory Exhaustion Runbook",
                section="Investigation Procedure",
                content=(
                    "Inspect retained allocations, "
                    "cache growth, and garbage collection."
                ),
            )
        ]

    return RAGAnswerResponse(
        query="Why is Recommendation memory increasing?",
        answer=(
            "Continuous memory growth may indicate retained "
            "allocations or unbounded cache behavior [RB-002]."
        ),
        retriever=RetrieverType.HYBRID,
        model="fake-grounded-model",
        grounded=True,
        retrieval_elapsed_ms=12.5,
        generation_elapsed_ms=25.0,
        citations=[
            AnswerCitation(
                document_id="RB-002",
                title="Memory Exhaustion Runbook",
                section="Investigation Procedure",
                source="runbooks/memory-exhaustion.md",
            )
        ],
        unsupported_citation_ids=[],
        warnings=[],
        evidence=evidence,
    )


def test_rag_answer_returns_grounded_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The endpoint should return a citation-validated answer."""

    def fake_generate(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        assert query == (
            "Why is Recommendation memory increasing?"
        )

        assert kwargs["retriever"] == (
            RetrieverType.HYBRID
        )

        assert kwargs["top_k"] == 3

        return make_answer_response()

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        fake_generate,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": (
                "Why is Recommendation "
                "memory increasing?"
            ),
            "retriever": "hybrid",
            "top_k": 3,
            "include_evidence": False,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["grounded"] is True
    assert payload["retriever"] == "hybrid"
    assert payload["model"] == "fake-grounded-model"

    assert (
        payload["citations"][0]["document_id"]
        == "RB-002"
    )

    assert "evidence" not in payload


def test_rag_answer_can_include_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clients may request the retrieved evidence."""

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        lambda *args, **kwargs: (
            make_answer_response(
                include_evidence=True
            )
        ),
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": (
                "Why is Recommendation "
                "memory increasing?"
            ),
            "include_evidence": True,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["evidence"]) == 1

    assert (
        payload["evidence"][0]["document_id"]
        == "RB-002"
    )


def test_rag_answer_uses_hybrid_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hybrid retrieval should be the answer default."""

    selected_retriever = None

    def fake_generate(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        nonlocal selected_retriever

        selected_retriever = kwargs[
            "retriever"
        ]

        return make_answer_response()

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        fake_generate,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": (
                "Why is Recommendation "
                "memory increasing?"
            )
        },
    )

    assert response.status_code == 200

    assert selected_retriever == (
        RetrieverType.HYBRID
    )


def test_rag_answer_rejects_invalid_retriever() -> None:
    """Unsupported retrievers should fail validation."""

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": "Why is checkout slow?",
            "retriever": "unknown",
        },
    )

    assert response.status_code == 422


def test_rag_answer_rejects_whitespace_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only queries should return HTTP 400."""

    def reject_query(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        raise ValueError(
            "Answer query cannot be empty."
        )

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        reject_query,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": "   ",
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Answer query cannot be empty."
    )


def test_rag_answer_reports_missing_model_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing model settings should return HTTP 503."""

    def missing_model(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        raise ModelConfigurationError(
            "No model configured."
        )

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        missing_model,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": "Why is checkout slow?",
        },
    )

    assert response.status_code == 503

    assert "language model" in (
        response.json()["detail"].lower()
    )


def test_rag_answer_reports_model_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider failures should return HTTP 502."""

    def failed_generation(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        raise AnswerGenerationError(
            "Provider failed."
        )

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        failed_generation,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": "Why is checkout slow?",
        },
    )

    assert response.status_code == 502

    assert "failed" in (
        response.json()["detail"].lower()
    )


def test_rag_answer_reports_missing_vector_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable vector storage should return HTTP 503."""

    def missing_index(
        query: str,
        **kwargs: object,
    ) -> RAGAnswerResponse:
        raise VectorIndexError(
            "Index unavailable."
        )

    monkeypatch.setattr(
        rag_route,
        "generate_grounded_answer",
        missing_index,
    )

    response = client.post(
        "/api/v1/rag/answer",
        json={
            "query": "Why is checkout slow?",
            "retriever": "hybrid",
        },
    )

    assert response.status_code == 503

    assert "vector index" in (
        response.json()["detail"].lower()
    )