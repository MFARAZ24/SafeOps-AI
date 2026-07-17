import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from app.rag.config import PROJECT_ROOT
from app.rag.evaluation import (
    hit_at_k,
    load_seed_questions,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.rag.vectorless import search_vectorless

DEFAULT_VECTORLESS_RESULTS_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "rag"
    / "results"
    / "vectorless_retrieval_results.json"
)


@dataclass(frozen=True)
class VectorlessQuestionEvaluation:
    """Metrics for one vectorless retrieval question."""

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


def evaluate_vectorless_question(
    item: dict[str, Any],
    *,
    max_k: int = 5,
) -> VectorlessQuestionEvaluation:
    """Evaluate one question using vectorless retrieval."""

    started = perf_counter()

    results = search_vectorless(
        item["question"],
        top_k=max_k,
    )

    latency_ms = (
        perf_counter()
        - started
    ) * 1000

    retrieved_results = []

    for rank, (document, score) in enumerate(
        results,
        start=1,
    ):
        retrieved_results.append(
            {
                "rank": rank,
                "document_id": str(
                    document.metadata[
                        "document_id"
                    ]
                ),
                "title": str(
                    document.metadata[
                        "title"
                    ]
                ),
                "document_type": str(
                    document.metadata[
                        "document_type"
                    ]
                ),
                "service": str(
                    document.metadata[
                        "service"
                    ]
                ),
                "score": float(score),
                "reasons": list(
                    document.metadata.get(
                        "vectorless_reasons",
                        [],
                    )
                ),
                "detected_services": list(
                    document.metadata.get(
                        "detected_services",
                        [],
                    )
                ),
                "detected_concepts": list(
                    document.metadata.get(
                        "detected_concepts",
                        [],
                    )
                ),
            }
        )

    retrieved_document_ids = [
        result["document_id"]
        for result in retrieved_results
    ]

    expected_document_ids = [
        str(document_id)
        for document_id
        in item["expected_document_ids"]
    ]

    expected = set(
        expected_document_ids
    )

    return VectorlessQuestionEvaluation(
        question_id=str(
            item["question_id"]
        ),
        question=str(
            item["question"]
        ),
        category=str(
            item["category"]
        ),
        expected_document_ids=(
            expected_document_ids
        ),
        retrieved_document_ids=(
            retrieved_document_ids
        ),
        retrieved_results=(
            retrieved_results
        ),
        recall_at_1=recall_at_k(
            retrieved_document_ids,
            expected,
            1,
        ),
        recall_at_3=recall_at_k(
            retrieved_document_ids,
            expected,
            3,
        ),
        recall_at_5=recall_at_k(
            retrieved_document_ids,
            expected,
            5,
        ),
        precision_at_3=precision_at_k(
            retrieved_document_ids,
            expected,
            3,
        ),
        precision_at_5=precision_at_k(
            retrieved_document_ids,
            expected,
            5,
        ),
        hit_at_1=hit_at_k(
            retrieved_document_ids,
            expected,
            1,
        ),
        hit_at_3=hit_at_k(
            retrieved_document_ids,
            expected,
            3,
        ),
        hit_at_5=hit_at_k(
            retrieved_document_ids,
            expected,
            5,
        ),
        reciprocal_rank=reciprocal_rank(
            retrieved_document_ids,
            expected,
        ),
        latency_ms=latency_ms,
    )


def average_metric(
    results: list[
        VectorlessQuestionEvaluation
    ],
    attribute: str,
) -> float:
    """Return the average value of one metric."""

    return sum(
        float(
            getattr(
                result,
                attribute,
            )
        )
        for result in results
    ) / len(results)


def evaluate_vectorless_retriever() -> dict[str, Any]:
    """Evaluate all vectorless seed questions."""

    dataset = load_seed_questions()

    results = [
        evaluate_vectorless_question(
            item
        )
        for item in dataset["questions"]
    ]

    summary = {
        "question_count": len(results),
        "recall_at_1": average_metric(
            results,
            "recall_at_1",
        ),
        "recall_at_3": average_metric(
            results,
            "recall_at_3",
        ),
        "recall_at_5": average_metric(
            results,
            "recall_at_5",
        ),
        "precision_at_3": average_metric(
            results,
            "precision_at_3",
        ),
        "precision_at_5": average_metric(
            results,
            "precision_at_5",
        ),
        "hit_rate_at_1": average_metric(
            results,
            "hit_at_1",
        ),
        "hit_rate_at_3": average_metric(
            results,
            "hit_at_3",
        ),
        "hit_rate_at_5": average_metric(
            results,
            "hit_at_5",
        ),
        "mean_reciprocal_rank": (
            average_metric(
                results,
                "reciprocal_rank",
            )
        ),
        "average_latency_ms": (
            average_metric(
                results,
                "latency_ms",
            )
        ),
    }

    return {
        "dataset_name": dataset[
            "dataset_name"
        ],
        "dataset_version": dataset[
            "dataset_version"
        ],
        "retriever": "vectorless",
        "summary": summary,
        "questions": [
            asdict(result)
            for result in results
        ],
    }


def save_vectorless_results(
    evaluation: dict[str, Any],
    path: Path = (
        DEFAULT_VECTORLESS_RESULTS_PATH
    ),
) -> Path:
    """Save vectorless evaluation results as JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            evaluation,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path