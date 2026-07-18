"""
Sequential drafting orchestrator.

Plain async flow:
TemplateExtractor -> Planner -> Researcher -> Writer -> Reviewer, with an
optional Writer retry when Reviewer requests revision.
"""

import logging

from app.agents.template_extractor import template_extractor_node
from app.agents.planner import planner_node
from app.agents.researcher import researcher_node
from app.agents.writer import writer_node
from app.agents.reviewer import reviewer_node

logger = logging.getLogger(__name__)


async def run_drafting_pipeline(
    user_request: str,
    doc_type: str,
    doc_type_label: str,
    input_data: dict,
    warehouse_ids: list[str],
    selected_document_ids: list[str] | None = None,
    trich_yeu: str = "",
    max_iterations: int = 3,
) -> dict:
    """Run the self-hosted drafting pipeline."""
    state = {
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
        "[DraftingPipeline] start doc_type=%s warehouses=%d max_iter=%d",
        doc_type,
        len(warehouse_ids),
        max_iterations,
    )

    try:
        state.update(await template_extractor_node(state))
        state.update(await planner_node(state))
        state.update(await researcher_node(state))

        while True:
            state.update(await writer_node(state))
            state.update(await reviewer_node(state))

            if state.get("review_pass", False):
                break
            if state.get("iteration", 1) >= max_iterations:
                logger.info(
                    "[DraftingPipeline] max iterations reached (%s/%s)",
                    state.get("iteration", 0),
                    max_iterations,
                )
                break

        logger.info(
            "[DraftingPipeline] complete iterations=%s pass=%s fields=%d",
            state.get("iteration", 0),
            state.get("review_pass", False),
            len(state.get("draft_data", {}) or {}),
        )
        return state

    except Exception as exc:
        logger.error("[DraftingPipeline] failed: %s", exc, exc_info=True)
        return {
            **state,
            "error": str(exc),
            "draft_data": {"noi_dung": f"Lỗi hệ thống: {str(exc)}"},
            "review_pass": False,
        }
