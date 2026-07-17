import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from app.rag.config import PROJECT_ROOT
from app.rag.vector_store import search_vector_index

SEED_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "rag" / "seed_questions.json"

DEFAULT_RESULTS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "rag"
    / "results"
    / "vector_retrieval_results.json"
)


@dataclass(frozen=True)
class QuestionEvaluation:
    """Retrieval results and metrics for one evaluation question."""

    question_id: str
    question: str
    category: str
    expected_document_ids: list[str]
    retrieved_document_ids: list[str]
    retrieved_results: list[dict[str, Any]]
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    precision_at_3: float
    precision_at_5: float
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    reciprocal_rank: float
    latency_ms: float


def load_seed_questions(path: Path = SEED_QUESTIONS_PATH) -> dict[str, Any]:
    """Load the ground-truth RAG evaluation dataset."""

    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset was not found: {path}")

    dataset = json.loads(path.read_text(encoding="utf-8"))

    questions = dataset.get("questions")

    if not isinstance(questions, list) or not questions:
        raise ValueError("Evaluation dataset must contain a nonempty questions list.")

    return dataset


def unique_in_order(values: list[str]) -> list[str]:
    """Deduplicate values while preserving their first occurrence."""

    return list(dict.fromkeys(values))


def recall_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    """Calculate document-level Recall@K."""

    return len(set(retrieved[:k]) & expected) / len(expected) if expected else 0.0


def precision_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    """Calculate document-level Precision@K."""

    return len(set(retrieved[:k]) & expected) / k


def hit_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    """Return one when at least one relevant document appears in the top K."""

    return float(bool(set(retrieved[:k]) & expected))


def reciprocal_rank(retrieved: list[str], expected: set[str]) -> float:
    """Calculate reciprocal rank of the first relevant document."""

    for rank, document_id in enumerate(retrieved, start=1):
        if document_id in expected:
            return 1.0 / rank

    return 0.0


def evaluate_question(
    item: dict[str, Any],
    *,
    max_k: int = 5,
    candidate_multiplier: int = 4,
) -> QuestionEvaluation:
    """Evaluate semantic retrieval for one seed question."""

    started = perf_counter()

    raw_results = search_vector_index(
        item["question"],
        top_k=max_k * candidate_multiplier,
    )

    latency_ms = (perf_counter() - started) * 1000

    retrieved_results: list[dict[str, Any]] = []
    seen_document_ids: set[str] = set()

    for document, score in raw_results:
        document_id = str(document.metadata["document_id"])

        if document_id in seen_document_ids:
            continue

        seen_document_ids.add(document_id)

        retrieved_results.append(
            {
                "rank": len(retrieved_results) + 1,
                "document_id": document_id,
                "chunk_id": document.metadata["chunk_id"],
                "title": document.metadata["title"],
                "heading_2": document.metadata.get("heading_2"),
                "score": float(score),
            }
        )

        if len(retrieved_results) == max_k:
            break

    retrieved_document_ids = [
        result["document_id"] for result in retrieved_results
    ]

    expected_document_ids = [str(value) for value in item["expected_document_ids"]]
    expected = set(expected_document_ids)

    return QuestionEvaluation(
        question_id=item["question_id"],
        question=item["question"],
        category=item["category"],
        expected_document_ids=expected_document_ids,
        retrieved_document_ids=retrieved_document_ids,
        retrieved_results=retrieved_results,
        recall_at_1=recall_at_k(retrieved_document_ids, expected, 1),
        recall_at_3=recall_at_k(retrieved_document_ids, expected, 3),
        recall_at_5=recall_at_k(retrieved_document_ids, expected, 5),
        precision_at_3=precision_at_k(retrieved_document_ids, expected, 3),
        precision_at_5=precision_at_k(retrieved_document_ids, expected, 5),
        hit_at_1=hit_at_k(retrieved_document_ids, expected, 1),
        hit_at_3=hit_at_k(retrieved_document_ids, expected, 3),
        hit_at_5=hit_at_k(retrieved_document_ids, expected, 5),
        reciprocal_rank=reciprocal_rank(retrieved_document_ids, expected),
        latency_ms=latency_ms,
    )


def average(results: list[QuestionEvaluation], attribute: str) -> float:
    """Calculate the average value of an evaluation attribute."""

    return sum(float(getattr(result, attribute)) for result in results) / len(results)


def evaluate_vector_retriever() -> dict[str, Any]:
    """Run the complete vector-retrieval evaluation dataset."""

    dataset = load_seed_questions()
    results = [evaluate_question(item) for item in dataset["questions"]]

    summary = {
        "question_count": len(results),
        "recall_at_1": average(results, "recall_at_1"),
        "recall_at_3": average(results, "recall_at_3"),
        "recall_at_5": average(results, "recall_at_5"),
        "precision_at_3": average(results, "precision_at_3"),
        "precision_at_5": average(results, "precision_at_5"),
        "hit_rate_at_1": average(results, "hit_at_1"),
        "hit_rate_at_3": average(results, "hit_at_3"),
        "hit_rate_at_5": average(results, "hit_at_5"),
        "mean_reciprocal_rank": average(results, "reciprocal_rank"),
        "average_latency_ms": average(results, "latency_ms"),
    }

    return {
        "dataset_name": dataset["dataset_name"],
        "dataset_version": dataset["dataset_version"],
        "retriever": "vector",
        "summary": summary,
        "questions": [asdict(result) for result in results],
    }


def save_evaluation_results(
    evaluation: dict[str, Any],
    path: Path = DEFAULT_RESULTS_PATH,
) -> Path:
    """Save retrieval metrics and per-question results as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    return path