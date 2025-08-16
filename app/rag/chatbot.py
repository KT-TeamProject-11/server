from __future__ import annotations

import asyncio
import contextlib
import hashlib
import html
import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo
KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).date()

# ── 프로젝트 의존 모듈
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from rapidfuzz import fuzz, process
from redis.asyncio import Redis

from app.config import (
    CACHE_TTL,
    DDG_HITS,
    FUZZ_LIMIT,
    FUZZ_SCORE,
    LOCAL_HIT_THRES,
    MAX_COMPLETION_TOKENS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    REDIS_URL,
    validate_runtime_env,
)
from app.rag.intent_classifier import classify_intent_and_entity
from app.rag.prompt import PROMPT_FUSION, PROMPT_SINGLE, STYLE_GUIDE
from app.rag.retriever import get_retriever, get_vectorstore
from app.rag.programs import (
    fuzzy_find_best_alias,
    fuzzy_find_best_tag,
    get_program_by_alias,
    get_programs_by_tag,
)
from app.rag.faq import find_faq_answer

# URL 라우터(사용자가 미리 매칭해 둔 링크)
try:
    from app.rag.url import find_url_answer
except Exception:
    def find_url_answer(_q: str):
        return None

# 센터소개 전용 유틸
from app.rag.sections.center_intro import build_center_intro_index, query_contact, query_section

# 🔥 새로 추가된 '오시는 길/지도' 전용 훅
from app.rag.hooks.directions import answer_directions

try:
    from app.rag.reranker import rerank  # type: ignore
except Exception:
    def rerank(query: str, docs: List[str], top_k: int = 5):
        return docs[:top_k], 1.0

# 크롤러가 쓰는 CLEAN 디렉토리
try:
    from app.config import CLEAN_DIR as _CLEAN_DIR
except Exception:
    _CLEAN_DIR = "app/data/clean"
CLEAN_DIR = Path(_CLEAN_DIR)

# ── LLM 및 검색
_SYS = SystemMessage(content="너는 천안시 도시재생지원센터 전용 챗봇이다. 정확하고 근거 있는 정보만 답한다.")
_LLM = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=OPENAI_TEMPERATURE,
    api_key=OPENAI_API_KEY,
    max_tokens=MAX_COMPLETION_TOKENS,
)
_DDG = DuckDuckGoSearchAPIWrapper()

_redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
STATE_TTL = int(os.getenv("URC_STATE_TTL", "1800"))

# ────────────────────────────────────────────────────────────
# 출력 포맷터(링크/오토링크)
_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
_LABEL_PAREN = re.compile(r'([^\n()]+?)\((https?://[^\s)]+)\)')
_AUTO_URL = re.compile(r'(https?://[^\s<>")]+|www\.[^\s<>")]+)', re.IGNORECASE)
_BAD_LINK_LABEL = re.compile(r"^(여기|바로가기|링크|클릭|click|here)$", re.IGNORECASE)

FAQ_STRONG = 90
FAQ_WEAK   = 85

_QUERY_EXPANSIONS = [
    (re.compile(r"아카이브|자료\s*실", re.IGNORECASE), ["아카이브", "자료실", "아카이브 페이지"]),
    (re.compile(r"투어|현장\s*투어|코스", re.IGNORECASE), ["도시재생 투어", "현장투어", "일반코스", "전문코스", "투어 안내"]),
    (re.compile(r"아카데미|교육|강좌", re.IGNORECASE), ["도시재생 아카데미", "교육", "강좌"]),
    (re.compile(r"사업비|비용|예산", re.IGNORECASE), ["사업비", "예산", "비용", "예산 지원"]),
    (re.compile(r"신청|모집", re.IGNORECASE), ["신청 방법", "모집 안내", "접수 방법"]),
    (re.compile(r"대상|자격", re.IGNORECASE), ["지원 대상", "참여 대상", "자격 요건"]),
    (re.compile(r"일정|기간|시간", re.IGNORECASE), ["일정", "기간", "운영 시간"]),
    (re.compile(r"사업\s*목표|사업목표|목표|사업\s*내용|사업내용|내용|개요|주요\s*사업|주요사업|구상도", re.IGNORECASE),
     ["사업목표", "사업내용", "사업개요", "주요사업", "구상도"]),
    (re.compile(r"조직도|팀장|담당|연락|연락처|전화|이메일|카카오톡|카톡|오시는\s*길|주소|위치|지도|약도", re.IGNORECASE),
     ["조직도", "담당자", "팀장", "연락처", "전화번호", "이메일", "오시는길", "주소", "위치", "약도"]),
]

CONTACT_FALLBACK = {
    "phone": ["041-417-4061~5"],
    "email": [],
    "address": ["천안시 은행길 15, 5층"],
    "hours": ["평일 09:00–18:00"],
    "online_inquiry": "홈페이지 '온라인 문의' 게시판을 이용해 주세요.",
}

_ADDR_LINE = re.compile(r"(충남|충청남도|천안시)[^\n]{0,80}\d", re.IGNORECASE)
_LATIN_HEAVY = re.compile(r"[A-Za-z]{6,}")

# ────────────────────────────────────────────────────────────
# 캐시/상태

def _cache_key(q: str) -> str:
    digest = hashlib.sha256(q.encode("utf-8")).hexdigest()[:24]
    return f"urc_cache:{digest}"


def _state_key(session_id: str) -> str:
    return f"urc_state:{session_id}"


async def _load_state(session_id: Optional[str]) -> Dict:
    if not session_id:
        return {}
    with contextlib.suppress(Exception):
        raw = await _redis.get(_state_key(session_id))
        return json.loads(raw) if raw else {}
    return {}


async def _save_state(session_id: Optional[str], state: Dict):
    if not session_id:
        return
    with contextlib.suppress(Exception):
        await _redis.set(_state_key(session_id), json.dumps(state, ensure_ascii=False), ex=STATE_TTL)


async def _get_cached(key: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        return await _redis.get(key)
    return None


async def _set_cached(key: str, val: str, ttl: int = CACHE_TTL):
    with contextlib.suppress(Exception):
        await _redis.set(key, val, ex=ttl)


# ────────────────────────────────────────────────────────────
# 출력 포맷

def _anchor(url: str, label: Optional[str] = None) -> str:
    u = url if url.startswith(("http://", "https://")) else f"https://{url}"
    lab = label or u
    return f'<a href="{u}" target="_blank" rel="noopener noreferrer">{html.escape(lab)}</a>'


def _to_html(text: str) -> str:
    if not text:
        return ""
    s = html.unescape(str(text))

    def _mk(m):
        label, url = m.group(1).strip(), m.group(2).strip()
        if re.match(r"^(여기|바로가기|링크|클릭|click|here)$", label, re.IGNORECASE) or len(label) <= 4:
            return _anchor(url, url)
        return _anchor(url, label)

    s = _MD_LINK.sub(_mk, s)
    s = _LABEL_PAREN.sub(_mk, s)

    parts = re.split(r'(<[^>]+>)', s)
    for i, part in enumerate(parts):
        if not part or part.startswith("<"):
            continue
        parts[i] = _AUTO_URL.sub(lambda m: _anchor(m.group(0), m.group(0)), part)
    s = "".join(parts)
    return s.replace("\n", "<br>")


# ────────────────────────────────────────────────────────────
# 로컬 RAG/웹 보강(기존)

def _shorten(texts: List[str], width: int = 420) -> List[str]:
    return [textwrap.shorten(t, width, placeholder="…") for t in texts if t and t.strip()]


def _expand_queries(q: str) -> List[str]:
    out = {q}
    for pat, repls in _QUERY_EXPANSIONS:
        if pat.search(q):
            out.update(repls)
    q2 = re.sub(r"(이란?|이야|뭐[야요]?|가?\s*궁금|알려줘|보여줘|어디서봐\??|어디서\s*봐\??|어디서\s*확인\??)", "", q).strip()
    if q2 and q2 != q:
        out.add(q2)
    return list(out)


def _local_ctx(q: str) -> Tuple[str, float, int]:
    queries = [q] + [x for x in _expand_queries(q) if x != q]
    seen = set()
    docs_all: List = []
    retriever = get_retriever()

    for qv in queries[:6]:
        try:
            docs = retriever.get_relevant_documents(qv)
        except Exception:
            docs = []
        for d in docs:
            key = (d.page_content, tuple(sorted((d.metadata or {}).items())))
            if key in seen:
                continue
            seen.add(key)
            docs_all.append(d)

    nraw = len(docs_all)
    if not docs_all:
        return "", 0.0, 0

    contents = [d.page_content for d in docs_all]
    try:
        top_strings, best = rerank(q, contents)
        used = []
        i = 0
        for s in top_strings:
            while i < len(docs_all):
                if docs_all[i].page_content == s:
                    used.append(docs_all[i])
                    i += 1
                    break
                i += 1
        if not used:
            used = docs_all[:6]
        best_score = float(best)
    except Exception:
        used = docs_all[:6]
        best_score = 1.0

    blocks = []
    for d in used:
        meta = d.metadata or {}
        title = meta.get("title") or ""
        section = meta.get("section") or ""
        url = meta.get("url") or meta.get("source") or ""
        head = f"[{title}{(' > ' + section) if section else ''}]".strip()
        tail = f"\n출처: {url}" if url else ""
        blocks.append(f"{head}\n{d.page_content}{tail}")

    ctx = "\n\n---\n\n".join(blocks)
    return ctx, best_score, nraw


def _fuzzy_ctx(q: str) -> Optional[str]:
    vs = get_vectorstore()
    texts = [d.page_content for d in getattr(vs.docstore, "_dict", {}).values()]
    if not texts:
        return None
    pairs = process.extract(q, texts, scorer=fuzz.partial_ratio, limit=FUZZ_LIMIT)
    chosen = [t for t, score, _ in pairs if score >= FUZZ_SCORE]
    if not chosen:
        return None
    return "\n\n".join(_shorten(chosen))


def _format_hits(hits: List[dict], max_items: int) -> Optional[str]:
    if not hits:
        return None
    out = []
    for h in hits[:max_items]:
        title = h.get("title") or h.get("snippet") or h.get("link")
        link = h.get("link")
        if not link:
            continue
        out.append(_anchor(link, title))
    return "<br>".join(out) if out else None


def _web_ctx(q: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        hits = _DDG.results(q, max_results=DDG_HITS)
        return _format_hits(hits, DDG_HITS)
    return None


def _web_fallback_answer(q: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        hits = _DDG.results(q, max_results=5)
        if not hits:
            return None
        lines = []
        for h in hits[:5]:
            title = h.get("title") or h.get("link")
            link = h.get("link")
            if not link:
                continue
            lines.append(f"- {_anchor(link, title)}")
        return "내 문서에서 정확히 찾기 어렵습니다. 다음 자료를 참고해 주세요:\n\n" + "\n".join(lines)
    return None


# ────────────────────────────────────────────────────────────
# 프로그램 기간/상태 질의 처리 (과거 포함)
@dataclass
class ProgramDoc:
    title: str
    url: str
    text_path: str
    status: Optional[str]  # 예정/진행중/마감
    start_date: Optional[date]
    end_date: Optional[date]

    def period_str(self) -> str:
        if self.start_date and self.end_date:
            return f"{self.start_date:%Y-%m-%d} ~ {self.end_date:%Y-%m-%d}"
        if self.start_date:
            return f"{self.start_date:%Y-%m-%d} ~"
        if self.end_date:
            return f"~ {self.end_date:%Y-%m-%d}"
        return "기간 정보 없음"


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def load_all_manifests() -> List[ProgramDoc]:
    out: List[ProgramDoc] = []
    if not CLEAN_DIR.exists():
        return out
    for mf in CLEAN_DIR.glob("**/manifest.jsonl"):
        with contextlib.suppress(Exception):
            for ln in mf.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                rec = json.loads(ln)
                out.append(
                    ProgramDoc(
                        title=rec.get("title") or "",
                        url=rec.get("url") or "",
                        text_path=rec.get("text_path") or "",
                        status=(rec.get("status") or None),
                        start_date=_parse_date(rec.get("start_date")),
                        end_date=_parse_date(rec.get("end_date")),
                    )
                )
    return out


ABS_RANGE = re.compile(
    r"(?P<y1>20\d{2})[.\-년/ ]*(?P<m1>\d{1,2})?[.\-월/ ]*(?P<d1>\d{1,2})?" r"\s*[~\-–]\s*"
    r"(?P<y2>20\d{2})[.\-년/ ]*(?P<m2>\d{1,2})?[.\-월/ ]*(?P<d2>\d{1,2})?"
)
ABS_ONE = re.compile(r"(?P<y>20\d{2})[.\-년/ ]*(?P<m>\d{1,2})?[.\-월/ ]*(?P<d>\d{1,2})?")
REL_WORDS = {"작년": -1, "지난해": -1, "올해": 0, "금년": 0, "내년": 1, "다음해": 1}
STATUS_WORDS = {"진행": "진행중", "진행중": "진행중", "모집중": "진행중", "예정": "예정", "마감": "마감", "종료": "마감"}
Q_WORDS = ("프로그램", "모집", "신청", "접수", "교육", "공모", "행사")


def is_program_date_query(q: str) -> bool:
    has_kw = any(k in q for k in Q_WORDS)
    has_time = bool(
        ABS_RANGE.search(q)
        or ABS_ONE.search(q)
        or any(w in q for w in REL_WORDS.keys())
        or any(
            w in q
            for w in [
                "지난달",
                "이번달",
                "다음달",
                "재작년",
                "상반기",
                "하반기",
                "1분기",
                "2분기",
                "3분기",
                "4분기",
                "기간",
            ]
        )
    )
    return has_kw and has_time


def month_start(dt: date) -> date:
    return date(dt.year, dt.month, 1)


def month_end(dt: date) -> date:
    if dt.month == 12:
        return date(dt.year, 12, 31)
    first_next = date(dt.year, dt.month + 1, 1)
    return first_next - timedelta(days=1)


def quarter_bounds(year: int, q: int) -> Tuple[date, date]:
    m1 = (q - 1) * 3 + 1
    start = date(year, m1, 1)
    end = month_end(date(year, m1 + 2, 1))
    return start, end


def half_bounds(year: int, half: str) -> Tuple[date, date]:
    if half == "상반기":
        return date(year, 1, 1), date(year, 6, 30)
    return date(year, 7, 1), date(year, 12, 31)


def parse_korean_date_range(q: str, today: date = TODAY) -> Tuple[Optional[date], Optional[date]]:
    # 범위
    m = ABS_RANGE.search(q)
    if m:
        y1, m1, d1 = int(m.group("y1")), m.group("m1"), m.group("d1")
        y2, m2, d2 = int(m.group("y2")), m.group("m2"), m.group("d2")
        m1i = int(m1) if m1 else 1
        d1i = int(d1) if d1 else 1
        m2i = int(m2) if m2 else 12
        d2i = int(d2) if d2 else month_end(date(y2, m2i, 1)).day
        return date(y1, m1i, d1i), date(y2, m2i, d2i)

    # 단일
    m = ABS_ONE.search(q)
    if m:
        y = int(m.group("y"))
        if m.group("m"):
            m_i = int(m.group("m"))
            if m.group("d"):
                d_i = int(m.group("d"))
                return date(y, m_i, d_i), date(y, m_i, d_i)
            return date(y, m_i, 1), month_end(date(y, m_i, 1))
        return date(y, 1, 1), date(y, 12, 31)

    # 상대
    for w, delta in REL_WORDS.items():
        if w in q:
            y = today.year + delta
            return date(y, 1, 1), date(y, 12, 31)

    # 지난달/이번달/다음달
    if "지난달" in q:
        y, m = today.year, today.month
        if m == 1:
            y -= 1
            m = 12
        else:
            m -= 1
        return date(y, m, 1), month_end(date(y, m, 1))
    if "이번달" in q or "이달" in q or "이번 달" in q:
        return month_start(today), month_end(today)
    if "다음달" in q:
        y, m = today.year, today.month
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
        return date(y, m, 1), month_end(date(y, m, 1))

    # 분기/반기
    for qi in (1, 2, 3, 4):
        if f"{qi}분기" in q:
            return quarter_bounds(today.year, qi)
    if "상반기" in q:
        return half_bounds(today.year, "상반기")
    if "하반기" in q:
        return half_bounds(today.year, "하반기")

    return None, None


def detect_status_filter(q: str) -> Optional[str]:
    for k, v in STATUS_WORDS.items():
        if k in q:
            return v
    return None


def overlaps(a_start: Optional[date], a_end: Optional[date], b_start: Optional[date], b_end: Optional[date]) -> bool:
    a_s = a_start or date.min
    a_e = a_end or date.max
    b_s = b_start or date.min
    b_e = b_end or date.max
    return not (a_e < b_s or b_e < a_s)


def filter_programs(
    docs: List[ProgramDoc],
    req_start: Optional[date],
    req_end: Optional[date],
    status_filter: Optional[str],
) -> List[ProgramDoc]:
    out = []
    for d in docs:
        if status_filter and (d.status or "").strip() != status_filter:
            continue
        if req_start or req_end:
            if not overlaps(d.start_date, d.end_date, req_start, req_end):
                continue
        out.append(d)

    def sort_key(x: ProgramDoc):
        sd = x.start_date or date.min
        return (sd, x.title)

    return sorted(out, key=sort_key, reverse=True)


def format_program_list_answer(
    filtered: List[ProgramDoc],
    req_start: Optional[date],
    req_end: Optional[date],
    status_filter: Optional[str],
    limit: int = 20,
) -> str:
    hdr = "요청하신"
    if req_start and req_end:
        hdr += f" 기간({req_start:%Y-%m-%d} ~ {req_end:%Y-%m-%d})"
    elif req_start:
        hdr += f" {req_start:%Y-%m-%d} 이후"
    elif req_end:
        hdr += f" {req_end:%Y-%m-%d} 이전"
    else:
        hdr += " 기간"

    if status_filter:
        hdr += f"의 **{status_filter}** 상태 프로그램 목록입니다.\n\n"
    else:
        hdr += "의 프로그램 목록입니다.\n\n"

    if not filtered:
        none_msg = f"{hdr}해당되는 프로그램을 찾지 못했습니다."
        if status_filter is None:
            return none_msg + " (검색 팁: '2024년 5월 프로그램', '2023년 하반기 마감 프로그램'처럼 기간/상태를 함께 적어보세요.)"
        return none_msg

    lines = [hdr]
    for i, d in enumerate(filtered[:limit], start=1):
        st = d.status or "상태 정보 없음"
        lines.append(f"{i}. [{d.title}]({d.url})  \n   기간: {d.period_str()}  \n   진행상태: **{st}**")
    if len(filtered) > limit:
        lines.append(f"\n… 외 {len(filtered) - limit}건")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# 센터소개 전용 훅 (주소/지도 제외)
_CI_HINT = re.compile(r"(센터\s*소개|인사말|연혁|조직도|목표|비전)", re.IGNORECASE)


def _answer_center_intro(q: str) -> Optional[str]:
    """'센터소개' 관련 간단 질의에 바로 응답(인사말/연혁/조직도/목표·비전).\n    ※ 주소/지도는 hooks.directions 가 전담"""
    if not _CI_HINT.search(q):
        return None

    idx = build_center_intro_index()

    if re.search(r"인사말", q):
        blocks = query_section(idx, "인사말")
        if blocks:
            return _to_html("\n\n".join(blocks))
    if re.search(r"연혁", q):
        blocks = query_section(idx, "연혁")
        if blocks:
            return _to_html("\n\n".join(blocks))
    if re.search(r"조직도", q):
        blocks = query_section(idx, "조직도")
        if blocks:
            return _to_html("\n\n".join(blocks))
    if re.search(r"(목표|비전)", q):
        blocks = query_section(idx, "목표비전")
        if blocks:
            return _to_html("\n\n".join(blocks))

    # '센터 소개'만 물었을 때: 인사말 일부 + 연락처 요약
    blocks = query_section(idx, "인사말")
    contacts = query_contact(idx)
    if blocks or contacts:
        msg = []
        if blocks:
            msg.append("\n\n".join(blocks[:1]))
        if contacts:
            msg.append("### 연락처 요약\n" + "\n".join(contacts))
        return _to_html("\n\n".join(msg))

    return None


# ────────────────────────────────────────────────────────────
# 메인 진입점
async def ask_async(question: str, session_id: Optional[str] = None) -> str:
    with contextlib.suppress(Exception):
        validate_runtime_env()

    q = (question or "").strip()
    if not q:
        return _to_html("질문이 비어 있습니다. 내용을 입력해 주세요.")

    state = await _load_state(session_id)
    cache_key = _cache_key((session_id or "") + "|" + q)
    if cached := await _get_cached(cache_key):
        return _to_html(cached)

    # 0) ✅ URL 라우터가 최우선
    hit = find_url_answer(q)
    if hit:
        html_out = hit.html if hasattr(hit, "html") else str(hit)
        asyncio.create_task(_set_cached(cache_key, html_out))
        await _save_state(session_id, {**state, "last_intent": "url_router"})
        return _to_html(html_out)

    # 1) 그다음: 오시는 길/지도 (주소 키워드 제거되어 과발동 방지)
    ans_dir = answer_directions(q)
    if ans_dir:
        asyncio.create_task(_set_cached(cache_key, ans_dir))
        await _save_state(session_id, {**state, "last_intent": "directions"})
        return _to_html(ans_dir)

    # 2) FAQ 초강매칭
    faq_exact = find_faq_answer(q, hard_threshold=100, soft_threshold=100)
    if faq_exact:
        asyncio.create_task(_set_cached(cache_key, faq_exact))
        await _save_state(session_id, {**state, "last_intent": "faq"})
        return _to_html(faq_exact)

    # 3) 센터소개(주소/지도 제외)
    ci = _answer_center_intro(q)
    if ci:
        asyncio.create_task(_set_cached(cache_key, ci))
        await _save_state(session_id, {**state, "last_intent": "center_intro"})
        return ci

    # 4) 연락처 의도일 때도 url.py → directions 순으로 재확인
    info = classify_intent_and_entity(q) or {}
    if info.get("intent") == "ask_contact":
        ctype = info.get("contact_type") or ""
        if ctype in {"address", "location", "map"}:
            hit2 = find_url_answer(q)
            if hit2:
                html_out = hit2.html if hasattr(hit2, "html") else str(hit2)
                asyncio.create_task(_set_cached(cache_key, html_out))
                await _save_state(session_id, {**state, "last_intent": "url_router"})
                return _to_html(html_out)
            ans = answer_directions(q)
            if ans:
                asyncio.create_task(_set_cached(cache_key, ans))
                await _save_state(session_id, {**state, "last_intent": "directions"})
                return _to_html(ans)

    # 5) 프로그램 기간/상태
    q_norm = q.lower()
    if is_program_date_query(q_norm):
        docs = await asyncio.to_thread(load_all_manifests)
        req_start, req_end = parse_korean_date_range(q_norm)
        status_filter = detect_status_filter(q_norm)
        filtered = filter_programs(docs, req_start, req_end, status_filter)
        answer = format_program_list_answer(filtered, req_start, req_end, status_filter)
        asyncio.create_task(_set_cached(cache_key, answer))
        await _save_state(session_id, {**state, "last_intent": "program_period"})
        return _to_html(answer)

    # 6) 로컬 → LLM
    local_ctx, best, nraw = _local_ctx(q)
    if local_ctx and (best >= LOCAL_HIT_THRES or nraw > 0):
        ans_local = _llm_single(q, local_ctx)
        if ans_local and not re.match(r"^(모르겠|잘 알 수 없|확인이 필요|정보가 부족)", ans_local):
            asyncio.create_task(_set_cached(cache_key, ans_local))
            await _save_state(session_id, {**state, "last_intent": "ask_info"})
            return _to_html(ans_local)

    # 7) FAQ(약)
    faq_ans_soft = find_faq_answer(q, hard_threshold=FAQ_WEAK, soft_threshold=FAQ_WEAK)
    if faq_ans_soft:
        asyncio.create_task(_set_cached(cache_key, faq_ans_soft))
        await _save_state(session_id, {**state, "last_intent": "faq"})
        return _to_html(faq_ans_soft)

    # 8) 퍼지 + LLM
    fuzzy_ctx = _fuzzy_ctx(q)
    if fuzzy_ctx:
        ans_fuzzy = _llm_single(q, fuzzy_ctx)
        if ans_fuzzy and not re.match(r"^(모르겠|잘 알 수 없|확인이 필요|정보가 부족)", ans_fuzzy):
            asyncio.create_task(_set_cached(cache_key, ans_fuzzy))
            await _save_state(session_id, {**state, "last_intent": "ask_info"})
            return _to_html(ans_fuzzy)

    # 9) 웹 폴백
    web_summary = _web_fallback_answer(q)
    if web_summary:
        asyncio.create_task(_set_cached(cache_key, web_summary))
        await _save_state(session_id, {**state, "last_intent": "web_fallback"})
        return _to_html(web_summary)

    # 10) 최종 융합
    web_ctx = _web_ctx(q) or ""
    final = _llm_fusion(q, local_ctx or fuzzy_ctx or "", "", web_ctx)
    asyncio.create_task(_set_cached(cache_key, final))
    await _save_state(session_id, {**state, "last_intent": "ask_info"})
    return _to_html(final)


# ────────────────────────────────────────────────────────────
# LLM 호출 래퍼

def _llm_single(q: str, ctx: str) -> str:
    msg = PROMPT_SINGLE.format(style=STYLE_GUIDE, context=ctx or "없음", question=q)
    return _LLM.invoke([_SYS, HumanMessage(content=msg)]).content.strip()


def _llm_fusion(q: str, local_ctx: str, rule_ctx: str, web_ctx: str) -> str:
    msg = PROMPT_FUSION.format(
        style=STYLE_GUIDE,
        local_ctx=local_ctx or "없음",
        rule_ctx=rule_ctx or "없음",
        web_ctx=web_ctx or "없음",
        question=q,
    )
    return _LLM.invoke([_SYS, HumanMessage(content=msg)]).content.strip()