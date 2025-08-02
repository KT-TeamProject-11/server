from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router

app = FastAPI(title="Cheonan URC Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         
    allow_credentials=True,
    allow_methods=["*"],         
    allow_headers=["*"],          
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}
