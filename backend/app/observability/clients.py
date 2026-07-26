from datetime import UTC, datetime
from typing import Any

import httpx

from app.observability.schemas import (
    JaegerServiceList,
    PrometheusQueryResult,
    PrometheusSample,
)


class ObservabilityBackendError(RuntimeError):
    """Raised when an observability backend cannot be queried."""


def _response_json(
    response: httpx.Response,
    *,
    backend_name: str,
) -> dict[str, Any]:
    """Validate an HTTP response and return its JSON body."""

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ObservabilityBackendError(
            f"{backend_name} returned HTTP {response.status_code}."
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ObservabilityBackendError(
            f"{backend_name} returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ObservabilityBackendError(
            f"{backend_name} returned an unexpected response."
        )

    return payload


class PrometheusClient:
    """Client for the Prometheus HTTP query API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None

        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        """Close the internally created HTTP client."""

        if self._owns_client:
            self._client.close()

    def query(
        self,
        expression: str,
    ) -> PrometheusQueryResult:
        """Run an instant PromQL query."""

        cleaned_expression = expression.strip()

        if not cleaned_expression:
            raise ValueError(
                "Prometheus query cannot be empty."
            )

        try:
            response = self._client.get(
                "/api/v1/query",
                params={
                    "query": cleaned_expression,
                },
            )
        except httpx.HTTPError as exc:
            raise ObservabilityBackendError(
                "Prometheus could not be reached."
            ) from exc

        payload = _response_json(
            response,
            backend_name="Prometheus",
        )

        if payload.get("status") != "success":
            error_message = payload.get(
                "error",
                "unknown Prometheus error",
            )

            raise ObservabilityBackendError(
                f"Prometheus query failed: {error_message}"
            )

        data = payload.get("data")

        if not isinstance(data, dict):
            raise ObservabilityBackendError(
                "Prometheus response is missing query data."
            )

        result_type = str(
            data.get(
                "resultType",
                "unknown",
            )
        )

        raw_result = data.get(
            "result",
            [],
        )

        if result_type == "scalar":
            raw_items = [
                {
                    "metric": {},
                    "value": raw_result,
                }
            ]
        elif isinstance(raw_result, list):
            raw_items = raw_result
        else:
            raise ObservabilityBackendError(
                "Prometheus returned an unsupported result."
            )

        samples: list[PrometheusSample] = []

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            raw_value = item.get("value")

            if (
                not isinstance(raw_value, list)
                or len(raw_value) != 2
            ):
                continue

            timestamp_value = float(
                raw_value[0]
            )

            sample_value = float(
                raw_value[1]
            )

            raw_metric = item.get(
                "metric",
                {},
            )

            metric = {
                str(key): str(value)
                for key, value in (
                    raw_metric.items()
                    if isinstance(raw_metric, dict)
                    else []
                )
            }

            samples.append(
                PrometheusSample(
                    metric=metric,
                    timestamp=datetime.fromtimestamp(
                        timestamp_value,
                        tz=UTC,
                    ),
                    value=sample_value,
                )
            )

        return PrometheusQueryResult(
            query=cleaned_expression,
            result_type=result_type,
            sample_count=len(samples),
            samples=samples,
        )


class JaegerClient:
    """Client for querying services known to Jaeger."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None

        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        """Close the internally created HTTP client."""

        if self._owns_client:
            self._client.close()

    def list_services(
        self,
    ) -> JaegerServiceList:
        """Return services currently available in Jaeger."""

        try:
            response = self._client.get(
                "/jaeger/ui/api/v3/services"
            )
        except httpx.HTTPError as exc:
            raise ObservabilityBackendError(
                "Jaeger could not be reached."
            ) from exc

        payload = _response_json(
            response,
            backend_name="Jaeger",
        )

        raw_services = payload.get(
            "services",
            [],
        )

        if not isinstance(raw_services, list):
            raise ObservabilityBackendError(
                "Jaeger returned an invalid service list."
            )

        services = sorted(
            {
                str(service)
                for service in raw_services
                if str(service).strip()
            }
        )

        return JaegerServiceList(
            service_count=len(services),
            services=services,
        )