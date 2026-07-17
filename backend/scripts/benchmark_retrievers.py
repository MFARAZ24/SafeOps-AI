from typing import Any

from app.rag.evaluation import (
    evaluate_vector_retriever,
    save_evaluation_results,
)
from app.rag.hybrid import search_hybrid
from app.rag.hybrid_evaluation import (
    evaluate_hybrid_retriever,
    save_hybrid_results,
)
from app.rag.vector_store import (
    search_vector_index,
)
from app.rag.vectorless_evaluation import (
    evaluate_vectorless_retriever,
    save_vectorless_results,
)


def warm_up_retrievers() -> None:
    """Warm up dense retrieval before measuring latency."""

    warmup_query = (
        "SafeOps service investigation "
        "retrieval warm-up"
    )

    search_vector_index(
        warmup_query,
        top_k=1,
    )

    search_hybrid(
        warmup_query,
        top_k=1,
        candidate_k=7,
    )


def metric_rows(
    vector: dict[str, Any],
    vectorless: dict[str, Any],
    hybrid: dict[str, Any],
) -> list[tuple[str, float, float, float]]:
    """Return comparison-table rows."""

    return [
        (
            "Recall@1",
            vector["recall_at_1"],
            vectorless["recall_at_1"],
            hybrid["recall_at_1"],
        ),
        (
            "Recall@3",
            vector["recall_at_3"],
            vectorless["recall_at_3"],
            hybrid["recall_at_3"],
        ),
        (
            "Recall@5",
            vector["recall_at_5"],
            vectorless["recall_at_5"],
            hybrid["recall_at_5"],
        ),
        (
            "Precision@3",
            vector["precision_at_3"],
            vectorless["precision_at_3"],
            hybrid["precision_at_3"],
        ),
        (
            "Precision@5",
            vector["precision_at_5"],
            vectorless["precision_at_5"],
            hybrid["precision_at_5"],
        ),
        (
            "Hit Rate@1",
            vector["hit_rate_at_1"],
            vectorless["hit_rate_at_1"],
            hybrid["hit_rate_at_1"],
        ),
        (
            "Hit Rate@3",
            vector["hit_rate_at_3"],
            vectorless["hit_rate_at_3"],
            hybrid["hit_rate_at_3"],
        ),
        (
            "MRR",
            vector[
                "mean_reciprocal_rank"
            ],
            vectorless[
                "mean_reciprocal_rank"
            ],
            hybrid[
                "mean_reciprocal_rank"
            ],
        ),
        (
            "Latency (ms)",
            vector[
                "average_latency_ms"
            ],
            vectorless[
                "average_latency_ms"
            ],
            hybrid[
                "average_latency_ms"
            ],
        ),
    ]


def print_hybrid_questions(
    evaluation: dict[str, Any],
) -> None:
    """Display per-question hybrid retrieval quality."""

    print()
    print(
        "HYBRID PER-QUESTION RESULTS"
    )
    print("=" * 72)

    for result in evaluation["questions"]:
        print()
        print(
            result["question_id"],
            "-",
            result["question"],
        )

        print(
            "Expected:",
            ", ".join(
                result[
                    "expected_document_ids"
                ]
            ),
        )

        print(
            "Retrieved:",
            ", ".join(
                result[
                    "retrieved_document_ids"
                ]
            ),
        )

        print(
            "Recall@3:",
            f'{result["recall_at_3"]:.4f}',
            "| MRR:",
            f'{result["reciprocal_rank"]:.4f}',
            "| Latency:",
            f'{result["latency_ms"]:.2f} ms',
        )


def print_comparison(
    vector: dict[str, Any],
    vectorless: dict[str, Any],
    hybrid: dict[str, Any],
) -> None:
    """Display the three-retriever comparison."""

    print()
    print(
        "SAFEOPS RETRIEVER BENCHMARK"
    )
    print("=" * 78)

    print(
        f'{"Metric":<18}'
        f'{"Vector":>20}'
        f'{"Vectorless":>20}'
        f'{"Hybrid":>20}'
    )

    print("-" * 78)

    for (
        metric,
        vector_value,
        vectorless_value,
        hybrid_value,
    ) in metric_rows(
        vector,
        vectorless,
        hybrid,
    ):
        print(
            f"{metric:<18}"
            f"{vector_value:>20.4f}"
            f"{vectorless_value:>20.4f}"
            f"{hybrid_value:>20.4f}"
        )


def main() -> None:
    """Run all SafeOps retrieval benchmarks."""

    print(
        "Warming up embedding and "
        "retrieval components..."
    )

    warm_up_retrievers()

    print(
        "Running vector evaluation..."
    )

    vector_evaluation = (
        evaluate_vector_retriever()
    )

    print(
        "Running vectorless evaluation..."
    )

    vectorless_evaluation = (
        evaluate_vectorless_retriever()
    )

    print(
        "Running hybrid evaluation..."
    )

    hybrid_evaluation = (
        evaluate_hybrid_retriever()
    )

    vector_path = save_evaluation_results(
        vector_evaluation
    )

    vectorless_path = (
        save_vectorless_results(
            vectorless_evaluation
        )
    )

    hybrid_path = save_hybrid_results(
        hybrid_evaluation
    )

    print_hybrid_questions(
        hybrid_evaluation
    )

    print_comparison(
        vector_evaluation["summary"],
        vectorless_evaluation["summary"],
        hybrid_evaluation["summary"],
    )

    print()
    print("Results saved to:")
    print("Vector:", vector_path)
    print(
        "Vectorless:",
        vectorless_path,
    )
    print("Hybrid:", hybrid_path)


if __name__ == "__main__":
    main()