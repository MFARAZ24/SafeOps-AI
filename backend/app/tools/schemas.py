from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.observability.service_models import EvidenceSource


class ToolRiskLevel(StrEnum):
    """Safety classification for an incident tool."""

    SAFE_READ_ONLY = "safe_read_only"
    APPROVAL_REQUIRED = "approval_required"
    FORBIDDEN = "forbidden"


class LogSeverity(StrEnum):
    """Supported log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ToolDescriptor(BaseModel):
    """Metadata describing an available incident tool."""

    name: str
    description: str
    risk_level: ToolRiskLevel
    requires_approval: bool = False


class ServiceDependencies(BaseModel):
    """Structured dependency information for one service."""

    service: str
    upstream_services: list[str] = Field(default_factory=list)
    downstream_services: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    message_queues: list[str] = Field(default_factory=list)


class MetricSnapshot(BaseModel):
    """Operational metrics with explicit evidence provenance."""

    service: str
    observed_at: datetime

    source: EvidenceSource = EvidenceSource.FIXTURE
    window: str | None = None
    warning: str | None = None

    request_rate_rps: float | None = None
    error_rate_percent: float | None = None

    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None

    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_usage_bytes: float | None = None


class TraceSummary(BaseModel):
    """Compact incident-tool representation of one trace."""

    trace_id: str
    duration_ms: float
    services: list[str] = Field(default_factory=list)
    span_count: int
    has_error: bool
    error_operations: list[str] = Field(default_factory=list)
    key_events: list[str] = Field(default_factory=list)


class RecentTraceSearchResult(BaseModel):
    """Recent distributed traces with explicit provenance."""

    service: str
    source: EvidenceSource
    lookback: str
    result_count: int

    warning: str | None = None
    traces: list[TraceSummary] = Field(default_factory=list)


class LogRecord(BaseModel):
    """One normalized service log entry."""

    timestamp: datetime
    service: str
    severity: LogSeverity
    message: str
    trace_id: str | None = None


class LogSearchResult(BaseModel):
    """Results returned by a log search."""

    service: str
    keywords: list[str]
    severity: LogSeverity | None
    result_count: int
    records: list[LogRecord]


class DeploymentRecord(BaseModel):
    """One application deployment."""

    deployment_id: str
    service: str
    version: str
    deployed_at: datetime
    status: str
    commit_sha: str
    deployed_by: str


class DeploymentSearchResult(BaseModel):
    """Recent deployments for one service."""

    service: str
    result_count: int
    deployments: list[DeploymentRecord]
