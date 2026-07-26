from datetime import datetime

from pydantic import BaseModel, Field


class PrometheusSample(BaseModel):
    """One sample returned by an instant Prometheus query."""

    metric: dict[str, str] = Field(
        default_factory=dict
    )
    timestamp: datetime
    value: float


class PrometheusQueryResult(BaseModel):
    """Normalized result of a Prometheus instant query."""

    query: str
    result_type: str
    sample_count: int
    samples: list[PrometheusSample]


class JaegerServiceList(BaseModel):
    """Services currently known to Jaeger."""

    service_count: int
    services: list[str]