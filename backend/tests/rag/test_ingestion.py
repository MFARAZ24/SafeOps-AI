from collections import defaultdict

from app.rag.config import CHUNK_SIZE
from app.rag.ingestion import (
    chunk_documents,
    load_documents,
    load_manifest,
)

EXPECTED_DOCUMENT_IDS = {
    "ARCH-001",
    "ARCH-002",
    "SVC-001",
    "SVC-002",
    "RB-001",
    "RB-002",
    "POL-001",
}


def test_manifest_contains_expected_documents() -> None:
    """The initial corpus manifest should contain seven documents."""

    manifest = load_manifest()

    assert manifest["corpus_name"] == (
        "safeops-initial-knowledge-base"
    )

    assert len(manifest["documents"]) == 7

    document_ids = {
        item["document_id"]
        for item in manifest["documents"]
    }

    assert document_ids == EXPECTED_DOCUMENT_IDS


def test_load_documents_preserves_required_metadata() -> None:
    """Every knowledge document should retain required metadata."""

    documents = load_documents()

    assert len(documents) == 7

    loaded_document_ids = set()

    for document in documents:
        metadata = document.metadata

        assert document.page_content.strip()

        assert metadata["document_id"]
        assert metadata["title"]
        assert metadata["document_type"]
        assert metadata["service"]
        assert metadata["source"]

        assert metadata["corpus_name"] == (
            "safeops-initial-knowledge-base"
        )

        loaded_document_ids.add(
            metadata["document_id"]
        )

    assert loaded_document_ids == EXPECTED_DOCUMENT_IDS


def test_chunk_documents_creates_valid_chunks() -> None:
    """Chunking should create nonempty retrieval-ready chunks."""

    documents = load_documents()

    chunks = chunk_documents(
        documents
    )

    assert len(chunks) >= len(documents)

    chunk_ids = []

    document_ids = set()

    for chunk in chunks:
        metadata = chunk.metadata

        assert chunk.page_content.strip()

        assert len(
            chunk.page_content
        ) <= CHUNK_SIZE

        assert metadata["document_id"]

        assert metadata["chunk_id"]

        assert metadata["chunk_index"] >= 1

        chunk_ids.append(
            metadata["chunk_id"]
        )

        document_ids.add(
            metadata["document_id"]
        )

    assert len(
        chunk_ids
    ) == len(
        set(chunk_ids)
    )

    assert document_ids == EXPECTED_DOCUMENT_IDS


def test_chunk_indexes_are_sequential_per_document() -> None:
    """Each document should receive sequential chunk indexes."""

    chunks = chunk_documents(
        load_documents()
    )

    indexes_by_document = defaultdict(
        list
    )

    for chunk in chunks:
        document_id = (
            chunk.metadata["document_id"]
        )

        chunk_index = (
            chunk.metadata["chunk_index"]
        )

        indexes_by_document[
            document_id
        ].append(
            chunk_index
        )

    for indexes in (
        indexes_by_document.values()
    ):
        expected_indexes = list(
            range(
                1,
                len(indexes) + 1,
            )
        )

        assert indexes == expected_indexes


def test_markdown_headings_are_preserved() -> None:
    """Markdown headings should remain available as metadata."""

    chunks = chunk_documents(
        load_documents()
    )

    assert any(
        chunk.metadata.get(
            "heading_1"
        )
        for chunk in chunks
    )

    assert any(
        chunk.metadata.get(
            "heading_2"
        )
        for chunk in chunks
    )