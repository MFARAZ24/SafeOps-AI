import pytest
from langchain_core.documents import Document

import app.rag.hybrid as hybrid


def make_document(
    document_id: str,
    document_type: str,
) -> Document:
    """Create a minimal retrieval document for testing."""

    return Document(
        page_content=(
            f"Content for {document_id}"
        ),
        metadata={
            "document_id": document_id,
            "chunk_id": (
                f"{document_id}-C001"
            ),
            "title": document_id,
            "document_type": document_type,
            "service": "platform",
        },
    )


def test_rrf_rewards_documents_found_by_both_retrievers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A document found by both methods should rank highly."""

    document_a = make_document(
        "DOC-A",
        "architecture",
    )

    document_b = make_document(
        "DOC-B",
        "runbook",
    )

    document_c = make_document(
        "DOC-C",
        "service",
    )

    monkeypatch.setattr(
        hybrid,
        "search_vector_index",
        lambda query, top_k: [
            (document_a, 0.90),
            (document_b, 0.80),
        ],
    )

    monkeypatch.setattr(
        hybrid,
        "search_vectorless",
        lambda query, top_k: [
            (document_b, 30.0),
            (document_c, 20.0),
        ],
    )

    results = hybrid.search_hybrid(
        "service latency",
        top_k=3,
        candidate_k=3,
    )

    retrieved_ids = [
        document.metadata[
            "document_id"
        ]
        for document, _ in results
    ]

    assert retrieved_ids[0] == "DOC-B"

    assert len(
        retrieved_ids
    ) == len(
        set(retrieved_ids)
    )


def test_safety_query_prioritizes_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Safety intent should prioritize the policy document."""

    service_document = make_document(
        "SVC-001",
        "service",
    )

    policy_document = make_document(
        "POL-001",
        "policy",
    )

    monkeypatch.setattr(
        hybrid,
        "search_vector_index",
        lambda query, top_k: [
            (service_document, 0.90),
            (policy_document, 0.70),
        ],
    )

    monkeypatch.setattr(
        hybrid,
        "search_vectorless",
        lambda query, top_k: [
            (policy_document, 40.0),
            (service_document, 30.0),
        ],
    )

    results = hybrid.search_hybrid(
        (
            "Can SafeOps automatically restart "
            "the Recommendation service?"
        ),
        top_k=2,
        candidate_k=2,
    )

    assert (
        results[0][0].metadata[
            "document_id"
        ]
        == "POL-001"
    )


def test_empty_query_is_rejected() -> None:
    """Hybrid retrieval should reject empty questions."""

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        hybrid.search_hybrid("   ")


def test_candidate_k_must_cover_top_k() -> None:
    """The candidate pool cannot be smaller than the result count."""

    with pytest.raises(
        ValueError,
        match="candidate_k",
    ):
        hybrid.search_hybrid(
            "latency",
            top_k=5,
            candidate_k=3,
        )