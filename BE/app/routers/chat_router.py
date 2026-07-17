"""
STTNB Chat Router — Chat Q&A with SSE simulated streaming.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.auth import get_current_user, can_access_repo
from app.models import ChatRequest, ChatMessage, ChatHistoryResponse
from app.services.chat_service import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories/{repo_id}/chat", tags=["Chat"])


@router.post("")
async def chat(
    repo_id: str,
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Chat hỏi đáp với dữ liệu trong kho.
    
    Gửi câu hỏi lên hệ thống AI và nhận phản hồi dạng Server-Sent Events (streaming).
    
    **SSE format:**
    ```
    data: {"type": "chunk", "content": "Theo tài liệu "}
    data: {"type": "chunk", "content": "trong kho, "}
    data: {"type": "done", "content": ""}
    ```
    """
    # Verify access (owner or shared)
    repo = await can_access_repo(repo_id, current_user)

    # Get full answer from AI engine
    try:
        full_answer = await chat_service.ask_question(
            repo_id=repo_id,
            user_id=current_user["id"],
            notebook_id=repo.get("notebook_id", ""),
            question=req.message,
            current_user=current_user,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi xử lý câu hỏi. Vui lòng thử lại sau.",
        )

    # Return SSE stream
    return EventSourceResponse(
        chat_service.stream_response(full_answer),
        media_type="text/event-stream",
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    repo_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Xem lịch sử chat trong kho dữ liệu."""
    await can_access_repo(repo_id, current_user)

    messages = await chat_service.get_history(repo_id, current_user["id"])
    return ChatHistoryResponse(
        repository_id=repo_id,
        messages=[
            ChatMessage(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
            )
            for m in messages
        ],
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    repo_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Xóa toàn bộ lịch sử chat trong kho dữ liệu."""
    await can_access_repo(repo_id, current_user)

    await chat_service.clear_history(repo_id, current_user["id"])
