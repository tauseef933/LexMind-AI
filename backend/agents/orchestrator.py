"""
LangGraph orchestrator for LexMind AI.

Flow:
  route_query → run_agents_parallel → merge_results → END

Exported symbols:
  orchestrator  — compiled LangGraph graph
  process(query, case_id, case_name) → dict
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agents import (
    action_agent,
    analytics_agent,
    document_agent,
    research_agent,
)

logger = logging.getLogger("lexmind.orchestrator")

from config import GROQ_MODEL

# ---------------------------------------------------------------------------
# Exact routing prompt from spec
# ---------------------------------------------------------------------------
ROUTING_PROMPT = """
You are the orchestrator of a legal AI system.
Given a user message, identify all required tasks and route each to
the correct agent. Output ONLY valid JSON, no other text.

Available agents:
- document_agent: Read, analyse and answer questions about case files, contracts, evidence, documents
- analytics_agent: ONLY for explicit billing queries, invoice amounts, payment totals, financial disputes — NOT for general case questions or summaries
- action_agent: Send emails, create calendar events, generate PDFs
- research_agent: Find relevant case law, statutes, legal precedents

Routing rules:
1. Use document_agent for ANY question about what is in the case documents, case summaries, facts, obligations, risks, parties, dates, events.
2. Use analytics_agent ONLY when the user explicitly asks about money, billing, invoices, hours billed, payments or financial data.
3. Use research_agent ONLY when the user asks for external case law or legal precedents.
4. Use action_agent ONLY when the user asks to send an email, schedule a meeting, or generate a document.
5. Default to document_agent if unsure.

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

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------
_AGENT_MAP = {
    "document_agent":  document_agent,
    "analytics_agent": analytics_agent,
    "action_agent":    action_agent,
    "research_agent":  research_agent,
}

_DEFAULT_SUBTASK = [
    {"agent": "document_agent", "priority": 1}
]


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    query:          str
    case_id:        str
    case_name:      str
    subtasks:       list[dict]
    results:        list[dict]
    final_response: str


# ---------------------------------------------------------------------------
# Node 1 — route_query
# ---------------------------------------------------------------------------
def route_query(state: AgentState) -> AgentState:
    query     = state["query"]
    case_id   = state["case_id"]
    case_name = state["case_name"]

    try:
        llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0,
        )
        filled = ROUTING_PROMPT.format(
            query=query,
            case_name=case_name,
            case_id=case_id,
        )
        response = llm.invoke([
            SystemMessage(content="You are a routing orchestrator. Output ONLY valid JSON."),
            HumanMessage(content=filled),
        ])
        raw = response.content.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
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

    state["subtasks"] = subtasks
    return state


# ---------------------------------------------------------------------------
# Node 2 — run_agents_parallel
# ---------------------------------------------------------------------------
def run_agents_parallel(state: AgentState) -> AgentState:
    subtasks = state["subtasks"]
    case_id  = state["case_id"]
    results: list[dict] = []

    def _run_one(task: dict) -> dict:
        agent_name = task["agent"]
        agent_query = task.get("query", state["query"])
        module = _AGENT_MAP.get(agent_name)
        if module is None:
            return {"error": f"Unknown agent: {agent_name}", "agent": agent_name}
        logger.debug("Running %s  query=%r", agent_name, agent_query[:80])
        return module.run(agent_query, case_id)

    # Run all subtasks in parallel
    with ThreadPoolExecutor(max_workers=len(subtasks)) as executor:
        future_to_task = {executor.submit(_run_one, t): t for t in subtasks}
        for future in as_completed(future_to_task):
            try:
                results.append(future.result())
            except Exception as exc:
                task = future_to_task[future]
                logger.error("Agent %s raised: %s", task.get("agent"), exc, exc_info=True)
                results.append({"error": str(exc), "agent": task.get("agent", "unknown")})

    state["results"] = results
    return state


# ---------------------------------------------------------------------------
# Node 3 — merge_results
# ---------------------------------------------------------------------------
def merge_results(state: AgentState) -> AgentState:
    results = state["results"]
    sections: list[str] = []

    _LABELS = {
        "document_agent":  "Document Analysis",
        "analytics_agent": "Analytics & Billing",
        "research_agent":  "Legal Research",
        "action_agent":    "Proposed Actions",
    }

    for result in results:
        agent_name = result.get("agent", "unknown")
        label = _LABELS.get(agent_name, agent_name.replace("_", " ").title())

        if "error" in result:
            sections.append(f"## {label}\n⚠️ {result['error']}")
            continue

        # Each agent returns different keys — normalise to a text block
        if agent_name == "document_agent":
            sections.append(f"## {label}\n{result.get('answer', '')}")

        elif agent_name == "analytics_agent":
            rows = result.get("data", [])
            table_hint = f"\n*SQL:* `{result.get('sql', '')}` — {len(rows)} row(s) returned." if rows else ""
            sections.append(f"## {label}\n{result.get('answer', '')}{table_hint}")

        elif agent_name == "research_agent":
            sources = result.get("sources", [])
            src_text = ("\n\n**Sources:**\n" + "\n".join(f"- {s}" for s in sources)) if sources else ""
            sections.append(f"## {label}\n{result.get('answer', '')}{src_text}")

        elif agent_name == "action_agent":
            preview   = result.get("preview", "")
            act_type  = result.get("action_type", "action")
            sections.append(
                f"## {label}\n*Type:* {act_type}\n\n{preview}\n\n"
                f"⚠️ **This action requires your confirmation before execution.**"
            )

        else:
            # Generic fallback
            text = result.get("answer") or result.get("preview") or str(result)
            sections.append(f"## {label}\n{text}")

    state["final_response"] = "\n\n---\n\n".join(sections)
    return state


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------
_graph = StateGraph(AgentState)

_graph.add_node("route_query",         route_query)
_graph.add_node("run_agents_parallel", run_agents_parallel)
_graph.add_node("merge_results",       merge_results)

_graph.set_entry_point("route_query")

_graph.add_edge("route_query",         "run_agents_parallel")
_graph.add_edge("run_agents_parallel", "merge_results")
_graph.add_edge("merge_results",       END)

orchestrator = _graph.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def process(query: str, case_id: str, case_name: str) -> dict:
    """
    Run the full orchestrator pipeline.

    Returns
    -------
    {
        "response":    str,          # merged final answer
        "agent_trace": list[dict],   # raw per-agent result dicts
        "sources":     list,         # deduplicated sources across all agents
    }
    """
    initial_state: AgentState = {
        "query":          query,
        "case_id":        case_id,
        "case_name":      case_name,
        "subtasks":       [],
        "results":        [],
        "final_response": "",
    }

    final_state: AgentState = orchestrator.invoke(initial_state)

    # Collect sources from all agents that emit them
    sources: list = []
    seen_sources: set = set()
    for result in final_state.get("results", []):
        for src in result.get("sources", []):
            key = str(src)
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append(src)

    return {
        "response":    final_state["final_response"],
        "agent_trace": final_state.get("results", []),
        "sources":     sources,
    }
