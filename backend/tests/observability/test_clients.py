import httpx

from app.observability.clients import (
    JaegerClient,
    PrometheusClient,
)


def test_prometheus_query_is_normalized() -> None:
    """Prometheus vector responses should become typed samples."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.path
            == "/api/v1/query"
        )

        assert (
            request.url.params["query"]
            == "up"
        )

        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "__name__": "up",
                                "job": "prometheus",
                            },
                            "value": [
                                1784664000.0,
                                "1",
                            ],
                        }
                    ],
                },
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    http_client = httpx.Client(
        base_url="http://prometheus",
        transport=transport,
    )

    client = PrometheusClient(
        "http://prometheus",
        client=http_client,
    )

    result = client.query("up")

    assert result.result_type == "vector"
    assert result.sample_count == 1
    assert result.samples[0].value == 1.0

    http_client.close()


def test_jaeger_service_list_is_normalized() -> None:
    """Jaeger services should be sorted and deduplicated."""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.path
            == "/jaeger/ui/api/v3/services"
        )

        return httpx.Response(
            200,
            json={
                "services": [
                    "payment",
                    "checkout",
                    "payment",
                ]
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    http_client = httpx.Client(
        base_url="http://jaeger",
        transport=transport,
    )

    client = JaegerClient(
        "http://jaeger",
        client=http_client,
    )

    result = client.list_services()

    assert result.service_count == 2

    assert result.services == [
        "checkout",
        "payment",
    ]

    http_client.close()