from collections.abc import Callable

from app.observability.metric_client import (
    PrometheusMetricClient,
    PrometheusMetricClientError,
)
from app.observability.metric_models import ServiceMetrics
from app.observability.service_models import (
    EvidenceSource,
    RecentTracesEvidence,
    ServiceMetricsEvidence,
)
from app.observability.trace_client import (
    JaegerTraceClient,
    JaegerTraceClientError,
)
from app.observability.trace_models import (
    JaegerTraceSearchResult,
)

MetricFallback = Callable[
    [str, str],
    ServiceMetrics,
]

TraceFallback = Callable[
    [str, str, int],
    JaegerTraceSearchResult,
]

MetricClientFactory = Callable[
    [],
    PrometheusMetricClient,
]

TraceClientFactory = Callable[
    [],
    JaegerTraceClient,
]


class ObservabilityService:
    """Unified read-only access to Prometheus and Jaeger."""

    def __init__(
        self,
        *,
        prometheus_base_url: str,
        jaeger_base_url: str,
        timeout_seconds: float = 10.0,
        metric_fallback: MetricFallback | None = None,
        trace_fallback: TraceFallback | None = None,
        metric_client_factory: (
            MetricClientFactory | None
        ) = None,
        trace_client_factory: (
            TraceClientFactory | None
        ) = None,
    ) -> None:
        cleaned_prometheus_url = (
            prometheus_base_url.strip().rstrip("/")
        )
        cleaned_jaeger_url = (
            jaeger_base_url.strip().rstrip("/")
        )

        if not cleaned_prometheus_url:
            raise ValueError(
                "Prometheus base URL cannot be empty."
            )

        if not cleaned_jaeger_url:
            raise ValueError(
                "Jaeger base URL cannot be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero."
            )

        self._metric_fallback = metric_fallback
        self._trace_fallback = trace_fallback

        if metric_client_factory is None:

            def build_metric_client(
            ) -> PrometheusMetricClient:
                return PrometheusMetricClient(
                    base_url=cleaned_prometheus_url,
                    timeout_seconds=timeout_seconds,
                )

            self._metric_client_factory = (
                build_metric_client
            )
        else:
            self._metric_client_factory = (
                metric_client_factory
            )

        if trace_client_factory is None:

            def build_trace_client(
            ) -> JaegerTraceClient:
                return JaegerTraceClient(
                    base_url=cleaned_jaeger_url,
                    timeout_seconds=timeout_seconds,
                )

            self._trace_client_factory = (
                build_trace_client
            )
        else:
            self._trace_client_factory = (
                trace_client_factory
            )

    def get_service_metrics(
        self,
        service_name: str,
        *,
        window: str = "5m",
    ) -> ServiceMetricsEvidence:
        """Return live metrics or an explicit fixture fallback."""

        try:
            with self._metric_client_factory() as client:
                metrics = client.get_service_metrics(
                    service_name=service_name,
                    window=window,
                )

            return ServiceMetricsEvidence(
                source=EvidenceSource.LIVE,
                data=metrics,
            )
        except PrometheusMetricClientError as exc:
            if self._metric_fallback is None:
                raise

            fallback_data = self._metric_fallback(
                service_name,
                window,
            )

            return ServiceMetricsEvidence(
                source=EvidenceSource.FIXTURE,
                data=fallback_data,
                warning=(
                    "Live Prometheus metrics were "
                    f"unavailable: {exc}"
                ),
            )

    def get_recent_traces(
        self,
        service_name: str,
        *,
        lookback: str = "1h",
        limit: int = 10,
    ) -> RecentTracesEvidence:
        """Return live traces or an explicit fixture fallback."""

        try:
            with self._trace_client_factory() as client:
                traces = client.search_traces(
                    service=service_name,
                    lookback=lookback,
                    limit=limit,
                )

            return RecentTracesEvidence(
                source=EvidenceSource.LIVE,
                data=traces,
            )
        except JaegerTraceClientError as exc:
            if self._trace_fallback is None:
                raise

            fallback_data = self._trace_fallback(
                service_name,
                lookback,
                limit,
            )

            return RecentTracesEvidence(
                source=EvidenceSource.FIXTURE,
                data=fallback_data,
                warning=(
                    "Live Jaeger traces were "
                    f"unavailable: {exc}"
                ),
            )