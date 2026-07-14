from pathlib import Path

# Repository layout:
#
# SafeOps-AI/
# ├── backend/
# │   └── app/
# │       └── rag/
# │           └── config.py
# └── data/
#     └── knowledge_base/

PROJECT_ROOT = Path(__file__).resolve().parents[3]

KNOWLEDGE_BASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "knowledge_base"
)

CORPUS_MANIFEST_PATH = (
    KNOWLEDGE_BASE_DIR
    / "corpus_manifest.json"
)

VECTOR_STORE_DIR = (
    PROJECT_ROOT
    / "data"
    / "vector_store"
    / "qdrant"
)

EMBEDDING_CACHE_DIR = (
    PROJECT_ROOT
    / ".cache"
    / "sentence_transformers"
)

COLLECTION_NAME = "safeops_knowledge_base"

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/all-MiniLM-L6-v2"
)

CHUNK_SIZE = 800

CHUNK_OVERLAP = 120

MARKDOWN_HEADERS = [
    ("#", "heading_1"),
    ("##", "heading_2"),
    ("###", "heading_3"),
]