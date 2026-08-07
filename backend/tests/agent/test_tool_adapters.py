from datetime import UTC, datetime

import pytest

from app.agent.schemas import IncidentToolName
from app.agent.tool_adapters import (
    UnsafeToolRegistrationError,
    build_safe_incident_tools,
    get_safe_incident_tool,
)
from app.observability.service_models import EvidenceSource
from app.tools import incident_tools
from app.tools.schemas import (
    MetricSnapshot,
    ToolDescriptor,
    ToolRiskLevel,
)


def test_builds_all_five_safe_tools() -> None:
    tools = build_safe_incident_tools()

    assert [tool.name for tool in tools] == [
        "get_service_dependencies",
        "get_service_metrics",
        "get_recent_traces",
        "search_logs",
        "get_recent_deployments",
    ]


def test_all_agent_tools_are_read_only() -> None:
    descriptors = {
        descriptor.name: descriptor for descriptor in incident_tools.list_incident_tools()
    }

    for tool in build_safe_incident_tools():
        descriptor = descriptors[tool.name]

        assert descriptor.risk_level == ToolRiskLevel.SAFE_READ_ONLY
        assert descriptor.requires_approval is False


def test_metric_adapter_returns_normalized_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_service_metrics(
        service_name: str,
        *,
        window: str,
    ) -> MetricSnapshot:
        return MetricSnapshot(
            service=service_name,
            observed_at=datetime.now(UTC),
            source=EvidenceSource.LIVE,
            window=window,
            request_rate_rps=2.5,
            error_rate_percent=4.0,
            p50_latency_ms=20.0,
            p95_latency_ms=80.0,
            p99_latency_ms=120.0,
            cpu_percent=25.0,
            memory_usage_bytes=104857600,
        )

    monkeypatch.setattr(
        incident_tools,
        "get_service_metrics",
        fake_get_service_metrics,
    )

    tool = get_safe_incident_tool(IncidentToolName.GET_SERVICE_METRICS)

    result = tool.invoke(
        {
            "service_name": "checkout",
            "window": "1h",
        }
    )

    assert result["tool_name"] == "get_service_metrics"
    assert result["service"] == "checkout"
    assert result["risk_level"] == "safe_read_only"
    assert result["requires_approval"] is False
    assert result["source"] == "live"
    assert result["result"]["window"] == "1h"
    assert result["result"]["request_rate_rps"] == 2.5


def test_rejects_approval_required_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = incident_tools.list_incident_tools()

    changed_descriptors = [
        descriptor.model_copy(
            update={"requires_approval": (descriptor.name == "get_service_metrics")}
        )
        for descriptor in descriptors
    ]

    monkeypatch.setattr(
        incident_tools,
        "list_incident_tools",
        lambda: changed_descriptors,
    )

    with pytest.raises(
        UnsafeToolRegistrationError,
        match="Approval-required tools",
    ):
        build_safe_incident_tools()


def test_rejects_non_read_only_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptors = incident_tools.list_incident_tools()

    changed_descriptors: list[ToolDescriptor] = [
        descriptor.model_copy(
            update={
                "risk_level": (
                    ToolRiskLevel.APPROVAL_REQUIRED
                    if descriptor.name == "get_recent_traces"
                    else descriptor.risk_level
                )
            }
        )
        for descriptor in descriptors
    ]

    monkeypatch.setattr(
        incident_tools,
        "list_incident_tools",
        lambda: changed_descriptors,
    )

    with pytest.raises(
        UnsafeToolRegistrationError,
        match="not read-only",
    ):
        build_safe_incident_tools()
