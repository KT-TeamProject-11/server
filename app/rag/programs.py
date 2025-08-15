# app/rag/programs.py
from __future__ import annotations
from typing import Optional, List, Dict
from rapidfuzz import process, fuzz
import re

from app.rag.textnorm import normalize_query, make_alias_variants, no_space

# ────────────────────────────────────────────────────────────
# 프로그램 사전(네가 준 구조 유지, 별칭/태그만 보강)
_PROGRAMS: Dict[str, Dict] = {
    # 상위
    "도시재생지원센터 센터소개": {
        "url": "https://www.cheonanurc.or.kr/24",
        "aliases": ["센터소개", "센터 소개", "기관 소개", "도시재생지원센터 센터소개"],
        "tags": ["센터", "소개", "메인"]
    },
    "도시재생지원센터 사업소개": {
        "url": "https://www.cheonanurc.or.kr/68",
        "aliases": ["사업소개", "사업 소개", "프로젝트", "현황", "도시재생지원센터 사업소개"],
        "tags": ["사업", "소개", "현황"]
    },
    "도시재생지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/92",
        "aliases": ["커뮤니티", "센터커뮤니티", "커뮤", "커뮤니티 페이지"],
        "tags": ["커뮤니티", "소통", "게시판"]
    },
    "도시재생지원센터 도시재생+": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["도시재생+", "도시재생 플러스", "공지", "공지사항", "소식", "뉴스"],
        "tags": ["도시재생+", "공지", "뉴스", "소식"]
    },
    "도시재생지원센터 아카이브": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["아카이브", "자료실", "아카이브 페이지", "자료 모음"],
        "tags": ["아카이브", "자료실", "발간물"]
    },

    # 센터소개 하위
    "도시재생지원센터 센터소개 인사말": {
        "url": "https://www.cheonanurc.or.kr/24",
        "aliases": ["인사말", "인사", "센터소개 인사말"],
        "tags": ["센터소개", "인사말"]
    },
    "도시재생지원센터 센터소개 목표와 비전": {
        "url": "https://www.cheonanurc.or.kr/79",
        "aliases": ["목표와비전", "목표와 비전", "목표", "비전"],
        "tags": ["센터소개", "비전", "목표"]
    },
    "도시재생지원센터 센터소개 센터 연혁": {
        "url": "https://www.cheonanurc.or.kr/101",
        "aliases": ["센터연혁", "센터 연혁", "연혁"],
        "tags": ["센터소개", "연혁"]
    },
    "도시재생지원센터 센터소개 조직 및 담당": {
        "url": "https://www.cheonanurc.or.kr/25",
        "aliases": ["조직및담당", "조직 및 담당", "조직", "담당", "담당자"],
        "tags": ["센터소개", "조직", "담당"]
    },

    # 오시는 길
    "도시재생지원센터 천안시 도시재생지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/131",
        "aliases": ["오시는길", "센터오시는길", "센터 위치", "센터 주소", "센터 지도"],
        "tags": ["오시는길", "주소", "위치", "지도", "센터"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터 오시는 길": {
        "url": "https://www.cheonanurc.or.kr/133",
        "aliases": ["봉명 오시는길", "봉명지구 오시는 길", "봉명 위치", "봉명 지도"],
        "tags": ["오시는길", "주소", "위치", "지도", "봉명지구", "현장지원센터"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터 오시는길": {
        "url": "https://www.cheonanurc.or.kr/128",
        "aliases": ["오룡 오시는길", "오룡지구 오시는 길", "오룡 위치", "오룡 지도"],
        "tags": ["오시는길", "주소", "위치", "지도", "오룡지구", "현장지원센터"]
    },

    # 사업 소개
    "도시재생지원센터 천안 도시재생 총괄사업현황": {
        "url": "https://www.cheonanurc.or.kr/68",
        "aliases": ["총괄사업현황", "총괄사업", "사업 현황"],
        "tags": ["도시재생사업", "현황", "천안"]
    },
    "도시재생지원센터 천안 도시재생선도사업": {
        "url": "https://www.cheonanurc.or.kr/27",
        "aliases": ["도시재생선도사업", "선도사업"],
        "tags": ["도시재생사업", "선도사업", "천안"]
    },
    "도시재생지원센터 천안역세권 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/71",
        "aliases": ["역세권도시재생", "천안역세권"],
        "tags": ["도시재생사업", "역세권"]
    },
    "도시재생지원센터 남산지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/70",
        "aliases": ["남산지구도시재생사업", "남산지구"],
        "tags": ["도시재생사업", "남산지구"]
    },
    "도시재생지원센터 봉명지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/72",
        "aliases": ["봉명지구도시재생사업", "봉명지구"],
        "tags": ["도시재생사업", "봉명지구"]
    },
    "도시재생지원센터 오룡지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/74",
        "aliases": ["오룡지구도시재생사업", "오룡지구"],
        "tags": ["도시재생사업", "오룡지구"]
    },
    "도시재생지원센터 천안역세권 혁신지구 도시재생사업": {
        "url": "https://www.cheonanurc.or.kr/75",
        "aliases": ["역세권혁신지구", "혁신지구 도시재생"],
        "tags": ["도시재생사업", "혁신지구", "역세권"]
    },
    "도시재생지원센터 오룡지구 민·관 협력형 도시재생 리츠사업": {
        "url": "https://www.cheonanurc.or.kr/73",
        "aliases": ["오룡지구 리츠사업", "민관 협력형 리츠"],
        "tags": ["도시재생사업", "오룡지구", "리츠"]
    },
    "도시재생지원센터 원성2지구 뉴:빌리지사업": {
        "url": "https://www.cheonanurc.or.kr/140",
        "aliases": ["원성2지구 뉴빌리지", "뉴빌리지 사업"],
        "tags": ["도시재생사업", "원성2지구", "뉴빌리지"]
    },

    # 커뮤니티
    "도시재생지원센터 천안시 도시재생지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/92",
        "aliases": ["센터 커뮤니티", "커뮤니티 메인"],
        "tags": ["커뮤니티", "소통"]
    },
    "도시재생지원센터 봉명지구 도시재생현장지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/95",
        "aliases": ["봉명 커뮤니티", "봉명지구 커뮤니티"],
        "tags": ["커뮤니티", "봉명지구", "현장지원센터"]
    },
    "도시재생지원센터 오룡지구 도시재생현장지원센터 커뮤니티": {
        "url": "https://www.cheonanurc.or.kr/121",
        "aliases": ["오룡 커뮤니티", "오룡지구 커뮤니티"],
        "tags": ["커뮤니티", "오룡지구", "현장지원센터"]
    },

    # 도시재생+ (프로그램/투어)
    "도시재생지원센터 공지사항": {
        "url": "https://www.cheonanurc.or.kr/new",
        "aliases": ["공지사항", "공지", "센터 공지", "알림"],
        "tags": ["도시재생+", "공지", "소식"]
    },
    "도시재생지원센터 센터 프로그램 신청": {
        "url": "https://www.cheonanurc.or.kr/41",
        "aliases": ["프로그램 신청", "센터프로그램 신청", "수강 신청"],
        "tags": ["도시재생+", "프로그램", "신청"]
    },
    "도시재생지원센터 도시재생 투어": {
        "url": "https://www.cheonanurc.or.kr/64",
        "aliases": ["도시재생투어", "투어", "현장투어", "일반투어", "전문투어", "코스 안내", "투어신청"],
        "tags": ["도시재생+", "투어", "코스"]
    },

    # 투어 코스 상세
    "도시재생 투어 일반코스 1": {
        "url": "https://www.cheonanurc.or.kr/78",
        "aliases": ["일반코스1", "일반 코스 1", "투어 일반코스1"],
        "tags": ["일반코스", "코스", "투어"]
    },
    "도시재생 투어 일반코스 2": {
        "url": "https://www.cheonanurc.or.kr/97",
        "aliases": ["일반코스2", "일반 코스 2", "투어 일반코스2"],
        "tags": ["일반코스", "코스", "투어"]
    },
    "도시재생 투어 전문코스 1": {
        "url": "https://www.cheonanurc.or.kr/98",
        "aliases": ["전문코스1", "전문 코스 1", "투어 전문코스1"],
        "tags": ["전문코스", "코스", "투어"]
    },
    "도시재생 투어 전문코스 2": {
        "url": "https://www.cheonanurc.or.kr/99",
        "aliases": ["전문코스2", "전문 코스 2", "투어 전문코스2"],
        "tags": ["전문코스", "코스", "투어"]
    },
    "도시재생 투어 전문코스 3": {
        "url": "https://www.cheonanurc.or.kr/100",
        "aliases": ["전문코스3", "전문 코스 3", "투어 전문코스3"],
        "tags": ["전문코스", "코스", "투어"]
    },

    # 아카이브 하위
    "도시재생지원센터 발간물": {
        "url": "https://www.cheonanurc.or.kr/36",
        "aliases": ["발간물", "자료집", "센터 발간물"],
        "tags": ["아카이브", "발간물"]
    },
    "도시재생지원센터 홍보 동영상": {
        "url": "https://www.youtube.com/watch?v=ghzmqbIRJo0",
        "aliases": ["홍보동영상", "홍보 영상", "동영상 자료"],
        "tags": ["아카이브", "동영상"]
    },
    "도시재생지원센터 도시재생 뉴스": {
        "url": "https://www.cheonanurc.or.kr/35",
        "aliases": ["도시재생뉴스", "뉴스", "센터뉴스"],
        "tags": ["아카이브", "뉴스"]
    },
    "도시재생지원센터 전문가 오피니언": {
        "url": "https://www.cheonanurc.or.kr/37",
        "aliases": ["전문가오피니언", "오피니언", "전문가 칼럼"],
        "tags": ["아카이브", "오피니언", "칼럼"]
    },
    "도시재생지원센터 마을기자단 및 인터뷰": {
        "url": "https://www.cheonanurc.or.kr/108",
        "aliases": ["마을기자단", "인터뷰", "마을기자단 및 인터뷰"],
        "tags": ["아카이브", "인터뷰", "마을기자단"]
    },
}

# ────────────────────────────────────────────────────────────
# 인덱스 구성(띄어쓰기 무시 변형 포함)
_ALIAS_POOL: List[str] = []           # 정규화 별칭 풀
_ALIAS_NOSPACE_POOL: List[str] = []   # 공백 제거 별칭 풀
_ALIAS_TO_KEY: Dict[str, str] = {}    # 별칭 → 프로그램 키
_ALIASNS_TO_KEY: Dict[str, str] = {}  # 별칭(no-space) → 프로그램 키
_TAG_POOL: List[str] = []

def _build_index():
    for key, meta in _PROGRAMS.items():
        # 1) 정식 명칭도 별칭으로
        all_aliases = list(meta.get("aliases", [])) + [key]
        # 2) 각 별칭의 변형(소문자/공백제거 포함) 추가
        expanded: List[str] = []
        for a in all_aliases:
            expanded += make_alias_variants(a)
        # 3) 풀에 적재
        for a in expanded:
            n = normalize_query(a)
            ns = no_space(n)
            _ALIAS_POOL.append(n)
            _ALIAS_TO_KEY[n] = key
            _ALIAS_NOSPACE_POOL.append(ns)
            _ALIASNS_TO_KEY[ns] = key
        # 4) 태그
        for t in meta.get("tags", []) or []:
            nt = normalize_query(t)
            if nt not in _TAG_POOL:
                _TAG_POOL.append(nt)

_build_index()

# ────────────────────────────────────────────────────────────
# 공개 API

def get_all_aliases() -> List[str]:
    return list(_ALIAS_POOL)

def get_all_tags() -> List[str]:
    return list(_TAG_POOL)

def get_program_by_alias(alias: str) -> Optional[Dict]:
    """정규화된 별칭 또는 no-space 별칭으로도 찾기"""
    n = normalize_query(alias)
    ns = no_space(n)
    key = _ALIAS_TO_KEY.get(n) or _ALIASNS_TO_KEY.get(ns)
    if not key:
        return None
    item = dict(_PROGRAMS[key])
    item["name"] = key
    return item

def get_programs_by_tag(tag: str) -> List[Dict]:
    nt = normalize_query(tag)
    return [
        {**v, "name": name}
        for name, v in _PROGRAMS.items()
        if nt in (normalize_query(t) for t in v.get("tags", []) or [])
    ]

def fuzzy_find_best_alias(q: str, min_score: int = 78) -> Optional[str]:
    """띄어쓰기/철자에 강한 퍼지 매칭: 정규화 + no-space 풀 모두 시도"""
    nq = normalize_query(q)
    # 1) 일반 풀
    if _ALIAS_POOL:
        cand = process.extractOne(nq, _ALIAS_POOL, scorer=fuzz.WRatio)
        if cand and cand[1] >= min_score:
            return cand[0]
    # 2) no-space 풀(질의도 no-space로)
    nqns = no_space(nq)
    if _ALIAS_NOSPACE_POOL:
        cand2 = process.extractOne(nqns, _ALIAS_NOSPACE_POOL, scorer=fuzz.WRatio)
        if cand2 and cand2[1] >= min_score:
            return cand2[0]
    return None

def fuzzy_find_best_tag(q: str, min_score: int = 80) -> Optional[str]:
    nq = normalize_query(q)
    if not _TAG_POOL:
        return None
    cand = process.extractOne(nq, _TAG_POOL, scorer=fuzz.WRatio)
    if cand and cand[1] >= min_score:
        return cand[0]
    # 태그도 no-space 보조
    cand2 = process.extractOne(no_space(nq), [no_space(t) for t in _TAG_POOL], scorer=fuzz.WRatio)
    if cand2 and cand2[1] >= min_score:
        # 원래 태그 문자열 복구
        idx = [no_space(t) for t in _TAG_POOL].index(cand2[0])
        return _TAG_POOL[idx]
    return None

def contains_program_keyword(text: str) -> bool:
    """문장에 프로그램 키워드가 '부분적으로라도' 포함되면 True (띄어쓰기 무시)"""
    nq = normalize_query(text)
    nqns = no_space(nq)
    for a in _ALIAS_POOL:
        if a in nq:
            return True
    for ans in _ALIAS_NOSPACE_POOL:
        if ans in nqns:
            return True
    for t in _TAG_POOL:
        if t in nq:
            return True
    return False
