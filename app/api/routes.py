# -*- coding: utf-8 -*-
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from ..rag.chatbot import ask_async

router = APIRouter() 

class AskBody(BaseModel):
    message: str
    session_id: Optional[str] = None

async def _stream_answer(msg: str) -> StreamingResponse:
    async def gen() -> AsyncGenerator[bytes, None]:
        yield msg.encode("utf-8")
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

@router.post("/chat")
async def chat(body: AskBody):
    ans = await ask_async(body.message, body.session_id)
    return await _stream_answer(ans)

@router.post("/ask")
async def ask(body: AskBody):
    ans = await ask_async(body.message, body.session_id)
    return await _stream_answer(ans)

@router.get("/ping")
async def ping():
    return {"ok": True}
