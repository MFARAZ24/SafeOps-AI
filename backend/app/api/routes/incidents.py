from fastapi import APIRouter, HTTPException, status

from app.agent.factory import create_incident_agent
from app.agent.investigation import (
    AgentToolCallLimitError,
    AgentToolExecutionError,
    IncidentAgentError,
    InvestigationOutputError,
    RepeatedAgentToolCallError,
    UnauthorizedAgentToolError,
)
from app.agent.investigation_schemas import (
    IncidentInvestigationRequest,
    IncidentInvestigationResult,
)
from app.llm.model import ModelConfigurationError
from app.rag.service import RAGServiceError
from app.rag.vector_store import VectorIndexError

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)


@router.post(
    "/investigate",
    response_model=IncidentInvestigationResult,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Investigate an operational incident",
    description=(
        "Combine SafeOps knowledge retrieval with controlled "
        "read-only metrics, traces, logs, dependencies, and "
        "deployment tools to produce a structured report."
    ),
)
def investigate_incident(
    request: IncidentInvestigationRequest,
) -> IncidentInvestigationResult:
    """Run a guarded read-only incident investigation."""

    try:
        agent = create_incident_agent()
        return agent.investigate(request)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except VectorIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The vector index is unavailable. "
                "Build or restore it before using vector "
                "or hybrid incident retrieval."
            ),
        ) from exc

    except ModelConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=("No usable language model is configured."),
        ) from exc

    except RAGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=("Knowledge retrieval failed during incident investigation."),
        ) from exc

    except (
        UnauthorizedAgentToolError,
        RepeatedAgentToolCallError,
        AgentToolCallLimitError,
        AgentToolExecutionError,
        InvestigationOutputError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=("The language-model investigation could not produce a valid guarded result."),
        ) from exc

    except IncidentAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Incident investigation failed.",
        ) from exc
