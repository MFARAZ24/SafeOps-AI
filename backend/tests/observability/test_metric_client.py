import httpx
import pytest

from app.observability.metric_client import (
    PrometheusMetricClient,
    PrometheusMetricClientError,
)


def test_get_service_metrics_parses_values() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        query = request.url.params["query"]

        value: str | None

        if query.startswith("sum(rate("):
            if "STATUS_CODE_ERROR" in query:
                value = "0.02"
            else:
                value = "0.50"
        elif query.startswith(
            "histogram_quantile(0.5,"
        ):
            value = "20.0"
        elif query.startswith(
            "histogram_quantile(0.95,"
        ):
            value = "80.0"
        elif query.startswith(
            "histogram_quantile(0.99,"
        ):
            value = "120.0"
        elif "process_cpu_utilization_ratio" in query:
            value = "0.25"
        elif "process_memory_usage_bytes" in query:
            value = "104857600"
        else:
            raise AssertionError(
                f"Unexpected query: {query}"
            )

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

    client = PrometheusMetricClient(
        base_url="http://prometheus.test",
        transport=httpx.MockTransport(handler),
    )

    metrics = client.get_service_metrics(
        service_name="checkout",
        window="5m",
    )

    client.close()

    assert metrics.service_name == "checkout"
    assert metrics.source == "prometheus"
    assert metrics.request_rate_per_second == 0.50
    assert metrics.error_rate_per_second == 0.02
    assert metrics.error_percentage == 4.0
    assert metrics.latency_p50_ms == 20.0
    assert metrics.latency_p95_ms == 80.0
    assert metrics.latency_p99_ms == 120.0
    assert metrics.cpu_utilization_ratio == 0.25
    assert metrics.memory_usage_bytes == 104857600


def test_get_service_metrics_allows_missing_process_data() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        query = request.url.params["query"]

        if (
            "process_cpu_utilization_ratio" in query
            or "process_memory_usage_bytes" in query
        ):
            result = []
        else:
            result = [
                {
                    "metric": {},
                    "value": [
                        1_700_000_000,
                        "0",
                    ],
                }
            ]

        return httpx.Response(
            status_code=200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": result,
                },
            },
        )

    client = PrometheusMetricClient(
        base_url="http://prometheus.test",
        transport=httpx.MockTransport(handler),
    )

    metrics = client.get_service_metrics(
        service_name="checkout",
    )

    client.close()

    assert metrics.cpu_utilization_ratio is None
    assert metrics.memory_usage_bytes is None
    assert metrics.error_percentage == 0.0


def test_query_scalar_rejects_prometheus_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            json={
                "status": "error",
                "error": "query failed",
            },
        )

    client = PrometheusMetricClient(
        base_url="http://prometheus.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        PrometheusMetricClientError,
        match="query request failed",
    ):
        client.query_scalar("up")

    client.close()


def test_get_service_metrics_validates_window() -> None:
    client = PrometheusMetricClient(
        base_url="http://prometheus.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status_code=200,
                json={
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [],
                    },
                },
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="Window must look like",
    ):
        client.get_service_metrics(
            service_name="checkout",
            window="five minutes",
        )

    client.close()