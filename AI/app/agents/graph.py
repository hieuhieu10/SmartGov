"""
Agent Graph — LangGraph state machine for self-hosted document drafting.

Orchestrates:
  START -> TemplateExtractor -> Planner -> Researcher -> Writer -> Reviewer
                                                     ^          |
                                                     +----------+
"""

import logging

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.template_extractor import template_extractor_node
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.agents.writer import writer_node
from app.agents.reviewer import reviewer_node

logger = logging.getLogger(__name__)


def _should_continue(state: dict) -> str:
    """
    Conditional edge after Reviewer:
    - If review passed OR max iterations reached -> END
    - Otherwise -> back to Writer for revision
    """
    if state.get("review_pass", False):
        return "end"

    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 2)
    if iteration >= max_iterations:
        logger.info("[Graph] Max iterations reached (%s/%s), ending", iteration, max_iterations)
        return "end"

    logger.info("[Graph] Reviewer requested revision (%s/%s)", iteration, max_iterations)
    return "revise"


def build_graph() -> StateGraph:
    """Build the LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("template_extractor", template_extractor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("template_extractor")
    graph.add_edge("template_extractor", "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        _should_continue,
        {
            "revise": "writer",
            "end": END,
        },
    )

    return graph.compile()


_compiled_graph = None


def _get_graph():
    """Get or build the compiled graph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
        logger.info("[Graph] LangGraph compiled successfully")
    return _compiled_graph


async def run_agent_graph(
    user_request: str,
    doc_type: str,
    doc_type_label: str,
    input_data: dict,
    warehouse_ids: list[str],
    selected_document_ids: list[str] | None = None,
    trich_yeu: str = "",
    max_iterations: int = 3,
) -> dict:
    """Run the self-hosted drafting LangGraph pipeline."""
    graph = _get_graph()
    initial_state: AgentState = {
        "user_request": user_request,
        "doc_type": doc_type,
        "doc_type_label": doc_type_label,
        "input_data": input_data,
        "warehouse_ids": warehouse_ids,
        "selected_document_ids": selected_document_ids or [],
        "trich_yeu": trich_yeu,
        "iteration": 0,
        "max_iterations": max_iterations,
    }

    logger.info(
        "[Graph] Starting pipeline: doc_type=%s warehouses=%d max_iter=%d",
        doc_type,
        len(warehouse_ids),
        max_iterations,
    )

    try:
        final_state = await graph.ainvoke(initial_state)
        logger.info(
            "[Graph] Pipeline complete: iterations=%s pass=%s draft_fields=%d",
            final_state.get("iteration", 0),
            final_state.get("review_pass", False),
            len(final_state.get("draft_data", {}) or {}),
        )
        return dict(final_state)
    except Exception as exc:
        logger.error("[Graph] Pipeline failed: %s", exc, exc_info=True)
        return {
            **initial_state,
            "error": str(exc),
            "draft_data": {"noi_dung": f"Lỗi hệ thống: {str(exc)}"},
            "review_pass": False,
        }
