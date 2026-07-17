from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_qdrant import (
    QdrantVectorStore,
    RetrievalMode,
)
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
)

from app.rag.config import (
    COLLECTION_NAME,
    VECTOR_STORE_DIR,
)
from app.rag.embeddings import (
    get_embedding_dimension,
    get_embeddings,
)
from app.rag.ingestion import (
    load_and_chunk_documents,
)


class VectorIndexError(RuntimeError):
    """Raised when the SafeOps vector index is unavailable."""


@dataclass(frozen=True)
class IndexBuildResult:
    """Summary returned after building the vector index."""

    collection_name: str
    chunk_count: int
    point_count: int
    vector_dimension: int
    storage_path: Path


def stable_point_id(chunk_id: str) -> str:
    """Create a deterministic Qdrant point ID for a chunk."""

    return str(
        uuid5(
            NAMESPACE_URL,
            f"safeops://knowledge/{chunk_id}",
        )
    )


def _make_json_safe(
    value: Any,
) -> Any:
    """Convert metadata values into JSON-safe values."""

    if isinstance(
        value,
        (date, datetime),
    ):
        return value.isoformat()

    if isinstance(
        value,
        Path,
    ):
        return str(value)

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            _make_json_safe(item)
            for item in value
        ]

    return value


def _sanitize_document(
    document: Document,
) -> Document:
    """Return a document with JSON-safe metadata."""

    return Document(
        page_content=document.page_content,
        metadata=_make_json_safe(
            document.metadata
        ),
    )


def _create_client() -> QdrantClient:
    """Create a persistent local Qdrant client."""

    VECTOR_STORE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return QdrantClient(
        path=str(
            VECTOR_STORE_DIR
        )
    )


def _create_vector_store(
    client: QdrantClient,
) -> QdrantVectorStore:
    """Connect LangChain to the SafeOps collection."""

    return QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=get_embeddings(),
        retrieval_mode=RetrievalMode.DENSE,
    )


def build_vector_index(
    *,
    recreate: bool = True,
) -> IndexBuildResult:
    """Create and populate the local SafeOps vector index."""

    raw_chunks = (
        load_and_chunk_documents()
    )

    chunks = [
        _sanitize_document(chunk)
        for chunk in raw_chunks
    ]

    vector_dimension = (
        get_embedding_dimension()
    )

    client = _create_client()

    try:
        collection_exists = (
            client.collection_exists(
                COLLECTION_NAME
            )
        )

        if (
            collection_exists
            and not recreate
        ):
            raise VectorIndexError(
                "The vector collection already exists. "
                "Use recreate=True to rebuild it."
            )

        if collection_exists:
            client.delete_collection(
                collection_name=(
                    COLLECTION_NAME
                )
            )

        client.create_collection(
            collection_name=(
                COLLECTION_NAME
            ),
            vectors_config=VectorParams(
                size=vector_dimension,
                distance=Distance.COSINE,
            ),
        )

        vector_store = (
            _create_vector_store(
                client
            )
        )

        point_ids = [
            stable_point_id(
                str(
                    chunk.metadata[
                        "chunk_id"
                    ]
                )
            )
            for chunk in chunks
        ]

        vector_store.add_documents(
            documents=chunks,
            ids=point_ids,
        )

        collection_info = (
            client.get_collection(
                COLLECTION_NAME
            )
        )

        point_count = int(
            collection_info.points_count
            or 0
        )

        return IndexBuildResult(
            collection_name=(
                COLLECTION_NAME
            ),
            chunk_count=len(chunks),
            point_count=point_count,
            vector_dimension=(
                vector_dimension
            ),
            storage_path=(
                VECTOR_STORE_DIR
            ),
        )

    finally:
        client.close()


def search_vector_index(
    query: str,
    *,
    top_k: int = 5,
) -> list[tuple[Document, float]]:
    """Return the most similar SafeOps chunks."""

    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    client = _create_client()

    try:
        if not client.collection_exists(
            COLLECTION_NAME
        ):
            raise VectorIndexError(
                "The SafeOps vector index does not exist. "
                "Build the index before searching."
            )

        vector_store = (
            _create_vector_store(
                client
            )
        )

        return (
            vector_store
            .similarity_search_with_score(
                query=cleaned_query,
                k=top_k,
            )
        )

    finally:
        client.close()