# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Dict, List, Tuple

# 정적 경로: 무조건 /static 사용 (config 있으면 따라가고, 없으면 /static 유지)
try:
    from app.config import STATIC_URL_PREFIX, PUBLIC_BASE_URL
except Exception:
    STATIC_URL_PREFIX, PUBLIC_BASE_URL = "/static", ""

def _img_url(filename: str) -> str:
    base = (STATIC_URL_PREFIX or "/static").rstrip("/")
    prefix = (PUBLIC_BASE_URL.rstrip("/") + base) if PUBLIC_BASE_URL else base
    return f"{prefix}/{filename}"

# 질문에 필드가 언급되면 강조
FIELD_HINTS = {
    "type":   re.compile(r"(유형|타입|종류)", re.IGNORECASE),
    "area":   re.compile(r"(사업\s*지[역구]|어디|위치)", re.IGNORECASE),
    "period": re.compile(r"(기간|언제|연도|년도)", re.IGNORECASE),
    "budget": re.compile(r"(사업비|예산|총\s*사업비|돈|비용)", re.IGNORECASE),
    "goals":  re.compile(r"(목표|지향|비전)", re.IGNORECASE),
    "main":   re.compile(r"(주요\s*사업|무엇을|무슨\s*사업|내용)", re.IGNORECASE),
}
def want_fields(q: str) -> List[str]:
    out: List[str] = []
    for k, pat in FIELD_HINTS.items():
        if pat.search(q or ""):
            out.append(k)
    return out

# 사업 데이터 (이미지는 전부 /static)
BUSINESS: Dict[str, Dict] = {
    "overview": {
        "title": "천안시 도시재생사업 총괄도",
        "img": _img_url("천안시 도시재생사업 총괄도.jpg"),
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
        "img": _img_url("천안역세권 도시재생사업.jpg"),
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
        "img": _img_url("천안역세권 혁신지구 도시재생사업.jpg"),
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
        "img": _img_url("남산지구 도시재생 뉴딜사업.jpg"),
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
        "img": _img_url("봉명지구 도시재생뉴딜사업.jpg"),
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
        "img": _img_url("오룡지구 민-관 협력형 도시재생 리츠사업.jpg"),
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
        "img": _img_url("오룡지구도시재생사업.jpg"),
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
        "img": _img_url("원성2지구 뉴-빌리지사업.jpg"),
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

def find_business_items(q: str) -> List[Dict]:
    keys = _guess_keys(q)
    return [BUSINESS[k] for k in keys if k in BUSINESS]
