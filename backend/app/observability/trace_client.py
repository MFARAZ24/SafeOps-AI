from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from app.observability.trace_models import (
    JaegerSpanSummary,
    JaegerTraceSearchResult,
    JaegerTraceSummary,
)


class JaegerTraceClientError(RuntimeError):
    """Raised when Jaeger trace retrieval or parsing fails."""


class JaegerTraceClient:
    """Read-only client for searching Jaeger traces."""

    TRACE_SEARCH_PATH = "/jaeger/ui/api/traces"

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        cleaned_base_url = base_url.strip().rstrip("/")

        if not cleaned_base_url:
            raise ValueError("Jaeger base URL cannot be empty.")

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

    def __enter__(self) -> "JaegerTraceClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def search_traces(
        self,
        service: str,
        *,
        lookback: str = "1h",
        limit: int = 10,
    ) -> JaegerTraceSearchResult:
        """Search recent traces for one service."""

        cleaned_service = service.strip()
        cleaned_lookback = lookback.strip()

        if not cleaned_service:
            raise ValueError(
                "Service name cannot be empty."
            )

        if not cleaned_lookback:
            raise ValueError(
                "Lookback cannot be empty."
            )

        if not 1 <= limit <= 100:
            raise ValueError(
                "Limit must be between 1 and 100."
            )

        try:
            response = self._client.get(
                self.TRACE_SEARCH_PATH,
                params={
                    "service": cleaned_service,
                    "lookback": cleaned_lookback,
                    "limit": limit,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise JaegerTraceClientError(
                "Jaeger trace search request failed."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise JaegerTraceClientError(
                "Jaeger trace search returned invalid JSON."
            ) from exc

        if not isinstance(payload, Mapping):
            raise JaegerTraceClientError(
                "Jaeger trace response must be a JSON object."
            )

        raw_traces = payload.get("data", [])

        if raw_traces is None:
            raw_traces = []

        if not isinstance(raw_traces, list):
            raise JaegerTraceClientError(
                "Jaeger response field 'data' must be a list."
            )

        traces = [
            self._parse_trace(raw_trace)
            for raw_trace in raw_traces
            if isinstance(raw_trace, Mapping)
        ]

        return JaegerTraceSearchResult(
            service=cleaned_service,
            lookback=cleaned_lookback,
            requested_limit=limit,
            returned_count=len(traces),
            reported_total=self._optional_int(
                payload.get("total")
            ),
            traces=traces,
        )

    @classmethod
    def _parse_trace(
        cls,
        raw_trace: Mapping[str, Any],
    ) -> JaegerTraceSummary:
        trace_id = str(raw_trace.get("traceID", ""))

        raw_processes = raw_trace.get("processes", {})

        processes = (
            raw_processes
            if isinstance(raw_processes, Mapping)
            else {}
        )

        raw_spans = raw_trace.get("spans", [])

        span_items = (
            raw_spans
            if isinstance(raw_spans, list)
            else []
        )

        spans: list[JaegerSpanSummary] = []

        for raw_span in span_items:
            if not isinstance(raw_span, Mapping):
                continue

            process_id = str(
                raw_span.get("processID", "")
            )

            raw_process = processes.get(
                process_id,
                {},
            )

            process = (
                raw_process
                if isinstance(raw_process, Mapping)
                else {}
            )

            service_name = str(
                process.get(
                    "serviceName",
                    "unknown",
                )
            )

            tags = cls._parse_tags(
                raw_span.get("tags", [])
            )

            events = cls._parse_events(
                raw_span.get("logs", [])
            )

            status_code = cls._optional_string(
                tags.get("otel.status_code")
            )

            status_description = cls._optional_string(
                tags.get("otel.status_description")
            )

            grpc_status_code = cls._optional_string(
                tags.get("rpc.grpc.status_code")
            )

            parent_span_id = cls._optional_string(
                raw_span.get("parentSpanID")
            )

            if parent_span_id == "":
                parent_span_id = None

            spans.append(
                JaegerSpanSummary(
                    trace_id=str(
                        raw_span.get(
                            "traceID",
                            trace_id,
                        )
                    ),
                    span_id=str(
                        raw_span.get("spanID", "")
                    ),
                    parent_span_id=parent_span_id,
                    service_name=service_name,
                    operation_name=str(
                        raw_span.get(
                            "operationName",
                            "unknown",
                        )
                    ),
                    start_time_unix_micros=cls._safe_int(
                        raw_span.get("startTime")
                    ),
                    duration_micros=cls._safe_int(
                        raw_span.get("duration")
                    ),
                    error=cls._span_has_error(
                        tags=tags,
                        status_code=status_code,
                        grpc_status_code=(
                            grpc_status_code
                        ),
                    ),
                    status_code=status_code,
                    status_description=(
                        status_description
                    ),
                    grpc_status_code=(
                        grpc_status_code
                    ),
                    tags=tags,
                    events=events,
                )
            )

        if spans:
            start_time = min(
                span.start_time_unix_micros
                for span in spans
            )

            end_time = max(
                (
                    span.start_time_unix_micros
                    + span.duration_micros
                )
                for span in spans
            )

            duration = max(
                0,
                end_time - start_time,
            )
        else:
            start_time = 0
            duration = 0

        services = sorted(
            {
                span.service_name
                for span in spans
                if span.service_name
            }
        )

        operations = sorted(
            {
                span.operation_name
                for span in spans
                if span.operation_name
            }
        )

        return JaegerTraceSummary(
            trace_id=trace_id,
            start_time_unix_micros=start_time,
            duration_micros=duration,
            services=services,
            operations=operations,
            has_error=any(
                span.error
                for span in spans
            ),
            spans=spans,
        )

    @staticmethod
    def _parse_tags(
        raw_tags: object,
    ) -> dict[str, Any]:
        if not isinstance(raw_tags, list):
            return {}

        tags: dict[str, Any] = {}

        for raw_tag in raw_tags:
            if not isinstance(raw_tag, Mapping):
                continue

            key = raw_tag.get("key")

            if key is None:
                continue

            tags[str(key)] = raw_tag.get("value")

        return tags

    @staticmethod
    def _parse_events(
        raw_logs: object,
    ) -> list[str]:
        if not isinstance(raw_logs, list):
            return []

        relevant_keys = {
            "event",
            "exception.type",
            "exception.message",
        }

        events: list[str] = []

        for raw_log in raw_logs:
            if not isinstance(raw_log, Mapping):
                continue

            raw_fields = raw_log.get(
                "fields",
                [],
            )

            if not isinstance(raw_fields, list):
                continue

            for raw_field in raw_fields:
                if not isinstance(
                    raw_field,
                    Mapping,
                ):
                    continue

                key = str(
                    raw_field.get("key", "")
                )

                if key not in relevant_keys:
                    continue

                value = raw_field.get("value")

                if value is None:
                    continue

                events.append(
                    f"{key}={value}"
                )

        return events

    @classmethod
    def _span_has_error(
        cls,
        *,
        tags: Mapping[str, Any],
        status_code: str | None,
        grpc_status_code: str | None,
    ) -> bool:
        if cls._is_truthy(tags.get("error")):
            return True

        if (
            status_code is not None
            and status_code.upper() == "ERROR"
        ):
            return True

        if grpc_status_code not in {
            None,
            "",
            "0",
        }:
            return True

        http_status = (
            tags.get("http.response.status_code")
            or tags.get("http.status_code")
        )

        parsed_http_status = cls._optional_int(
            http_status
        )

        return (
            parsed_http_status is not None
            and parsed_http_status >= 500
        )

    @staticmethod
    def _is_truthy(value: object) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {
                "true",
                "1",
                "yes",
            }

        return False

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _optional_int(
        value: object,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_string(
        value: object,
    ) -> str | None:
        if value is None:
            return None

        return str(value)