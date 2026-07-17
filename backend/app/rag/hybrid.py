from dataclasses import dataclass

from langchain_core.documents import Document

from app.rag.vector_store import search_vector_index
from app.rag.vectorless import (
    analyze_query,
    search_vectorless,
)

DEFAULT_RRF_K = 60.0
DEFAULT_VECTOR_WEIGHT = 1.0
DEFAULT_VECTORLESS_WEIGHT = 1.25


@dataclass
class HybridCandidate:
    """One document collected from the component retrievers."""

    document: Document
    vector_rank: int | None = None
    vector_score: float | None = None
    vectorless_rank: int | None = None
    vectorless_score: float | None = None


def reciprocal_rank_score(
    rank: int | None,
    *,
    weight: float,
    rrf_k: float,
) -> float:
    """Calculate one weighted reciprocal-rank contribution."""

    if rank is None:
        return 0.0

    return weight / (
        rrf_k + rank
    )


def document_level_vector_results(
    query: str,
    *,
    candidate_k: int,
) -> list[tuple[Document, float]]:
    """Convert chunk-level vector results into document results."""

    raw_results = search_vector_index(
        query,
        top_k=candidate_k * 4,
    )

    document_results: list[
        tuple[Document, float]
    ] = []

    seen_document_ids: set[str] = set()

    for document, score in raw_results:
        document_id = str(
            document.metadata[
                "document_id"
            ]
        )

        if document_id in seen_document_ids:
            continue

        seen_document_ids.add(
            document_id
        )

        document_results.append(
            (document, score)
        )

        if (
            len(document_results)
            == candidate_k
        ):
            break

    return document_results


def search_hybrid(
    query: str,
    *,
    top_k: int = 5,
    candidate_k: int = 7,
    vector_weight: float = (
        DEFAULT_VECTOR_WEIGHT
    ),
    vectorless_weight: float = (
        DEFAULT_VECTORLESS_WEIGHT
    ),
    rrf_k: float = DEFAULT_RRF_K,
) -> list[tuple[Document, float]]:
    """Combine vector and vectorless rankings using weighted RRF."""

    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    if candidate_k < top_k:
        raise ValueError(
            "candidate_k must be greater than "
            "or equal to top_k."
        )

    if vector_weight <= 0:
        raise ValueError(
            "vector_weight must be positive."
        )

    if vectorless_weight <= 0:
        raise ValueError(
            "vectorless_weight must be positive."
        )

    if rrf_k <= 0:
        raise ValueError(
            "rrf_k must be positive."
        )

    vector_results = (
        document_level_vector_results(
            cleaned_query,
            candidate_k=candidate_k,
        )
    )

    vectorless_results = (
        search_vectorless(
            cleaned_query,
            top_k=candidate_k,
        )
    )

    candidates: dict[
        str,
        HybridCandidate,
    ] = {}

    for rank, (
        document,
        score,
    ) in enumerate(
        vector_results,
        start=1,
    ):
        document_id = str(
            document.metadata[
                "document_id"
            ]
        )

        candidates[document_id] = (
            HybridCandidate(
                document=document,
                vector_rank=rank,
                vector_score=float(score),
            )
        )

    for rank, (
        document,
        score,
    ) in enumerate(
        vectorless_results,
        start=1,
    ):
        document_id = str(
            document.metadata[
                "document_id"
            ]
        )

        candidate = candidates.get(
            document_id
        )

        if candidate is None:
            candidate = HybridCandidate(
                document=document
            )

            candidates[
                document_id
            ] = candidate

        candidate.vectorless_rank = rank
        candidate.vectorless_score = float(
            score
        )

    query_signals = analyze_query(
        cleaned_query
    )

    safety_intent = bool(
        {
            "approval",
            "prompt_injection",
        }
        & query_signals.concepts
    )

    fused_results: list[
        tuple[Document, float]
    ] = []

    for candidate in candidates.values():
        vector_contribution = (
            reciprocal_rank_score(
                candidate.vector_rank,
                weight=vector_weight,
                rrf_k=rrf_k,
            )
        )

        vectorless_contribution = (
            reciprocal_rank_score(
                candidate.vectorless_rank,
                weight=vectorless_weight,
                rrf_k=rrf_k,
            )
        )

        safety_boost = 0.0

        document_type = str(
            candidate.document.metadata[
                "document_type"
            ]
        ).lower()

        if (
            safety_intent
            and document_type == "policy"
        ):
            safety_boost = (
                1.0
                / (
                    rrf_k + 1.0
                )
            )

        hybrid_score = (
            vector_contribution
            + vectorless_contribution
            + safety_boost
        )

        hybrid_document = Document(
            page_content=(
                candidate.document.page_content
            ),
            metadata={
                **candidate.document.metadata,
                "hybrid_score": hybrid_score,
                "vector_rank": (
                    candidate.vector_rank
                ),
                "vector_score": (
                    candidate.vector_score
                ),
                "vectorless_rank": (
                    candidate.vectorless_rank
                ),
                "vectorless_score": (
                    candidate.vectorless_score
                ),
                "vector_contribution": (
                    vector_contribution
                ),
                "vectorless_contribution": (
                    vectorless_contribution
                ),
                "safety_boost": (
                    safety_boost
                ),
                "detected_services": sorted(
                    query_signals.services
                ),
                "detected_concepts": sorted(
                    query_signals.concepts
                ),
            },
        )

        fused_results.append(
            (
                hybrid_document,
                hybrid_score,
            )
        )

    fused_results.sort(
        key=lambda item: (
            -item[1],
            (
                item[0].metadata.get(
                    "vectorless_rank"
                )
                or 10_000
            ),
            (
                item[0].metadata.get(
                    "vector_rank"
                )
                or 10_000
            ),
            str(
                item[0].metadata[
                    "document_id"
                ]
            ),
        )
    )

    return fused_results[:top_k]