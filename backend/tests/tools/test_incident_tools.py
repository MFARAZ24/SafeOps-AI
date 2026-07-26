import pytest

from app.tools.incident_tools import (
    get_recent_deployments,
    get_service_dependencies,
    get_service_metrics,
    list_incident_tools,
    search_logs,
)
from app.tools.schemas import (
    LogSeverity,
    ToolRiskLevel,
)


def test_all_initial_tools_are_safe_read_only() -> None:
    """The first incident tools must not modify infrastructure."""

    tools = list_incident_tools()

    assert len(tools) == 5

    assert all(tool.risk_level == ToolRiskLevel.SAFE_READ_ONLY for tool in tools)

    assert all(tool.requires_approval is False for tool in tools)


def test_checkout_dependencies_include_payment() -> None:
    """Checkout should expose its important downstream services."""

    dependencies = get_service_dependencies("checkout")

    assert "payment" in (dependencies.downstream_services)

    assert "shipping" in (dependencies.downstream_services)


def test_service_alias_is_normalized() -> None:
    """Common service aliases should resolve correctly."""

    dependencies = get_service_dependencies("recommendation-service")

    assert dependencies.service == "recommendation"

    assert dependencies.downstream_services == ["product-catalog"]


def test_recommendation_metrics_show_high_memory(
    monkeypatch,
) -> None:
    """The fallback fixture should represent a memory incident."""

    monkeypatch.setenv(
        "PROMETHEUS_BASE_URL",
        "http://127.0.0.1:1",
    )
    monkeypatch.setenv(
        "OBSERVABILITY_TIMEOUT_SECONDS",
        "0.2",
    )

    metrics = get_service_metrics("recommendation")

    assert metrics.source == "fixture"
    assert metrics.warning is not None
    assert metrics.memory_percent is not None
    assert metrics.memory_percent > 90


def test_log_search_filters_keywords_and_service() -> None:
    """Log search should return relevant service records."""

    results = search_logs(
        "recommendation",
        keywords=[
            "memory",
            "cache",
        ],
    )

    assert results.result_count == 2

    assert all(record.service == "recommendation" for record in results.records)


def test_log_search_filters_severity() -> None:
    """Severity filtering should return only matching records."""

    results = search_logs(
        "payment",
        severity=LogSeverity.ERROR,
    )

    assert results.result_count == 1

    assert results.records[0].severity == LogSeverity.ERROR


def test_recent_deployments_are_newest_first() -> None:
    """Deployment results should be ordered by recency."""

    results = get_recent_deployments(
        "checkout",
        limit=2,
    )

    assert results.result_count == 2

    assert results.deployments[0].deployed_at >= results.deployments[1].deployed_at


def test_unknown_service_is_rejected() -> None:
    """Unknown services should not silently return empty data."""

    with pytest.raises(
        ValueError,
        match="Unknown service",
    ):
        get_service_dependencies("nonexistent-service")
