# -*- coding: utf-8 -*-
"""
천안시 도시재생지원센터 전용 챗봇 메인

우선순위
1) FAQ(강) →
2) 센터소개/오시는길(지도), 사업소개(정적 카드/단답) →
3) URL 라우터(아카이브/투어/커뮤니티/도시재생+ 등) ← **우선어 강화**
4) 프로그램 기간/상태 →
5) 로컬RAG/FAQ(약)/퍼지/웹 폴백
"""
from __future__ import annotations

import asyncio, contextlib, hashlib, html, json, os, re, textwrap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).date()

from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from rapidfuzz import fuzz, process
from redis.asyncio import Redis

from app.config import (
    CACHE_TTL, DDG_HITS, FUZZ_LIMIT, FUZZ_SCORE, LOCAL_HIT_THRES,
    MAX_COMPLETION_TOKENS, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE,
    REDIS_URL, validate_runtime_env
)
from app.rag.intent_classifier import classify_intent_and_entity
from app.rag.prompt import PROMPT_FUSION, PROMPT_SINGLE, STYLE_GUIDE
from app.rag.retriever import get_retriever, get_vectorstore
from app.rag.faq import find_faq_answer
from app.rag.hooks.directions import answer_directions
from app.rag.sections.center_intro import build_center_intro_index, query_contact, query_section, render_intro_summary_with_link
from app.rag.url import find_url_answer
from app.rag.sections.business import answer_business, is_business_query

try:
    from app.rag.reranker import rerank  # type: ignore
except Exception:
    def rerank(query: str, docs: List[str], top_k: int = 5):
        return docs[:top_k], 1.0

try:
    from app.config import CLEAN_DIR as _CLEAN_DIR
except Exception:
    _CLEAN_DIR = "app/data/clean"
CLEAN_DIR = Path(_CLEAN_DIR)

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

# ─────────────────────────────────────────────────────────
# 링크/오토링크 포맷터
_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
_LABEL_PAREN = re.compile(r'([^\n()]+?)\((https?://[^\s)]+)\)')
_AUTO_URL = re.compile(r'(https?://[^\s<>")]+|www\.[^\s<>")]+)', re.IGNORECASE)

FAQ_STRONG = 90
FAQ_WEAK   = 85

# ─────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────
# HTML 헬퍼
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

# ─────────────────────────────────────────────────────────
# 로컬 RAG/웹
def _shorten(texts: List[str], width: int = 420) -> List[str]:
    return [textwrap.shorten(t, width, placeholder="…") for t in texts if t and t.strip()]

def _local_ctx(q: str) -> Tuple[str, float, int]:
    queries = [q]
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
                    used.append(docs_all[i]); i += 1; break
                i += 1
        if not used:
            used = docs_all[:6]
        best_score = float(best)
    except Exception:
        used = docs_all[:6]; best_score = 1.0

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

def _web_ctx(q: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        hits = _DDG.results(q, max_results=DDG_HITS)
        if not hits:
            return None
        out = []
        for h in hits[:DDG_HITS]:
            title = h.get("title") or h.get("snippet") or h.get("link")
            link  = h.get("link")
            if not link: 
                continue
            out.append(_anchor(link, title))
        return "<br>".join(out) if out else None
    return None

def _web_fallback_answer(q: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        hits = _DDG.results(q, max_results=5)
        if not hits:
            return None
        lines = []
        for h in hits[:5]:
            title = h.get("title") or h.get("link")
            link  = h.get("link")
            if not link: 
                continue
            lines.append(f"- {_anchor(link, title)}")
        return "내 문서에서 정확히 찾기 어렵습니다. 다음 자료를 참고해 주세요:\n\n" + "\n".join(lines)
    return None

# ─────────────────────────────────────────────────────────
# 프로그램 기간/상태 (기존 로직 그대로)
@dataclass
class ProgramDoc:
    title: str
    url: str
    text_path: str
    status: Optional[str]
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
    if not s: return None
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
                if not ln.strip(): continue
                rec = json.loads(ln)
                out.append(ProgramDoc(
                    title=rec.get("title") or "",
                    url=rec.get("url") or "",
                    text_path=rec.get("text_path") or "",
                    status=(rec.get("status") or None),
                    start_date=_parse_date(rec.get("start_date")),
                    end_date=_parse_date(rec.get("end_date")),
                ))
    return out

ABS_RANGE = re.compile(
    r"(?P<y1>20\d{2})[.\-년/ ]*(?P<m1>\d{1,2})?[.\-월/ ]*(?P<d1>\d{1,2})?\s*[~\-–]\s*"
    r"(?P<y2>20\d{2})[.\-년/ ]*(?P<m2>\d{1,2})?[.\-월/ ]*(?P<d2>\d{1,2})?"
)
ABS_ONE  = re.compile(r"(?P<y>20\d{2})[.\-년/ ]*(?P<m>\d{1,2})?[.\-월/ ]*(?P<d>\d{1,2})?")
REL_WORDS= {"작년":-1,"지난해":-1,"올해":0,"금년":0,"내년":1,"다음해":1}
STATUS_WORDS={"진행":"진행중","진행중":"진행중","모집중":"진행중","예정":"예정","마감":"마감","종료":"마감"}
Q_WORDS=("프로그램","모집","신청","접수","교육","공모","행사")

def is_program_date_query(q: str) -> bool:
    has_kw = any(k in q for k in Q_WORDS)
    has_time = bool(ABS_RANGE.search(q) or ABS_ONE.search(q) or
                    any(w in q for w in REL_WORDS) or
                    any(w in q for w in ["지난달","이번달","다음달","재작년","상반기","하반기","1분기","2분기","3분기","4분기","기간"]))
    return has_kw and has_time

def month_start(dt: date) -> date: return date(dt.year, dt.month, 1)
def month_end(dt: date) -> date:
    if dt.month == 12: return date(dt.year,12,31)
    first_next = date(dt.year, dt.month+1, 1)
    return first_next - timedelta(days=1)

def parse_korean_date_range(q: str, today: date = TODAY) -> Tuple[Optional[date], Optional[date]]:
    m = ABS_RANGE.search(q)
    if m:
        y1,m1,d1 = int(m.group("y1")), m.group("m1"), m.group("d1")
        y2,m2,d2 = int(m.group("y2")), m.group("m2"), m.group("d2")
        m1i = int(m1) if m1 else 1; d1i = int(d1) if d1 else 1
        m2i = int(m2) if m2 else 12; d2i = int(d2) if d2 else month_end(date(y2,m2i,1)).day
        return date(y1,m1i,d1i), date(y2,m2i,d2i)

    m = ABS_ONE.search(q)
    if m:
        y = int(m.group("y"))
        if m.group("m"):
            mi = int(m.group("m"))
            if m.group("d"):
                di = int(m.group("d"))
                return date(y,mi,di), date(y,mi,di)
            return date(y,mi,1), month_end(date(y,mi,1))
        return date(y,1,1), date(y,12,31)

    for w, dlt in REL_WORDS.items():
        if w in q:
            y = today.year + dlt
            return date(y,1,1), date(y,12,31)

    if "지난달" in q:
        y,m = today.year, today.month
        if m == 1: y,m = y-1,12
        else: m -= 1
        return date(y,m,1), month_end(date(y,m,1))
    if "이번달" in q or "이달" in q or "이번 달" in q:
        return month_start(today), month_end(today)
    if "다음달" in q:
        y,m = today.year, today.month
        if m == 12: y,m = y+1,1
        else: m += 1
        return date(y,m,1), month_end(date(y,m,1))

    for qi in (1,2,3,4):
        if f"{qi}분기" in q:
            m1 = (qi-1)*3+1
            return date(today.year,m1,1), month_end(date(today.year,m1+2,1))
    if "상반기" in q: return date(today.year,1,1), date(today.year,6,30)
    if "하반기" in q: return date(today.year,7,1), date(today.year,12,31)
    return None, None

def detect_status_filter(q: str) -> Optional[str]:
    for k,v in STATUS_WORDS.items():
        if k in q:
            return v
    return None

def overlaps(a_start: Optional[date], a_end: Optional[date], b_start: Optional[date], b_end: Optional[date]) -> bool:
    a_s = a_start or date.min; a_e = a_end or date.max
    b_s = b_start or date.min; b_e = b_end or date.max
    return not (a_e < b_s or b_e < a_s)

def filter_programs(docs: List[ProgramDoc], req_start: Optional[date], req_end: Optional[date], status_filter: Optional[str]) -> List[ProgramDoc]:
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


URL_PRIORITY_WORDS = [
    "아카이브", "자료실", "보고서", "강의자료",
    "전문투어", "투어", "전문 코스", "코스",
    "공지", "소식", "모집공고", "온라인 문의",
    # ▼ 우선순위 강화
    "커뮤니티", "도시재생+", "도시재생플러스", "프로그램 신청", "오시는길", "주소", "링크", "url"
]

def _should_prioritize_url(q: str) -> bool:
    t = (q or "").lower()
    return any(w.lower() in t for w in URL_PRIORITY_WORDS)

def format_program_list_answer(filtered: List[ProgramDoc], req_start: Optional[date], req_end: Optional[date], status_filter: Optional[str], limit: int = 20) -> str:
    hdr = "요청하신"
    if req_start and req_end: hdr += f" 기간({req_start:%Y-%m-%d} ~ {req_end:%Y-%m-%d})"
    elif req_start: hdr += f" {req_start:%Y-%m-%d} 이후"
    elif req_end: hdr += f" {req_end:%Y-%m-%d} 이전"
    else: hdr += " 기간"
    hdr += f"의 **{status_filter}** 상태 프로그램 목록입니다.\n\n" if status_filter else "의 프로그램 목록입니다.\n\n"
    if not filtered:
        msg = f"{hdr}해당되는 프로그램을 찾지 못했습니다."
        return msg if status_filter else msg + " (예: '2024년 5월 프로그램', '2023년 하반기 마감 프로그램')"
    lines = [hdr]
    for i, d in enumerate(filtered[:limit], start=1):
        st = d.status or "상태 정보 없음"
        lines.append(f"{i}. [{d.title}]({d.url})  \n   기간: {d.period_str()}  \n   진행상태: **{st}**")
    if len(filtered) > limit:
        lines.append(f"\n… 외 {len(filtered)-limit}건")
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────
# 센터소개(요약) — 주소/지도 제외
_CI_HINT = re.compile(r"(센터\s*소개|인사말|연혁|조직도|목표|비전)", re.IGNORECASE)
def _answer_center_intro(q: str) -> Optional[str]:
    if not _CI_HINT.search(q):
        return None
    
    if re.search(r"인사말", q):
        return _to_html(render_intro_summary_with_link("https://www.cheonanurc.or.kr/24"))
    
    idx = build_center_intro_index()
    if re.search(r"연혁", q):
        blocks = query_section(idx, "연혁");    return _to_html("\n\n".join(blocks)) if blocks else None
    if re.search(r"조직도", q):
        blocks = query_section(idx, "조직도");   return _to_html("\n\n".join(blocks)) if blocks else None
    if re.search(r"(목표|비전)", q):
        blocks = query_section(idx, "목표비전"); return _to_html("\n\n".join(blocks)) if blocks else None

    return None

# ─────────────────────────────────────────────────────────
# 메인
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
        
    # 0) URL 라우터 — 우선 키워드일 때는 FAQ보다 먼저 처리 (아카이브, 투어, 커뮤니티, 도시재생+ 등)
    if _should_prioritize_url(q):
        hit0 = find_url_answer(q)
        if hit0:
            html_out0 = hit0.html
            asyncio.create_task(_set_cached(cache_key, html_out0))
            await _save_state(session_id, {**state, "last_intent": "url_router_priority"})
            return _to_html(html_out0)

    # 1) FAQ(강)
    faq_exact = find_faq_answer(q, hard_threshold=100, soft_threshold=100)
    if faq_exact:
        asyncio.create_task(_set_cached(cache_key, faq_exact))
        await _save_state(session_id, {**state, "last_intent": "faq_strong"})
        return _to_html(faq_exact)

    # 2) 센터 오시는길(지도) / 사업소개(정적)
    ans_dir = answer_directions(q)
    if ans_dir:
        asyncio.create_task(_set_cached(cache_key, ans_dir))
        await _save_state(session_id, {**state, "last_intent": "directions"})
        return _to_html(ans_dir)

    if is_business_query(q):
        biz = answer_business(q)
        if biz:
            asyncio.create_task(_set_cached(cache_key, biz))
            await _save_state(session_id, {**state, "last_intent": "business"})
            return _to_html(biz)

    ci = _answer_center_intro(q)
    if ci:
        asyncio.create_task(_set_cached(cache_key, ci))
        await _save_state(session_id, {**state, "last_intent": "center_intro"})
        return _to_html(ci)

    # 3) URL 라우터(아카이브/투어/커뮤니티/도시재생+ 섹션 링크)
    hit = find_url_answer(q)
    if hit:
        html_out = hit.html
        asyncio.create_task(_set_cached(cache_key, html_out))
        await _save_state(session_id, {**state, "last_intent": "url_router"})
        return _to_html(html_out)

    # 4) 프로그램 기간/상태
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

    # 5) 로컬 → LLM
    local_ctx, best, nraw = _local_ctx(q)
    if local_ctx and (best >= LOCAL_HIT_THRES or nraw > 0):
        ans_local = _llm_single(q, local_ctx)
        if ans_local and not re.match(r"^(모르겠|잘 알 수 없|확인이 필요|정보가 부족)", ans_local):
            asyncio.create_task(_set_cached(cache_key, ans_local))
            await _save_state(session_id, {**state, "last_intent": "ask_info"})
            return _to_html(ans_local)

    # 6) FAQ(약)
    faq_soft = find_faq_answer(q, hard_threshold=FAQ_WEAK, soft_threshold=FAQ_WEAK)
    if faq_soft:
        asyncio.create_task(_set_cached(cache_key, faq_soft))
        await _save_state(session_id, {**state, "last_intent": "faq_soft"})
        return _to_html(faq_soft)

    # 7) 퍼지 + LLM
    fuzzy_ctx = _fuzzy_ctx(q)
    if fuzzy_ctx:
        ans_fuzzy = _llm_single(q, fuzzy_ctx)
        if ans_fuzzy and not re.match(r"^(모르겠|잘 알 수 없|확인이 필요|정보가 부족)", ans_fuzzy):
            asyncio.create_task(_set_cached(cache_key, ans_fuzzy))
            await _save_state(session_id, {**state, "last_intent": "ask_info"})
            return _to_html(ans_fuzzy)

    # 8) 웹 폴백
    web_summary = _web_fallback_answer(q)
    if web_summary:
        asyncio.create_task(_set_cached(cache_key, web_summary))
        await _save_state(session_id, {**state, "last_intent": "web_fallback"})
        return _to_html(web_summary)

    # 9) 최종 융합
    web_ctx = _web_ctx(q) or ""
    final = _llm_fusion(q, local_ctx or fuzzy_ctx or "", "", web_ctx)
    asyncio.create_task(_set_cached(cache_key, final))
    await _save_state(session_id, {**state, "last_intent": "ask_info"})
    return _to_html(final)

# ─────────────────────────────────────────────────────────
# LLM 래퍼
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
