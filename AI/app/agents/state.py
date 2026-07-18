"""
Agent State — Shared state definition for the multi-agent workflow.

All agents read from and write to this shared state as it flows through the
LangGraph self-hosted drafting orchestrator.
"""

from typing import TypedDict, Optional


class AgentState(TypedDict, total=False):
    """Shared state for the TemplateExtractor → Planner → Researcher → Writer → Reviewer pipeline."""

    # ── Input (set by caller) ─────────────────────────────────────────
    user_request: str           # Original user request / noi_dung_chinh
    doc_type: str               # Document type code (e.g. "bao_cao")
    doc_type_label: str         # Vietnamese label (e.g. "Báo cáo")
    input_data: dict            # All user-provided metadata fields
    warehouse_ids: list[str]    # List of repo IDs to search
    selected_document_ids: list[str] # Optional user-selected source document IDs
    trich_yeu: str              # Document subject/summary

    # ── Template extraction output ───────────────────────────────────
    template_outline: dict      # Same-type sample outline: {source, headings, notes}

    # ── Planner output ────────────────────────────────────────────────
    plan: dict                  # Outline: {sections: [{title, key_points, search_queries}]}

    # ── Researcher output ─────────────────────────────────────────────
    scanner_results: list[dict] # Shared retrieval (pgvector+FTS) entries, with
                                 # DocumentScanner full-scan fallback per repo
                                 # when a repo has no vectors yet: [{filename,
                                 # excerpts, doc_id, citation_label?, section_label?}]
    research_context: str       # Formatted context string for Writer

    # ── Writer output ─────────────────────────────────────────────────
    draft: str                  # Generated draft content (JSON string)
    draft_data: dict            # Parsed draft data (dict)
    section_drafts: list[dict]  # Section-by-section generated content before merge

    # ── Reviewer output ───────────────────────────────────────────────
    review_feedback: str        # Detailed feedback from Reviewer
    review_pass: bool           # Whether the draft passed review
    review_issues: list[str]    # List of specific issues found

    # ── Control flow ──────────────────────────────────────────────────
    iteration: int              # Current Writer↔Reviewer iteration
    max_iterations: int         # Maximum allowed iterations (default: 2)
    error: str                  # Error message if any step fails
