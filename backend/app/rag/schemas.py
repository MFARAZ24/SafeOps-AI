from enum import StrEnum

from pydantic import BaseModel, Field


class RetrieverType(StrEnum):
    """Retrieval strategies supported by SafeOps."""

    VECTOR = "vector"
    VECTORLESS = "vectorless"
    HYBRID = "hybrid"


class RAGSearchRequest(BaseModel):
    """Request body for knowledge-base retrieval."""

    query: str = Field(
        min_length=3,
        max_length=2000,
        description=(
            "Incident or operational question "
            "to search for."
        ),
    )

    retriever: RetrieverType = (
        RetrieverType.HYBRID
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    include_content: bool = True


class RetrievalDetails(BaseModel):
    """Retriever-specific ranking information."""

    vector_rank: int | None = None
    vector_score: float | None = None

    vectorless_rank: int | None = None
    vectorless_score: float | None = None

    safety_boost: float | None = None


class RAGSearchResult(BaseModel):
    """One piece of retrieved SafeOps evidence."""

    rank: int

    document_id: str

    chunk_id: str | None = None

    title: str

    document_type: str

    service: str

    source: str

    section: str | None = None

    score: float

    score_type: str

    content: str | None = None

    details: RetrievalDetails


class RAGSearchResponse(BaseModel):
    """Complete knowledge-search response."""

    query: str

    retriever: RetrieverType

    top_k: int

    result_count: int

    elapsed_ms: float

    results: list[RAGSearchResult]