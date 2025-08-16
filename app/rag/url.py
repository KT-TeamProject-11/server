# -*- coding: utf-8 -*-
"""
url.py — 천안URC '링크/주소/URL' 고도화 라우터 (외부 사용자 모든 표현 대비)

포인트
- 질문 정규화 → 다단계 매칭: (1)정확일치 (2)규칙/ID (3)토큰 스코어링(오타·동의어·영문 혼용)
- 섹션(센터소개/사업소개/도시재생+/커뮤니티/아카이브) 질의 시: 해당 섹션의 모든 상세 링크를 한 번에 나열(브로드캐스트)
- RapidFuzz 있으면 token_set_ratio 사용, 없으면 Jaccard 대체
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============== 정규화 & 유틸 ==============

_POLITE_SUFFIX = re.compile(
    r"(좀|조금|구체적으로|자세히|정확히|빨리|빠르게|바로|지금|가능해\??|가능한가요\??|가능할까요\??|한번|한 번)$"
)
_ENDING_NOISE = re.compile(
    r"(이[야요]?$|인가요\??$|인가요$|인가$|뭐[야요]?$|알려줘(요)?$|알려[ ]?주세요$|가르쳐줘(요)?$|보여줘(요)?$|찾아줘(요)?$)"
)
_PUNCT = re.compile(r"[?!.,;:~…·/\\]+")
_WS = re.compile(r"\s+")
_REQ_TRAILER = re.compile(r"(링크|url|주소|홈페이지|페이지|사이트|경로|어디|바로가기)$", re.IGNORECASE)
_NUM_EXTRACT = re.compile(
    r"\b(\d{2,3})\b|/(new|41|64|78|97|98|99|100|24|79|101|25|131|133|128|68|27|71|70|72|74|75|73|140|92|95|121|36|35|37|108)\b",
    re.IGNORECASE,
)

def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")

def _normalize(s: str) -> str:
    """정확/토큰 매칭 공통 정규화 텍스트."""
    if not s:
        return ""
    s = _nfkc(s).strip()
    s = _POLITE_SUFFIX.sub("", s)
    s = _ENDING_NOISE.sub("", s)
    s = _REQ_TRAILER.sub("", s)
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip().lower()
    return s

def _anchor(url: str, label: Optional[str] = None) -> str:
    u = url if url.startswith(("http://", "https://")) else f"https://{url}"
    lab = label or u
    return f'<a href="{html.escape(u)}" target="_blank" rel="noopener noreferrer">{html.escape(lab)}</a>'

def _tokenize(s: str) -> List[str]:
    s = _normalize(s)
    if not s:
        return []
    return s.split()

# ============== 동의어 & 기본 사전 ==============

# 토큰 단위 동의어
SYN: Dict[str, str] = {
    # 플랫폼
    "인스타": "instagram", "인스타그램": "instagram", "insta": "instagram", "ig": "instagram",
    "유튜브": "youtube", "yt": "youtube", "youtube": "youtube",
    "밴드": "band", "band": "band",
    "블로그": "blog", "blog": "blog", "네이버": "blog", "naver": "blog",

    # 상위 메뉴(섹션)
    "센터소개": "센터소개", "소개": "센터소개",
    "사업소개": "사업소개", "사업": "사업소개",
    "도시재생+": "도시재생+", "도시재생플러스": "도시재생+", "재생+": "도시재생+",
    "아카이브": "아카이브", "자료실": "아카이브",
    "커뮤니티": "커뮤니티",

    # 하위 기능/페이지
    "오시는길": "오시는길", "오시는": "오시는길", "찾아오시는길": "오시는길", "찾아오는길": "오시는길", "찾아오는": "오시는길",
    "위치": "오시는길", "지도": "오시는길", "약도": "오시는길", "주소": "오시는길",

    "프로그램": "프로그램", "신청": "프로그램신청", "접수": "프로그램신청", "모집": "프로그램신청",
    "참가신청": "프로그램신청", "신청페이지": "프로그램신청",

    "도시재생투어": "투어", "투어": "투어", "현장투어": "투어", "tour": "투어",
    "일반코스": "일반코스", "전문코스": "전문코스", "코스": "코스",

    "발간물": "발간물", "뉴스": "도시재생뉴스", "도시재생뉴스": "도시재생뉴스",
    "오피니언": "오피니언", "전문가오피니언": "오피니언",
    "마을기자단": "마을기자단", "인터뷰": "마을기자단",

    # 지명/센터
    "센터": "센터", "지원센터": "센터",
    "천안역세권": "역세권", "역세권": "역세권",
    "오룡": "오룡지구", "오룡지구": "오룡지구",
    "봉평": "봉평지구", "봉평지구": "봉평지구", "봉명": "봉평지구", "봉명지구": "봉평지구",
    "남산지구": "남산지구", "혁신지구": "혁신지구",
    "원성2지구": "원성2지구", "원성2지규": "원성2지구", "원성 2지구": "원성2지구",
}

# 한글·한자 숫자(코스 번호)
KNUM = {"일": "1", "이": "2", "삼": "3", "하나": "1", "둘": "2", "셋": "3"}

SECTION_KEYS = ["센터소개", "사업소개", "도시재생+", "커뮤니티", "아카이브"]
BROADCAST_HINTS = {"목록", "전체", "전부", "다", "정리", "한번에", "한번에", "한 눈에", "목차", "메뉴", "카테고리", "링크", "페이지", "주소", "url"}
GENERIC_IGNORE = {"센터", "지원센터", "도시재생", "천안", "천안시"}  # 섹션 외 일반 단어

def _canon_tokens(tokens: List[str]) -> List[str]:
    out: List[str] = []
    for t in tokens:
        if t in KNUM:
            out.append(KNUM[t]); continue
        out.append(SYN.get(t, t))
    return out

# 코스 번호 추출
_COURSE_RE = re.compile(r"(일반|전문)?\s*코스\s*([0-9일이삼])", re.IGNORECASE)

def _extract_course(tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
    s = " ".join(tokens)
    m = _COURSE_RE.search(s)
    if not m:
        return None, None
    kind = (m.group(1) or "").replace(" ", "")
    num  = m.group(2)
    num = KNUM.get(num, num)
    if kind and kind.lower() in ("일반", "전문"):
        kind = "일반코스" if kind == "일반" else "전문코스"
    return kind, num

# ============== 데이터 모델 ==============

@dataclass
class LinkItem:
    url: str
    label: Optional[str] = None

@dataclass
class UrlEntry:
    q: str
    title: str
    answer: str
    links: List[LinkItem]
    aliases: List[str] = field(default_factory=list)
    page_ids: List[str] = field(default_factory=list)  # 숫자/식별자 매핑용
    _token_profiles: List[List[str]] = field(default_factory=list, repr=False)  # 인덱싱 캐시

    def to_html(self) -> str:
        parts: List[str] = []
        if self.title:
            parts.append(f"<strong>{html.escape(self.title)}</strong><br><br>")
        if self.answer:
            parts.append(html.escape(self.answer))
        if self.links:
            parts.append("<br><br><ul>")
            for li in self.links:
                parts.append(f"<li>{_anchor(li.url, li.label or li.url)}</li>")
            parts.append("</ul>")
        return "".join(parts)

@dataclass
class UrlResult:
    html: str
    hits: List[UrlEntry]  # 1개 이상

# ============== 매핑(제공하신 링크 정식 반영) ==============

ENTRIES: List[UrlEntry] = [
    # Main
    UrlEntry(
        q="메인",
        title="천안도시재생지원센터 메인",
        answer="센터 메인 페이지입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/", label="메인 페이지")],
        aliases=["홈", "홈페이지", "센터 홈페이지", "천안도시재생 홈페이지", "메인 페이지", "main"],
        page_ids=[],
    ),

    # Instagram
    UrlEntry(
        q="인스타그램 도시재생지원센터",
        title="Instagram — 천안시 도시재생지원센터",
        answer="공식 인스타그램 계정입니다.",
        links=[LinkItem(url="https://www.instagram.com/cheonan_urc/?hl=ko", label="cheonan_urc")],
        aliases=["인스타 센터", "센터 인스타", "인스타그램 센터", "cheonan_urc", "인스타 도시재생지원센터", "insta cheonan_urc"],
    ),
    UrlEntry(
        q="인스타그램 천안역세권 도시재생현장지원센터",
        title="Instagram — 천안역세권 도시재생현장지원센터",
        answer="천안역세권 현장지원센터 인스타그램입니다.",
        links=[LinkItem(url="https://www.instagram.com/cheonan.want/?hl=ko", label="cheonan.want")],
        aliases=["인스타 역세권", "역세권 인스타", "천안역세권 인스타", "cheonan.want"],
    ),
    UrlEntry(
        q="인스타그램 오룡지구 도시재생현장지원센터",
        title="Instagram — 오룡지구 도시재생현장지원센터",
        answer="오룡지구 현장지원센터 인스타그램입니다.",
        links=[LinkItem(url="https://www.instagram.com/cheonan_base/", label="cheonan_base")],
        aliases=["인스타 오룡", "오룡 인스타", "오룡지구 인스타", "cheonan_base"],
    ),

    # Blog
    UrlEntry(
        q="블로그 천안도시지원센터",
        title="블로그 — 천안도시지원센터",
        answer="센터 네이버 블로그입니다.",
        links=[LinkItem(url="https://blog.naver.com/urc-cheonan", label="urc-cheonan")],
        aliases=["센터 블로그", "천안도시재생 블로그", "urc-cheonan 블로그", "네이버 블로그 센터"],
    ),
    UrlEntry(
        q="블로그 봉명지구 도시재생 현장 지원센터",
        title="블로그 — 봉명지구 도시재생 현장 지원센터",
        answer="봉명지구 현장지원센터 네이버 블로그입니다.",
        links=[LinkItem(url="https://blog.naver.com/tongdol2020", label="tongdol2020")],
        aliases=["블로그 봉명지구", "봉명 블로그", "tongdol2020", "봉명지구 블로그"],
    ),

    # Youtube (요청 매핑 그대로)
    UrlEntry(
        q="유튜브 천안도시재생지원센터",
        title="YouTube — 천안도시재생지원센터",
        answer="센터 공식 유튜브 채널입니다.",
        links=[LinkItem(url="https://www.youtube.com/channel/UCnmu-XM_ssRWVnwmCUVmFGg", label="YouTube 채널")],
        aliases=["유튜브 센터", "센터 유튜브", "youtube 센터", "yt 센터"],
    ),
    UrlEntry(
        q="유튜브 천안역세권 도시재생현장지원센터",
        title="YouTube — 천안역세권 도시재생현장지원센터",
        answer="(요청 매핑 그대로) 해당 항목은 아래 링크로 연결됩니다.",
        links=[LinkItem(url="https://www.band.us/band/86255676", label="Band (제공된 링크)")],
        aliases=["유튜브 역세권", "역세권 유튜브", "youtube 천안역세권"],
    ),

    # Band
    UrlEntry(
        q="밴드 천안도시재생지원센터",
        title="Band — 천안도시재생지원센터",
        answer="센터 공식 밴드입니다.",
        links=[LinkItem(url="https://www.band.us/band/86255676", label="Band")],
        aliases=["밴드 센터", "센터 밴드", "band 센터", "밴드"],
    ),

    # ── 센터소개
    UrlEntry(
        q="센터소개 인사말",
        title="센터소개 > 인사말",
        answer="센터 인사말 페이지입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/24", label="인사말")],
        aliases=["인사말", "greeting"],
        page_ids=["24"],
    ),
    UrlEntry(
        q="센터소개 목표와비전",
        title="센터소개 > 목표와 비전",
        answer="센터의 목표와 비전 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/79", label="목표와 비전")],
        aliases=["목표와 비전", "비전", "목표"],
        page_ids=["79"],
    ),
    UrlEntry(
        q="센터소개 센터 연혁",
        title="센터소개 > 센터 연혁",
        answer="센터 연혁 페이지입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/101", label="센터 연혁")],
        aliases=["연혁", "센터연혁"],
        page_ids=["101"],
    ),
    UrlEntry(
        q="센터소개 조직 및 담당",
        title="센터소개 > 조직 및 담당",
        answer="조직도 및 담당자 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/25", label="조직 및 담당")],
        aliases=["조직도", "담당자", "조직"],
        page_ids=["25"],
    ),
    UrlEntry(
        q="센터소개 오시는길 천안시 도시재생지원센터",
        title="센터소개 > 오시는길 > 천안시 도시재생지원센터",
        answer="센터 오시는 길 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/131", label="오시는길(센터)")],
        aliases=["오시는길 센터", "센터 오시는길", "주소 센터", "위치 센터", "찾아오시는길 센터"],
        page_ids=["131"],
    ),
    UrlEntry(
        q="센터소개 오시는길 봉평지구 도시재생현장지원센터",
        title="센터소개 > 오시는길 > 봉평지구 도시재생현장지원센터",
        answer="봉평지구 현장지원센터 오시는 길입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/133", label="오시는길(봉평지구)")],
        aliases=["오시는길 봉평지구", "봉평 오시는길", "봉명 오시는길", "위치 봉평", "주소 봉평"],
        page_ids=["133"],
    ),
    UrlEntry(
        q="센터소개 오시는길 오룡지구 도시재생현장지원센터",
        title="센터소개 > 오시는길 > 오룡지구 도시재생현장지원센터",
        answer="오룡지구 현장지원센터 오시는 길입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/128", label="오시는길(오룡지구)")],
        aliases=["오시는길 오룡지구", "오룡 오시는길", "위치 오룡", "주소 오룡"],
        page_ids=["128"],
    ),

    # ── 사업소개 (9)
    UrlEntry(
        q="사업소개 천안 도시재생 총괄 사업현황",
        title="사업소개 > 천안 도시재생 총괄 사업현황",
        answer="천안 도시재생 총괄 사업현황입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/68", label="총괄 사업현황")],
        aliases=["총괄 사업현황", "도시재생 총괄"],
        page_ids=["68"],
    ),
    UrlEntry(
        q="사업소개 도시재생선도사업",
        title="사업소개 > 도시재생선도사업",
        answer="도시재생선도사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/27", label="도시재생선도사업")],
        aliases=["선도사업"],
        page_ids=["27"],
    ),
    UrlEntry(
        q="사업소개 천안역세권 도시재생사업",
        title="사업소개 > 천안역세권 도시재생사업",
        answer="천안역세권 도시재생사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/71", label="역세권 도시재생사업")],
        aliases=["천안역세권 사업", "역세권 사업"],
        page_ids=["71"],
    ),
    UrlEntry(
        q="사업소개 남산지구 도시재생사업",
        title="사업소개 > 남산지구 도시재생사업",
        answer="남산지구 도시재생사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/70", label="남산지구 도시재생사업")],
        aliases=["남산지구 사업"],
        page_ids=["70"],
    ),
    UrlEntry(
        q="사업소개 봉평지구 도시재생사업",
        title="사업소개 > 봉평지구 도시재생사업",
        answer="봉평지구 도시재생사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/72", label="봉평지구 도시재생사업")],
        aliases=["봉평지구 사업", "봉명지구 사업"],
        page_ids=["72"],
    ),
    UrlEntry(
        q="사업소개 오룡지구 도시재생사업",
        title="사업소개 > 오룡지구 도시재생사업",
        answer="오룡지구 도시재생사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/74", label="오룡지구 도시재생사업")],
        aliases=["오룡지구 사업", "오룡 사업"],
        page_ids=["74"],
    ),
    UrlEntry(
        q="사업소개 천안역세권 혁신지구 도시재생사업",
        title="사업소개 > 천안역세권 혁신지구 도시재생사업",
        answer="천안역세권 혁신지구 도시재생사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/75", label="역세권 혁신지구 도시재생사업")],
        aliases=["혁신지구 사업", "천안역세권 혁신지구"],
        page_ids=["75"],
    ),
    UrlEntry(
        q="사업소개 오룡지구 민-관 협력형 도시재생 리츠사업",
        title="사업소개 > 오룡지구 민-관 협력형 도시재생 리츠사업",
        answer="오룡지구 민·관 협력형 도시재생 리츠사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/73", label="오룡지구 리츠사업")],
        aliases=["오룡 리츠사업", "민관 협력형 리츠", "리츠사업"],
        page_ids=["73"],
    ),
    UrlEntry(
        q="사업소개 원성2지규 뉴:빌리지 사업",
        title="사업소개 > 원성2지규 뉴:빌리지 사업",
        answer="원성2지규 뉴:빌리지 사업 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/140", label="원성2지규 뉴:빌리지")],
        aliases=["뉴빌리지", "원성2지구 뉴빌리지", "원성2지규", "원성2지구"],
        page_ids=["140"],
    ),

    # ── 커뮤니티 (3)
    UrlEntry(
        q="커뮤니티 천안시 도시재생지원센터",
        title="커뮤니티 > 천안시 도시재생지원센터",
        answer="센터 커뮤니티 게시판입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/92", label="커뮤니티(센터)")],
        aliases=["커뮤니티 센터"],
        page_ids=["92"],
    ),
    UrlEntry(
        q="커뮤니티 봉명지구 도시재생 현장지원센터",
        title="커뮤니티 > 봉명지구 도시재생 현장지원센터",
        answer="봉명지구 커뮤니티 게시판입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/95", label="커뮤니티(봉명지구)")],
        aliases=["커뮤니티 봉명지구", "봉명 커뮤니티", "봉평 커뮤니티"],
        page_ids=["95"],
    ),
    UrlEntry(
        q="커뮤니티 오룡지구 도시재생현장지원센터",
        title="커뮤니티 > 오룡지구 도시재생현장지원센터",
        answer="오룡지구 커뮤니티 게시판입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/121", label="커뮤니티(오룡지구)")],
        aliases=["커뮤니티 오룡지구", "오룡 커뮤니티"],
        page_ids=["121"],
    ),

    # ── 도시재생+
    UrlEntry(
        q="도시재생플러스 공지사항",
        title="도시재생+ > 공지사항",
        answer="도시재생+ 공지사항(전체/공지/채용/유관기관/기타) 목록입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/new", label="공지사항(new)")],
        aliases=["도시재생+ 공지사항", "공지사항", "공지", "채용공고", "유관기관 공지"],
        page_ids=["new"],
    ),
    UrlEntry(
        q="도시재생플러스 센터 프로그램 신청",
        title="도시재생+ > 센터 프로그램 신청",
        answer="센터 프로그램 신청/모집 안내 목록입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/41", label="센터 프로그램 신청")],
        aliases=["프로그램 신청", "센터 프로그램", "참여 프로그램", "도시재생+ 프로그램 신청", "신청 페이지", "접수 페이지", "모집 안내"],
        page_ids=["41"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어",
        title="도시재생+ > 도시재생투어",
        answer="도시재생 투어 안내(코스별 상세는 아래 참조).",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/64", label="도시재생투어")],
        aliases=["도시재생 투어", "투어 안내", "현장투어"],
        page_ids=["64"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어 일반코스1",
        title="도시재생+ > 도시재생투어 > 일반코스1",
        answer="일반코스1 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/78", label="일반코스1")],
        aliases=["일반코스 1", "일반 코스 1", "코스1 (일반)", "투어 일반코스1"],
        page_ids=["78"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어 일반코스2",
        title="도시재생+ > 도시재생투어 > 일반코스2",
        answer="일반코스2 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/97", label="일반코스2")],
        aliases=["일반코스 2", "일반 코스 2", "코스2 (일반)", "투어 일반코스2"],
        page_ids=["97"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어 전문코스1",
        title="도시재생+ > 도시재생투어 > 전문코스1",
        answer="전문코스1 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/98", label="전문코스1")],
        aliases=["전문코스 1", "전문 코스 1", "코스1 (전문)", "투어 전문코스1"],
        page_ids=["98"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어 전문코스2",
        title="도시재생+ > 도시재생투어 > 전문코스2",
        answer="전문코스2 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/99", label="전문코스2")],
        aliases=["전문코스 2", "전문 코스 2", "코스2 (전문)", "투어 전문코스2"],
        page_ids=["99"],
    ),
    UrlEntry(
        q="도시재생플러스 도시재생투어 전문코스3",
        title="도시재생+ > 도시재생투어 > 전문코스3",
        answer="전문코스3 안내입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/100", label="전문코스3")],
        aliases=["전문코스 3", "전문 코스 3", "코스3 (전문)", "투어 전문코스3"],
        page_ids=["100"],
    ),

    # ── 아카이브
    UrlEntry(
        q="아카이브 발간물",
        title="아카이브 > 발간물",
        answer="센터 발간물 모음입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/36", label="발간물")],
        aliases=["발간물"],
        page_ids=["36"],
    ),
    UrlEntry(
        q="아카이브 홍보동영상",
        title="아카이브 > 홍보동영상",
        answer="요청하신 매핑 그대로 제공된 링크입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/httpswwwyoutubecomwatchvghzmqbIRJo0", label="홍보동영상(제공된 링크)")],
        aliases=["홍보 동영상", "홍보영상", "동영상"],
    ),
    UrlEntry(
        q="아카이브 도시재생뉴스",
        title="아카이브 > 도시재생뉴스",
        answer="도시재생 뉴스(외부 기사) 모음입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/35", label="도시재생뉴스")],
        aliases=["뉴스", "도시재생 뉴스"],
        page_ids=["35"],
    ),
    UrlEntry(
        q="아카이브 전문가 오피니언",
        title="아카이브 > 전문가 오피니언",
        answer="전문가 오피니언 모음입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/37", label="전문가 오피니언")],
        aliases=["오피니언", "전문가 의견"],
        page_ids=["37"],
    ),
    UrlEntry(
        q="아카이브 마을기자단 및 인터뷰",
        title="아카이브 > 마을기자단 및 인터뷰",
        answer="마을기자단/인터뷰 모음입니다.",
        links=[LinkItem(url="https://www.cheonanurc.or.kr/108", label="마을기자단 및 인터뷰")],
        aliases=["마을기자단", "인터뷰"],
        page_ids=["108"],
    ),
]

# ============== 인덱스 구성 + 섹션 브로드캐스트 ==============

class _Index:
    def __init__(self, entries: List[UrlEntry]):
        self.entries = entries
        self.phrase_map: Dict[str, UrlEntry] = {}
        self.id_map: Dict[str, UrlEntry] = {}
        self.section_map: Dict[str, List[UrlEntry]] = {s: [] for s in SECTION_KEYS}

        for e in entries:
            # 대표문구/별칭 → 정확일치 인덱스
            for ph in [e.q] + e.aliases:
                k = _normalize(ph)
                if k:
                    self.phrase_map[k] = e
                    e._token_profiles.append(_canon_tokens(_tokenize(ph)))
            # 숫자/식별자 → ID 인덱스
            for pid in e.page_ids:
                self.id_map[str(pid).lower()] = e
            # 제목/설명도 토큰 프로필 가산(검색 가중)
            for extra in [e.title, e.answer]:
                if extra:
                    e._token_profiles.append(_canon_tokens(_tokenize(extra)))

            # 섹션 인덱스(제목 접두 "섹션 > " 기준)
            for section in SECTION_KEYS:
                if e.title.startswith(f"{section} >"):
                    self.section_map[section].append(e)

    def by_phrase(self, query: str) -> Optional[UrlEntry]:
        return self.phrase_map.get(_normalize(query))

    def by_id(self, query: str) -> Optional[UrlEntry]:
        m = _NUM_EXTRACT.findall(query)
        if not m:
            return None
        for num, ident in m:
            key = (num or ident or "").lower()
            if not key:
                continue
            if key in self.id_map:
                return self.id_map[key]
        return None

    def entries_in_section(self, section: str) -> List[UrlEntry]:
        return list(self.section_map.get(section, []))

_INDEX = _Index(ENTRIES)

def _detect_section(tokens: List[str]) -> Optional[str]:
    tset = set(tokens)
    for s in SECTION_KEYS:
        if s in tset:
            return s
    return None

def _should_broadcast_section(tokens: List[str], section: str) -> bool:
    """섹션만 물었거나(또는 '목록/전체/링크/페이지/주소/url' 류 힌트) → 전체 나열"""
    tset = set(tokens)
    if section not in tset:
        return False
    # 브로드캐스트 힌트가 있으면 무조건
    if tset & BROADCAST_HINTS:
        return True
    # 섹션 외 의미 있는 추가 토큰이 없으면(=섹션만 언급) 브로드캐스트
    others = tset - {section} - GENERIC_IGNORE
    return len(others) == 0

def _render_section_broadcast(section: str) -> Optional[UrlResult]:
    items = _INDEX.entries_in_section(section)
    if not items:
        return None
    parts = [f"<strong>{html.escape(section)} 섹션 링크 모음</strong><br><br><ul>"]
    for e in items:
        first = e.links[0] if e.links else None
        if not first:
            continue
        parts.append(f"<li><strong>{html.escape(e.title)}</strong><br>{_anchor(first.url, first.label or first.url)}</li>")
    parts.append("</ul>")
    return UrlResult(html="".join(parts), hits=items)

# ============== 스코어링(오타/동의어/영문 혼용) ==============

try:
    from rapidfuzz.fuzz import token_set_ratio as _rf_token_set_ratio
    _HAS_RAPIDFUZZ = True
except Exception:
    _HAS_RAPIDFUZZ = False

def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))

def _score_tokens(qtoks: List[str], profiles: List[List[str]]) -> float:
    if not profiles:
        return 0.0
    if _HAS_RAPIDFUZZ:
        qs = " ".join(qtoks)
        return max(_rf_token_set_ratio(qs, " ".join(p)) for p in profiles) / 100.0
    return max(_jaccard(qtoks, p) for p in profiles)

def _domain_boost(qtoks: List[str], e: UrlEntry) -> float:
    t = set(qtoks)
    boost = 0.0
    if any(k in t for k in ("instagram", "youtube", "band", "blog")):
        title_s = _normalize(e.title)
        if any(p in title_s for p in ("instagram", "youtube", "band", "blog")):
            boost += 0.15
    if "오시는길" in t and "오시는길" in _normalize(e.title):
        boost += 0.15
    if ("투어" in t or "코스" in t or "일반코스" in t or "전문코스" in t) and "투어" in _normalize(e.title):
        boost += 0.10
    if "프로그램신청" in t and "프로그램" in _normalize(e.title):
        boost += 0.10
    if "봉평지구" in t and "봉평" in _normalize(e.title):
        boost += 0.05
    if "오룡지구" in t and "오룡" in _normalize(e.title):
        boost += 0.05
    if "역세권" in t and "역세권" in _normalize(e.title):
        boost += 0.05
    return boost

def _rule_match(qtoks: List[str]) -> Optional[UrlEntry]:
    toks = set(qtoks)

    # 오시는길 + 대상
    if "오시는길" in toks:
        # 센터
        for e in ENTRIES:
            if e.page_ids == ["131"] and ("센터" in toks or "천안시" in " ".join(qtoks)):
                return e
        # 봉평
        for e in ENTRIES:
            if e.page_ids == ["133"] and ("봉평지구" in toks or "봉명" in toks):
                return e
        # 오룡
        for e in ENTRIES:
            if e.page_ids == ["128"] and ("오룡지구" in toks or "오룡" in toks):
                return e

    # 프로그램 신청(도시재생+)
    if "프로그램신청" in toks or ("프로그램" in toks and ({"신청","접수","모집"} & toks)):
        for e in ENTRIES:
            if e.page_ids == ["41"]:
                return e

    # 투어 + (일반|전문)코스 + 번호
    kind, num = _extract_course(qtoks)
    if "투어" in toks:
        if kind and num:
            target = {
                ("일반코스", "1"): "78",
                ("일반코스", "2"): "97",
                ("전문코스", "1"): "98",
                ("전문코스", "2"): "99",
                ("전문코스", "3"): "100",
            }.get((kind, num))
            if target:
                for e in ENTRIES:
                    if target in e.page_ids:
                        return e
        # 코스 미지정: 투어 안내
        for e in ENTRIES:
            if e.page_ids == ["64"]:
                return e

    # 상하위 간단 조합
    if "센터소개" in toks and ({"인사말","greeting"} & toks):
        for e in ENTRIES:
            if e.page_ids == ["24"]:
                return e
    if "센터소개" in toks and ({"조직","조직도","담당자"} & toks):
        for e in ENTRIES:
            if e.page_ids == ["25"]:
                return e
    if "아카이브" in toks and ({"발간물"} & toks):
        for e in ENTRIES:
            if e.page_ids == ["36"]:
                return e
    if "아카이브" in toks and ({"뉴스","도시재생뉴스"} & toks):
        for e in ENTRIES:
            if e.page_ids == ["35"]:
                return e

    return None

def _best_candidates(query: str) -> List[Tuple[UrlEntry, float]]:
    # 1) ID
    hit = _INDEX.by_id(query)
    if hit:
        return [(hit, 1.0)]

    # 2) 정확 일치
    hit = _INDEX.by_phrase(query)
    if hit:
        return [(hit, 0.98)]

    # 3) 규칙
    qtoks = _canon_tokens(_tokenize(query))
    rule = _rule_match(qtoks)
    if rule:
        return [(rule, 0.95)]

    # 4) 토큰 스코어링
    scored: List[Tuple[UrlEntry, float]] = []
    for e in ENTRIES:
        score = _score_tokens(qtoks, e._token_profiles) + _domain_boost(qtoks, e)
        scored.append((e, score))
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return []
    top = scored[:3]
    base = top[0][1]
    TH = 0.45 if _HAS_RAPIDFUZZ else 0.35
    return [(e, s) for e, s in top if s >= TH and s >= base - 0.06]

# ============== 공개 API ==============

def find_url_answer(query: str) -> Optional[UrlResult]:
    """
    사용자 질의 → 최적 링크(1~N개) HTML.
    - 섹션 질문이면 해당 섹션 전체를 브로드캐스트(모두 나열)
    - 개별 상세로 판단되면 단건/근접 다건
    """
    if not (query or "").strip():
        return None

    # 섹션 브로드캐스트 감지
    qtoks = _canon_tokens(_tokenize(query))
    sec = _detect_section(qtoks)
    if sec and _should_broadcast_section(qtoks, sec):
        return _render_section_broadcast(sec)

    # 일반 매칭
    cands = _best_candidates(query)
    if not cands:
        return None

    cands.sort(key=lambda x: x[1], reverse=True)
    best_score = cands[0][1]
    hits = [cands[0][0]]
    for e, s in cands[1:]:
        if s >= best_score - 0.03:
            hits.append(e)
        if len(hits) >= 3:
            break

    if len(hits) == 1:
        return UrlResult(html=hits[0].to_html(), hits=hits)

    parts = ["원하시는 항목에 가장 가까운 링크들입니다.<br><br><ul>"]
    for e in hits:
        first = e.links[0] if e.links else None
        if first:
            parts.append(f"<li><strong>{html.escape(e.title)}</strong><br>{_anchor(first.url, first.label or first.url)}</li>")
    parts.append("</ul>")
    return UrlResult(html="".join(parts), hits=hits)

def list_registered_keys() -> List[str]:
    return [e.q for e in ENTRIES]

# ============== 디버그 ==============
if __name__ == "__main__":
    tests = [
        # 섹션 브로드캐스트
        "아카이브 주소좀", "센터소개 링크", "사업소개 전체", "도시재생+ 페이지", "커뮤니티 목록",
        # 특정 상세
        "센터소개 인사말", "아카이브 발간물", "도시재생+ 전문코스2", "투어 일반코스 1",
        # ID/직접
        "131", "/41", "new",
        # 플랫폼
        "인스타 센터", "유튜브 센터", "밴드 링크", "네이버 블로그 센터",
        # 오시는길
        "오시는길 센터", "봉명 오시는 길", "오룡 약도",
    ]
    for q in tests:
        r = find_url_answer(q)
        print(f"\nQ: {q}")
        if r:
            print("HIT:", [h.title for h in r.hits], "→", r.html[:100], "...")
        else:
            print("MISS")
