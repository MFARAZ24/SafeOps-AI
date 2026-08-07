from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.observability.service_models import EvidenceSource
from app.tools.schemas import LogSeverity, ToolRiskLevel


class IncidentToolName(StrEnum):
    """Read-only tools available to the incident agent."""

    GET_SERVICE_DEPENDENCIES = "get_service_dependencies"
    GET_SERVICE_METRICS = "get_service_metrics"
    GET_RECENT_TRACES = "get_recent_traces"
    SEARCH_LOGS = "search_logs"
    GET_RECENT_DEPLOYMENTS = "get_recent_deployments"


class ServiceToolInput(BaseModel):
    """Input shared by tools that require only a service."""

    service_name: str = Field(
        min_length=1,
        description=("Service to investigate, such as checkout, payment, or recommendation."),
    )


class MetricToolInput(ServiceToolInput):
    """Input for retrieving service metrics."""

    window: str = Field(
        default="5m",
        pattern=r"^[1-9][0-9]*[smhdwy]$",
        description=("Prometheus lookback window, such as 5m or 1h."),
    )


class TraceToolInput(ServiceToolInput):
    """Input for retrieving recent distributed traces."""

    lookback: str = Field(
        default="1h",
        pattern=r"^[1-9][0-9]*[smhdwy]$",
        description=("Jaeger lookback window, such as 15m or 1h."),
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of traces to retrieve.",
    )


class LogSearchToolInput(ServiceToolInput):
    """Input for searching deterministic incident logs."""

    keywords: list[str] = Field(
        default_factory=list,
        description=("Optional keywords to match in log messages."),
    )
    severity: LogSeverity | None = Field(
        default=None,
        description=("Optional minimum search category: debug, info, warning, error, or critical."),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of log records.",
    )


class DeploymentToolInput(ServiceToolInput):
    """Input for retrieving recent deployments."""

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of deployment records.",
    )


class ToolEvidence(BaseModel):
    """Normalized evidence returned to the incident agent."""

    tool_name: IncidentToolName
    service: str

    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE_READ_ONLY
    requires_approval: bool = False

    source: EvidenceSource | None = None
    warning: str | None = None

    result: dict[str, Any]
