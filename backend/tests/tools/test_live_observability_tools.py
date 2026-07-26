from datetime import UTC, datetime

from app.observability.metric_models import ServiceMetrics
from app.observability.service_models import (
    EvidenceSource,
    RecentTracesEvidence,
    ServiceMetricsEvidence,
)
from app.observability.trace_models import (
    JaegerSpanSummary,
    JaegerTraceSearchResult,
    JaegerTraceSummary,
)
from app.tools import incident_tools
from app.tools.schemas import ToolRiskLevel


class FakeLiveObservabilityService:
    def get_service_metrics(
        self,
        service_name: str,
        *,
        window: str,
    ) -> ServiceMetricsEvidence:
        return ServiceMetricsEvidence(
            source=EvidenceSource.LIVE,
            data=ServiceMetrics(
                service_name=service_name,
                window=window,
                request_rate_per_second=2.5,
                error_rate_per_second=0.1,
                error_percentage=4.0,
                latency_p50_ms=20.0,
                latency_p95_ms=80.0,
                latency_p99_ms=120.0,
                cpu_utilization_ratio=0.25,
                memory_usage_bytes=104857600,
            ),
        )

    def get_recent_traces(
        self,
        service_name: str,
        *,
        lookback: str,
        limit: int,
    ) -> RecentTracesEvidence:
        span = JaegerSpanSummary(
            trace_id="trace-live",
            span_id="span-live",
            service_name=service_name,
            operation_name=("oteldemo.CheckoutService/PlaceOrder"),
            start_time_unix_micros=1_000_000,
            duration_micros=50_000,
            error=False,
            events=[
                "event=prepared",
                "event=charged",
                "event=shipped",
            ],
        )

        trace = JaegerTraceSummary(
            trace_id="trace-live",
            start_time_unix_micros=1_000_000,
            duration_micros=50_000,
            services=[
                "checkout",
                "payment",
                "shipping",
            ],
            operations=[
                "oteldemo.CheckoutService/PlaceOrder",
            ],
            has_error=False,
            spans=[span],
        )

        return RecentTracesEvidence(
            source=EvidenceSource.LIVE,
            data=JaegerTraceSearchResult(
                service=service_name,
                lookback=lookback,
                requested_limit=limit,
                returned_count=1,
                reported_total=1,
                traces=[trace],
            ),
        )


class FakeFixtureObservabilityService:
    def get_service_metrics(
        self,
        service_name: str,
        *,
        window: str,
    ) -> ServiceMetricsEvidence:
        return ServiceMetricsEvidence(
            source=EvidenceSource.FIXTURE,
            warning="Prometheus unavailable.",
            data=ServiceMetrics(
                service_name=service_name,
                window=window,
                source="fixture",
                request_rate_per_second=41.8,
                error_percentage=4.7,
            ),
        )


def test_catalog_includes_safe_trace_tool() -> None:
    descriptors = {
        descriptor.name: descriptor for descriptor in incident_tools.list_incident_tools()
    }

    assert "get_recent_traces" in descriptors
    assert descriptors["get_recent_traces"].risk_level == ToolRiskLevel.SAFE_READ_ONLY
    assert descriptors["get_recent_traces"].requires_approval is False


def test_get_service_metrics_returns_live_data(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        incident_tools,
        "build_observability_service",
        lambda: FakeLiveObservabilityService(),
    )

    result = incident_tools.get_service_metrics(
        "checkout",
        window="5m",
    )

    assert result.service == "checkout"
    assert result.source == EvidenceSource.LIVE
    assert result.window == "5m"
    assert result.warning is None
    assert result.request_rate_rps == 2.5
    assert result.error_rate_percent == 4.0
    assert result.p95_latency_ms == 80.0
    assert result.cpu_percent == 25.0
    assert result.memory_usage_bytes == 104857600
    assert result.memory_percent is None
    assert isinstance(
        result.observed_at,
        datetime,
    )
    assert result.observed_at.tzinfo == UTC


def test_get_service_metrics_marks_fixture_fallback(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        incident_tools,
        "build_observability_service",
        lambda: FakeFixtureObservabilityService(),
    )

    result = incident_tools.get_service_metrics(
        "checkout",
        window="5m",
    )

    assert result.source == EvidenceSource.FIXTURE
    assert result.warning == "Prometheus unavailable."
    assert result.request_rate_rps == 41.8
    assert result.error_rate_percent == 4.7
    assert result.memory_percent == 58.4


def test_get_recent_traces_returns_compact_data(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        incident_tools,
        "build_observability_service",
        lambda: FakeLiveObservabilityService(),
    )

    result = incident_tools.get_recent_traces(
        "checkout",
        lookback="1h",
        limit=5,
    )

    assert result.source == EvidenceSource.LIVE
    assert result.result_count == 1

    trace = result.traces[0]

    assert trace.trace_id == "trace-live"
    assert trace.duration_ms == 50.0
    assert trace.span_count == 1
    assert trace.has_error is False
    assert trace.error_operations == []
    assert trace.key_events == [
        "event=prepared",
        "event=charged",
        "event=shipped",
    ]
