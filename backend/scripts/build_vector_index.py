from app.rag.config import (
    EMBEDDING_MODEL_NAME,
)
from app.rag.vector_store import (
    build_vector_index,
)


def main() -> None:
    """Build and display the SafeOps vector index."""

    print(
        "Building SafeOps vector index..."
    )

    print(
        "Embedding model:",
        EMBEDDING_MODEL_NAME,
    )

    result = build_vector_index(
        recreate=True
    )

    print()
    print(
        "Vector index created successfully."
    )

    print(
        "Collection:",
        result.collection_name,
    )

    print(
        "Source chunks:",
        result.chunk_count,
    )

    print(
        "Stored points:",
        result.point_count,
    )

    print(
        "Vector dimension:",
        result.vector_dimension,
    )

    print(
        "Storage path:",
        result.storage_path,
    )


if __name__ == "__main__":
    main()