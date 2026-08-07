from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from app.agent.investigation import (
    IncidentInvestigationAgent,
)
from app.agent.investigation_schemas import (
    IncidentInvestigationReport,
)
from app.llm.model import get_chat_model
from app.rag.service import search_knowledge


def create_incident_agent(
    model: BaseChatModel | None = None,
) -> IncidentInvestigationAgent:
    """Create the production RAG-aware incident agent."""

    selected_model = model if model is not None else get_chat_model()

    report_model = None

    try:
        report_model = selected_model.with_structured_output(
            IncidentInvestigationReport,
            method="function_calling",
        )
    except (NotImplementedError, ValueError):
        report_model = None

    return IncidentInvestigationAgent(
        chat_model=selected_model,
        knowledge_retriever=search_knowledge,
        report_model=report_model,
    )
