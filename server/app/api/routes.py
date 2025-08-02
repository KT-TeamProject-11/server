from fastapi import APIRouter
from pydantic import BaseModel
from ..rag.chatbot import ask      

router = APIRouter()

class Query(BaseModel):
    message: str

@router.post("/chat")
async def chat(query: Query):
    return {"answer": ask(query.message)}

