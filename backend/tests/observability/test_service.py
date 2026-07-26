import httpx

from app.observability.metric_client import (
    PrometheusMetricClient,
)
from app.observability.metric_models import ServiceMetrics
from app.observability.service import (
    ObservabilityService,
)
from app.observability.service_models import (
    EvidenceSource,
)
from app.observability.trace_client import (
    JaegerTraceClient,
)
from app.observability.trace_models import (
    JaegerTraceSearchResult,
)


def test_returns_live_prometheus_metrics() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        query = request.url.params["query"]

        if "STATUS_CODE_ERROR" in query:
            value = "0.01"
        elif "process_cpu_utilization_ratio" in query:
            value = "0.20"
        elif "process_memory_usage_bytes" in query:
            value = "104857600"
        elif "histogram_quantile" in query:
            value = "25"
        else:
            value = "0.50"

        return httpx.Response(
            status_code=200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {},
                            "value": [
                                1_700_000_000,
                                value,
                            ],
                        }
                    ],
                },
            },
        )

    def build_metric_client(
    ) -> PrometheusMetricClient:
        return PrometheusMetricClient(
            base_url="http://prometheus.test",
            transport=httpx.MockTransport(
                handler
            ),
        )

    service = ObservabilityService(
        prometheus_base_url=(
            "http://prometheus.test"
        ),
        jaeger_base_url="http://jaeger.test",
        metric_client_factory=(
            build_metric_client
        ),
    )

    result = service.get_service_metrics(
        service_name="checkout",
        window="5m",
    )

    assert result.source == EvidenceSource.LIVE
    assert result.warning is None
    assert result.data.service_name == "checkout"
    assert (
        result.data.request_rate_per_second
        == 0.50
    )
    assert result.data.error_percentage == 2.0


def test_uses_explicit_metric_fallback() -> None:
    def failing_handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=503,
            json={
                "status": "error",
                "error": "unavailable",
            },
        )

    def build_metric_client(
    ) -> PrometheusMetricClient:
        return PrometheusMetricClient(
            base_url="http://prometheus.test",
            transport=httpx.MockTransport(
                failing_handler
            ),
        )

    def metric_fallback(
        service_name: str,
        window: str,
    ) -> ServiceMetrics:
        return ServiceMetrics(
            service_name=service_name,
            window=window,
            source="fixture",
            request_rate_per_second=1.25,
            error_rate_per_second=0.05,
            error_percentage=4.0,
        )

    service = ObservabilityService(
        prometheus_base_url=(
            "http://prometheus.test"
        ),
        jaeger_base_url="http://jaeger.test",
        metric_fallback=metric_fallback,
        metric_client_factory=(
            build_metric_client
        ),
    )

    result = service.get_service_metrics(
        service_name="checkout",
        window="5m",
    )

    assert result.source == EvidenceSource.FIXTURE
    assert result.warning is not None
    assert result.data.source == "fixture"
    assert (
        result.data.request_rate_per_second
        == 1.25
    )


def test_returns_live_jaeger_traces() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "traceID": "trace-live",
                        "processes": {},
                        "spans": [],
                    }
                ],
                "total": 1,
            },
        )

    def build_trace_client(
    ) -> JaegerTraceClient:
        return JaegerTraceClient(
            base_url="http://jaeger.test",
            transport=httpx.MockTransport(
                handler
            ),
        )

    service = ObservabilityService(
        prometheus_base_url=(
            "http://prometheus.test"
        ),
        jaeger_base_url="http://jaeger.test",
        trace_client_factory=build_trace_client,
    )

    result = service.get_recent_traces(
        service_name="checkout",
        lookback="1h",
        limit=5,
    )

    assert result.source == EvidenceSource.LIVE
    assert result.warning is None
    assert result.data.returned_count == 1
    assert (
        result.data.traces[0].trace_id
        == "trace-live"
    )


def test_uses_explicit_trace_fallback() -> None:
    def failing_handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=503,
            json={
                "error": "unavailable",
            },
        )

    def build_trace_client(
    ) -> JaegerTraceClient:
        return JaegerTraceClient(
            base_url="http://jaeger.test",
            transport=httpx.MockTransport(
                failing_handler
            ),
        )

    def trace_fallback(
        service_name: str,
        lookback: str,
        limit: int,
    ) -> JaegerTraceSearchResult:
        return JaegerTraceSearchResult(
            service=service_name,
            lookback=lookback,
            requested_limit=limit,
            returned_count=0,
            reported_total=0,
            traces=[],
        )

    service = ObservabilityService(
        prometheus_base_url=(
            "http://prometheus.test"
        ),
        jaeger_base_url="http://jaeger.test",
        trace_fallback=trace_fallback,
        trace_client_factory=build_trace_client,
    )

    result = service.get_recent_traces(
        service_name="checkout",
        lookback="1h",
        limit=5,
    )

    assert result.source == EvidenceSource.FIXTURE
    assert result.warning is not None
    assert result.data.returned_count == 0