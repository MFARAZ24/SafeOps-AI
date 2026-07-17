from app.rag.evaluation import (
    evaluate_vector_retriever,
    save_evaluation_results,
)


def main() -> None:
    """Evaluate and display the SafeOps vector retriever."""

    evaluation = evaluate_vector_retriever()
    summary = evaluation["summary"]

    print("SAFEOPS VECTOR RETRIEVAL EVALUATION")
    print("=" * 56)

    for result in evaluation["questions"]:
        print()
        print(result["question_id"], "-", result["question"])
        print("Expected:", ", ".join(result["expected_document_ids"]))
        print("Retrieved:", ", ".join(result["retrieved_document_ids"]))
        print(
            "Recall@3:",
            f'{result["recall_at_3"]:.4f}',
            "| MRR:",
            f'{result["reciprocal_rank"]:.4f}',
            "| Latency:",
            f'{result["latency_ms"]:.2f} ms',
        )

    print()
    print("=" * 56)
    print("SUMMARY")
    print("=" * 56)
    print("Questions:", summary["question_count"])
    print("Recall@1:", f'{summary["recall_at_1"]:.4f}')
    print("Recall@3:", f'{summary["recall_at_3"]:.4f}')
    print("Recall@5:", f'{summary["recall_at_5"]:.4f}')
    print("Precision@3:", f'{summary["precision_at_3"]:.4f}')
    print("Precision@5:", f'{summary["precision_at_5"]:.4f}')
    print("Hit Rate@1:", f'{summary["hit_rate_at_1"]:.4f}')
    print("Hit Rate@3:", f'{summary["hit_rate_at_3"]:.4f}')
    print("Hit Rate@5:", f'{summary["hit_rate_at_5"]:.4f}')
    print("MRR:", f'{summary["mean_reciprocal_rank"]:.4f}')
    print("Average latency:", f'{summary["average_latency_ms"]:.2f} ms')

    output_path = save_evaluation_results(evaluation)

    print()
    print("Results saved to:")
    print(output_path)


if __name__ == "__main__":
    main()