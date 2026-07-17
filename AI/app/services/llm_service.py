"""
STTNB LLM Service — OpenAI-compatible client for vLLM / Ollama.

Connects to a self-hosted LLM via the OpenAI API format.
Used for template analysis and content generation that doesn't require RAG.
"""

import json
import logging
import re
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Async client for vLLM / OpenAI-compatible inference servers."""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy-init the AsyncOpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=settings.vllm_base_url,
                api_key=settings.vllm_api_key,
                timeout=600.0,  # 10 phút — tài liệu lớn cần thời gian xử lý
            )
            logger.info(f"LLM client initialized: {settings.vllm_base_url} / {settings.vllm_model_name}")
        return self._client

    async def chat(self, system_prompt: str, user_prompt: str,
                   temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """
        Send a chat completion request and return the assistant's response.
        """
        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=settings.vllm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "unknown"
            logger.info(f"LLM response: {len(content)} chars (finish_reason={finish_reason})")
            if finish_reason == "length":
                logger.warning(f"LLM response TRUNCATED (max_tokens={max_tokens})")
            return content

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    async def chat_json(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.1, max_tokens: int = 4096) -> dict:
        """
        Send a chat request expecting JSON output. Parses and returns the dict.
        """
        raw = await self.chat(system_prompt, user_prompt, temperature, max_tokens)
        return self._extract_json(raw)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON object from text that may contain markdown wrapping,
        <think> tags (Qwen3/reasoning models), or truncated responses."""
        if not text:
            logger.warning("Could not extract JSON from LLM response (0 chars)")
            return {}

        text = text.strip()

        # Strip <think>...</think> blocks (Qwen3 / reasoning model output)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # Remove markdown code fences (anywhere in text)
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Try direct parse
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text, strict=False)
            except json.JSONDecodeError as e:
                logger.debug(f"Direct parse failed: {e}")
                # Try to repair truncated JSON
                repaired = self._repair_truncated_json(text)
                if repaired is not None:
                    logger.info("Recovered JSON from truncated LLM response")
                    return repaired

        # Find the outermost balanced JSON object using brace matching
        result = self._find_balanced_json(text)
        if result is not None:
            return result

        logger.warning(
            f"Could not extract JSON from LLM response ({len(text)} chars) "
            f"head={text[:100]!r} tail={text[-100:]!r}"
        )
        return {}

    @staticmethod
    def _repair_truncated_json(text: str) -> dict | None:
        """Attempt to repair truncated JSON by closing unclosed brackets/braces."""
        # Count open vs close braces/brackets (outside strings)
        in_string = False
        escape = False
        stack = []

        for c in text:
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c in ('{', '['):
                stack.append(c)
            elif c == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif c == ']' and stack and stack[-1] == '[':
                stack.pop()

        if not stack:
            return None  # Already balanced, can't repair

        # Close any unclosed string (remove trailing partial string)
        if in_string:
            # Find last complete string and truncate there
            last_quote = text.rfind('"', 0, len(text) - 1)
            if last_quote > 0:
                text = text[:last_quote + 1]

        # Remove any trailing comma or incomplete key-value
        text = re.sub(r',\s*$', '', text)
        text = re.sub(r',\s*"[^"]*"\s*:\s*$', '', text)  # trailing "key":
        text = re.sub(r',\s*"[^"]*$', '', text)  # trailing partial "key
        text = re.sub(r',\s*$', '', text)  # trailing comma again after cleanup

        # Close unclosed brackets/braces in reverse order
        for opener in reversed(stack):
            if opener == '{':
                text += '}'
            elif opener == '[':
                text += ']'

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _find_balanced_json(text: str) -> dict | None:
        """Find and parse the first balanced JSON object in text."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate, strict=False)
                    except json.JSONDecodeError:
                        # Try finding next JSON object
                        next_start = text.find("{", i + 1)
                        if next_start != -1:
                            start = next_start
                            depth = 0
                        else:
                            return None
        return None

    async def health_check(self) -> bool:
        """Check if the LLM server is reachable."""
        try:
            client = self._get_client()
            models = await client.models.list()
            logger.info(f"LLM health OK — {len(models.data)} models available")
            return True
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False


# Singleton
llm_service = LLMService()
