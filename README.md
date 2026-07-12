# SafeOps AI

SafeOps AI is a production-oriented, guardrailed platform for AI-assisted incident investigation and response.

The project will combine stateful AI workflows, retrieval-augmented generation, operational tools, human approval, safety guardrails, observability, and systematic evaluation.

## Project Goals

SafeOps AI will:

- Accept technical incident reports.
- Retrieve relevant architecture documents and operational runbooks.
- Investigate logs, metrics, traces, deployments, and service dependencies.
- Generate evidence-grounded root-cause hypotheses.
- Recommend remediation actions.
- Require human approval before risky operations.
- Evaluate retrieval quality, tool use, incident diagnosis, safety, latency, and cost.
- Use NetInjectBench as an external adversarial safety evaluation framework.

## Current Status

- [x] Repository structure created
- [x] FastAPI backend foundation created
- [x] Health endpoint created
- [x] Initial automated tests created
- [ ] OpenTelemetry demo environment
- [ ] RAG knowledge base
- [ ] LangGraph investigation workflow
- [ ] MCP operational tools
- [ ] Guardrails and human approval
- [ ] Evaluation framework
- [ ] Next.js frontend
- [ ] Deployment and CI/CD

## Repository Structure

SafeOps-AI/

- backend/
  - app/
  - tests/
  - pyproject.toml
- data/
  - knowledge_base/
  - incidents/
  - telemetry/
- docs/
- evaluation/
- scripts/
- README.md

## Run the Backend Locally

From the backend directory:

1. Install or verify uv.
2. Install Python 3.12 through uv.
3. Pin Python 3.12 for the backend.
4. Synchronize the project dependencies.
5. Run the tests.
6. Start the API.

Commands:

    uv python install 3.12
    uv python pin 3.12
    uv sync --extra dev
    uv run pytest
    uv run uvicorn app.main:app --reload

Local URLs:

- API: http://127.0.0.1:8000
- Health endpoint: http://127.0.0.1:8000/api/v1/health
- Interactive API documentation: http://127.0.0.1:8000/docs

## Relationship to NetInjectBench

NetInjectBench remains a separate research benchmark for evaluating prompt-injection attacks and guardrail effectiveness in LLM-based network agents.

SafeOps AI is a separate production-oriented application. NetInjectBench will later be integrated as an external adversarial safety evaluation suite without changing the submitted research version.
