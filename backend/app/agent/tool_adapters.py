from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from app.agent.schemas import (
    DeploymentToolInput,
    IncidentToolName,
    LogSearchToolInput,
    MetricToolInput,
    ServiceToolInput,
    ToolEvidence,
    TraceToolInput,
)
from app.observability.service_models import EvidenceSource
from app.tools import incident_tools
from app.tools.schemas import (
    ToolDescriptor,
    ToolRiskLevel,
)


class UnsafeToolRegistrationError(RuntimeError):
    """Raised when a tool fails the read-only safety policy."""


ToolFunction = Callable[..., dict[str, Any]]


def _descriptor_map() -> dict[str, ToolDescriptor]:
    """Return current tool descriptors by name."""

    return {descriptor.name: descriptor for descriptor in incident_tools.list_incident_tools()}


def _validate_safe_descriptor(
    tool_name: IncidentToolName,
    descriptors: dict[str, ToolDescriptor],
) -> ToolDescriptor:
    """Ensure a tool is explicitly safe and approval-free."""

    descriptor = descriptors.get(tool_name.value)

    if descriptor is None:
        raise UnsafeToolRegistrationError(
            f"Required tool is missing from the catalog: {tool_name.value}"
        )

    if descriptor.risk_level != ToolRiskLevel.SAFE_READ_ONLY:
        raise UnsafeToolRegistrationError(f"Tool is not read-only: {tool_name.value}")

    if descriptor.requires_approval:
        raise UnsafeToolRegistrationError(
            f"Approval-required tools cannot be exposed to the read-only agent: {tool_name.value}"
        )

    return descriptor


def _extract_source(
    payload: dict[str, Any],
) -> EvidenceSource | None:
    """Parse optional live or fixture provenance."""

    raw_source = payload.get("source")

    if raw_source is None:
        return None

    try:
        return EvidenceSource(str(raw_source))
    except ValueError:
        return None


def _build_evidence(
    *,
    tool_name: IncidentToolName,
    service: str,
    result: BaseModel,
) -> dict[str, Any]:
    """Normalize a tool result for the incident agent."""

    payload = result.model_dump(
        mode="json",
    )

    evidence = ToolEvidence(
        tool_name=tool_name,
        service=service,
        source=_extract_source(payload),
        warning=payload.get("warning"),
        result=payload,
    )

    return evidence.model_dump(
        mode="json",
    )


def _get_service_dependencies(
    service_name: str,
) -> dict[str, Any]:
    result = incident_tools.get_service_dependencies(service_name)

    return _build_evidence(
        tool_name=(IncidentToolName.GET_SERVICE_DEPENDENCIES),
        service=result.service,
        result=result,
    )


def _get_service_metrics(
    service_name: str,
    window: str = "5m",
) -> dict[str, Any]:
    result = incident_tools.get_service_metrics(
        service_name,
        window=window,
    )

    return _build_evidence(
        tool_name=IncidentToolName.GET_SERVICE_METRICS,
        service=result.service,
        result=result,
    )


def _get_recent_traces(
    service_name: str,
    lookback: str = "1h",
    limit: int = 10,
) -> dict[str, Any]:
    result = incident_tools.get_recent_traces(
        service_name,
        lookback=lookback,
        limit=limit,
    )

    return _build_evidence(
        tool_name=IncidentToolName.GET_RECENT_TRACES,
        service=result.service,
        result=result,
    )


def _search_logs(
    service_name: str,
    keywords: list[str] | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    result = incident_tools.search_logs(
        service_name,
        keywords=keywords,
        severity=severity,
        limit=limit,
    )

    return _build_evidence(
        tool_name=IncidentToolName.SEARCH_LOGS,
        service=result.service,
        result=result,
    )


def _get_recent_deployments(
    service_name: str,
    limit: int = 5,
) -> dict[str, Any]:
    result = incident_tools.get_recent_deployments(
        service_name,
        limit=limit,
    )

    return _build_evidence(
        tool_name=(IncidentToolName.GET_RECENT_DEPLOYMENTS),
        service=result.service,
        result=result,
    )


def _structured_tool(
    *,
    tool_name: IncidentToolName,
    description: str,
    function: ToolFunction,
    args_schema: type[BaseModel],
    descriptors: dict[str, ToolDescriptor],
) -> StructuredTool:
    """Create one tool only after validating safety."""

    _validate_safe_descriptor(
        tool_name,
        descriptors,
    )

    return StructuredTool.from_function(
        func=function,
        name=tool_name.value,
        description=description,
        args_schema=args_schema,
    )


def build_safe_incident_tools() -> list[BaseTool]:
    """Build the complete read-only incident tool set."""

    descriptors = _descriptor_map()

    tools: list[BaseTool] = [
        _structured_tool(
            tool_name=(IncidentToolName.GET_SERVICE_DEPENDENCIES),
            description=(
                "Inspect the upstream and downstream "
                "dependencies, databases, and message queues "
                "for a service. Use this to understand likely "
                "failure propagation."
            ),
            function=_get_service_dependencies,
            args_schema=ServiceToolInput,
            descriptors=descriptors,
        ),
        _structured_tool(
            tool_name=(IncidentToolName.GET_SERVICE_METRICS),
            description=(
                "Retrieve service request rate, error rate, "
                "latency percentiles, CPU, and memory metrics. "
                "The result explicitly identifies live or "
                "fixture evidence."
            ),
            function=_get_service_metrics,
            args_schema=MetricToolInput,
            descriptors=descriptors,
        ),
        _structured_tool(
            tool_name=(IncidentToolName.GET_RECENT_TRACES),
            description=(
                "Retrieve compact recent Jaeger traces, "
                "including errors, involved services, "
                "operations, durations, and key events."
            ),
            function=_get_recent_traces,
            args_schema=TraceToolInput,
            descriptors=descriptors,
        ),
        _structured_tool(
            tool_name=IncidentToolName.SEARCH_LOGS,
            description=(
                "Search normalized service logs using optional keywords and severity filters."
            ),
            function=_search_logs,
            args_schema=LogSearchToolInput,
            descriptors=descriptors,
        ),
        _structured_tool(
            tool_name=(IncidentToolName.GET_RECENT_DEPLOYMENTS),
            description=(
                "Retrieve recent deployments for a service to "
                "check whether an incident correlates with a "
                "release or configuration change."
            ),
            function=_get_recent_deployments,
            args_schema=DeploymentToolInput,
            descriptors=descriptors,
        ),
    ]

    return tools


def get_safe_incident_tool(
    tool_name: IncidentToolName | str,
) -> BaseTool:
    """Return one validated incident tool by name."""

    selected_name = IncidentToolName(tool_name)

    tools = {tool.name: tool for tool in build_safe_incident_tools()}

    return tools[selected_name.value]
