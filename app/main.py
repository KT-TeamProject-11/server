# app/main.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import STATIC_URL_PREFIX, STATIC_DIR

# 기존 라우터(이미 프로젝트에 있으므로 그대로 사용)
try:
    from .api.routes import router
except Exception:
    router = None

app = FastAPI(title="Cheonan URC Chatbot")

origins = ["http://localhost", "http://127.0.0.1", "http://localhost:8666", "http://localhost:8666/",  "http://localhost:8667", "http://127.0.0.1:8666", "http://222.116.135.71:8666", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# 정적
app.mount(STATIC_URL_PREFIX, StaticFiles(directory=STATIC_DIR), name="static")

# ✨ 구상도 프록시: /static-biz/{slug}
@app.get("/static-biz/{slug}")
async def static_biz(slug: str):
    fname = BIZ_IMAGE_MAP.get(slug)
    if not fname:
        raise HTTPException(status_code=404, detail="unknown image key")
    path = Path(STATIC_DIR) / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(str(path))

app.include_router(router)

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}