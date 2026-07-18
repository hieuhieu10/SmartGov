"""
Template Extractor Agent.

Kế hoạch now uses a fixed administrative outline, so this node intentionally
does not extract same-type headings from repository documents.
"""


async def template_extractor_node(state: dict) -> dict:
    """Return an empty template outline for the drafting graph."""
    return {"template_outline": {}}
