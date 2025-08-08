from fastapi import APIRouter
from pydantic import BaseModel
from ..rag.chatbot import ask_async
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter() 

class Query(BaseModel):
    message: str

@router.post("/chat")
async def chat(query: Query):
    answer = await ask_async(query.message)

    async def char_stream():
        for ch in answer:
            yield ch
            await asyncio.sleep(0.06)

    return StreamingResponse(
        char_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
