from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.agent.schemas import IncidentToolName
from app.observability.service_models import EvidenceSource
from app.rag.schemas import RetrieverType


class IncidentConfidence(StrEnum):
    """Confidence assigned to an investigation conclusion."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentSafetyStatus(StrEnum):
    """Safety boundary enforced during investigation."""

    READ_ONLY_ONLY = "read_only_only"


class IncidentInvestigationRequest(BaseModel):
    """User request for an incident investigation."""

    question: str = Field(
        min_length=3,
        max_length=2000,
        description="Incident question to investigate.",
    )
    service_name: str = Field(
        min_length=1,
        description="Primary service being investigated.",
    )
    metrics_window: str = Field(
        default="5m",
        pattern=r"^[1-9][0-9]*[smhdwy]$",
    )
    trace_lookback: str = Field(
        default="1h",
        pattern=r"^[1-9][0-9]*[smhdwy]$",
    )

    retriever: RetrieverType = RetrieverType.HYBRID
    rag_top_k: int = Field(
        default=3,
        ge=1,
        le=10,
    )
    include_rag_evidence: bool = True

    max_tool_calls: int = Field(
        default=6,
        ge=1,
        le=10,
    )
    max_planning_rounds: int = Field(
        default=4,
        ge=1,
        le=6,
    )


class AgentToolCallRecord(BaseModel):
    """One tool invocation performed by the agent."""

    tool_name: IncidentToolName
    arguments: dict[str, Any]

    source: EvidenceSource | None = None
    warning: str | None = None

    result: dict[str, Any]


class KnowledgeEvidence(BaseModel):
    """One bounded knowledge-base result supplied to the agent."""

    rank: int
    document_id: str
    chunk_id: str | None = None

    title: str
    document_type: str
    service: str
    source: str
    section: str | None = None

    score: float
    content: str


class IncidentInvestigationReport(BaseModel):
    """Structured conclusion produced after evidence collection."""

    service: str
    question: str

    incident_summary: str
    likely_root_cause: str
    confidence: IncidentConfidence

    evidence: list[str] = Field(default_factory=list)
    recommended_next_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    tools_used: list[IncidentToolName] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    knowledge_documents: list[str] = Field(default_factory=list)

    safety_status: AgentSafetyStatus = AgentSafetyStatus.READ_ONLY_ONLY


class IncidentInvestigationResult(BaseModel):
    """Complete investigation output and execution record."""

    report: IncidentInvestigationReport
    tool_calls: list[AgentToolCallRecord]
    planning_notes: list[str] = Field(default_factory=list)

    rag_retriever: RetrieverType | None = None
    rag_retrieval_elapsed_ms: float | None = None
    rag_evidence: list[KnowledgeEvidence] | None = None
