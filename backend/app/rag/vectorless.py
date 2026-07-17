import re
from dataclasses import dataclass

from langchain_core.documents import Document

from app.rag.ingestion import load_documents

SERVICE_ALIASES = {
    "recommendation": {
        "recommendation",
        "recommendations",
    },
    "checkout": {
        "checkout",
        "check out",
    },
    "payment": {
        "payment",
        "payments",
    },
    "cart": {
        "cart",
        "shopping cart",
    },
    "shipping": {
        "shipping",
    },
    "product-catalog": {
        "product catalog",
        "product information",
    },
    "frontend": {
        "frontend",
        "front end",
    },
}

CONCEPT_KEYWORDS = {
    "memory": {
        "memory",
        "ram",
        "memory leak",
        "out of memory",
        "oom",
        "cache",
        "garbage collection",
        "resource exhaustion",
    },
    "latency": {
        "latency",
        "slow",
        "slower",
        "timeout",
        "response time",
        "takes most",
        "consumes most",
    },
    "dependency": {
        "dependency",
        "downstream",
        "which service",
        "which services",
        "where should",
        "investigation continue",
        "child span",
        "span",
    },
    "approval": {
        "automatically",
        "can safeops",
        "human approval",
        "approval",
        "approve",
        "allowed",
        "permission",
        "safety rules",
        "ignore all safety",
    },
    "remediation": {
        "restart",
        "restarting",
        "rollback",
        "configuration change",
        "permanent fix",
        "remediation",
    },
    "prompt_injection": {
        "ignore previous instructions",
        "ignore all safety",
        "safety rules",
        "prompt injection",
        "untrusted instruction",
        "log message says",
    },
}

TYPE_BOOSTS = {
    "memory": {
        "runbook": 16.0,
        "service": 9.0,
        "architecture": 2.0,
    },
    "latency": {
        "runbook": 16.0,
        "service": 8.0,
        "architecture": 7.0,
    },
    "dependency": {
        "architecture": 16.0,
        "service": 7.0,
        "runbook": 4.0,
    },
    "approval": {
        "policy": 25.0,
        "service": 4.0,
        "runbook": 3.0,
    },
    "remediation": {
        "runbook": 9.0,
        "service": 5.0,
        "policy": 5.0,
    },
    "prompt_injection": {
        "policy": 30.0,
    },
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class QuerySignals:
    """Structured signals extracted from a user query."""

    normalized_query: str
    tokens: frozenset[str]
    services: frozenset[str]
    concepts: frozenset[str]


def tokenize(text: str) -> frozenset[str]:
    """Convert text into normalized lexical tokens."""

    return frozenset(
        TOKEN_PATTERN.findall(
            text.lower()
        )
    )


def analyze_query(query: str) -> QuerySignals:
    """Extract service and operational signals from a query."""

    normalized_query = " ".join(
        query.lower().split()
    )

    if not normalized_query:
        raise ValueError(
            "Search query cannot be empty."
        )

    services = {
        service
        for service, aliases
        in SERVICE_ALIASES.items()
        if any(
            alias in normalized_query
            for alias in aliases
        )
    }

    concepts = {
        concept
        for concept, keywords
        in CONCEPT_KEYWORDS.items()
        if any(
            keyword in normalized_query
            for keyword in keywords
        )
    }

    return QuerySignals(
        normalized_query=normalized_query,
        tokens=tokenize(
            normalized_query
        ),
        services=frozenset(
            services
        ),
        concepts=frozenset(
            concepts
        ),
    )


def score_document(
    document: Document,
    signals: QuerySignals,
) -> tuple[float, list[str]]:
    """Score a document using metadata and lexical evidence."""

    metadata = document.metadata

    document_type = str(
        metadata["document_type"]
    ).lower()

    service = str(
        metadata["service"]
    ).lower()

    title = str(
        metadata["title"]
    ).lower()

    tags = " ".join(
        str(tag).lower()
        for tag in metadata.get(
            "tags",
            [],
        )
    )

    body = document.page_content.lower()

    metadata_text = (
        f"{title} {tags} {service}"
    )

    score = 0.0
    reasons: list[str] = []

    if service in signals.services:
        score += 14.0
        reasons.append(
            f"matching service: {service}"
        )

    title_overlap = (
        signals.tokens
        & tokenize(title)
    )

    tag_overlap = (
        signals.tokens
        & tokenize(tags)
    )

    body_overlap = (
        signals.tokens
        & tokenize(body)
    )

    if title_overlap:
        score += (
            3.0
            * len(title_overlap)
        )

        reasons.append(
            "title overlap: "
            f"{sorted(title_overlap)}"
        )

    if tag_overlap:
        score += (
            2.5
            * len(tag_overlap)
        )

        reasons.append(
            "tag overlap: "
            f"{sorted(tag_overlap)}"
        )

    if body_overlap:
        score += min(
            5.0,
            0.4 * len(body_overlap),
        )

        reasons.append(
            "body overlap: "
            f"{len(body_overlap)} tokens"
        )

    for concept in signals.concepts:
        keywords = (
            CONCEPT_KEYWORDS[
                concept
            ]
        )

        metadata_match = any(
            keyword in metadata_text
            for keyword in keywords
        )

        body_match = any(
            keyword in body
            for keyword in keywords
        )

        type_boost = (
            TYPE_BOOSTS
            .get(concept, {})
            .get(
                document_type,
                0.0,
            )
        )

        if metadata_match:
            score += (
                type_boost
                + 6.0
            )

            reasons.append(
                f"{concept} metadata match"
            )

        elif body_match:
            score += (
                type_boost
                + 2.0
            )

            reasons.append(
                f"{concept} content match"
            )

    policy_intent = bool(
        {
            "approval",
            "prompt_injection",
        }
        & signals.concepts
    )

    if (
        policy_intent
        and document_type == "policy"
    ):
        score += 25.0

        reasons.append(
            "explicit safety-policy intent"
        )

    if (
        "dependency" in signals.concepts
        and document_type == "architecture"
    ):
        score += 10.0

        reasons.append(
            "architecture dependency intent"
        )

    return score, reasons


def preferred_document_types(
    signals: QuerySignals,
) -> list[str]:
    """Return preferred document-type diversity for a query."""

    if {
        "approval",
        "prompt_injection",
    } & signals.concepts:
        return [
            "policy",
            "service",
            "runbook",
            "architecture",
        ]

    if "memory" in signals.concepts:
        return [
            "runbook",
            "service",
            "architecture",
            "policy",
        ]

    if "latency" in signals.concepts:
        return [
            "runbook",
            "service",
            "architecture",
            "policy",
        ]

    if "dependency" in signals.concepts:
        return [
            "architecture",
            "service",
            "runbook",
            "policy",
        ]

    return [
        "service",
        "runbook",
        "architecture",
        "policy",
    ]


def diversify_results(
    scored_documents: list[
        tuple[Document, float]
    ],
    signals: QuerySignals,
    top_k: int,
) -> list[tuple[Document, float]]:
    """Prefer useful document-type diversity before filling ranks."""

    selected: list[
        tuple[Document, float]
    ] = []

    selected_ids: set[str] = set()

    for document_type in (
        preferred_document_types(
            signals
        )
    ):
        for document, score in scored_documents:
            document_id = str(
                document.metadata[
                    "document_id"
                ]
            )

            if (
                document_id
                in selected_ids
            ):
                continue

            if (
                str(
                    document.metadata[
                        "document_type"
                    ]
                ).lower()
                != document_type
            ):
                continue

            selected.append(
                (document, score)
            )

            selected_ids.add(
                document_id
            )

            break

        if len(selected) == top_k:
            return selected

    for document, score in scored_documents:
        document_id = str(
            document.metadata[
                "document_id"
            ]
        )

        if document_id in selected_ids:
            continue

        selected.append(
            (document, score)
        )

        selected_ids.add(
            document_id
        )

        if len(selected) == top_k:
            break

    return selected


def search_vectorless(
    query: str,
    *,
    top_k: int = 5,
) -> list[tuple[Document, float]]:
    """Retrieve documents without embeddings or vector search."""

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    signals = analyze_query(
        query
    )

    scored_documents: list[
        tuple[Document, float]
    ] = []

    for document in load_documents():
        score, reasons = score_document(
            document,
            signals,
        )

        ranked_document = Document(
            page_content=(
                document.page_content
            ),
            metadata={
                **document.metadata,
                "vectorless_reasons": (
                    reasons
                ),
                "detected_services": sorted(
                    signals.services
                ),
                "detected_concepts": sorted(
                    signals.concepts
                ),
            },
        )

        scored_documents.append(
            (
                ranked_document,
                score,
            )
        )

    scored_documents.sort(
        key=lambda item: (
            -item[1],
            str(
                item[0].metadata[
                    "document_id"
                ]
            ),
        )
    )

    return diversify_results(
        scored_documents,
        signals,
        top_k,
    )