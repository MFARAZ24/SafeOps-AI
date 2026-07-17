import json

from app.rag.config import PROJECT_ROOT

RESULTS_DIRECTORY = (
    PROJECT_ROOT
    / "evaluation"
    / "rag"
    / "results"
)

VECTOR_PATH = (
    RESULTS_DIRECTORY
    / "vector_retrieval_results.json"
)

VECTORLESS_PATH = (
    RESULTS_DIRECTORY
    / "vectorless_retrieval_results.json"
)


def load_summary(path):
    """Load one retrieval evaluation summary."""

    if not path.exists():
        raise FileNotFoundError(
            f"Result file was not found: {path}"
        )

    evaluation = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    return evaluation["summary"]


def main() -> None:
    """Compare vector and vectorless retrieval."""

    vector = load_summary(
        VECTOR_PATH
    )

    vectorless = load_summary(
        VECTORLESS_PATH
    )

    rows = [
        (
            "Recall@1",
            vector["recall_at_1"],
            vectorless["recall_at_1"],
        ),
        (
            "Recall@3",
            vector["recall_at_3"],
            vectorless["recall_at_3"],
        ),
        (
            "Recall@5",
            vector["recall_at_5"],
            vectorless["recall_at_5"],
        ),
        (
            "Precision@3",
            vector["precision_at_3"],
            vectorless["precision_at_3"],
        ),
        (
            "Precision@5",
            vector["precision_at_5"],
            vectorless["precision_at_5"],
        ),
        (
            "Hit Rate@1",
            vector["hit_rate_at_1"],
            vectorless["hit_rate_at_1"],
        ),
        (
            "MRR",
            vector[
                "mean_reciprocal_rank"
            ],
            vectorless[
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
        ),
    ]

    print(
        "SAFEOPS RETRIEVER COMPARISON"
    )

    print("=" * 58)

    print(
        f'{"Metric":<18}'
        f'{"Vector":>18}'
        f'{"Vectorless":>18}'
    )

    print("-" * 58)

    for metric, vector_value, vectorless_value in rows:
        print(
            f"{metric:<18}"
            f"{vector_value:>18.4f}"
            f"{vectorless_value:>18.4f}"
        )


if __name__ == "__main__":
    main()