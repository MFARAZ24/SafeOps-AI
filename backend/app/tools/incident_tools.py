import os
from datetime import UTC, datetime

from app.observability.metric_models import ServiceMetrics
from app.observability.service import ObservabilityService
from app.observability.service_models import (
    EvidenceSource,
    RecentTracesEvidence,
    ServiceMetricsEvidence,
)
from app.observability.trace_models import (
    JaegerTraceSearchResult,
    JaegerTraceSummary,
)
from app.tools.local_data import (
    DEPLOYMENT_RECORDS,
    LOG_RECORDS,
    METRIC_SNAPSHOTS,
    SERVICE_DEPENDENCIES,
)
from app.tools.schemas import (
    DeploymentRecord,
    DeploymentSearchResult,
    LogRecord,
    LogSearchResult,
    LogSeverity,
    MetricSnapshot,
    RecentTraceSearchResult,
    ServiceDependencies,
    ToolDescriptor,
    ToolRiskLevel,
    TraceSummary,
)

SERVICE_ALIASES = {
    "recommendations": "recommendation",
    "recommendation-service": "recommendation",
    "checkout-service": "checkout",
    "payment-service": "payment",
    "product catalog": "product-catalog",
    "product-catalog-service": "product-catalog",
}


TOOL_CATALOG = [
    ToolDescriptor(
        name="get_service_dependencies",
        description=(
            "Return upstream services, downstream services, databases, and queues for a service."
        ),
        risk_level=ToolRiskLevel.SAFE_READ_ONLY,
    ),
    ToolDescriptor(
        name="get_service_metrics",
        description=(
            "Return live Prometheus operational metrics when "
            "available, otherwise an explicitly marked fixture."
        ),
        risk_level=ToolRiskLevel.SAFE_READ_ONLY,
    ),
    ToolDescriptor(
        name="get_recent_traces",
        description=("Return compact recent distributed trace summaries from Jaeger."),
        risk_level=ToolRiskLevel.SAFE_READ_ONLY,
    ),
    ToolDescriptor(
        name="search_logs",
        description=("Search normalized logs by service, keywords, and optional severity."),
        risk_level=ToolRiskLevel.SAFE_READ_ONLY,
    ),
    ToolDescriptor(
        name="get_recent_deployments",
        description=("Return recent deployment records for a service."),
        risk_level=ToolRiskLevel.SAFE_READ_ONLY,
    ),
]


def normalize_service_name(
    service_name: str,
) -> str:
    """Normalize and validate a service name."""

    normalized = "-".join(service_name.strip().lower().split())

    normalized = SERVICE_ALIASES.get(
        normalized,
        normalized,
    )

    if not normalized:
        raise ValueError("Service name cannot be empty.")

    return normalized


def list_incident_tools() -> list[ToolDescriptor]:
    """Return available incident tools and safety metadata."""

    return [descriptor.model_copy() for descriptor in TOOL_CATALOG]


def _fixture_metric_fallback(
    service_name: str,
    window: str,
) -> ServiceMetrics:
    """Convert an existing deterministic fixture to live shape."""

    metric_data = METRIC_SNAPSHOTS.get(service_name)

    if metric_data is None:
        raise ValueError(f"No metric fixture is available for service: {service_name}")

    snapshot = MetricSnapshot.model_validate(metric_data)

    cpu_ratio = snapshot.cpu_percent / 100.0 if snapshot.cpu_percent is not None else None

    return ServiceMetrics(
        service_name=service_name,
        window=window,
        source="fixture",
        request_rate_per_second=(snapshot.request_rate_rps),
        error_percentage=(snapshot.error_rate_percent),
        latency_p50_ms=(snapshot.p50_latency_ms),
        latency_p95_ms=(snapshot.p95_latency_ms),
        latency_p99_ms=(snapshot.p99_latency_ms),
        cpu_utilization_ratio=cpu_ratio,
        memory_usage_bytes=None,
    )


def _fixture_trace_fallback(
    service_name: str,
    lookback: str,
    limit: int,
) -> JaegerTraceSearchResult:
    """Return an explicitly empty trace fixture."""

    return JaegerTraceSearchResult(
        service=service_name,
        lookback=lookback,
        requested_limit=limit,
        returned_count=0,
        reported_total=0,
        traces=[],
    )


def _observability_timeout_seconds() -> float:
    raw_value = os.getenv(
        "OBSERVABILITY_TIMEOUT_SECONDS",
        "10",
    )

    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError("OBSERVABILITY_TIMEOUT_SECONDS must be numeric.") from exc

    if timeout <= 0:
        raise ValueError("OBSERVABILITY_TIMEOUT_SECONDS must be positive.")

    return timeout


def build_observability_service() -> ObservabilityService:
    """Build the default local observability service."""

    return ObservabilityService(
        prometheus_base_url=os.getenv(
            "PROMETHEUS_BASE_URL",
            "http://127.0.0.1:9090",
        ),
        jaeger_base_url=os.getenv(
            "JAEGER_BASE_URL",
            "http://127.0.0.1:8080",
        ),
        timeout_seconds=(_observability_timeout_seconds()),
        metric_fallback=(_fixture_metric_fallback),
        trace_fallback=(_fixture_trace_fallback),
    )


def get_service_dependencies(
    service_name: str,
) -> ServiceDependencies:
    """Return structured service dependency information."""

    service = normalize_service_name(service_name)

    dependency_data = SERVICE_DEPENDENCIES.get(service)

    if dependency_data is None:
        raise ValueError(f"Unknown service: {service}")

    return ServiceDependencies(
        service=service,
        **dependency_data,
    )


def _fixture_metric_snapshot(
    service: str,
    evidence: ServiceMetricsEvidence,
    window: str,
) -> MetricSnapshot:
    raw_fixture = METRIC_SNAPSHOTS.get(service)

    if raw_fixture is None:
        raise ValueError(f"No metric fixture is available for service: {service}")

    snapshot = MetricSnapshot.model_validate(raw_fixture)

    return snapshot.model_copy(
        update={
            "source": EvidenceSource.FIXTURE,
            "window": window,
            "warning": evidence.warning,
        }
    )


def _live_metric_snapshot(
    service: str,
    evidence: ServiceMetricsEvidence,
    window: str,
) -> MetricSnapshot:
    metrics = evidence.data

    cpu_percent = (
        metrics.cpu_utilization_ratio * 100.0 if metrics.cpu_utilization_ratio is not None else None
    )

    return MetricSnapshot(
        service=service,
        observed_at=datetime.now(UTC),
        source=EvidenceSource.LIVE,
        window=window,
        warning=evidence.warning,
        request_rate_rps=(metrics.request_rate_per_second),
        error_rate_percent=(metrics.error_percentage),
        p50_latency_ms=(metrics.latency_p50_ms),
        p95_latency_ms=(metrics.latency_p95_ms),
        p99_latency_ms=(metrics.latency_p99_ms),
        cpu_percent=cpu_percent,
        memory_percent=None,
        memory_usage_bytes=(metrics.memory_usage_bytes),
    )


def get_service_metrics(
    service_name: str,
    *,
    window: str = "5m",
) -> MetricSnapshot:
    """Return live metrics or an explicit fixture fallback."""

    service = normalize_service_name(service_name)

    observability = build_observability_service()

    evidence = observability.get_service_metrics(
        service_name=service,
        window=window,
    )

    if evidence.source == EvidenceSource.FIXTURE:
        return _fixture_metric_snapshot(
            service=service,
            evidence=evidence,
            window=window,
        )

    return _live_metric_snapshot(
        service=service,
        evidence=evidence,
        window=window,
    )


def _trace_key_events(
    trace: JaegerTraceSummary,
    *,
    limit: int = 20,
) -> list[str]:
    events: list[str] = []
    seen: set[str] = set()

    for span in trace.spans:
        for event in span.events:
            if event in seen:
                continue

            seen.add(event)
            events.append(event)

            if len(events) >= limit:
                return events

    return events


def _compact_trace(
    trace: JaegerTraceSummary,
) -> TraceSummary:
    error_operations = sorted({span.operation_name for span in trace.spans if span.error})

    return TraceSummary(
        trace_id=trace.trace_id,
        duration_ms=(trace.duration_micros / 1000.0),
        services=trace.services,
        span_count=len(trace.spans),
        has_error=trace.has_error,
        error_operations=error_operations,
        key_events=_trace_key_events(trace),
    )


def get_recent_traces(
    service_name: str,
    *,
    lookback: str = "1h",
    limit: int = 10,
) -> RecentTraceSearchResult:
    """Return compact live traces or explicit fallback data."""

    service = normalize_service_name(service_name)

    observability = build_observability_service()

    evidence: RecentTracesEvidence = observability.get_recent_traces(
        service_name=service,
        lookback=lookback,
        limit=limit,
    )

    compact_traces = [_compact_trace(trace) for trace in evidence.data.traces]

    return RecentTraceSearchResult(
        service=service,
        source=evidence.source,
        lookback=lookback,
        result_count=len(compact_traces),
        warning=evidence.warning,
        traces=compact_traces,
    )


def search_logs(
    service_name: str,
    *,
    keywords: list[str] | None = None,
    severity: LogSeverity | str | None = None,
    limit: int = 20,
) -> LogSearchResult:
    """Search service logs using deterministic filters."""

    service = normalize_service_name(service_name)

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")

    normalized_keywords = [
        keyword.strip().lower() for keyword in (keywords or []) if keyword.strip()
    ]

    selected_severity = LogSeverity(severity) if severity is not None else None

    matching_records: list[LogRecord] = []

    for raw_record in LOG_RECORDS:
        record = LogRecord.model_validate(raw_record)

        if record.service != service:
            continue

        if selected_severity is not None and record.severity != selected_severity:
            continue

        normalized_message = record.message.lower()

        if normalized_keywords and not any(
            keyword in normalized_message for keyword in normalized_keywords
        ):
            continue

        matching_records.append(record)

    matching_records.sort(
        key=lambda record: record.timestamp,
        reverse=True,
    )

    limited_records = matching_records[:limit]

    return LogSearchResult(
        service=service,
        keywords=normalized_keywords,
        severity=selected_severity,
        result_count=len(limited_records),
        records=limited_records,
    )


def get_recent_deployments(
    service_name: str,
    *,
    limit: int = 5,
) -> DeploymentSearchResult:
    """Return recent deployments for a service."""

    service = normalize_service_name(service_name)

    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20.")

    deployments = [
        DeploymentRecord.model_validate(record)
        for record in DEPLOYMENT_RECORDS
        if record["service"] == service
    ]

    deployments.sort(
        key=lambda deployment: deployment.deployed_at,
        reverse=True,
    )

    limited_deployments = deployments[:limit]

    return DeploymentSearchResult(
        service=service,
        result_count=len(limited_deployments),
        deployments=limited_deployments,
    )
