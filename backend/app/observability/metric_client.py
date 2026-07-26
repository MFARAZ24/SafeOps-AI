import math
import re
from collections.abc import Mapping
from types import TracebackType

import httpx

from app.observability.metric_models import (
    PrometheusSample,
    ServiceMetrics,
)


class PrometheusMetricClientError(RuntimeError):
    """Raised when Prometheus retrieval or parsing fails."""


class PrometheusMetricClient:
    """Read-only client for service-level Prometheus metrics."""

    QUERY_PATH = "/api/v1/query"
    WINDOW_PATTERN = re.compile(r"^[1-9][0-9]*[smhdwy]$")

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        cleaned_base_url = base_url.strip().rstrip("/")

        if not cleaned_base_url:
            raise ValueError(
                "Prometheus base URL cannot be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Timeout must be greater than zero."
            )

        self._client = httpx.Client(
            base_url=cleaned_base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self._client.close()

    def __enter__(self) -> "PrometheusMetricClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def query_scalar(
        self,
        promql: str,
    ) -> PrometheusSample | None:
        """Run an instant query expected to return one scalar value."""

        cleaned_query = promql.strip()

        if not cleaned_query:
            raise ValueError(
                "PromQL query cannot be empty."
            )

        try:
            response = self._client.get(
                self.QUERY_PATH,
                params={"query": cleaned_query},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrometheusMetricClientError(
                "Prometheus query request failed."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise PrometheusMetricClientError(
                "Prometheus returned invalid JSON."
            ) from exc

        if not isinstance(payload, Mapping):
            raise PrometheusMetricClientError(
                "Prometheus response must be a JSON object."
            )

        if payload.get("status") != "success":
            raise PrometheusMetricClientError(
                "Prometheus query was not successful."
            )

        raw_data = payload.get("data")

        if not isinstance(raw_data, Mapping):
            raise PrometheusMetricClientError(
                "Prometheus response field 'data' is invalid."
            )

        result_type = raw_data.get("resultType")
        raw_result = raw_data.get("result")

        if result_type == "vector":
            return self._parse_vector_result(raw_result)

        if result_type == "scalar":
            return self._parse_sample_pair(raw_result)

        raise PrometheusMetricClientError(
            "Prometheus returned an unsupported result type."
        )

    def get_service_metrics(
        self,
        service_name: str,
        *,
        window: str = "5m",
    ) -> ServiceMetrics:
        """Retrieve request, error, latency, CPU, and memory metrics."""

        cleaned_service = service_name.strip()
        cleaned_window = window.strip()

        if not cleaned_service:
            raise ValueError(
                "Service name cannot be empty."
            )

        if not self.WINDOW_PATTERN.fullmatch(
            cleaned_window
        ):
            raise ValueError(
                "Window must look like 5m, 1h, or 1d."
            )

        escaped_service = self._escape_label_value(
            cleaned_service
        )

        server_selector = (
            f'service_name="{escaped_service}",'
            'span_kind="SPAN_KIND_SERVER"'
        )

        error_selector = (
            f'{server_selector},'
            'status_code="STATUS_CODE_ERROR"'
        )

        request_query = (
            "sum(rate("
            "traces_span_metrics_calls_total"
            f"{{{server_selector}}}"
            f"[{cleaned_window}]"
            "))"
        )

        error_query = (
            "sum(rate("
            "traces_span_metrics_calls_total"
            f"{{{error_selector}}}"
            f"[{cleaned_window}]"
            "))"
        )

        latency_queries = {
            "p50": self._latency_query(
                quantile=0.50,
                selector=server_selector,
                window=cleaned_window,
            ),
            "p95": self._latency_query(
                quantile=0.95,
                selector=server_selector,
                window=cleaned_window,
            ),
            "p99": self._latency_query(
                quantile=0.99,
                selector=server_selector,
                window=cleaned_window,
            ),
        }

        cpu_query = (
            "max("
            "process_cpu_utilization_ratio"
            f'{{service_name="{escaped_service}"}}'
            ")"
        )

        memory_query = (
            "max("
            "process_memory_usage_bytes"
            f'{{service_name="{escaped_service}"}}'
            ")"
        )

        request_rate = self._sample_value(
            self.query_scalar(request_query)
        )

        error_rate = self._sample_value(
            self.query_scalar(error_query)
        )

        latency_p50 = self._sample_value(
            self.query_scalar(
                latency_queries["p50"]
            )
        )

        latency_p95 = self._sample_value(
            self.query_scalar(
                latency_queries["p95"]
            )
        )

        latency_p99 = self._sample_value(
            self.query_scalar(
                latency_queries["p99"]
            )
        )

        cpu_utilization = self._sample_value(
            self.query_scalar(cpu_query)
        )

        memory_usage = self._sample_value(
            self.query_scalar(memory_query)
        )

        error_percentage = self._error_percentage(
            request_rate=request_rate,
            error_rate=error_rate,
        )

        return ServiceMetrics(
            service_name=cleaned_service,
            window=cleaned_window,
            request_rate_per_second=request_rate,
            error_rate_per_second=error_rate,
            error_percentage=error_percentage,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_p99_ms=latency_p99,
            cpu_utilization_ratio=cpu_utilization,
            memory_usage_bytes=memory_usage,
        )

    @staticmethod
    def _latency_query(
        *,
        quantile: float,
        selector: str,
        window: str,
    ) -> str:
        return (
            f"histogram_quantile({quantile}, "
            "sum by (le) (rate("
            "traces_span_metrics_duration_milliseconds_bucket"
            f"{{{selector}}}"
            f"[{window}]"
            ")))"
        )

    @classmethod
    def _parse_vector_result(
        cls,
        raw_result: object,
    ) -> PrometheusSample | None:
        if not isinstance(raw_result, list):
            raise PrometheusMetricClientError(
                "Prometheus vector result must be a list."
            )

        if not raw_result:
            return None

        first_result = raw_result[0]

        if not isinstance(first_result, Mapping):
            raise PrometheusMetricClientError(
                "Prometheus vector item is invalid."
            )

        return cls._parse_sample_pair(
            first_result.get("value")
        )

    @staticmethod
    def _parse_sample_pair(
        raw_sample: object,
    ) -> PrometheusSample | None:
        if not isinstance(raw_sample, list):
            raise PrometheusMetricClientError(
                "Prometheus sample must be a list."
            )

        if len(raw_sample) != 2:
            raise PrometheusMetricClientError(
                "Prometheus sample must contain two values."
            )

        try:
            timestamp = float(raw_sample[0])
            value = float(raw_sample[1])
        except (TypeError, ValueError) as exc:
            raise PrometheusMetricClientError(
                "Prometheus sample contains invalid numbers."
            ) from exc

        if not math.isfinite(value):
            return None

        return PrometheusSample(
            timestamp_unix=timestamp,
            value=value,
        )

    @staticmethod
    def _sample_value(
        sample: PrometheusSample | None,
    ) -> float | None:
        if sample is None:
            return None

        return sample.value

    @staticmethod
    def _error_percentage(
        *,
        request_rate: float | None,
        error_rate: float | None,
    ) -> float | None:
        if request_rate is None:
            return None

        if request_rate <= 0:
            return 0.0

        if error_rate is None:
            return 0.0

        return min(
            100.0,
            max(
                0.0,
                error_rate / request_rate * 100.0,
            ),
        )

    @staticmethod
    def _escape_label_value(value: str) -> str:
        return (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )