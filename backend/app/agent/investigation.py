import ast
import json
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from app.agent.investigation_schemas import (
    AgentSafetyStatus,
    AgentToolCallRecord,
    IncidentInvestigationReport,
    IncidentInvestigationRequest,
    IncidentInvestigationResult,
    KnowledgeEvidence,
)
from app.agent.prompts import (
    PLANNER_SYSTEM_PROMPT,
    REPORT_REPAIR_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    build_planner_request,
)
from app.agent.rag_evidence import (
    build_knowledge_context,
    to_knowledge_evidence,
)
from app.agent.schemas import IncidentToolName
from app.agent.tool_adapters import (
    build_safe_incident_tools,
)
from app.observability.service_models import EvidenceSource
from app.rag.schemas import (
    RAGSearchResponse,
    RetrieverType,
)
from app.tools.incident_tools import normalize_service_name


class BoundInvestigationModel(Protocol):
    """Tool-bound model interface required by the agent."""

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        """Invoke the model."""


class InvestigationChatModel(Protocol):
    """Chat model interface required by the agent."""

    def bind_tools(
        self,
        tools: Sequence[BaseTool],
    ) -> BoundInvestigationModel:
        """Return a tool-bound model."""

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> BaseMessage:
        """Invoke the unbound model."""


class StructuredReportModel(Protocol):
    """Optional model that directly returns a structured report."""

    def invoke(
        self,
        input: list[BaseMessage],
    ) -> object:
        """Invoke the structured-output model."""


class KnowledgeRetriever(Protocol):
    """Knowledge-search function required by production agents."""

    def __call__(
        self,
        query: str,
        *,
        retriever: RetrieverType | str,
        top_k: int,
        include_content: bool,
    ) -> RAGSearchResponse:
        """Retrieve knowledge-base evidence."""


class IncidentAgentError(RuntimeError):
    """Base error for incident-agent failures."""


class UnauthorizedAgentToolError(IncidentAgentError):
    """Raised when the model requests an unavailable tool."""


class AgentToolCallLimitError(IncidentAgentError):
    """Raised when the model exceeds the tool-call limit."""


class RepeatedAgentToolCallError(IncidentAgentError):
    """Retained for compatibility with earlier API handling."""


class AgentToolExecutionError(IncidentAgentError):
    """Raised when an approved tool fails during execution."""


class InvestigationOutputError(IncidentAgentError):
    """Raised when the final report cannot be validated."""


class IncidentInvestigationAgent:
    """Controlled read-only tool-calling incident agent."""

    def __init__(
        self,
        chat_model: InvestigationChatModel,
        *,
        knowledge_retriever: KnowledgeRetriever | None = None,
        report_model: StructuredReportModel | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._knowledge_retriever = knowledge_retriever
        self._report_model = report_model

        self._tools = build_safe_incident_tools()
        self._tool_map = {tool.name: tool for tool in self._tools}
        self._bound_model = chat_model.bind_tools(self._tools)

    def investigate(
        self,
        request: IncidentInvestigationRequest,
    ) -> IncidentInvestigationResult:
        """Collect RAG and operational evidence."""

        service_name = normalize_service_name(request.service_name)

        (
            knowledge_evidence,
            rag_retriever,
            rag_elapsed_ms,
        ) = self._retrieve_knowledge(request)

        knowledge_context = build_knowledge_context(knowledge_evidence)

        messages: list[BaseMessage] = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=build_planner_request(
                    question=request.question,
                    service_name=service_name,
                    metrics_window=request.metrics_window,
                    trace_lookback=request.trace_lookback,
                    knowledge_context=knowledge_context,
                )
            ),
        ]

        tool_records: list[AgentToolCallRecord] = []
        planning_notes: list[str] = []

        executed_calls: dict[
            str,
            AgentToolCallRecord,
        ] = {}

        for _ in range(request.max_planning_rounds):
            response = self._bound_model.invoke(messages)

            if not isinstance(response, AIMessage):
                raise IncidentAgentError("Planner must return an AIMessage.")

            messages.append(response)

            if not response.tool_calls:
                note = self._message_text(response)

                if note:
                    planning_notes.append(note)

                break

            for raw_call in response.tool_calls:
                (
                    record,
                    tool_message,
                    reused,
                ) = self._execute_tool_call(
                    raw_call=raw_call,
                    executed_calls=executed_calls,
                    max_tool_calls=request.max_tool_calls,
                )

                messages.append(tool_message)

                if reused:
                    planning_notes.append(
                        f"Skipped repeated identical tool call: {record.tool_name.value}."
                    )
                    continue

                tool_records.append(record)

        else:
            planning_notes.append(
                "Planning-round limit reached; the report uses the evidence collected so far."
            )

        report = self._synthesize_report(
            request=request,
            service_name=service_name,
            tool_records=tool_records,
            planning_notes=planning_notes,
            knowledge_evidence=knowledge_evidence,
        )

        return IncidentInvestigationResult(
            report=report,
            tool_calls=tool_records,
            planning_notes=planning_notes,
            rag_retriever=rag_retriever,
            rag_retrieval_elapsed_ms=rag_elapsed_ms,
            rag_evidence=(knowledge_evidence if request.include_rag_evidence else None),
        )

    def _retrieve_knowledge(
        self,
        request: IncidentInvestigationRequest,
    ) -> tuple[
        list[KnowledgeEvidence],
        RetrieverType | None,
        float | None,
    ]:
        if self._knowledge_retriever is None:
            return [], None, None

        retrieval = self._knowledge_retriever(
            request.question,
            retriever=request.retriever,
            top_k=request.rag_top_k,
            include_content=True,
        )

        return (
            to_knowledge_evidence(retrieval),
            retrieval.retriever,
            retrieval.elapsed_ms,
        )

    def _execute_tool_call(
        self,
        *,
        raw_call: dict[str, Any],
        executed_calls: dict[
            str,
            AgentToolCallRecord,
        ],
        max_tool_calls: int,
    ) -> tuple[
        AgentToolCallRecord,
        ToolMessage,
        bool,
    ]:
        raw_name = raw_call.get("name")

        try:
            tool_name = IncidentToolName(str(raw_name))
        except ValueError as exc:
            raise UnauthorizedAgentToolError(
                f"The model requested an unauthorized tool: {raw_name}"
            ) from exc

        tool = self._tool_map.get(tool_name.value)

        if tool is None:
            raise UnauthorizedAgentToolError(
                f"The requested tool was not registered: {tool_name.value}"
            )

        arguments = self._normalize_arguments(raw_call.get("args", {}))

        call_signature = self._tool_call_signature(
            tool_name=tool_name,
            arguments=arguments,
        )

        tool_call_id = self._tool_call_id(
            raw_call=raw_call,
            tool_name=tool_name,
            call_number=len(executed_calls) + 1,
        )

        existing_record = executed_calls.get(call_signature)

        if existing_record is not None:
            duplicate_payload = {
                "status": "duplicate_skipped",
                "message": (
                    "This identical read-only tool call was "
                    "already executed. Reuse the prior evidence."
                ),
                "prior_evidence": existing_record.model_dump(mode="json"),
            }

            return (
                existing_record,
                ToolMessage(
                    content=json.dumps(
                        duplicate_payload,
                        ensure_ascii=False,
                        default=str,
                    ),
                    tool_call_id=tool_call_id,
                    name=tool_name.value,
                ),
                True,
            )

        if len(executed_calls) >= max_tool_calls:
            raise AgentToolCallLimitError(
                "The agent exceeded the configured unique tool-call limit."
            )

        try:
            raw_result = tool.invoke(arguments)
        except Exception as exc:
            raise AgentToolExecutionError(f"Tool execution failed: {tool_name.value}") from exc

        if not isinstance(raw_result, dict):
            raise AgentToolExecutionError("Agent tools must return dictionary evidence.")

        source = self._parse_source(raw_result.get("source"))

        warning_value = raw_result.get("warning")
        warning = str(warning_value) if warning_value is not None else None

        record = AgentToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            source=source,
            warning=warning,
            result=raw_result,
        )

        executed_calls[call_signature] = record

        tool_message = ToolMessage(
            content=json.dumps(
                raw_result,
                ensure_ascii=False,
                default=str,
            ),
            tool_call_id=tool_call_id,
            name=tool_name.value,
        )

        return record, tool_message, False

    def _synthesize_report(
        self,
        *,
        request: IncidentInvestigationRequest,
        service_name: str,
        tool_records: list[AgentToolCallRecord],
        planning_notes: list[str],
        knowledge_evidence: list[KnowledgeEvidence],
    ) -> IncidentInvestigationReport:
        schema = IncidentInvestigationReport.model_json_schema()

        synthesis_request = {
            "service": service_name,
            "question": request.question,
            "tool_evidence": [record.model_dump(mode="json") for record in tool_records],
            "knowledge_evidence": [item.model_dump(mode="json") for item in knowledge_evidence],
            "allowed_knowledge_document_ids": [item.document_id for item in knowledge_evidence],
            "planning_notes": planning_notes,
            "required_json_schema": schema,
        }

        messages: list[BaseMessage] = [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    synthesis_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]

        report = self._structured_report(messages)

        if report is None:
            report = self._text_report_with_repair(
                messages=messages,
                synthesis_request=synthesis_request,
            )

        actual_tools = self._unique_tools(tool_records)
        actual_sources = self._unique_sources(tool_records)
        actual_documents = list(dict.fromkeys(item.document_id for item in knowledge_evidence))

        return report.model_copy(
            update={
                "service": service_name,
                "question": request.question,
                "tools_used": actual_tools,
                "evidence_sources": actual_sources,
                "knowledge_documents": actual_documents,
                "safety_status": (AgentSafetyStatus.READ_ONLY_ONLY),
            }
        )

    def _structured_report(
        self,
        messages: list[BaseMessage],
    ) -> IncidentInvestigationReport | None:
        if self._report_model is None:
            return None

        try:
            raw_report = self._report_model.invoke(messages)
        except Exception:
            return None

        if isinstance(
            raw_report,
            IncidentInvestigationReport,
        ):
            return raw_report

        if isinstance(raw_report, dict):
            try:
                return IncidentInvestigationReport.model_validate(raw_report)
            except ValueError:
                return None

        return None

    def _text_report_with_repair(
        self,
        *,
        messages: list[BaseMessage],
        synthesis_request: dict[str, Any],
    ) -> IncidentInvestigationReport:
        """Generate, compactly repair, or safely fall back."""

        try:
            response = self._chat_model.invoke(messages)
        except Exception as exc:
            return self._build_fallback_report(
                synthesis_request=synthesis_request,
                failure_reason=(
                    f"Initial report synthesis request failed: {type(exc).__name__}: {exc}"
                ),
            )

        try:
            return self._parse_report_message(response)
        except InvestigationOutputError:
            raw_output = self._base_message_text(response)

        # The repair call should fix formatting only. Do not resend
        # the complete RAG and operational evidence payload because
        # that can exceed the hosted model's token limits.
        compact_schema = {
            "service": "string",
            "question": "string",
            "incident_summary": "string",
            "likely_root_cause": "string",
            "confidence": "low | medium | high",
            "evidence": ["string"],
            "recommended_next_checks": ["string"],
            "limitations": ["string"],
            "tools_used": ["approved tool name"],
            "evidence_sources": ["live | fixture"],
            "knowledge_documents": ["document ID"],
            "safety_status": "read_only_only",
        }

        repair_payload = {
            "service": synthesis_request.get("service"),
            "question": synthesis_request.get("question"),
            "invalid_model_output": raw_output[:6000],
            "required_object_shape": compact_schema,
            "instructions": (
                "Repair only the formatting of the supplied "
                "model output. Preserve its supported claims. "
                "Do not add facts. Return one JSON object."
            ),
        }

        try:
            repair_response = self._chat_model.invoke(
                [
                    SystemMessage(content=(REPORT_REPAIR_SYSTEM_PROMPT)),
                    HumanMessage(
                        content=json.dumps(
                            repair_payload,
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
        except Exception as exc:
            return self._build_fallback_report(
                synthesis_request=synthesis_request,
                failure_reason=(f"Report repair request failed: {type(exc).__name__}: {exc}"),
            )

        try:
            return self._parse_report_message(repair_response)
        except InvestigationOutputError as exc:
            return self._build_fallback_report(
                synthesis_request=synthesis_request,
                failure_reason=str(exc),
            )

    @staticmethod
    def _build_fallback_report(
        *,
        synthesis_request: dict[str, Any],
        failure_reason: str,
    ) -> IncidentInvestigationReport:
        """Build a conservative evidence-aware report."""

        service = str(
            synthesis_request.get(
                "service",
                "unknown",
            )
        )

        question = str(
            synthesis_request.get(
                "question",
                "Incident investigation",
            )
        )

        raw_tool_evidence = synthesis_request.get(
            "tool_evidence",
            [],
        )

        raw_knowledge_evidence = synthesis_request.get(
            "knowledge_evidence",
            [],
        )

        metrics: dict[str, Any] | None = None
        traces: list[dict[str, Any]] = []
        dependencies: dict[str, Any] | None = None

        tools_seen: set[str] = set()

        if isinstance(raw_tool_evidence, list):
            for item in raw_tool_evidence:
                if not isinstance(item, dict):
                    continue

                tool_name = str(
                    item.get(
                        "tool_name",
                        "",
                    )
                )

                if tool_name:
                    tools_seen.add(tool_name)

                wrapper = item.get("result")

                if not isinstance(wrapper, dict):
                    continue

                payload = wrapper.get("result")

                if not isinstance(payload, dict):
                    continue

                if tool_name == "get_service_metrics":
                    metrics = payload

                elif tool_name == "get_recent_traces":
                    raw_traces = payload.get(
                        "traces",
                        [],
                    )

                    if isinstance(raw_traces, list):
                        traces = [
                            trace
                            for trace in raw_traces
                            if isinstance(
                                trace,
                                dict,
                            )
                        ]

                elif tool_name == "get_service_dependencies":
                    dependencies = payload

        evidence: list[str] = []
        limitations: list[str] = []
        recommended_checks: list[str] = []

        metric_error_rate: float | None = None
        metric_p95: float | None = None
        metric_p99: float | None = None
        metric_request_rate: float | None = None

        if metrics is not None:
            metric_request_rate = metrics.get("request_rate_rps")
            metric_error_rate = metrics.get("error_rate_percent")
            metric_p95 = metrics.get("p95_latency_ms")
            metric_p99 = metrics.get("p99_latency_ms")

            metric_parts: list[str] = []

            if metric_request_rate is not None:
                metric_parts.append(f"request rate {float(metric_request_rate):.4f} rps")

            if metric_error_rate is not None:
                metric_parts.append(f"error rate {float(metric_error_rate):.2f}%")

            if metric_p95 is not None:
                metric_parts.append(f"p95 latency {float(metric_p95):.0f} ms")

            if metric_p99 is not None:
                metric_parts.append(f"p99 latency {float(metric_p99):.0f} ms")

            if metric_parts:
                evidence.append("Live checkout metrics reported " + ", ".join(metric_parts) + ".")

            cpu = metrics.get("cpu_percent")
            memory = metrics.get("memory_percent")

            if cpu is None and memory is None:
                limitations.append("CPU and memory telemetry were not available for the service.")

        error_traces = [trace for trace in traces if bool(trace.get("has_error"))]

        if traces:
            durations = [
                float(trace["duration_ms"])
                for trace in traces
                if trace.get("duration_ms") is not None
            ]

            trace_sentence = (
                f"{len(traces)} recent traces were "
                f"inspected; {len(error_traces)} "
                "contained recorded errors."
            )

            if durations:
                trace_sentence += (
                    " Observed trace durations ranged "
                    f"from {min(durations):.0f} ms to "
                    f"{max(durations):.0f} ms."
                )

            evidence.append(trace_sentence)

            successful_completion_events = {
                "event=prepared",
                "event=charged",
                "event=shipped",
            }

            completed_traces = 0

            for trace in traces:
                events = trace.get(
                    "key_events",
                    [],
                )

                if isinstance(events, list) and successful_completion_events.issubset(set(events)):
                    completed_traces += 1

            if completed_traces:
                evidence.append(
                    f"{completed_traces} of "
                    f"{len(traces)} sampled traces "
                    "contained prepared, charged, "
                    "and shipped completion events."
                )

        downstream_services: list[str] = []

        if dependencies is not None:
            raw_downstream = dependencies.get(
                "downstream_services",
                [],
            )

            if isinstance(raw_downstream, list):
                downstream_services = [str(value) for value in raw_downstream]

            if downstream_services:
                evidence.append("Checkout depends on " + ", ".join(downstream_services) + ".")

        knowledge_ids: list[str] = []

        if isinstance(
            raw_knowledge_evidence,
            list,
        ):
            for item in raw_knowledge_evidence:
                if not isinstance(item, dict):
                    continue

                document_id = item.get("document_id")

                if document_id:
                    knowledge_ids.append(str(document_id))

        if knowledge_ids:
            evidence.append(
                "Relevant knowledge documents "
                "retrieved: " + ", ".join(f"[{document_id}]" for document_id in knowledge_ids) + "."
            )

        has_traces = bool(traces)

        degraded_metrics = (metric_error_rate is not None and float(metric_error_rate) > 5.0) or (
            metric_p95 is not None and float(metric_p95) > 2000.0
        )

        recent_traces_healthy = has_traces and len(error_traces) == 0

        if degraded_metrics and recent_traces_healthy:
            incident_summary = (
                "The metrics window shows significant "
                "checkout degradation, while the most "
                "recent sampled traces contain no recorded "
                "errors. This pattern is consistent with "
                "an earlier or intermittent problem that "
                "may have recovered by the time of the "
                "latest trace sample."
            )

            likely_root_cause = (
                "No single root cause is confirmed. "
                "The evidence supports an earlier or "
                "intermittent checkout degradation, but "
                "the recent successful traces do not "
                "identify a currently failing dependency."
            )

            confidence = "medium"

        elif degraded_metrics:
            incident_summary = (
                "Checkout metrics show elevated errors or latency during the observation window."
            )

            likely_root_cause = (
                "The available evidence confirms service "
                "degradation but does not identify a "
                "single root cause."
            )

            confidence = "medium"

        elif recent_traces_healthy:
            incident_summary = (
                "Recent checkout traces completed without "
                "recorded errors, and the available "
                "operational evidence does not confirm "
                "an active failure."
            )

            likely_root_cause = (
                "No active root cause could be confirmed from the collected evidence."
            )

            confidence = "medium"

        else:
            incident_summary = (
                "SafeOps collected the available read-only "
                "evidence, but there was not enough "
                "validated operational data to determine "
                "the incident state."
            )

            likely_root_cause = "No root cause could be confirmed from the collected evidence."

            confidence = "low"

        if downstream_services:
            recommended_checks.append(
                "Compare metrics and traces for the "
                "downstream dependencies: " + ", ".join(downstream_services) + "."
            )

        if traces:
            recommended_checks.append(
                "Inspect the slowest recent checkout "
                "traces and compare them with a known "
                "healthy trace."
            )

        if "search_logs" not in tools_seen:
            recommended_checks.append(
                "Inspect correlated checkout and dependency logs for the degraded metrics interval."
            )

            limitations.append("Correlated log evidence was not collected in this investigation.")

        if "get_recent_deployments" not in tools_seen:
            recommended_checks.append(
                "Check whether a deployment or configuration change preceded the degradation."
            )

            limitations.append("Deployment evidence was not collected in this investigation.")

        if metrics is not None and traces:
            limitations.append(
                "Metrics summarize a broader time window "
                "than the limited recent trace sample, so "
                "the two evidence sources may represent "
                "different phases of the incident."
            )

        limitations.append(
            "The language model did not return a valid "
            "structured report, so SafeOps generated "
            "this conservative report directly from "
            "validated tool evidence."
        )

        if failure_reason:
            limitations.append(f"Structured synthesis failure: {failure_reason}")

        if not evidence:
            evidence.append(
                "No validated operational evidence was available for automatic synthesis."
            )

        if not recommended_checks:
            recommended_checks.append(
                "Collect additional read-only operational evidence before assigning a root cause."
            )

        return IncidentInvestigationReport(
            service=service,
            question=question,
            incident_summary=incident_summary,
            likely_root_cause=likely_root_cause,
            confidence=confidence,
            evidence=evidence,
            recommended_next_checks=(recommended_checks),
            limitations=limitations,
            tools_used=[],
            evidence_sources=[],
            knowledge_documents=[],
            safety_status=(AgentSafetyStatus.READ_ONLY_ONLY),
        )

    @classmethod
    def _parse_report_message(
        cls,
        message: BaseMessage,
    ) -> IncidentInvestigationReport:
        """Parse a structured report from a model response."""

        if not isinstance(message, AIMessage):
            raise InvestigationOutputError("Report synthesizer must return an AIMessage.")

        return cls._parse_report_text(cls._message_text(message))

    @classmethod
    def _parse_report_text(
        cls,
        raw_text: str,
    ) -> IncidentInvestigationReport:
        """Parse JSON, escaped JSON, or Python-style objects."""

        candidates = cls._report_text_candidates(raw_text)

        last_error: Exception | None = None

        for candidate in candidates:
            current: object = candidate

            for _ in range(6):
                if isinstance(current, dict):
                    try:
                        return IncidentInvestigationReport.model_validate(current)
                    except ValueError as exc:
                        last_error = exc
                        break

                if not isinstance(current, str):
                    last_error = ValueError("The decoded report must be an object or string.")
                    break

                normalized = current.strip()

                if not normalized:
                    break

                decoded: object | None = None

                try:
                    decoded = json.loads(normalized)
                except json.JSONDecodeError as exc:
                    last_error = exc

                if decoded is None:
                    try:
                        decoded = ast.literal_eval(normalized)
                    except (
                        ValueError,
                        SyntaxError,
                    ) as exc:
                        last_error = exc

                if decoded is not None:
                    current = decoded
                    continue

                unescaped = cls._unescape_json_text(normalized)

                if unescaped == normalized:
                    break

                current = unescaped

        raise InvestigationOutputError(
            "The model returned an invalid incident report."
        ) from last_error

    @classmethod
    def _report_text_candidates(
        cls,
        raw_text: str,
    ) -> list[str]:
        """Return distinct possible report representations."""

        cleaned = raw_text.strip()

        candidates: list[str] = []

        def add_candidate(value: str) -> None:
            normalized = value.strip()

            if normalized and normalized not in candidates:
                candidates.append(normalized)

        add_candidate(cleaned)

        without_fences = cleaned

        if without_fences.startswith("```"):
            lines = without_fences.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            without_fences = "\n".join(lines)

            add_candidate(without_fences)

        for value in list(candidates):
            try:
                add_candidate(cls._extract_json_object(value))
            except InvestigationOutputError:
                pass

            unescaped = cls._unescape_json_text(value)

            add_candidate(unescaped)

            try:
                add_candidate(cls._extract_json_object(unescaped))
            except InvestigationOutputError:
                pass

        return candidates

    @staticmethod
    def _unescape_json_text(
        text: str,
    ) -> str:
        """Decode one or more common JSON escaping layers."""

        current = text

        for _ in range(6):
            updated = (
                current.replace("\\r\\n", "\n")
                .replace("\\n", "\n")
                .replace("\\r", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\'", "'")
                .replace("\\/", "/")
                .replace("\\\\", "\\")
            )

            if updated == current:
                break

            current = updated

        return current

    @staticmethod
    def _tool_call_signature(
        *,
        tool_name: IncidentToolName,
        arguments: dict[str, Any],
    ) -> str:
        return json.dumps(
            {
                "tool": tool_name.value,
                "arguments": arguments,
            },
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def _tool_call_id(
        *,
        raw_call: dict[str, Any],
        tool_name: IncidentToolName,
        call_number: int,
    ) -> str:
        raw_call_id = raw_call.get("id")

        if raw_call_id:
            return str(raw_call_id)

        return f"{tool_name.value}-{call_number}"

    @staticmethod
    def _normalize_arguments(
        raw_arguments: object,
    ) -> dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return raw_arguments

        if isinstance(raw_arguments, str):
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise AgentToolExecutionError("Tool arguments were not valid JSON.") from exc

            if isinstance(parsed, dict):
                return parsed

        raise AgentToolExecutionError("Tool arguments must be a JSON object.")

    @staticmethod
    def _parse_source(
        raw_source: object,
    ) -> EvidenceSource | None:
        if raw_source is None:
            return None

        try:
            return EvidenceSource(str(raw_source))
        except ValueError:
            return None

    @staticmethod
    def _base_message_text(
        message: BaseMessage,
    ) -> str:
        if isinstance(message.content, str):
            return message.content.strip()

        return json.dumps(
            message.content,
            ensure_ascii=False,
            default=str,
        ).strip()

    @classmethod
    def _message_text(
        cls,
        message: AIMessage,
    ) -> str:
        return cls._base_message_text(message)

    @staticmethod
    def _extract_json_object(
        text: str,
    ) -> str:
        start_index = text.find("{")
        end_index = text.rfind("}")

        if start_index < 0 or end_index < start_index:
            raise InvestigationOutputError("The final response did not contain JSON.")

        return text[start_index : end_index + 1]

    @staticmethod
    def _unique_tools(
        records: list[AgentToolCallRecord],
    ) -> list[IncidentToolName]:
        tools: list[IncidentToolName] = []

        for record in records:
            if record.tool_name not in tools:
                tools.append(record.tool_name)

        return tools

    @staticmethod
    def _unique_sources(
        records: list[AgentToolCallRecord],
    ) -> list[EvidenceSource]:
        sources: list[EvidenceSource] = []

        for record in records:
            if record.source is not None and record.source not in sources:
                sources.append(record.source)

        return sources
