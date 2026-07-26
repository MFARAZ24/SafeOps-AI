from pydantic import BaseModel, Field

from app.rag.schemas import RetrieverType


class RAGAnswerRequest(BaseModel):
    """Request for an evidence-grounded SafeOps answer."""

    query: str = Field(
        min_length=3,
        max_length=2000,
    )

    retriever: RetrieverType = RetrieverType.HYBRID

    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
    )

    include_evidence: bool = False


class AnswerCitation(BaseModel):
    """A validated citation used by the generated answer."""

    document_id: str
    title: str
    section: str | None = None
    source: str


class AnswerEvidence(BaseModel):
    """Retrieved evidence optionally returned to the client."""

    rank: int
    document_id: str
    chunk_id: str | None = None
    title: str
    section: str | None = None
    content: str


class RAGAnswerResponse(BaseModel):
    """Grounded answer plus retrieval and citation metadata."""

    query: str
    answer: str
    retriever: RetrieverType
    model: str

    grounded: bool

    retrieval_elapsed_ms: float
    generation_elapsed_ms: float

    citations: list[AnswerCitation]
    unsupported_citation_ids: list[str]
    warnings: list[str]

    evidence: list[AnswerEvidence] | None = None