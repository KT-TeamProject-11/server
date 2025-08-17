# -*- coding: utf-8 -*-
from __future__ import annotations
import html
from typing import Dict, List, Tuple

try:
    from app.config import STATIC_URL_PREFIX, CENTER_IMG_SUBDIR, PUBLIC_BASE_URL
except Exception:
    STATIC_URL_PREFIX, CENTER_IMG_SUBDIR, PUBLIC_BASE_URL = "/static", "", ""

# business의 Data URI 우선 로더 재사용
try:
    from app.rag.sections.business import _img_src
except Exception:
    def _img_src(filename: str, prefer_data_uri: bool = True) -> str:
        base = (STATIC_URL_PREFIX or "/static").rstrip("/")
        sub  = ("/" + CENTER_IMG_SUBDIR.strip("/")) if CENTER_IMG_SUBDIR else ""
        prefix = (PUBLIC_BASE_URL.rstrip("/") + base) if PUBLIC_BASE_URL else base
        return f"{prefix}{sub}/{filename}"

CENTER_MAPS: Dict[str, Dict] = {
    "cheonan": {
        "title": "천안시 도시재생지원센터 오시는 길",
        "img": _img_src("center-cheonan.png", prefer_data_uri=True),
        "aliases": ["천안시 도시재생지원센터","천안시도시재생지원센터","본센터","센터 본원","두드림센터"],
        "address": "충남 천안시 동남구 은행길 15, 두드림센터 5층",
        "tel": "041-417-4062",
        "fax": "041-417-4069",
        "email": "",
        "link": "https://www.cheonanurc.or.kr/79",
    },
    "bongmyeong": {
        "title": "봉명지구 도시재생현장지원센터 오시는 길",
        "img": _img_src("center-bongmyeong.png", prefer_data_uri=True),
        "aliases": ["봉명지구","봉명 현장지원센터","봉명센터","봉명동","봉정로"],
        "address": "충남 천안시 동남구 봉정로 39, 봉명동 행정복지센터 3층",
        "tel": "041-577-3992",
        "fax": "041-577-3992",
        "email": "tongdol2020@naver.com",
        "link": "https://www.cheonanurc.or.kr/118",
    },
    "oryong": {
        "title": "오룡지구 도시재생현장지원센터 오시는 길",
        "img": _img_src("center-oryong.png", prefer_data_uri=True),
        "aliases": ["오룡지구","오룡 현장지원센터","오룡센터","신부동"],
        "address": "충남 천안시 동남구 신부7길 14, 1층",
        "tel": "041-566-4526",
        "fax": "",
        "email": "khkang0724@kongju.ac.kr",
        "link": "https://www.cheonanurc.or.kr/119",
    },
}

def _li_if(label: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    return f"<li><strong>{html.escape(label)}</strong>: {html.escape(v)}</li>"

def _guess_center_keys(q: str) -> List[str]:
    q = (q or "").lower()
    hits: List[Tuple[str, int]] = []
    for k, meta in CENTER_MAPS.items():
        score = 0
        for alias in meta["aliases"]:
            if alias.lower() in q:
                score += 2
        if k in q:
            score += 1
        if score > 0:
            hits.append((k, score))
    hits.sort(key=lambda x: x[1], reverse=True)
    return [k for k, _ in hits] if hits else list(CENTER_MAPS.keys())

def find_map_images(query: str) -> List[Dict]:
    keys = _guess_center_keys(query)
    return [CENTER_MAPS[k] for k in keys if k in CENTER_MAPS]

def render_map_html(items: List[Dict]) -> str:
    if not items:
        return ""
    blocks = []
    for m in items:
        head = f"<h3>{html.escape(m['title'])}</h3>"
        img  = (
            f'<div style="margin:8px 0 6px">'
            f'<img src="{m["img"]}" alt="{html.escape(m["title"])}" '
            f'style="max-width:100%;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.08);display:block;">'
            f"</div>"
        )
        lis = "".join([
            _li_if("주소",  m.get("address", "")),
            _li_if("Tel",  m.get("tel", "")),
            _li_if("Fax",  m.get("fax", "")),
            _li_if("이메일", m.get("email", "")),
        ])
        ul = f"<ul>{lis}</ul>" if lis else ""
        blocks.append(head + img + ul)
    return "<div>" + "<hr>".join(blocks) + "</div>"
