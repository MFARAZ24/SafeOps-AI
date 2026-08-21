import json
from collections.abc import Sequence

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
)
from langchain_core.tools import BaseTool

from app.agent.investigation import (
    AgentToolCallLimitError,
    IncidentInvestigationAgent,
    UnauthorizedAgentToolError,
)
from app.agent.investigation_schemas import (
    IncidentInvestigationRequest,
)
from app.observability.service_models import EvidenceSource
from app.tools import incident_tools
from app.tools.schemas import MetricSnapshot


class FakeBoundModel:
    def __init__(
        self,
        responses: list[AIMessage],
    ) -> None:
        self._responses = list(responses)

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        if not self._responses:
            return AIMessage(content="Evidence collection complete.")

        return self._responses.pop(0)


class FakeChatModel:
    def __init__(
        self,
        *,
        planner_responses: list[AIMessage],
        synthesis_contents: list[str],
    ) -> None:
        self._bound_model = FakeBoundModel(planner_responses)
        self._synthesis_contents = list(synthesis_contents)
        self.bound_tool_names: list[str] = []

    def bind_tools(
        self,
        tools: Sequence[BaseTool],
    ) -> FakeBoundModel:
        self.bound_tool_names = [tool.name for tool in tools]

        return self._bound_model

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        if not self._synthesis_contents:
            return AIMessage(content="Invalid response.")

        return AIMessage(content=self._synthesis_contents.pop(0))


def report_json() -> str:
    return json.dumps(
        {
            "service": "incorrect-service",
            "question": "incorrect-question",
            "incident_summary": ("Checkout has an elevated error rate."),
            "likely_root_cause": ("Payment latency is the likely cause."),
            "confidence": "medium",
            "evidence": ["Checkout error rate is 4 percent."],
            "recommended_next_checks": ["Inspect recent payment traces."],
            "limitations": [],
            "tools_used": [],
            "evidence_sources": [],
            "knowledge_documents": [],
            "safety_status": "read_only_only",
        }
    )


def metric_tool_call(
    *,
    call_id: str = "call-1",
) -> dict[str, object]:
    return {
        "name": "get_service_metrics",
        "args": {
            "service_name": "checkout",
            "window": "1h",
        },
        "id": call_id,
        "type": "tool_call",
    }


def fake_live_metrics(
    service_name: str,
    *,
    window: str,
) -> MetricSnapshot:
    return MetricSnapshot(
        service=service_name,
        observed_at="2026-07-25T20:00:00Z",
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


def test_collects_tool_evidence_and_returns_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        incident_tools,
        "get_service_metrics",
        fake_live_metrics,
    )

    model = FakeChatModel(
        planner_responses=[
            AIMessage(
                content="",
                tool_calls=[metric_tool_call()],
            ),
            AIMessage(content="Evidence collection complete."),
        ],
        synthesis_contents=[report_json()],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question="Why is checkout failing?",
            service_name="checkout-service",
            metrics_window="1h",
        )
    )

    assert len(model.bound_tool_names) == 5
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].source == EvidenceSource.LIVE
    assert result.report.service == "checkout"
    assert result.report.tools_used == ["get_service_metrics"]
    assert result.report.evidence_sources == [EvidenceSource.LIVE]
    assert result.report.safety_status == "read_only_only"


def test_rejects_unknown_tool() -> None:
    model = FakeChatModel(
        planner_responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "restart_service",
                        "args": {"service_name": "checkout"},
                        "id": "call-unsafe",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        synthesis_contents=[report_json()],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    with pytest.raises(
        UnauthorizedAgentToolError,
        match="unauthorized tool",
    ):
        agent.investigate(
            IncidentInvestigationRequest(
                question="Restart checkout.",
                service_name="checkout",
            )
        )


def test_skips_repeated_identical_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        incident_tools,
        "get_service_metrics",
        fake_live_metrics,
    )

    model = FakeChatModel(
        planner_responses=[
            AIMessage(
                content="",
                tool_calls=[metric_tool_call(call_id="call-1")],
            ),
            AIMessage(
                content="",
                tool_calls=[metric_tool_call(call_id="call-2")],
            ),
            AIMessage(content="Evidence collection complete."),
        ],
        synthesis_contents=[report_json()],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question="Investigate checkout errors.",
            service_name="checkout",
        )
    )

    assert len(result.tool_calls) == 1
    assert any("Skipped repeated identical tool call" in note for note in result.planning_notes)


def test_enforces_unique_tool_call_limit() -> None:
    model = FakeChatModel(
        planner_responses=[
            AIMessage(
                content="",
                tool_calls=[
                    metric_tool_call(call_id="call-1"),
                    {
                        "name": ("get_service_dependencies"),
                        "args": {"service_name": "checkout"},
                        "id": "call-2",
                        "type": "tool_call",
                    },
                ],
            )
        ],
        synthesis_contents=[report_json()],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    with pytest.raises(
        AgentToolCallLimitError,
        match="unique tool-call limit",
    ):
        agent.investigate(
            IncidentInvestigationRequest(
                question="Investigate checkout errors.",
                service_name="checkout",
                max_tool_calls=1,
            )
        )


def test_parses_valid_report_embedded_in_reasoning() -> None:
    model = FakeChatModel(
        planner_responses=[AIMessage(content="Evidence collection complete.")],
        synthesis_contents=[],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    response = AIMessage(
        content=(
            "<think>\n"
            "I need to produce the required schema.\n"
            'Example shape: {"service": "string", '
            '"confidence": "low"}\n'
            "</think>\n\n"
            "{"
            '"service":"checkout",'
            '"question":"Investigate checkout.",'
            '"incident_summary":"Checkout latency is elevated.",'
            '"likely_root_cause":"The available evidence does not '
            'confirm one root cause.",'
            '"confidence":"low",'
            '"evidence":["p95 latency is elevated."],'
            '"recommended_next_checks":['
            '"Inspect downstream dependency metrics."],'
            '"limitations":["Live trace evidence is unavailable."],'
            '"tools_used":["get_service_metrics"],'
            '"evidence_sources":["fixture"],'
            '"knowledge_documents":["RB-001"],'
            '"safety_status":"read_only_only"'
            "}\n\n"
            "Additional trailing model text that must be ignored."
        )
    )

    report = agent._parse_report_message(response)

    assert report.service == "checkout"
    assert report.confidence == "low"
    assert report.tools_used == ["get_service_metrics"]
    assert report.evidence_sources == ["fixture"]
    assert report.safety_status == ("read_only_only")


def test_repairs_non_json_report() -> None:
    model = FakeChatModel(
        planner_responses=[AIMessage(content="Evidence collection complete.")],
        synthesis_contents=[
            "Here is my analysis without JSON.",
            report_json(),
        ],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question="Investigate checkout errors.",
            service_name="checkout",
        )
    )

    assert result.report.service == "checkout"
    assert result.report.confidence == "medium"


def test_accepts_escaped_json_report() -> None:
    formatted_report = json.dumps(
        json.loads(report_json()),
        indent=2,
    )

    escaped_report = formatted_report.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    model = FakeChatModel(
        planner_responses=[AIMessage(content=("Evidence collection complete."))],
        synthesis_contents=[
            escaped_report,
        ],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question=("Investigate checkout errors."),
            service_name="checkout",
        )
    )

    assert result.report.service == "checkout"
    assert result.report.confidence == "medium"
    assert result.report.safety_status == "read_only_only"


def test_read_only_tool_failure_does_not_abort_investigation() -> None:
    model = FakeChatModel(
        planner_responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_service_metrics",
                        "args": {
                            "service_name": "cart",
                            "window": "1h",
                        },
                        "id": "call-cart-metrics",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Evidence collection complete."),
        ],
        synthesis_contents=[
            (
                '{"service":"checkout",'
                '"question":"Investigate checkout.",'
                '"incident_summary":"Some evidence was unavailable.",'
                '"likely_root_cause":"No root cause was confirmed.",'
                '"confidence":"low",'
                '"evidence":["Cart metrics were unavailable."],'
                '"recommended_next_checks":["Inspect other read-only evidence."],'
                '"limitations":["Cart metrics were unavailable."],'
                '"tools_used":["get_service_metrics"],'
                '"evidence_sources":[],'
                '"knowledge_documents":[],'
                '"safety_status":"read_only_only"}'
            )
        ],
    )

    def failing_metrics_tool(
        service_name: str,
        *,
        window: str = "5m",
    ) -> dict:
        del service_name, window

        raise ValueError("No metric fixture is available for service: cart")

    agent = IncidentInvestigationAgent(
        chat_model=model,
    )

    metric_tool = agent._tool_map["get_service_metrics"]

    metric_tool.func = failing_metrics_tool

    result = agent.investigate(
        IncidentInvestigationRequest(
            question="Investigate checkout.",
            service_name="checkout",
        )
    )

    assert result.report.safety_status == "read_only_only"
    assert len(result.tool_calls) == 1

    failed_call = result.tool_calls[0]

    assert failed_call.tool_name == "get_service_metrics"
    assert failed_call.warning is not None
    assert "No metric fixture" in failed_call.warning
    assert failed_call.result["result"]["status"] == "unavailable"


def test_returns_safe_fallback_after_invalid_report() -> None:
    model = FakeChatModel(
        planner_responses=[AIMessage(content=("Evidence collection complete."))],
        synthesis_contents=[
            "This is not JSON.",
            "This is still not JSON.",
        ],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question=("Investigate checkout errors."),
            service_name="checkout",
        )
    )

    assert result.report.service == "checkout"
    assert result.report.confidence == "low"
    assert result.report.likely_root_cause == (
        "No root cause could be confirmed from the collected evidence."
    )
    assert result.report.safety_status == "read_only_only"
    assert any("valid structured report" in limitation for limitation in result.report.limitations)


def test_accepts_python_style_report_dictionary() -> None:
    python_style_report = str(json.loads(report_json()))

    model = FakeChatModel(
        planner_responses=[AIMessage(content=("Evidence collection complete."))],
        synthesis_contents=[
            python_style_report,
        ],
    )

    agent = IncidentInvestigationAgent(chat_model=model)

    result = agent.investigate(
        IncidentInvestigationRequest(
            question=("Investigate checkout errors."),
            service_name="checkout",
        )
    )

    assert result.report.service == "checkout"
    assert result.report.confidence == "medium"
