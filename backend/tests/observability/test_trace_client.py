import httpx
import pytest

from app.observability.trace_client import (
    JaegerTraceClient,
    JaegerTraceClientError,
)


def test_search_traces_parses_jaeger_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.path
            == "/jaeger/ui/api/traces"
        )
        assert (
            request.url.params["service"]
            == "checkout"
        )
        assert (
            request.url.params["lookback"]
            == "15m"
        )
        assert request.url.params["limit"] == "5"

        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "traceID": "trace-123",
                        "processes": {
                            "p1": {
                                "serviceName": "checkout",
                            },
                            "p2": {
                                "serviceName": "payment",
                            },
                        },
                        "spans": [
                            {
                                "traceID": "trace-123",
                                "spanID": (
                                    "span-checkout"
                                ),
                                "parentSpanID": "",
                                "processID": "p1",
                                "operationName": (
                                    "oteldemo."
                                    "CheckoutService/"
                                    "PlaceOrder"
                                ),
                                "startTime": 1_000_000,
                                "duration": 20_000,
                                "tags": [
                                    {
                                        "key": (
                                            "otel."
                                            "status_code"
                                        ),
                                        "value": "OK",
                                    }
                                ],
                                "logs": [
                                    {
                                        "fields": [
                                            {
                                                "key": (
                                                    "event"
                                                ),
                                                "value": (
                                                    "prepared"
                                                ),
                                            },
                                            {
                                                "key": (
                                                    "event"
                                                ),
                                                "value": (
                                                    "charged"
                                                ),
                                            },
                                        ]
                                    }
                                ],
                            },
                            {
                                "traceID": "trace-123",
                                "spanID": (
                                    "span-payment"
                                ),
                                "parentSpanID": (
                                    "span-checkout"
                                ),
                                "processID": "p2",
                                "operationName": (
                                    "oteldemo."
                                    "PaymentService/"
                                    "Charge"
                                ),
                                "startTime": 1_005_000,
                                "duration": 5_000,
                                "tags": [
                                    {
                                        "key": (
                                            "rpc.grpc."
                                            "status_code"
                                        ),
                                        "value": 0,
                                    }
                                ],
                                "logs": [],
                            },
                        ],
                    }
                ],
                "total": 1,
                "limit": 5,
                "offset": 0,
                "errors": None,
            },
        )

    client = JaegerTraceClient(
        base_url="http://jaeger.test",
        transport=httpx.MockTransport(handler),
    )

    result = client.search_traces(
        service="checkout",
        lookback="15m",
        limit=5,
    )

    client.close()

    assert result.service == "checkout"
    assert result.returned_count == 1
    assert result.reported_total == 1

    trace = result.traces[0]

    assert trace.trace_id == "trace-123"
    assert trace.has_error is False
    assert trace.services == [
        "checkout",
        "payment",
    ]
    assert (
        trace.start_time_unix_micros
        == 1_000_000
    )
    assert trace.duration_micros == 20_000
    assert len(trace.spans) == 2

    checkout_span = trace.spans[0]

    assert (
        checkout_span.service_name
        == "checkout"
    )
    assert checkout_span.status_code == "OK"
    assert checkout_span.events == [
        "event=prepared",
        "event=charged",
    ]


def test_search_traces_marks_error_span() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {
                        "traceID": "trace-error",
                        "processes": {
                            "p1": {
                                "serviceName": (
                                    "frontend"
                                ),
                            }
                        },
                        "spans": [
                            {
                                "traceID": (
                                    "trace-error"
                                ),
                                "spanID": (
                                    "span-error"
                                ),
                                "processID": "p1",
                                "operationName": "POST",
                                "startTime": 100,
                                "duration": 50,
                                "tags": [
                                    {
                                        "key": (
                                            "otel."
                                            "status_code"
                                        ),
                                        "value": "ERROR",
                                    },
                                    {
                                        "key": (
                                            "otel."
                                            "status_description"
                                        ),
                                        "value": "Timeout",
                                    },
                                ],
                                "logs": [],
                            }
                        ],
                    }
                ],
                "total": 1,
            },
        )

    client = JaegerTraceClient(
        base_url="http://jaeger.test",
        transport=httpx.MockTransport(handler),
    )

    result = client.search_traces(
        service="frontend"
    )

    client.close()

    trace = result.traces[0]
    span = trace.spans[0]

    assert trace.has_error is True
    assert span.error is True
    assert (
        span.status_description
        == "Timeout"
    )


def test_search_traces_rejects_invalid_json() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            text="<html>Jaeger UI</html>",
        )

    client = JaegerTraceClient(
        base_url="http://jaeger.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        JaegerTraceClientError,
        match="invalid JSON",
    ):
        client.search_traces(
            service="checkout"
        )

    client.close()


def test_search_traces_validates_limit() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"data": []},
        )

    client = JaegerTraceClient(
        base_url="http://jaeger.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ValueError,
        match="between 1 and 100",
    ):
        client.search_traces(
            service="checkout",
            limit=0,
        )

    client.close()