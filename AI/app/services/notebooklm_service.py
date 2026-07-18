"""
STTNB NotebookLM Service — Integration with notebooklm-py.

Handles Repository Management:
1. Creating persistent notebooks for repositories
2. Uploading document sources
3. Chat Q&A for repositories
4. Deleting notebooks
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from notebooklm import NotebookLMClient

logger = logging.getLogger(__name__)


class NotebookLMService:
    """Service to interact with Google NotebookLM via unofficial API."""

    def __init__(self):
        pass

    async def _get_client(self) -> NotebookLMClient:
        """Get a fresh NotebookLM client from stored credentials."""
        return await NotebookLMClient.from_storage()

    def get_session_fingerprint(self) -> str:
        """
        Return a stable hash for the currently stored NotebookLM session.

        The raw session/cookies are never stored in the application database;
        only this digest is used to detect that the active NotebookLM account
        or session has changed.
        """
        candidates = [
            Path.home() / ".notebooklm" / "profiles" / "default" / "storage_state.json",
            Path.home() / ".notebooklm" / "storage_state.json",
        ]
        digest = hashlib.sha256()
        found = False
        for path in candidates:
            if not path.exists():
                continue
            try:
                content = path.read_bytes()
            except OSError as e:
                logger.warning("Could not read NotebookLM session file %s: %s", path, e)
                continue
            found = True
            digest.update(str(path.name).encode("utf-8"))
            digest.update(content)

        return digest.hexdigest() if found else ""

    # ─── Repository Management Methods ───────────────────────────────

    async def create_notebook(self, name: str) -> str:
        """Create a new notebook and return its ID."""
        client = await self._get_client()
        async with client:
            nb = await client.notebooks.create(name)
            logger.info(f"Created notebook: {nb.id} — {name}")
            return nb.id

    async def delete_notebook(self, notebook_id: str):
        """Delete a notebook by ID."""
        client = await self._get_client()
        async with client:
            await client.notebooks.delete(notebook_id)
            logger.info(f"Deleted notebook: {notebook_id}")

    async def upload_source(self, notebook_id: str, file_path: str) -> Optional[str]:
        """
        Upload a file as a source to a notebook.
        Returns the source ID if available.
        """
        client = await self._get_client()
        async with client:
            result = await client.sources.add_file(notebook_id, file_path, wait=True)
            source_id = getattr(result, 'id', None) if result else None
            logger.info(f"Uploaded source to notebook {notebook_id}: {file_path} → {source_id}")
            return source_id

    async def delete_source(self, notebook_id: str, source_id: str):
        """Delete a source from a notebook."""
        client = await self._get_client()
        async with client:
            await client.sources.delete(notebook_id, source_id)
            logger.info(f"Deleted source {source_id} from notebook {notebook_id}")

    async def chat_ask(self, notebook_id: str, question: str) -> str:
        """
        Send a question to a notebook's chat and return the answer text.
        """
        client = await self._get_client()
        async with client:
            result = await client.chat.ask(notebook_id, question)
            answer = result.answer
            
            # Remove NotebookLM citations like [1], [1, 2], [15, 16]
            answer = re.sub(r'\s*\[\d+(?:[,\s\-]+\d+)*\]', '', answer)
            
            logger.info(f"Chat response from notebook {notebook_id}: {len(answer)} chars")
            return answer

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON string from text that may contain markdown or other wrapping."""
        text_stripped = text.strip()
        if text_stripped.startswith("{"):
            return text_stripped

        patterns = [
            r'```json\s*\n(.*?)\n\s*```',
            r'```\s*\n(.*?)\n\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                candidate = match.group(1).strip()
                if candidate.startswith("{"):
                    return candidate

        match = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return None


# Singleton service instance
notebooklm_service = NotebookLMService()
