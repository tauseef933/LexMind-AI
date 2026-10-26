"""
LangGraph orchestrator for LexMind AI.

Flow:
  contextualize_query → route_query → run_agents_parallel → merge_results → END

Nodes report progress through LangGraph's custom stream channel, so callers
of stream_events() receive, in order:
  {"type": "agent_trace", "step": {"agent": ..., "status": ...}}   live agent status
  {"type": "token", "content": "..."}                             answer text as it is generated
  {"type": "final", "response": ..., "agent_trace": [...], "sources": [...], "actions": [...]}

Concatenating every "token" content gives exactly final["response"].

Exported symbols:
  orchestrator                                   — compiled LangGraph graph
  stream_events(query, case_id, case_name, history) → iterator of events above
  process(query, case_id, case_name, history)    → final event (no streaming)
"""

import contextvars
import logging
import queue
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, TypedDict, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from agents import (
    action_agent,
    analytics_agent,
    document_agent,
    research_agent,
)
from llm import ask, get_llm, parse_json_response

logger = logging.getLogger("lexmind.orchestrator")

# ---------------------------------------------------------------------------
# Routing prompt
# ---------------------------------------------------------------------------
ROUTING_PROMPT = """
You are the orchestrator of a legal AI system.
Given a user message, identify all required tasks and route each to
the correct agent. Output ONLY valid JSON, no other text.

Available agents:
- document_agent: Read, analyse and answer questions about case files, contracts, evidence, documents — including any amounts, fees, prices, caps or payment terms WRITTEN IN the documents
- analytics_agent: ONLY the law firm's own billing records for this matter (invoices it issued, hours billed, totals paid, disputed invoices) — NOT money terms inside contracts
- action_agent: Send emails, create calendar events, generate PDFs
- research_agent: Find relevant case law, statutes, legal precedents

Routing rules:
1. Use document_agent for ANY question about what is in the case documents, case summaries, facts, obligations, risks, parties, dates, events — and for fees, prices, liability caps, penalties or payment deadlines stated in a contract or agreement.
2. Use analytics_agent ONLY when the user asks about the firm's billing records: "how much have we billed", "list our invoices", "hours billed", "which invoice is disputed".
3. Use research_agent ONLY when the user asks for external case law or legal precedents.
4. Use action_agent ONLY when the user asks to send an email, schedule a meeting, or generate a document.
5. Default to document_agent if unsure.

Examples:
- "What is the monthly fee under the services agreement?" → document_agent
- "What is the liability cap in the NDA?" → document_agent
- "How much have we invoiced the client so far?" → analytics_agent
- "Which of our invoices is disputed?" → analytics_agent

User message: {query}
Active case: {case_name} (ID: {case_id})

Respond with:
{{
  "subtasks": [
    {{
      "agent": "agent_name",
      "query": "specific query for this agent",
      "priority": 1
    }}
  ]
}}
"""

_REWRITE_SYSTEM = """You rewrite follow-up questions in a legal case chat.
Given the recent conversation and the user's latest message, rewrite the latest
message as a single standalone question that can be understood without the
conversation (resolve pronouns like "it", "that clause", "the second one").
If it is already standalone, return it unchanged.
Output ONLY the rewritten question."""

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------
_AGENT_MAP = {
    "document_agent":  document_agent,
    "analytics_agent": analytics_agent,
    "action_agent":    action_agent,
    "research_agent":  research_agent,
}

# Agents whose run() accepts on_token and streams its answer
_STREAMING_AGENTS = {"document_agent", "research_agent"}

_LABELS = {
    "document_agent":  "Document Analysis",
    "analytics_agent": "Analytics & Billing",
    "research_agent":  "Legal Research",
    "action_agent":    "Proposed Actions",
}

_SECTION_SEPARATOR = "\n\n---\n\n"
_HISTORY_CHARS = 1500   # per message, when building the rewrite prompt


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    query:          str           # user's message as typed
    case_id:        str
    case_name:      str
    history:        list[dict]    # earlier messages: {"role", "content"}
    standalone:     str           # query rewritten to stand on its own
    subtasks:       list[dict]
    results:        list[dict]    # one per subtask, in display order
    lead_text:      str           # lead section body exactly as streamed
    final_response: str


def _emit(writer: Any, agent: str, status: str) -> None:
    writer({"type": "agent_trace", "step": {"agent": agent, "status": status}})


# ---------------------------------------------------------------------------
# Node 1 — contextualize_query (conversation memory)
# ---------------------------------------------------------------------------
def contextualize_query(state: AgentState) -> dict:
    history = state["history"]
    query = state["query"]
    if not history:
        return {"standalone": query}

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content'][:_HISTORY_CHARS]}" for m in history
    )
    try:
        rewritten = ask(get_llm(0), [
            SystemMessage(content=_REWRITE_SYSTEM),
            HumanMessage(content=f"Conversation:\n{transcript}\n\nLatest message: {query}"),
        ])
        standalone = rewritten.strip().strip('"') or query
    except Exception:
        logger.exception("Query rewrite failed — using the message as typed")
        standalone = query

    if standalone != query:
        logger.info("Rewrote follow-up %r → %r", query[:80], standalone[:80])
    return {"standalone": standalone}


# ---------------------------------------------------------------------------
# Node 2 — route_query
# ---------------------------------------------------------------------------
def route_query(state: AgentState) -> dict:
    writer = get_stream_writer()
    _emit(writer, "orchestrator", "routing")

    query     = state["standalone"]
    case_id   = state["case_id"]
    case_name = state["case_name"]

    try:
        filled = ROUTING_PROMPT.format(
            query=query,
            case_name=case_name,
            case_id=case_id,
        )
        response = ask(get_llm(0), [
            SystemMessage(content="You are a routing orchestrator. Output ONLY valid JSON."),
            HumanMessage(content=filled),
        ])
        parsed = parse_json_response(response)
        subtasks: list[dict] = parsed.get("subtasks", [])

        # Validate: keep only tasks that map to a known agent
        subtasks = [t for t in subtasks if t.get("agent") in _AGENT_MAP]
        if not subtasks:
            raise ValueError("No valid agent subtasks parsed")

        # Sort by priority (lower = higher priority)
        subtasks.sort(key=lambda t: t.get("priority", 99))

        logger.info("Routed %d subtask(s) for case %s: %s",
                    len(subtasks), case_id, [t["agent"] for t in subtasks])

    except Exception as exc:
        logger.warning("Routing failed (%s) — falling back to document_agent.", exc)
        subtasks = [{"agent": "document_agent", "query": query, "priority": 1}]

    # The first streaming-capable agent is shown first so its answer can
    # stream live; the others follow in priority order.
    lead = next((i for i, t in enumerate(subtasks) if t["agent"] in _STREAMING_AGENTS), None)
    if lead:
        subtasks.insert(0, subtasks.pop(lead))

    _emit(writer, "orchestrator", "done")
    for task in subtasks:
        _emit(writer, task["agent"], "running")
    return {"subtasks": subtasks}


# ---------------------------------------------------------------------------
# Section formatting (shared by streaming and the final merge)
# ---------------------------------------------------------------------------
def _section_body(result: dict) -> str:
    agent_name = result.get("agent", "unknown")

    if "error" in result:
        return f"⚠️ {result['error']}"

    if agent_name == "analytics_agent":
        rows = result.get("data", [])
        hint = f"\n\n*Report:* `{result.get('report', '')}` — {len(rows)} row(s)." if rows else ""
        return f"{result.get('answer', '')}{hint}"

    if agent_name == "research_agent":
        sources = result.get("sources", [])
        src_text = ("\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)) if sources else ""
        return f"{result.get('answer', '')}{src_text}"

    if agent_name == "action_agent":
        return (
            f"*Type:* {result.get('action_type', 'action')}\n\n{result.get('preview', '')}\n\n"
            "⚠️ **Nothing has been sent. Review the draft and use the buttons below to act on it.**"
        )

    return result.get("answer") or result.get("preview") or ""


def _section_header(agent_name: str, multi: bool) -> str:
    if not multi:
        return ""
    label = _LABELS.get(agent_name, agent_name.replace("_", " ").title())
    return f"## {label}\n"


# ---------------------------------------------------------------------------
# Node 3 — run_agents_parallel
# ---------------------------------------------------------------------------
def run_agents_parallel(state: AgentState) -> dict:
    writer = get_stream_writer()
    subtasks = state["subtasks"]
    case_id  = state["case_id"]
    multi = len(subtasks) > 1
    lead_streams = subtasks[0]["agent"] in _STREAMING_AGENTS

    # Worker threads report here; this thread forwards to the stream writer
    events: queue.Queue = queue.Queue()

    def _run_one(index: int, task: dict) -> None:
        agent_name = task["agent"]
        module = _AGENT_MAP[agent_name]
        agent_query = task.get("query") or state["standalone"]
        try:
            if index == 0 and lead_streams:
                result = module.run(agent_query, case_id, on_token=lambda t: events.put(("token", index, t)))
            else:
                result = module.run(agent_query, case_id)
        except Exception:
            logger.exception("Agent %s raised", agent_name)
            result = {"error": "Agent failed unexpectedly.", "agent": agent_name}
        events.put(("done", index, result))

    results: list[Optional[dict]] = [None] * len(subtasks)
    streamed = ""   # lead section text already sent to the client

    writer({"type": "token", "content": _section_header(subtasks[0]["agent"], multi)})

    with ThreadPoolExecutor(max_workers=len(subtasks)) as executor:
        for i, task in enumerate(subtasks):
            # copy_context keeps the request ID on agent log lines
            executor.submit(contextvars.copy_context().run, _run_one, i, task)

        pending = len(subtasks)
        while pending:
            kind, index, payload = events.get()
            if kind == "token":
                streamed += payload
                writer({"type": "token", "content": payload})
                continue

            pending -= 1
            results[index] = payload
            _emit(writer, payload.get("agent", subtasks[index]["agent"]),
                  "error" if "error" in payload else "done")

            if index == 0:
                # Send whatever part of the lead section was not streamed
                # (e.g. research sources, an error, or a non-streaming agent)
                body = _section_body(payload)
                if body.startswith(streamed):
                    rest = body[len(streamed):]
                else:
                    rest = "\n\n" + body
                if rest:
                    writer({"type": "token", "content": rest})
                streamed += rest

    # Remaining sections, in display order, once everything has finished
    for result, task in zip(results[1:], subtasks[1:]):
        assert result is not None
        writer({
            "type": "token",
            "content": _SECTION_SEPARATOR + _section_header(task["agent"], multi) + _section_body(result),
        })

    return {"results": results, "lead_text": streamed}


# ---------------------------------------------------------------------------
# Node 4 — merge_results
# ---------------------------------------------------------------------------
def merge_results(state: AgentState) -> dict:
    """Build the final text exactly as it was streamed, for persistence."""
    results = state["results"]
    multi = len(results) > 1
    sections = [_section_header(results[0].get("agent", ""), multi) + state["lead_text"]]
    sections += [_section_header(r.get("agent", ""), multi) + _section_body(r) for r in results[1:]]
    return {"final_response": _SECTION_SEPARATOR.join(sections)}


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------
_graph = StateGraph(AgentState)

_graph.add_node("contextualize_query", contextualize_query)
_graph.add_node("route_query",         route_query)
_graph.add_node("run_agents_parallel", run_agents_parallel)
_graph.add_node("merge_results",       merge_results)

_graph.set_entry_point("contextualize_query")

_graph.add_edge("contextualize_query", "route_query")
_graph.add_edge("route_query",         "run_agents_parallel")
_graph.add_edge("run_agents_parallel", "merge_results")
_graph.add_edge("merge_results",       END)

orchestrator = _graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _final_event(state: dict) -> dict:
    results: list[dict] = state.get("results") or []

    # Collect sources from all agents that emit them
    sources: list = []
    seen_sources: set = set()
    for result in results:
        for src in result.get("sources", []):
            key = str(src)
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(src)

    actions = [
        {"action_type": r.get("action_type"), **(r.get("action") or {})}
        for r in results
        if r.get("agent") == "action_agent" and "error" not in r
    ]

    return {
        "type":        "final",
        "response":    state.get("final_response", ""),
        "agent_trace": results,
        "sources":     sources,
        "actions":     actions,
    }


def stream_events(
    query: str,
    case_id: str,
    case_name: str,
    history: Optional[list[dict]] = None,
) -> Iterator[dict]:
    """Run the pipeline, yielding progress/token events and then the final event."""
    initial_state: AgentState = {
        "query":          query,
        "case_id":        case_id,
        "case_name":      case_name,
        "history":        history or [],
        "standalone":     query,
        "subtasks":       [],
        "results":        [],
        "lead_text":      "",
        "final_response": "",
    }

    last_state: dict = {}
    for mode, raw_chunk in orchestrator.stream(initial_state, stream_mode=["custom", "values"]):
        chunk = cast(dict, raw_chunk)
        if mode == "custom":
            if chunk.get("type") != "token" or chunk.get("content"):
                yield chunk
        else:
            last_state = chunk

    yield _final_event(last_state)


def process(
    query: str,
    case_id: str,
    case_name: str,
    history: Optional[list[dict]] = None,
) -> dict:
    """Run the full pipeline without streaming; returns the final event."""
    final: dict = {}
    for event in stream_events(query, case_id, case_name, history):
        if event["type"] == "final":
            final = event
    return final
