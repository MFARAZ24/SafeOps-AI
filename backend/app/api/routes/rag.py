from fastapi import APIRouter, HTTPException, status

from app.rag.schemas import (
    RAGSearchRequest,
    RAGSearchResponse,
)
from app.rag.service import (
    RAGServiceError,
    search_knowledge,
)
from app.rag.vector_store import VectorIndexError

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


@router.post(
    "/search",
    response_model=RAGSearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Search the SafeOps knowledge base",
    description=(
        "Search operational runbooks, service guides, "
        "architecture documents, and safety policies using "
        "vector, vectorless, or hybrid retrieval."
    ),
)
def search_rag(
    request: RAGSearchRequest,
) -> RAGSearchResponse:
    """Search SafeOps operational knowledge."""

    try:
        return search_knowledge(
            query=request.query,
            retriever=request.retriever,
            top_k=request.top_k,
            include_content=(
                request.include_content
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    except VectorIndexError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "The vector index is unavailable. "
                "Build or restore the index before "
                "using vector or hybrid retrieval."
            ),
        ) from exc

    except RAGServiceError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="Knowledge retrieval failed.",
        ) from exc