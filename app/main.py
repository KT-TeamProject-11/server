# -*- coding: utf-8 -*-
from __future__ import annotations

import mimetypes, os, re, unicodedata
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import STATIC_URL_PREFIX, STATIC_DIR

app = FastAPI(title="Cheonan URC Chatbot")

# CORS
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8666",
    "http://127.0.0.1:8666",
    "http://localhost:8667",
    "http://222.116.135.71:8666",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 서빙(/static → app/static)
STATIC_PREFIX = (STATIC_URL_PREFIX or "/static").rstrip("/")
app.mount(STATIC_PREFIX, StaticFiles(directory=STATIC_DIR), name="static")

# ✅ 실제 API 라우터 붙이기 (경로는 /chat, /ask)
try:
    from .api.routes import router as api_router
    app.include_router(api_router)
except Exception as e:
    import traceback
    print("\n[ERROR] failed to import .api.routes\n")
    traceback.print_exc()

# ✅ 이미지 프록시 (/img?name=파일명) — 한글/NFD/NFC/공백 대응
@app.get("/img")
def serve_image(name: str = Query(..., description="파일명(확장자 포함)")):
    base = Path(STATIC_DIR)
    if not base.exists():
        raise HTTPException(status_code=404, detail="static dir not found")

    nfc = unicodedata.normalize("NFC", unquote(name))
    p = base / nfc
    if p.exists():
        mt = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return FileResponse(str(p), media_type=mt)

    target_norm = re.sub(r"\s+", "", nfc).lower()
    try:
        with os.scandir(base) as it:
            for e in it:
                en = unicodedata.normalize("NFC", e.name)
                if re.sub(r"\s+", "", en).lower() == target_norm:
                    q = base / e.name
                    mt = mimetypes.guess_type(q.name)[0] or "application/octet-stream"
                    return FileResponse(str(q), media_type=mt)
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="image not found")

@app.get("/")
async def root():
    return {"msg": "연결 완료 ✅"}
