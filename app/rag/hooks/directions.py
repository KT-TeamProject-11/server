# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Optional
from app.rag.sections.center_maps import find_map_images, render_map_html

# ✅ '주소'는 제외 — 주소 질의는 url.py가 먼저 처리
_ADDR_OR_MAP_TRIG = re.compile(
    r"(오시는?\s*길|오는\s*길|가는\s*길|찾아오[는기]|길\s*찾기|길찾기|지도|약도|위치|동선|how\s*to\s*get|방문법|어떻게\s*가|네비|내비|map|route)",
    re.IGNORECASE,
)

def answer_directions(q: str) -> Optional[str]:
    """오시는 길/지도 질문일 때만 지도 카드 반환. url.py는 여기서 사용하지 않음."""
    if not q or not _ADDR_OR_MAP_TRIG.search(q):
        return None
    items = find_map_images(q)
    html_out = render_map_html(items)
    return html_out or None
