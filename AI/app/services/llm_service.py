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
    """Async client for vLLM / OpenAI-compatible inference servers.

    Hỗ trợ 1 model chính (vllm_*) + 1 model dự phòng (vllm_fallback_*, tùy
    chọn). Nếu model chính lỗi (timeout, 5xx, bị chặn...), tự động thử lại
    bằng model dự phòng trước khi báo lỗi.
    """

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._fallback_client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy-init the AsyncOpenAI client (model chính)."""
        if self._client is None:
            default_headers = (
                {"User-Agent": settings.vllm_user_agent}
                if settings.vllm_user_agent
                else None
            )
            self._client = AsyncOpenAI(
                base_url=settings.vllm_base_url,
                api_key=settings.vllm_api_key,
                # Fail-fast: hết timeout là bỏ ngay, KHÔNG retry (max_retries=0),
                # để rơi sang model dự phòng luôn thay vì retry nhiều lần chờ lâu.
                timeout=settings.vllm_primary_timeout,
                max_retries=0,
                default_headers=default_headers,
            )
            logger.info(f"LLM client initialized: {settings.vllm_base_url} / {settings.vllm_model_name}")
        return self._client

    def _get_fallback_client(self) -> Optional[AsyncOpenAI]:
        """Lazy-init the AsyncOpenAI client dự phòng, nếu có cấu hình."""
        if not (settings.vllm_fallback_base_url and settings.vllm_fallback_model_name):
            return None
        if self._fallback_client is None:
            self._fallback_client = AsyncOpenAI(
                base_url=settings.vllm_fallback_base_url,
                api_key=settings.vllm_fallback_api_key or settings.vllm_api_key,
                timeout=settings.vllm_fallback_timeout,
            )
            logger.info(
                f"LLM fallback client initialized: "
                f"{settings.vllm_fallback_base_url} / {settings.vllm_fallback_model_name}"
            )
        return self._fallback_client

    async def chat(self, system_prompt: str, user_prompt: str,
                   temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """
        Send a chat completion request and return the assistant's response.

        Thử model chính trước; nếu lỗi và có cấu hình model dự phòng, tự
        động thử lại bằng model dự phòng. Nếu phản hồi bị cắt vì hết token
        (finish_reason=length), tự nối tiếp (xem ``_chat_with_continuation``).
        """
        try:
            return await self._chat_with_continuation(
                self._get_client(), settings.vllm_model_name,
                system_prompt, user_prompt, temperature, max_tokens,
            )
        except Exception as e:
            fallback_client = self._get_fallback_client()
            if fallback_client is None:
                logger.error(f"LLM request failed (no fallback configured): {e}")
                raise
            logger.warning(f"LLM primary request failed, retrying with fallback: {e}")
            return await self._chat_with_continuation(
                fallback_client, settings.vllm_fallback_model_name,
                system_prompt, user_prompt, temperature, max_tokens,
            )

    async def _chat_with_continuation(
        self, client: AsyncOpenAI, model: str, system_prompt: str,
        user_prompt: str, temperature: float, max_tokens: int,
    ) -> str:
        """(B) Gọi model; nếu bị cắt vì hết token thì tự yêu cầu viết tiếp và nối
        lại, tối đa ``llm_max_continuations`` lần, để sinh được tài liệu dài."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content, finish = await self._chat_once(client, model, messages, temperature, max_tokens)
        full = content

        max_cont = settings.llm_max_continuations if settings.llm_auto_continue else 0
        attempts = 0
        while finish == "length" and attempts < max_cont:
            attempts += 1
            logger.info(f"LLM bị cắt vì hết token, nối tiếp lần {attempts}/{max_cont} (model={model})")
            cont_messages = messages + [
                {"role": "assistant", "content": full},
                {"role": "user", "content": (
                    "Phần trả lời trên bị cắt vì hết độ dài. Hãy VIẾT TIẾP NGAY tại chỗ "
                    "bị cắt, nối liền mạch, TUYỆT ĐỐI không lặp lại nội dung đã viết, "
                    "không mở đầu lại, không thêm lời dẫn."
                )},
            ]
            part, finish = await self._chat_once(
                client, model, cont_messages, temperature, max_tokens
            )
            if not part.strip():
                break
            full += part

        if finish == "length":
            logger.warning(
                f"LLM vẫn bị cắt sau {attempts} lần nối tiếp (model={model}, "
                f"max_tokens={max_tokens})"
            )
        return full

    @staticmethod
    async def _chat_once(client: AsyncOpenAI, model: str, messages: list[dict],
                         temperature: float, max_tokens: int) -> tuple[str, str]:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            # Tắt chế độ suy luận của model reasoning (Qwen3...) qua tham số
            # chuẩn của vLLM, thay vì dựa vào chuỗi "/no_think" rải rác trong
            # từng prompt. Nếu không tắt, model có thể dùng hết max_tokens cho
            # phần <think> và trả về content rỗng dù finish_reason=length.
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason or "unknown"
        logger.info(f"LLM response ({model}): {len(content)} chars (finish_reason={finish_reason})")
        return content, finish_reason

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
