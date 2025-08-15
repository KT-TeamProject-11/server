# app/api/routes.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from ..rag.chatbot import ask_async

router = APIRouter()

class AskBody(BaseModel):
    message: str
    session_id: Optional[str] = None

async def _stream_answer(msg: str) -> StreamingResponse:
    async def gen():
        yield msg
    # 프론트가 HTML을 그대로 렌더하므로 text/plain/UTF-8로 충분
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

@router.post("/chat")
async def chat(body: AskBody):
    ans = await ask_async(body.message, body.session_id)
    return await _stream_answer(ans)

# 구버전 호환
@router.post("/ask")
async def ask(body: AskBody):
    ans = await ask_async(body.message, body.session_id)
    return await _stream_answer(ans)
