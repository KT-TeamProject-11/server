# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.routes import router
from .config import STATIC_URL_PREFIX, STATIC_DIR

app = FastAPI(title="Cheonan URC Chatbot")

origins = ["http://localhost", "http://localhost:8666", "http://127.0.0.1:8666"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


app.mount(STATIC_URL_PREFIX, StaticFiles(directory=STATIC_DIR), name="static")
app.mount(STATIC_URL_PREFIX, StaticFiles(directory=STATIC_DIR), name="assets")

app.include_router(router)

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}
