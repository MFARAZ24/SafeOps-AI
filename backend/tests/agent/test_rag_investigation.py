import json
from collections.abc import Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
)
from langchain_core.tools import BaseTool

from app.agent.investigation import (
    IncidentInvestigationAgent,
)
from app.agent.investigation_schemas import (
    IncidentInvestigationRequest,
)
from app.rag.schemas import (
    RAGSearchResponse,
    RAGSearchResult,
    RetrievalDetails,
    RetrieverType,
)


class RecordingBoundModel:
    def __init__(self) -> None:
        self.inputs: list[list[BaseMessage]] = []

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        self.inputs.append(input)

        return AIMessage(content="Evidence collection complete.")


class RecordingChatModel:
    def __init__(self) -> None:
        self.bound_model = RecordingBoundModel()
        self.synthesis_inputs: list[list[BaseMessage]] = []

    def bind_tools(
        self,
        tools: Sequence[BaseTool],
    ) -> RecordingBoundModel:
        return self.bound_model

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        self.synthesis_inputs.append(input)

        return AIMessage(
            content=json.dumps(
                {
                    "service": "checkout",
                    "question": ("Why is checkout failing?"),
                    "incident_summary": ("Evidence is insufficient."),
                    "likely_root_cause": ("No operational cause is confirmed."),
                    "confidence": "low",
                    "evidence": ["Approval policy was retrieved [POL-001]."],
                    "recommended_next_checks": ["Inspect live checkout traces."],
                    "limitations": ["No operational tool was used."],
                    "tools_used": [],
                    "evidence_sources": [],
                    "knowledge_documents": [],
                    "safety_status": ("read_only_only"),
                }
            )
        )


def fake_retriever(
    query: str,
    *,
    retriever: RetrieverType | str,
    top_k: int,
    include_content: bool,
) -> RAGSearchResponse:
    return RAGSearchResponse(
        query=query,
        retriever=RetrieverType(retriever),
        top_k=top_k,
        result_count=1,
        elapsed_ms=12.5,
        results=[
            RAGSearchResult(
                rank=1,
                document_id="POL-001",
                chunk_id="POL-001-001",
                title="Tool Safety Policy",
                document_type="policy",
                service="all",
                source="data/knowledge_base/POL-001.md",
                section="Approval Requirements",
                score=0.95,
                score_type="reciprocal_rank_fusion",
                content=("Infrastructure-changing actions require human approval."),
                details=RetrievalDetails(),
            )
        ],
    )


def test_investigation_includes_rag_evidence() -> None:
    model = RecordingChatModel()

    agent = IncidentInvestigationAgent(
        chat_model=model,
        knowledge_retriever=fake_retriever,
    )

    result = agent.investigate(
        IncidentInvestigationRequest(
            question="Why is checkout failing?",
            service_name="checkout",
            retriever=RetrieverType.HYBRID,
            rag_top_k=3,
            include_rag_evidence=True,
        )
    )

    assert result.rag_retriever == RetrieverType.HYBRID
    assert result.rag_retrieval_elapsed_ms == 12.5
    assert result.rag_evidence is not None
    assert result.rag_evidence[0].document_id == "POL-001"

    assert result.report.knowledge_documents == ["POL-001"]

    planner_messages = model.bound_model.inputs[0]
    assert "POL-001" in str(planner_messages[1].content)

    synthesis_messages = model.synthesis_inputs[0]
    assert "POL-001" in str(synthesis_messages[1].content)
