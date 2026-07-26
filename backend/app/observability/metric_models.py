from pydantic import BaseModel


class PrometheusSample(BaseModel):
    """One normalized scalar value returned by Prometheus."""

    timestamp_unix: float
    value: float


class ServiceMetrics(BaseModel):
    """Live observability metrics for one service."""

    service_name: str
    window: str
    source: str = "prometheus"

    request_rate_per_second: float | None = None
    error_rate_per_second: float | None = None
    error_percentage: float | None = None

    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_p99_ms: float | None = None

    cpu_utilization_ratio: float | None = None
    memory_usage_bytes: float | None = None