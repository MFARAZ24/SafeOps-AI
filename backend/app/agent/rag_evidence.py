from app.agent.investigation_schemas import (
    KnowledgeEvidence,
)
from app.rag.schemas import RAGSearchResponse

MAX_EVIDENCE_CONTENT_CHARACTERS = 4_000
MAX_KNOWLEDGE_CONTEXT_CHARACTERS = 12_000


def to_knowledge_evidence(
    retrieval: RAGSearchResponse,
) -> list[KnowledgeEvidence]:
    """Convert retrieval results into bounded agent evidence."""

    return [
        KnowledgeEvidence(
            rank=result.rank,
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            title=result.title,
            document_type=result.document_type,
            service=result.service,
            source=result.source,
            section=result.section,
            score=result.score,
            content=(result.content or "")[:MAX_EVIDENCE_CONTENT_CHARACTERS],
        )
        for result in retrieval.results
    ]


def build_knowledge_context(
    evidence: list[KnowledgeEvidence],
) -> str:
    """Build a bounded prompt context from untrusted documents."""

    blocks: list[str] = []
    current_length = 0

    for item in evidence:
        block = (
            "<knowledge_evidence "
            f'document_id="{item.document_id}" '
            f'title="{item.title}" '
            f'section="{item.section or ""}" '
            f'service="{item.service}">\n'
            f"{item.content}\n"
            "</knowledge_evidence>"
        )

        remaining = MAX_KNOWLEDGE_CONTEXT_CHARACTERS - current_length

        if remaining <= 0:
            break

        if len(block) > remaining:
            block = block[:remaining]

        blocks.append(block)
        current_length += len(block)

    if not blocks:
        return "No knowledge-base evidence was retrieved."

    return "\n\n".join(blocks)
