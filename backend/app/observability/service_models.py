from enum import StrEnum

from pydantic import BaseModel

from app.observability.metric_models import ServiceMetrics
from app.observability.trace_models import (
    JaegerTraceSearchResult,
)


class EvidenceSource(StrEnum):
    """Origin of observability evidence."""

    LIVE = "live"
    FIXTURE = "fixture"


class ServiceMetricsEvidence(BaseModel):
    """Service metrics with explicit provenance."""

    source: EvidenceSource
    data: ServiceMetrics
    warning: str | None = None


class RecentTracesEvidence(BaseModel):
    """Recent traces with explicit provenance."""

    source: EvidenceSource
    data: JaegerTraceSearchResult
    warning: str | None = None