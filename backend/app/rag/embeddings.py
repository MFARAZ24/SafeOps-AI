from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.rag.config import (
    EMBEDDING_CACHE_DIR,
    EMBEDDING_MODEL_NAME,
)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the shared SafeOps embedding model."""

    EMBEDDING_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        cache_folder=str(
            EMBEDDING_CACHE_DIR
        ),
        model_kwargs={
            "device": "cpu",
        },
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,
        },
    )


def get_embedding_dimension() -> int:
    """Return the embedding-vector dimension."""

    embeddings = get_embeddings()

    probe_vector = embeddings.embed_query(
        "SafeOps embedding dimension probe"
    )

    return len(probe_vector)