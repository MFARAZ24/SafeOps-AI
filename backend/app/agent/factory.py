from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from app.agent.investigation import (
    IncidentInvestigationAgent,
)
from app.llm.model import (
    get_chat_model,
    get_report_chat_model,
)
from app.rag.service import search_knowledge


def create_incident_agent(
    model: BaseChatModel | None = None,
) -> IncidentInvestigationAgent:
    """Create the production RAG-aware incident agent."""

    selected_model = model if model is not None else get_chat_model()

    report_model = model if model is not None else get_report_chat_model()

    return IncidentInvestigationAgent(
        chat_model=selected_model,
        knowledge_retriever=search_knowledge,
        report_model=report_model,
    )
