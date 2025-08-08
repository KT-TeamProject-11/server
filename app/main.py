from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router 

app = FastAPI(title="Cheonan URC Chatbot")

origins = [
    "http://localhost",
    "http://localhost:8666",
    "http://127.0.0.1:8666",  # ✅ 프론트 포트 허용
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}
