"""Chat domain service. AI execution is delegated to the internal AI service."""

import asyncio
import re
from typing import AsyncGenerator

from app import database as db
from app.auth import is_user_self_hosted
from app.config import settings
from app.services.ai_client import ai_client

STREAM_DELAY_MS = 35


class ChatService:
    async def ask_question(
        self, repo_id: str, user_id: str, notebook_id: str, question: str, current_user: dict = None
    ) -> str:
        await db.add_chat_message(repo_id, user_id, "user", question)
        engine = "self_hosted" if (
            is_user_self_hosted(current_user) if current_user else settings.is_self_hosted
        ) else "notebooklm"
        try:
            if engine == "self_hosted":
                data = await ai_client.request(
                    "/internal/chat/self-hosted",
                    repo_id=repo_id,
                    user_id=user_id,
                    engine=engine,
                    input_data={
                        "question": question,
                        "documents": await ai_client.documents(repo_id),
                    },
                    kind="chat",
                )
            else:
                data = await ai_client.request(
                    "/internal/notebook/chat",
                    repo_id=repo_id,
                    user_id=user_id,
                    engine=engine,
                    input_data={
                        "notebook_id": notebook_id,
                        "question": f"{question}\n\n(Hãy trả lời dạng văn xuôi, không dùng bảng)",
                    },
                    kind="chat",
                )
            answer = re.sub(r"<br\s*/?>", "\n", data["answer"], flags=re.IGNORECASE)
        except Exception:
            await db.add_chat_message(
                repo_id, user_id, "assistant", "Lỗi hệ thống khi xử lý câu hỏi. Vui lòng thử lại sau."
            )
            raise
        await db.add_chat_message(repo_id, user_id, "assistant", answer)
        return answer

    async def stream_response(self, full_response: str) -> AsyncGenerator[str, None]:
        tokens = re.findall(r"\S+\s*", full_response)
        if not tokens:
            yield f'{{"type": "chunk", "content": "{full_response}"}}'
        for token in tokens:
            escaped = token.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
            yield f'{{"type": "chunk", "content": "{escaped}"}}'
            await asyncio.sleep(STREAM_DELAY_MS / 1000)
        yield '{"type": "done", "content": ""}'

    async def get_history(self, repo_id: str, user_id: str, limit: int = 50):
        return await db.get_chat_history(repo_id, user_id, limit)

    async def clear_history(self, repo_id: str, user_id: str):
        await db.delete_chat_history(repo_id, user_id)


chat_service = ChatService()
