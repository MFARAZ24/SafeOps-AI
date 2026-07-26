from fastapi import APIRouter, HTTPException, status

from app.llm.model import ModelConfigurationError
from app.rag.answer_schemas import (
    RAGAnswerRequest,
    RAGAnswerResponse,
)
from app.rag.answering import (
    AnswerGenerationError,
    generate_grounded_answer,
)
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
            include_content=request.include_content,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VectorIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The vector index is unavailable. "
                "Build or restore the index before using "
                "vector or hybrid retrieval."
            ),
        ) from exc

    except RAGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Knowledge retrieval failed.",
        ) from exc


@router.post(
    "/answer",
    response_model=RAGAnswerResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Generate a grounded SafeOps answer",
    description=(
        "Retrieve operational evidence and generate an answer "
        "containing validated document citations."
    ),
)
def answer_rag(
    request: RAGAnswerRequest,
) -> RAGAnswerResponse:
    """Generate an evidence-grounded operational answer."""

    try:
        return generate_grounded_answer(
            query=request.query,
            retriever=request.retriever,
            top_k=request.top_k,
            include_evidence=request.include_evidence,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VectorIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The vector index is unavailable. "
                "Build or restore the index before using "
                "vector or hybrid retrieval."
            ),
        ) from exc

    except ModelConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No usable language model is configured. "
                "Set an LLM API key or an OpenAI-compatible "
                "base URL before generating answers."
            ),
        ) from exc

    except AnswerGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The configured language model failed "
                "to generate an answer."
            ),
        ) from exc

    except RAGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Knowledge retrieval failed.",
        ) from exc