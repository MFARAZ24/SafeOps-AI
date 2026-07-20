from time import perf_counter

from langchain_core.documents import Document

from app.rag.hybrid import search_hybrid
from app.rag.schemas import (
    RAGSearchResponse,
    RAGSearchResult,
    RetrievalDetails,
    RetrieverType,
)
from app.rag.vector_store import (
    search_vector_index,
)
from app.rag.vectorless import (
    search_vectorless,
)


class RAGServiceError(RuntimeError):
    """Raised when the RAG service cannot search knowledge."""


def _get_section(
    document: Document,
) -> str | None:
    """Return the most specific Markdown section available."""

    metadata = document.metadata

    for key in (
        "heading_3",
        "heading_2",
        "heading_1",
    ):
        value = metadata.get(key)

        if value:
            return str(value)

    return None


def _score_type(
    retriever: RetrieverType,
) -> str:
    """Describe the meaning of the returned score."""

    score_types = {
        RetrieverType.VECTOR: (
            "cosine_similarity"
        ),
        RetrieverType.VECTORLESS: (
            "rule_score"
        ),
        RetrieverType.HYBRID: (
            "reciprocal_rank_fusion"
        ),
    }

    return score_types[retriever]


def _run_retriever(
    query: str,
    *,
    retriever: RetrieverType,
    top_k: int,
) -> list[tuple[Document, float]]:
    """Run the requested SafeOps retriever."""

    if retriever == RetrieverType.VECTOR:
        return search_vector_index(
            query,
            top_k=top_k,
        )

    if retriever == RetrieverType.VECTORLESS:
        return search_vectorless(
            query,
            top_k=top_k,
        )

    if retriever == RetrieverType.HYBRID:
        return search_hybrid(
            query,
            top_k=top_k,
            candidate_k=max(
                7,
                top_k,
            ),
        )

    raise RAGServiceError(
        f"Unsupported retriever: {retriever}"
    )


def _to_search_result(
    document: Document,
    score: float,
    *,
    rank: int,
    retriever: RetrieverType,
    include_content: bool,
) -> RAGSearchResult:
    """Convert an internal document into an API-safe result."""

    metadata = document.metadata

    return RAGSearchResult(
        rank=rank,
        document_id=str(
            metadata["document_id"]
        ),
        chunk_id=(
            str(metadata["chunk_id"])
            if metadata.get("chunk_id")
            else None
        ),
        title=str(
            metadata.get(
                "title",
                metadata["document_id"],
            )
        ),
        document_type=str(
            metadata.get(
                "document_type",
                "unknown",
            )
        ),
        service=str(
            metadata.get(
                "service",
                "unknown",
            )
        ),
        source=str(
            metadata.get(
                "source",
                "",
            )
        ),
        section=_get_section(
            document
        ),
        score=float(score),
        score_type=_score_type(
            retriever
        ),
        content=(
            document.page_content
            if include_content
            else None
        ),
        details=RetrievalDetails(
            vector_rank=metadata.get(
                "vector_rank"
            ),
            vector_score=metadata.get(
                "vector_score"
            ),
            vectorless_rank=metadata.get(
                "vectorless_rank"
            ),
            vectorless_score=metadata.get(
                "vectorless_score"
            ),
            safety_boost=metadata.get(
                "safety_boost"
            ),
        ),
    )


def search_knowledge(
    query: str,
    *,
    retriever: RetrieverType | str = (
        RetrieverType.HYBRID
    ),
    top_k: int = 5,
    include_content: bool = True,
) -> RAGSearchResponse:
    """Search the SafeOps knowledge base."""

    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    if top_k < 1 or top_k > 10:
        raise ValueError(
            "top_k must be between 1 and 10."
        )

    selected_retriever = (
        RetrieverType(retriever)
    )

    started = perf_counter()

    retrieved_documents = (
        _run_retriever(
            cleaned_query,
            retriever=selected_retriever,
            top_k=top_k,
        )
    )

    elapsed_ms = (
        perf_counter() - started
    ) * 1000

    results = [
        _to_search_result(
            document,
            score,
            rank=rank,
            retriever=(
                selected_retriever
            ),
            include_content=(
                include_content
            ),
        )
        for rank, (
            document,
            score,
        ) in enumerate(
            retrieved_documents,
            start=1,
        )
    ]

    return RAGSearchResponse(
        query=cleaned_query,
        retriever=selected_retriever,
        top_k=top_k,
        result_count=len(results),
        elapsed_ms=elapsed_ms,
        results=results,
    )