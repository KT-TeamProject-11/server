# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
import edge_tts

# /api/tts/* 경로로 붙이기
router = APIRouter(prefix="/api/tts", tags=["tts"])

# 고정 음성/속도/볼륨(환경변수로 바꾸고 싶으면 아래 기본값만 바꿔도 됨)
VOICE  = os.getenv("TTS_VOICE",  "ko-KR-SunHiNeural")
RATE   = os.getenv("TTS_RATE",   "-4%")
VOLUME = os.getenv("TTS_VOLUME", "+0%")

async def _audio_gen(text: str, voice: Optional[str] = None) -> AsyncGenerator[bytes, None]:
    t = (text or "").strip()
    if not t:
        raise HTTPException(status_code=400, detail="text is empty")

    v = (voice or VOICE).strip()
    # edge-tts는 비동기 스트리밍으로 MP3 바이트를 줍니다.
    communicate = edge_tts.Communicate(t, v, rate=RATE, volume=VOLUME)

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]

@router.post("/speak")
async def speak_post(payload: dict = Body(...)):
    text = (payload or {}).get("text", "")
    voice = (payload or {}).get("voice", None)  # 고정 쓰면 프론트에서 안 보냄
    return StreamingResponse(_audio_gen(text, voice), media_type="audio/mpeg")

@router.get("/speak")
async def speak_get(
    text: str = Query(..., max_length=4000),
    voice: Optional[str] = Query(None)
):
    return StreamingResponse(_audio_gen(text, voice), media_type="audio/mpeg")

@router.get("/ping")
async def ping():
    return {"ok": True, "voice": VOICE, "rate": RATE, "volume": VOLUME}
