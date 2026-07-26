from typing import Any

from pydantic import BaseModel, Field


class JaegerSpanSummary(BaseModel):
    """Compact representation of one Jaeger span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    service_name: str
    operation_name: str

    start_time_unix_micros: int
    duration_micros: int

    error: bool = False
    status_code: str | None = None
    status_description: str | None = None
    grpc_status_code: str | None = None

    tags: dict[str, Any] = Field(default_factory=dict)
    events: list[str] = Field(default_factory=list)


class JaegerTraceSummary(BaseModel):
    """Normalized summary of one distributed trace."""

    trace_id: str
    start_time_unix_micros: int
    duration_micros: int

    services: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)

    has_error: bool = False
    spans: list[JaegerSpanSummary] = Field(default_factory=list)


class JaegerTraceSearchResult(BaseModel):
    """Typed result returned by a Jaeger trace search."""

    service: str
    lookback: str
    requested_limit: int
    returned_count: int

    reported_total: int | None = None
    traces: list[JaegerTraceSummary] = Field(default_factory=list)