from __future__ import annotations

import asyncio
import contextlib
import hashlib
import html
import json
import os
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
_LABEL_PAREN = re.compile(r'([^\n()]+?)\((https?://[^\s)]+)\)')
_AUTO_URL = re.compile(r'(https?://[^\s<>"\')]+|www\.[^\s<>"\')]+)', re.IGNORECASE)
_BAD_LINK_LABEL = re.compile(r"^(여기|바로가기|링크|클릭|click|here)$", re.IGNORECASE)

FAQ_STRONG = 90
FAQ_WEAK   = 85
_ELLIPSIS_TRIGGER = re.compile(r"(그건|그거|그럼|는\?)$")

_NAV_ENTITY_HINT = re.compile(
    r"(아카이브|자료실|도시재생\+|투어|코스|일반코스|전문코스|전문투어|일반투어|공지|뉴스|아카데미|교육|프로그램|신청|게시판|갤러리|페이지|사이트|홈페이지)",
    re.IGNORECASE,
)

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
    (re.compile(r"조직도|팀장|담당|연락|연락처|전화|이메일|카카오톡|카톡", re.IGNORECASE),
     ["조직도", "담당자", "팀장", "연락처", "전화번호", "이메일", "카카오톡"]),
]

_OCR_ALT = {
    "오룡": r"오[룡릉]",
    "역세권": r"역세[권궈]",
    "봉명": r"봉[명明]",
}

CONTACT_FALLBACK = {
    "phone": ["041-417-4061~5"],
    "email": [],
    "address": ["천안시 은행길 15, 5층"],
    "hours": ["평일 09:00–18:00"],
    "online_inquiry": "홈페이지 '온라인 문의' 게시판을 이용해 주세요.",
}

# 주소 라인 필터(한글 주소 패턴, 영어/URL 과다 포함 라인 제외)
_ADDR_LINE = re.compile(r"(충남|충청남도|천안시)[^\n]{0,80}\d", re.IGNORECASE)
_LATIN_HEAVY = re.compile(r"[A-Za-z]{6,}")

def _cache_key(q: str) -> str:
    digest = hashlib.sha256(q.encode("utf-8")).hexdigest()[:24]
    return f"urc_cache:{digest}"

def _state_key(session_id: str) -> str:
    return f"urc_state:{session_id}"

async def _load_state(session_id: Optional[str]) -> Dict:
    if not session_id: return {}
    with contextlib.suppress(Exception):
        raw = await _redis.get(_state_key(session_id))
        return json.loads(raw) if raw else {}
    return {}

async def _save_state(session_id: Optional[str], state: Dict):
    if not session_id: return
    with contextlib.suppress(Exception):
        await _redis.set(_state_key(session_id), json.dumps(state, ensure_ascii=False), ex=STATE_TTL)

async def _get_cached(key: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        return await _redis.get(key)
    return None

async def _set_cached(key: str, val: str, ttl: int = CACHE_TTL):
    with contextlib.suppress(Exception):
        await _redis.set(key, val, ex=ttl)

def _shorten(texts: List[str], width: int = 420) -> List[str]:
    return [textwrap.shorten(t, width, placeholder="…") for t in texts if t and t.strip()]

def _looks_like_idk(ans: str) -> bool:
    s = (ans or "").strip()
    return bool(re.match(r"^(모르겠|잘 알 수 없|확인이 필요|정보가 부족)", s))

def _normalize(text: str) -> str:
    if not text: return ""
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _anchor(url: str, label: Optional[str] = None) -> str:
    u = url if url.startswith(("http://", "https://")) else f"https://{url}"
    lab = label or u
    return f'<a href="{u}" target="_blank" rel="noopener noreferrer">{html.escape(lab)}</a>'

def _to_html(text: str) -> str:
    if not text: return ""
    s = html.unescape(str(text))

    def _mk(m):
        label, url = m.group(1).strip(), m.group(2).strip()
        if _BAD_LINK_LABEL.match(label) or len(label) <= 4:
            return _anchor(url, url)
        return _anchor(url, label)

    s = _MD_LINK.sub(_mk, s)
    s = _LABEL_PAREN.sub(_mk, s)

    parts = re.split(r'(<[^>]+>)', s)
    for i, part in enumerate(parts):
        if not part or part.startswith("<"): continue
        parts[i] = _AUTO_URL.sub(lambda m: _anchor(m.group(0), m.group(0)), part)
    s = "".join(parts)
    return s.replace("\n", "<br>")

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
            if key in seen: continue
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
        if not used: used = docs_all[:6]
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
    if not hits: return None
    out = []
    for h in hits[:max_items]:
        title = h.get("title") or h.get("snippet") or h.get("link")
        link  = h.get("link")
        if not link: continue
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
        if not hits: return None
        lines = []
        for h in hits[:5]:
            title = h.get("title") or h.get("link")
            link  = h.get("link")
            if not link: continue
            lines.append(f"- {_anchor(link, title)}")
        return "내 문서에서 정확히 찾기 어렵습니다. 다음 자료를 참고해 주세요:\n\n" + "\n".join(lines)
    return None

_EMAIL_RE  = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE  = re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b|\b0\d{8,10}\b|0\d{1,2}-\d{4}-\d{4}|\d{3,4}-\d{4}\b")
_ADDR_HINT = re.compile(r"(주소|오시는\s*길|위치|도로명|천안시|충남\s*천안)", re.IGNORECASE)
_HOURS_HINT= re.compile(r"(운영\s*시간|업무\s*시간|영업\s*시간|근무\s*시간|점심\s*시간)", re.IGNORECASE)

def _iter_clean_md_texts() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not CLEAN_DIR.exists(): return out
    for md in CLEAN_DIR.glob("**/*.md"):
        try:
            txt = md.read_text(encoding="utf-8", errors="ignore")
            out.append((str(md), txt))
        except Exception:
            continue
    return out

def _scan_docs_for(regex: re.Pattern, must_include: Optional[re.Pattern] = None, limit: int = 5) -> List[str]:
    vs = get_vectorstore()
    texts = [d.page_content for d in getattr(vs.docstore, "_dict", {}).values()]
    found: List[str] = []
    for t in texts:
        if must_include and not must_include.search(t):
            continue
        for m in regex.findall(t):
            val = m if isinstance(m, str) else m[0]
            if val and val not in found:
                found.append(val)
            if len(found) >= limit:
                return found
    return found

def _scan_raw_md_for(regex: re.Pattern, include_pats: List[re.Pattern], limit: int = 5) -> List[str]:
    matches_prior: List[str] = []
    matches_any: List[str] = []
    for _, txt in _iter_clean_md_texts():
        for line in txt.splitlines():
            for m in regex.findall(line):
                val = m if isinstance(m, str) else m[0]
                if not val: 
                    continue
                if include_pats and any(p.search(line) for p in include_pats):
                    if val not in matches_prior:
                        matches_prior.append(val)
                        if len(matches_prior) >= limit:
                            return matches_prior
                else:
                    if val not in matches_any:
                        matches_any.append(val)
    return matches_prior[:limit] if matches_prior else matches_any[:limit]

def _keywords_from(q: str, alias: Optional[str], tag: Optional[str]) -> List[re.Pattern]:
    base_words = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", (q or "")))
    if alias: base_words.add(alias)
    if tag:   base_words.add(tag)
    pats: List[re.Pattern] = []
    for w in base_words:
        alt = _OCR_ALT.get(w)
        pats.append(re.compile(alt) if alt else re.compile(re.escape(w)))
    return pats

def _contact_answer(q: str, ctype: str, alias: Optional[str] = None, tag: Optional[str] = None) -> Optional[str]:
    if ctype == "email":
        found = _scan_docs_for(_EMAIL_RE, limit=5)
        if not found:
            kw = _keywords_from(q, alias, tag)
            found = _scan_raw_md_for(_EMAIL_RE, kw, limit=5)
        if found:
            items = "".join(f"<li><a href='mailto:{e}'>{html.escape(e)}</a></li>" for e in found)
            return f"<strong>이메일</strong><br><br><ul>{items}</ul>"
        if CONTACT_FALLBACK["email"]:
            items = "".join(f"<li><a href='mailto:{e}'>{html.escape(e)}</a></li>" for e in CONTACT_FALLBACK["email"])
            return f"<strong>이메일</strong><br><br><ul>{items}</ul>"
        return f"<strong>이메일</strong><br><br>{html.escape(CONTACT_FALLBACK['online_inquiry'])}"

    if ctype == "phone":
        found = _scan_docs_for(_PHONE_RE, limit=5)
        if not found:
            kw = _keywords_from(q, alias, tag)
            found = _scan_raw_md_for(_PHONE_RE, kw, limit=5)
        if found:
            items = "".join(f"<li><a href='tel:{p}'>{html.escape(p)}</a></li>" for p in found)
            return f"<strong>전화번호</strong><br><br><ul>{items}</ul>"
        items = "".join(f"<li><a href='tel:{p}'>{html.escape(p)}</a></li>" for p in CONTACT_FALLBACK["phone"])
        return f"<strong>전화번호</strong><br><br><ul>{items}</ul>"

    if ctype == "fax":
        return "팩스 번호가 문서에서 확인되지 않았습니다. 필요 시 대표전화로 문의해 주세요."

    if ctype == "address":
        # 주소처럼 보이는 라인만 필터링
        lines: List[str] = []
        vs = get_vectorstore()
        texts = [d.page_content for d in getattr(vs.docstore, "_dict", {}).values()]
        for t in texts:
            for line in t.splitlines():
                L = line.strip()
                if not L: continue
                if _ADDR_LINE.search(L) and not _LATIN_HEAVY.search(L) and len(L) <= 120:
                    if L not in lines:
                        lines.append(L)
                if len(lines) >= 5: break
            if len(lines) >= 5: break

        if not lines:
            for _, txt in _iter_clean_md_texts():
                for line in txt.splitlines():
                    L = line.strip()
                    if not L: continue
                    if _ADDR_LINE.search(L) and not _LATIN_HEAVY.search(L) and len(L) <= 120:
                        if L not in lines:
                            lines.append(L)
                    if len(lines) >= 5: break
                if len(lines) >= 5: break

        if lines:
            bullets = "".join(f"<li>{html.escape(line)}</li>" for line in lines[:5])
            return f"<strong>주소/오시는 길</strong><br><br><ul>{bullets}</ul>"

        # 폴백
        bullets = "".join(f"<li>{html.escape(line)}</li>" for line in CONTACT_FALLBACK["address"])
        return f"<strong>주소/오시는 길</strong><br><br><ul>{bullets}</ul>"

    if ctype == "hours":
        vs = get_vectorstore()
        texts = [d.page_content for d in getattr(vs.docstore, "_dict", {}).values()]
        lines: List[str] = []
        for t in texts:
            for line in t.splitlines():
                L = line.strip()
                if _HOURS_HINT.search(L) and not _LATIN_HEAVY.search(L):
                    if L not in lines:
                        lines.append(L)
                if len(lines) >= 5: break
            if len(lines) >= 5: break
        if not lines:
            for _, txt in _iter_clean_md_texts():
                for line in txt.splitlines():
                    L = line.strip()
                    if _HOURS_HINT.search(L) and not _LATIN_HEAVY.search(L):
                        if L not in lines:
                            lines.append(L)
                    if len(lines) >= 5: break
                if len(lines) >= 5: break
        if lines:
            bullets = "".join(f"<li>{html.escape(line)}</li>" for line in lines[:5])
            return f"<strong>운영/업무 시간</strong><br><br><ul>{bullets}</ul>"
        bullets = "".join(f"<li>{html.escape(line)}</li>" for line in CONTACT_FALLBACK["hours"])
        return f"<strong>운영/업무 시간</strong><br><br><ul>{bullets}</ul>"

    return None

_COURSE_NUM = re.compile(
    r"(?:(전문|일반)\s*코스\s*([0-9]+)|"
    r"(전문|일반)코스\s*([0-9]+)|"
    r"(전문|일반)\s*코스([0-9]+)|"
    r"코스\s*([0-9]+))",
    re.IGNORECASE,
)

def _extract_course_spec(q: str) -> Tuple[Optional[str], Optional[str]]:
    m = _COURSE_NUM.search(q)
    if not m: return None, None
    if m.group(1) and m.group(2):   return m.group(1).replace(" ", ""), m.group(2)
    if m.group(3) and m.group(4):   return m.group(3).replace(" ", ""), m.group(4)
    if m.group(5) and m.group(6):   return m.group(5).replace(" ", ""), m.group(6)
    return None, m.group(7)

def _prefer_program_alias_by_query(q: str, alias: Optional[str]) -> Optional[str]:
    if not alias: return None
    if re.search(r"(코스|투어|전문코스|일반코스|아카데미)", q):
        if "오시는 길" in alias:
            return None
    return alias

def _lookup_program_by_spec(kind: Optional[str], num: Optional[str]) -> Optional[dict]:
    if not num and not kind: return None
    if kind and num:
        alias = f"{kind}코스 {num}"
        prog = get_program_by_alias(alias)
        if prog: return prog
    tags_to_try = []
    if kind == "전문": tags_to_try.append("전문코스")
    elif kind == "일반": tags_to_try.append("일반코스")
    else: tags_to_try.extend(["전문코스", "일반코스"])
    for tag in tags_to_try:
        progs = get_programs_by_tag(tag) or []
        if num:
            for p in progs:
                name = (p.get("name") or "") + " " + (p.get("alias") or "")
                if re.search(fr"\b{num}\b", name):
                    return p
        if progs and not num:
            return progs[0]
    return None

def _rule_ctx_url(alias: Optional[str], tag: Optional[str], q: str) -> Optional[str]:
    kind, num = _extract_course_spec(q)
    if kind or num:
        prog = _lookup_program_by_spec(kind, num)
        if prog:
            url = prog["url"]
            return f"<strong>‘{prog['name']}’ 안내</strong><br><br>{_anchor(url, url)}"

    if alias:
        alias2 = _prefer_program_alias_by_query(q, alias)
        if alias2:
            prog = get_program_by_alias(alias2)
            if prog:
                url = prog["url"]
                return f"<strong>‘{prog['name']}’ 안내</strong><br><br>{_anchor(url, url)}"

    if tag:
        progs = get_programs_by_tag(tag)
        if progs:
            if num:
                filtered = []
                for p in progs:
                    name = (p.get("name") or "") + " " + (p.get("alias") or "")
                    if re.search(fr"\b{num}\b", name):
                        filtered.append(p)
                if filtered:
                    p = filtered[0]
                    return f"<strong>‘{p['name']}’ 안내</strong><br><br>{_anchor(p['url'], p['url'])}"
            items = "".join(f"<li>{_anchor(p['url'], p['url'])}</li>" for p in progs)
            return f"<strong>‘{tag}’ 관련 페이지</strong><br><br><ul>{items}</ul>"

    alias_guess = _prefer_program_alias_by_query(q, fuzzy_find_best_alias(q, min_score=82) or "")
    if alias_guess:
        prog = get_program_by_alias(alias_guess)
        if prog:
            return f"<strong>‘{prog['name']}’ 안내</strong><br><br>{_anchor(prog['url'], prog['url'])}"

    tag_guess = fuzzy_find_best_tag(q, min_score=82)
    if tag_guess:
        progs = get_programs_by_tag(tag_guess)
        if progs:
            items = "".join(f"<li>{_anchor(p['url'], p['url'])}</li>" for p in progs)
            return f"<strong>‘{tag_guess}’ 관련 페이지</strong><br><br><ul>{items}</ul>"
    return None

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

def _resolve_intent_with_context(info: Dict[str, Optional[str]], q: str, state: Dict) -> Dict[str, Optional[str]]:
    resolved = dict(info)
    nav_mode = state.get("nav_mode", False)

    if (re.search(r"(주소|어디서|확인\s*가능|링크|URL)", q, re.IGNORECASE) and _NAV_ENTITY_HINT.search(q)):
        resolved["intent"] = "find_program_url"

    if resolved.get("intent") == "find_program_url":
        if re.search(r"(사업비|예산|비용|정의|개요|설명|일정|기간|대상|자격|내용|사업\s*내용|목표|주요\s*사업|구상도)", q, re.IGNORECASE):
            resolved["intent"] = "ask_info"

    if resolved.get("intent") == "general_question":
        has_prog = (resolved.get("program_name") or resolved.get("tag"))
        if nav_mode and (has_prog or _ELLIPSIS_TRIGGER.search(q)):
            resolved["intent"] = "find_program_url"

    if not resolved.get("program_name") and state.get("last_program_alias"):
        resolved["program_name"] = state["last_program_alias"]
    if not resolved.get("tag") and state.get("last_program_tag"):
        resolved["tag"] = state["last_program_tag"]

    return resolved

async def ask_async(question: str, session_id: Optional[str] = None) -> str:
    with contextlib.suppress(Exception):
        validate_runtime_env()

    q = _normalize(question)
    if not q:
        return _to_html("질문이 비어 있습니다. 내용을 입력해 주세요.")

    state = await _load_state(session_id)
    cache_key = _cache_key((session_id or "") + "|" + q)
    if (cached := await _get_cached(cache_key)):
        return _to_html(cached)

    # 0) FAQ 초강매칭(정확/부분일치 우선) → 톤/고정문 우선권
    faq_exact = find_faq_answer(q, hard_threshold=100, soft_threshold=100)
    if faq_exact:
        asyncio.create_task(_set_cached(cache_key, faq_exact))
        await _save_state(session_id, {**state, "last_intent": "faq"})
        return _to_html(faq_exact)

    # 1) 의도 + 보정 (연락처/URL 우선)
    info = classify_intent_and_entity(q)
    info = _resolve_intent_with_context(info, q, state)

    if info.get("intent") == "ask_contact":
        ans = _contact_answer(q, info.get("contact_type"), info.get("program_name"), info.get("tag"))
        if ans:
            asyncio.create_task(_set_cached(cache_key, ans))
            await _save_state(session_id, {**state, "last_intent": "ask_contact"})
            return _to_html(ans)

    if info.get("intent") == "find_program_url":
        rule_ans = _rule_ctx_url(info.get("program_name"), info.get("tag"), q)
        if rule_ans:
            asyncio.create_task(_set_cached(cache_key, rule_ans))
            state.update({
                "last_intent": "find_program_url",
                "nav_mode": True,
                "last_program_alias": info.get("program_name") or state.get("last_program_alias"),
                "last_program_tag": info.get("tag") or state.get("last_program_tag"),
            })
            await _save_state(session_id, state)
            return _to_html(rule_ans)

    # 2) FAQ(강)
    if info.get("intent") not in ("ask_contact", "find_program_url"):
        blocked = []
        if re.search(r"(주소|링크|url|페이지|어디서\s*봐|확인\s*가능)", q, re.IGNORECASE):
            blocked.append("cost")
        faq_ans_strong = find_faq_answer(
            q,
            hard_threshold=FAQ_STRONG,
            soft_threshold=FAQ_STRONG,
            preferred_intent=None,
            blocked_intents=blocked or None,
        )
        if faq_ans_strong:
            asyncio.create_task(_set_cached(cache_key, faq_ans_strong))
            await _save_state(session_id, {**state, "last_intent": "faq"})
            return _to_html(faq_ans_strong)

    # 3) 로컬(md) → LLM
    local_ctx, best, nraw = _local_ctx(q)
    if local_ctx and (best >= LOCAL_HIT_THRES or nraw > 0):
        ans_local = _llm_single(q, local_ctx)
        if ans_local and not _looks_like_idk(ans_local):
            asyncio.create_task(_set_cached(cache_key, ans_local))
            await _save_state(session_id, {**state, "last_intent": info.get("intent") or "ask_info"})
            return _to_html(ans_local)

    # 4) FAQ(약)
    if info.get("intent") not in ("ask_contact", "find_program_url"):
        faq_ans_soft = find_faq_answer(
            q,
            hard_threshold=FAQ_WEAK,
            soft_threshold=FAQ_WEAK,
            preferred_intent=None,
            blocked_intents=None,
        )
        if faq_ans_soft:
            asyncio.create_task(_set_cached(cache_key, faq_ans_soft))
            await _save_state(session_id, {**state, "last_intent": "faq"})
            return _to_html(faq_ans_soft)

    # 5) 퍼지 로컬
    fuzzy_ctx = _fuzzy_ctx(q)
    if fuzzy_ctx:
        ans_fuzzy = _llm_single(q, fuzzy_ctx)
        if ans_fuzzy and not _looks_like_idk(ans_fuzzy):
            asyncio.create_task(_set_cached(cache_key, ans_fuzzy))
            await _save_state(session_id, {**state, "last_intent": "ask_info"})
            return _to_html(ans_fuzzy)

    # 6) 웹 폴백
    web_summary = _web_fallback_answer(q)
    if web_summary:
        asyncio.create_task(_set_cached(cache_key, web_summary))
        await _save_state(session_id, {**state, "last_intent": "web_fallback"})
        return _to_html(web_summary)

    # 7) 최종 융합
    web_ctx = _web_ctx(q) or ""
    final = _llm_fusion(q, local_ctx or fuzzy_ctx or "", "", web_ctx)
    asyncio.create_task(_set_cached(cache_key, final))
    await _save_state(session_id, {**state, "last_intent": "ask_info"})
    return _to_html(final)
