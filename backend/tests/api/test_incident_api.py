from fastapi.testclient import TestClient

from app.agent.investigation import (
    InvestigationOutputError,
)
from app.agent.investigation_schemas import (
    IncidentInvestigationReport,
    IncidentInvestigationResult,
    KnowledgeEvidence,
)
from app.api.routes import incidents
from app.main import create_app
from app.rag.schemas import RetrieverType


class FakeSuccessfulAgent:
    def investigate(
        self,
        request,
    ) -> IncidentInvestigationResult:
        return IncidentInvestigationResult(
            report=IncidentInvestigationReport(
                service=request.service_name,
                question=request.question,
                incident_summary=("Checkout evidence was reviewed."),
                likely_root_cause=("No root cause is confirmed."),
                confidence="low",
                evidence=["Runbook evidence was retrieved [RB-001]."],
                recommended_next_checks=["Inspect recent checkout traces."],
                limitations=["This test uses synthetic evidence."],
                tools_used=[],
                evidence_sources=[],
                knowledge_documents=["RB-001"],
            ),
            tool_calls=[],
            planning_notes=["Evidence collection complete."],
            rag_retriever=RetrieverType.HYBRID,
            rag_retrieval_elapsed_ms=4.2,
            rag_evidence=[
                KnowledgeEvidence(
                    rank=1,
                    document_id="RB-001",
                    chunk_id="RB-001-001",
                    title="Checkout Runbook",
                    document_type="runbook",
                    service="checkout",
                    source="knowledge/RB-001.md",
                    section="Investigation",
                    score=0.9,
                    content="Inspect downstream latency.",
                )
            ],
        )


class FakeFailingAgent:
    def investigate(self, request):
        raise InvestigationOutputError("Invalid model output.")


def test_incident_api_returns_structured_report(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        incidents,
        "create_incident_agent",
        lambda: FakeSuccessfulAgent(),
    )

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/incidents/investigate",
        json={
            "question": "Why is checkout failing?",
            "service_name": "checkout",
            "metrics_window": "1h",
            "trace_lookback": "1h",
            "retriever": "hybrid",
            "rag_top_k": 3,
            "include_rag_evidence": True,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["report"]["service"] == "checkout"
    assert payload["report"]["safety_status"] == "read_only_only"
    assert payload["rag_retriever"] == "hybrid"
    assert payload["rag_evidence"][0]["document_id"] == "RB-001"


def test_incident_api_maps_invalid_model_output(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        incidents,
        "create_incident_agent",
        lambda: FakeFailingAgent(),
    )

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/incidents/investigate",
        json={
            "question": "Why is checkout failing?",
            "service_name": "checkout",
        },
    )

    assert response.status_code == 502
