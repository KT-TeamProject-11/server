# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import mimetypes, os, re, unicodedata
from urllib.parse import unquote

from app.api.tts import router as tts_router
from app.api.routes import router as api_router   

from app.config import (
    STATIC_URL_PREFIX, STATIC_DIR,
    CORS_ORIGINS,
)

app = FastAPI(title="Cheonan URC Chatbot")
app.include_router(tts_router)
app.include_router(api_router)

# CORS (환경변수에서 로드)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일
STATIC_PREFIX = (STATIC_URL_PREFIX or "/static").rstrip("/")
app.mount(STATIC_PREFIX, StaticFiles(directory=STATIC_DIR), name="static")

# 이미지 프록시
@app.get("/img")
def serve_image(name: str):
    base = Path(STATIC_DIR)
    if not base.exists():
        raise HTTPException(status_code=404, detail="static dir not found")

    nfc = unicodedata.normalize("NFC", unquote(name))
    p = base / nfc
    if p.exists():
        mt = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return FileResponse(str(p), media_type=mt)

    target_norm = re.sub(r"\s+", "", nfc).lower()
    with os.scandir(base) as it:
        for e in it:
            en = unicodedata.normalize("NFC", e.name)
            if re.sub(r"\s+", "", en).lower() == target_norm:
                q = base / e.name
                mt = mimetypes.guess_type(q.name)[0] or "application/octet-stream"
                return FileResponse(str(q), media_type=mt)

    raise HTTPException(status_code=404, detail="image not found")

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}
