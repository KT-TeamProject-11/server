# -*- coding: utf-8 -*-
from __future__ import annotations

import base64, html, mimetypes, os, re, unicodedata
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from app.config import STATIC_URL_PREFIX, PUBLIC_BASE_URL, CENTER_IMG_SUBDIR, STATIC_DIR

# ─────────────────────────────────────────────────────────
# 파일/이미지 유틸
def _static_dir() -> Path:
    """
    정적 이미지 디렉터리 탐색 (우선순위)
    1) app.config.STATIC_DIR [+ CENTER_IMG_SUBDIR]
    2) app/rag/static   (이 모듈 기준)
    3) app/static       (프로젝트 루트 기준)
    """
    candidates: List[Path] = []
    try:
        d = Path(STATIC_DIR)
        if CENTER_IMG_SUBDIR:
            d = d / CENTER_IMG_SUBDIR.strip("/")
        candidates.append(d)
    except Exception:
        pass

    here = Path(__file__).resolve()
    candidates.append(here.parent.parent / "static")   # app/rag/static
    candidates.append(here.parents[2] / "static")      # app/static

    for d in candidates:
        if d.exists():
            return d
    return candidates[0] if candidates else Path("static")

def _find_file_path(filename: str) -> Optional[str]:
    """맥OS 한글(NFD/NFC) 문제를 우회: 정규화/대소문자 무시/공백무시 매칭."""
    base = _static_dir()
    target = unicodedata.normalize("NFC", filename)
    p = base / target
    if p.exists():
        return str(p)

    if not base.exists():
        return None

    norm = re.sub(r"\s+", "", target).lower()
    with os.scandir(base) as it:
        for e in it:
            name = unicodedata.normalize("NFC", e.name)
            if re.sub(r"\s+", "", name).lower() == norm:
                return str(Path(base) / e.name)
    return None

def _to_data_uri(filepath: str) -> str:
    mime = mimetypes.guess_type(filepath)[0] or "image/jpeg"
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def _img_src(filename: str, prefer_data_uri: bool = True) -> str:
    if prefer_data_uri:
        fp = _find_file_path(filename)
        if fp and os.path.exists(fp):
            try:
                return _to_data_uri(fp)
            except Exception:
                pass
    base = (STATIC_URL_PREFIX or "/static").rstrip("/")
    sub  = ("/" + CENTER_IMG_SUBDIR.strip("/")) if CENTER_IMG_SUBDIR else ""
    prefix = (PUBLIC_BASE_URL.rstrip("/") + base) if PUBLIC_BASE_URL else base
    return f"{prefix}{sub}/{filename}"

def _img_tag(filename: str, alt: str) -> str:
    src = _img_src(filename, prefer_data_uri=True)
    return (f"<img src='{src}' alt='{html.escape(alt)}' "
            "style='max-width:100%;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);display:block;'>")

# ─────────────────────────────────────────────────────────
# 질의 의도: 사업 전체/단답/구상도
FIELD_HINTS = {
    "name":   re.compile(r"(사업\s*명|사업명|명칭|이름)", re.IGNORECASE),
    "type":   re.compile(r"(유형|타입|종류)", re.IGNORECASE),
    "area":   re.compile(r"(사업\s*지[역구]|어디|위치|대상지)", re.IGNORECASE),
    "period": re.compile(r"(기간|연도|년도|언제부터|언제까지)", re.IGNORECASE),
    "budget": re.compile(r"(사업비|예산|총\s*사업비|비용|돈)", re.IGNORECASE),
    "goals":  re.compile(r"(목표|지향|비전)", re.IGNORECASE),
    "main":   re.compile(r"(주요\s*사업|세부\s*사업|내용|무슨\s*사업)", re.IGNORECASE),
    "plan":   re.compile(r"(구상도|총괄도|마스터\s*플[랜]|계획도|조감도|그림|이미지|사진)", re.IGNORECASE),
}

def _want_fields(q: str) -> List[str]:
    out: List[str] = []
    for k, pat in FIELD_HINTS.items():
        if pat.search(q or ""):
            out.append(k)
    return out

# ─────────────────────────────────────────────────────────
# 사업 데이터 — 이미지 필드는 "파일명"만 보관(확장자 포함)
BUSINESS: Dict[str, Dict] = {
    "overview": {
        "title": "천안시 도시재생사업 총괄도",
        "name":  "천안시 도시재생사업 총괄도",
        "img": "천안시 도시재생사업 총괄도.jpg",
        "aliases": ["총괄도","종합구상도","한눈에","전체","모두","지도","계획","사업 전체"],
        "type": "-",
        "area": "천안시 전역(표시 구역 참조)",
        "period": "-",
        "budget": "-",
        "goals": [],
        "main": [],
        "link": None,
    },
    "cheonan-station": {
        "title": "천안역세권 도시재생사업",
        "name":  "천안역세권 도시재생사업",
        "img": "천안역세권 도시재생사업.jpg",
        "aliases": ["천안역세권","역세권","스테이션 캠퍼스","캠퍼스타운","중심시가지형"],
        "type": "중심시가지형",
        "area": "천안시 서북구 와촌동 106-17 일원",
        "period": "2018 ~ 2025",
        "budget": "438억 (국비 180, 도비 36, 시비 142, 기타 80)",
        "goals": ["청년활력 키움공간", "스마트산업 거점공간", "교통결절 중심공간", "살기 좋은 도시공간"],
        "main": ["도시재생 어울림센터", "공영주차장", "캠퍼스타운", "스마트 친수공원", "복합문화센터", "집수리 지원"],
        "link": None,
    },
    "cheonan-innovation": {
        "title": "천안역세권 혁신지구 도시재생사업",
        "name":  "천안역세권 혁신지구 도시재생사업",
        "img": "천안역세권 혁신지구 도시재생사업.jpg",
        "aliases": ["혁신지구","역세권 혁신지구","혁신","혁신재생"],
        "type": "혁신지구 재생사업",
        "area": "천안시 서북구 와촌동 106-68 일원",
        "period": "2020 ~ 2027",
        "budget": "2,271억 (국비 206, 도비 41, 시비 96, 기타 1,928)",
        "goals": ["주거·상업·산업 복합 지역거점 조성", "파급효과를 통한 도시재생 촉진"],
        "main": ["복합환승센터(교통·환승주차장·상업·생활SOC)", "주상복합(공동주택·상업)", "지식산업센터(업무·상업)", "지구대 등 공공시설"],
        "link": None,
    },
    "namsan": {
        "title": "남산지구 도시재생 뉴딜사업",
        "name":  "남산지구 도시재생 뉴딜사업",
        "img": "남산지구 도시재생 뉴딜사업.jpg",
        "aliases": ["남산지구","사직동","고령친화"],
        "type": "일반근린형",
        "area": "천안시 동남구 사직동 284-3 번지 일원",
        "period": "2018 ~ 2025",
        "budget": "225억 (국비 130, 도비 26, 시비 69)",
        "goals": ["원도심 매력 공간 창출", "노후주거지 정비 및 공공서비스 기반 구축", "주민역량 강화·공동체 회복"],
        "main": ["지역사 박물관 및 커뮤니티 거점", "녹지축 공원", "어르신 복지문화센터", "집수리 지원"],
        "link": None,
    },
    "bongmyeong": {
        "title": "봉명지구 도시재생뉴딜사업",
        "name":  "봉명지구 도시재생뉴딜사업",
        "img": "봉명지구 도시재생뉴딜사업.jpg",
        "aliases": ["봉명지구","통합돌봄마을","봉명"],
        "type": "일반근린형",
        "area": "천안시 동남구 봉명동 39-1 일원",
        "period": "2021 ~ 2025",
        "budget": "191억 (국비 100, 도비 20, 시비 47, 기타 24)",
        "goals": ["역세권 일원 쇠퇴 심화 대응", "도시재생 여건 조성", "실행계획 마련"],
        "main": ["통합돌봄 시스템", "거점·주거환경 개선", "철도테마 복합문화창업공간", "상권 활성화·자생경제"],
        "link": None,
    },
    "oryong-ritz": {
        "title": "오룡지구 민·관 협력형 도시재생 리츠사업",
        "name":  "오룡지구 민·관 협력형 도시재생 리츠사업",
        "img": "오룡지구 민-관 협력형 도시재생 리츠사업.jpg",
        "aliases": ["오룡 리츠","오룡경기장","민관협력형"],
        "type": "민관협력형 리츠사업",
        "area": "천안시 동남구 원성동 31-70 일원",
        "period": "2021 ~ 2028",
        "budget": "4,232억 (기타)",
        "goals": ["대규모 체육복합시설로 균형 있는 체육 인프라 구축", "도시재생 구현"],
        "main": ["체육·복지·문화시설", "아파트(687세대)", "근린생활·보육·작은도서관·경로당 등"],
        "link": None,
    },
    "oryong": {
        "title": "오룡지구 도시재생사업",
        "name":  "오룡지구 도시재생사업",
        "img": "오룡지구도시재생사업.png",
        "aliases": ["오룡지구","로코노미","골목 벤처밸리","원성동 31-25"],
        "type": "특화재생형",
        "area": "천안시 동남구 원성동 31-25 일원",
        "period": "2023 ~ 2028",
        "budget": "341억 (국비 180, 지방비 120, 자치지방비 16, 민간 25)",
        "goals": ["상권활성화·일자리 창출", "새로운 산업생태계로 활력 부여", "골목상권 경쟁력 강화"],
        "main": ["오룡 라이프 이노베이션 랩", "오룡 코리빙 하우스", "보행네트워크·특화거리", "빈 점포 채움"],
        "link": None,
    },
    "wonseong2": {
        "title": "원성2지구 뉴·빌리지사업",
        "name":  "원성2지구 뉴·빌리지사업",
        "img": "원성2지구 뉴-빌리지사업.png",
        "aliases": ["원성2지구","뉴빌리지","N분 생활권","원성2"],
        "type": "뉴·빌리지 사업",
        "area": "천안시 동남구 원성동 635 일원",
        "period": "2025 ~ 2029",
        "budget": "252억 (국비 150, 도비 30, 시비 70, 자체 2)",
        "goals": ["살고 싶은 정주환경", "안심 가능한 생활환경", "인구 유입 위한 주택정비 촉진"],
        "main": ["생활 문화 인프라", "생활가로 안전환경", "주택정비 활성화 지원"],
        "link": None,
    },
}

# ─────────────────────────────────────────────────────────
# 키 추정
def _score_hit(q: str, meta: Dict) -> int:
    ql = (q or "").lower()
    s = 0
    for a in meta.get("aliases", []):
        if a and a.lower() in ql:
            s += 3
    if meta["title"].lower() in ql:
        s += 5
    return s

def _guess_keys(q: str) -> List[str]:
    hits: List[Tuple[str, int]] = []
    for k, m in BUSINESS.items():
        sc = _score_hit(q, m)
        if sc > 0:
            hits.append((k, sc))
    if not hits:
        return ["overview"]
    hits.sort(key=lambda x: x[1], reverse=True)
    return [k for k, _ in hits]

# 외부에서 사용: 사업성 질의인지?
_BIZ_ANY_HINT = re.compile(r"(사업|구상도|총괄도|마스터\s*플[랜]|조감도|계획도)", re.IGNORECASE)
def is_business_query(q: str) -> bool:
    if not q:
        return False
    if _BIZ_ANY_HINT.search(q):
        return True
    ql = q.lower()
    for meta in BUSINESS.values():
        if any(a.lower() in ql for a in meta.get("aliases", [])):
            return True
    return False

# ─────────────────────────────────────────────────────────
# 렌더링
def answer_business(q: str) -> Optional[str]:
    keys = _guess_keys(q)
    items = [BUSINESS[k] for k in keys if k in BUSINESS]
    if not items:
        return None

    item = items[0]
    wants = _want_fields(q)

    # ① 단답(필드 지정)
    if wants:
        if len(wants) == 1 and wants[0] == "plan":
            title = f"{item.get('title','')} 구상도".strip()
            imgfile = item.get("img")
            if not imgfile:
                return "<b>구상도</b>: 없음"
            return "<div>" + \
                   f"<div style='font-weight:700;font-size:16px;margin:4px 0 8px'>{html.escape(title)}</div>" + \
                   _img_tag(imgfile, title) + \
                   "</div>"

        label_map = {"name":"사업명","type":"유형","area":"사업지역","period":"사업기간","budget":"사업비"}
        rows: List[str] = []
        for w in wants:
            if w in ("goals","main"):
                key_label = "사업목표" if w == "goals" else "주요사업"
                vals = item.get(w, []) or []
                rows.append(f"• <b>{key_label}</b>: {html.escape(', '.join(vals) or '-')}")
            elif w == "plan":
                imgfile = item.get("img")
                rows.append("<div style='margin-top:8px'><b>구상도</b></div>" + (_img_tag(imgfile, item.get('title','')) if imgfile else "없음"))
            else:
                rows.append(f"• <b>{label_map.get(w,w)}</b>: {html.escape(item.get(w,'-'))}")
        return "<div>" + "<br>".join(rows) + "</div>"

    # ② 전체 카드
    head = f"<div style='font-weight:700;font-size:18px;margin:4px 0 10px'>{html.escape(item['title'])}</div>"
    img_html = _img_tag(item["img"], item["title"]) if item.get("img") else ""
    rows = [
        f"• <b>사업명</b>: {html.escape(item.get('name','-'))}",
        f"• <b>유형</b>: {html.escape(item.get('type','-'))}",
        f"• <b>사업지역</b>: {html.escape(item.get('area','-'))}",
        f"• <b>사업기간</b>: {html.escape(item.get('period','-'))}",
        f"• <b>사업비</b>: {html.escape(item.get('budget','-'))}",
    ]
    if item.get("goals"):
        rows.append("<div style='margin-top:6px'><b>사업목표</b></div><ul>" +
                    "".join(f"<li>{html.escape(x)}</li>" for x in item["goals"]) + "</ul>")
    if item.get("main"):
        rows.append("<div style='margin-top:6px'><b>주요사업</b></div><ul>" +
                    "".join(f"<li>{html.escape(x)}</li>" for x in item["main"]) + "</ul>")

    return "<div>" + head + img_html + "<br>".join(rows) + "</div>"
