import json
from pathlib import Path
from typing import Any

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CORPUS_MANIFEST_PATH,
    KNOWLEDGE_BASE_DIR,
    MARKDOWN_HEADERS,
)


class KnowledgeBaseError(RuntimeError):
    """Raised when the SafeOps knowledge corpus is invalid."""


def load_manifest(
    manifest_path: Path = CORPUS_MANIFEST_PATH,
) -> dict[str, Any]:
    """Load and validate the SafeOps corpus manifest."""

    if not manifest_path.exists():
        raise KnowledgeBaseError(
            f"Corpus manifest was not found: {manifest_path}"
        )

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise KnowledgeBaseError(
            "Corpus manifest contains invalid JSON: "
            f"{manifest_path}"
        ) from exc

    documents = manifest.get("documents")

    if not isinstance(documents, list):
        raise KnowledgeBaseError(
            "Corpus manifest must contain a documents list."
        )

    if not documents:
        raise KnowledgeBaseError(
            "Corpus manifest contains no documents."
        )

    document_ids = [
        item.get("document_id")
        for item in documents
    ]

    if any(
        document_id is None
        for document_id in document_ids
    ):
        raise KnowledgeBaseError(
            "Every manifest entry requires a document_id."
        )

    if len(document_ids) != len(set(document_ids)):
        raise KnowledgeBaseError(
            "Corpus manifest contains duplicate document IDs."
        )

    return manifest


def parse_front_matter(
    text: str,
    source_path: Path,
) -> tuple[dict[str, Any], str]:
    """Return YAML metadata and Markdown content."""

    normalized_text = text.replace(
        "\r\n",
        "\n",
    )

    if not normalized_text.startswith("---\n"):
        raise KnowledgeBaseError(
            "Document is missing YAML front matter: "
            f"{source_path}"
        )

    parts = normalized_text.split(
        "---\n",
        maxsplit=2,
    )

    if len(parts) != 3:
        raise KnowledgeBaseError(
            "Document front matter is malformed: "
            f"{source_path}"
        )

    yaml_text = parts[1]

    document_body = parts[2].strip()

    try:
        metadata = yaml.safe_load(
            yaml_text
        )
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(
            "Document contains invalid YAML metadata: "
            f"{source_path}"
        ) from exc

    if not isinstance(metadata, dict):
        raise KnowledgeBaseError(
            "Document YAML metadata must be a mapping: "
            f"{source_path}"
        )

    if not document_body:
        raise KnowledgeBaseError(
            f"Document body is empty: {source_path}"
        )

    return metadata, document_body


def load_documents(
    manifest_path: Path = CORPUS_MANIFEST_PATH,
    knowledge_base_dir: Path = KNOWLEDGE_BASE_DIR,
) -> list[Document]:
    """Load all knowledge files as LangChain documents."""

    manifest = load_manifest(
        manifest_path
    )

    loaded_documents: list[Document] = []

    for manifest_item in manifest["documents"]:
        relative_path = Path(
            manifest_item["path"]
        )

        source_path = (
            knowledge_base_dir
            / relative_path
        )

        if not source_path.exists():
            raise KnowledgeBaseError(
                "Manifest document was not found: "
                f"{source_path}"
            )

        text = source_path.read_text(
            encoding="utf-8"
        )

        front_matter, document_body = (
            parse_front_matter(
                text=text,
                source_path=source_path,
            )
        )

        expected_document_id = (
            manifest_item["document_id"]
        )

        actual_document_id = (
            front_matter.get("document_id")
        )

        if (
            actual_document_id
            != expected_document_id
        ):
            raise KnowledgeBaseError(
                "Document ID mismatch for "
                f"{source_path}. "
                f"Expected {expected_document_id}, "
                f"found {actual_document_id}."
            )

        metadata = {
            **manifest_item,
            **front_matter,
            "source": (
                relative_path.as_posix()
            ),
            "absolute_source": str(
                source_path
            ),
            "corpus_name": (
                manifest["corpus_name"]
            ),
            "corpus_version": (
                manifest["corpus_version"]
            ),
        }

        loaded_documents.append(
            Document(
                page_content=document_body,
                metadata=metadata,
            )
        )

    return loaded_documents


def chunk_documents(
    documents: list[Document],
) -> list[Document]:
    """Split documents into retrieval-ready chunks."""

    markdown_splitter = (
        MarkdownHeaderTextSplitter(
            headers_to_split_on=(
                MARKDOWN_HEADERS
            ),
            strip_headers=False,
        )
    )

    size_splitter = (
        RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )
    )

    all_chunks: list[Document] = []

    for document in documents:
        section_documents = (
            markdown_splitter.split_text(
                document.page_content
            )
        )

        for section_document in (
            section_documents
        ):
            section_document.metadata = {
                **document.metadata,
                **section_document.metadata,
            }

        document_chunks = (
            size_splitter.split_documents(
                section_documents
            )
        )

        for chunk_index, chunk in enumerate(
            document_chunks,
            start=1,
        ):
            document_id = str(
                document.metadata[
                    "document_id"
                ]
            )

            chunk.metadata = {
                **chunk.metadata,
                "chunk_id": (
                    f"{document_id}"
                    f"-C{chunk_index:03d}"
                ),
                "chunk_index": (
                    chunk_index
                ),
            }

            all_chunks.append(
                chunk
            )

    return all_chunks


def load_and_chunk_documents() -> list[Document]:
    """Load and chunk the complete knowledge corpus."""

    documents = load_documents()

    return chunk_documents(
        documents
    )