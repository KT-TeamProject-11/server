# api/routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from ..rag.chatbot import ask_async
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

class Query(BaseModel):
    message: str

def chunk_text(text: str, size: int = 80):
    for i in range(0, len(text), size):
        yield text[i:i+size]

@router.post("/chat")
async def chat(query: Query):
    # 모델에서 최종 답을 받아온 뒤 청크 단위로 흘려보냄
    answer = await ask_async(query.message)

    async def stream():
        # 공백 기준 토큰이 더 자연스러우면 위의 chunk_text 대신 아래 사용:
        # for token in re.findall(r"\S+\s*", answer):
        #     yield token
        #     await asyncio.sleep(0.01)
        for chunk in chunk_text(answer, size=80):
            yield chunk
            await asyncio.sleep(0.01)

    return StreamingResponse(
        stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
