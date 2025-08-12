# api/routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from ..rag.chatbot import ask_async
from fastapi.responses import StreamingResponse
import asyncio
import re 

router = APIRouter()

class Query(BaseModel):
    message: str

def chunk_text(text: str):
    pattern = r'https?://\S+|\S+\s*'
    for m in re.finditer(pattern, text):
        yield m.group(0)

@router.post("/chat")
async def chat(query: Query):
    # 모델에서 최종 답을 받아온 뒤 청크 단위로 흘려보냄
    answer = await ask_async(query.message)

    async def stream():
        for chunk in chunk_text(answer):
            yield chunk
            await asyncio.sleep(0.005)

    return StreamingResponse(
        stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

