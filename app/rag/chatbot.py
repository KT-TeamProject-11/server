# app/rag/chatbot.py
from __future__ import annotations
import asyncio, contextlib, hashlib, re, textwrap, os, html
from typing import Optional, Tuple, List

from redis.asyncio import Redis
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from rapidfuzz import process, fuzz

from app.config import (
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE, MAX_COMPLETION_TOKENS,
    REDIS_URL, CACHE_TTL, DDG_HITS, LOCAL_HIT_THRES, FUZZ_LIMIT, FUZZ_SCORE,
    validate_runtime_env,
)
from app.rag.prompt import PROMPT_SINGLE, PROMPT_FUSION
from app.rag.retriever import get_retriever, get_vectorstore
from app.rag.reranker import rerank
from app.rag.programs import (
    get_program_by_alias, get_programs_by_tag,
    fuzzy_find_best_alias, fuzzy_find_best_tag
)
from app.rag.intent_classifier import classify_intent_and_entity
from app.rag.faq import find_faq_answer   # ✅ FAQ 즉답

# -------------------- 서비스 공통 --------------------
_SYS = SystemMessage(content="너는 천안 도시재생지원센터 전용 챗봇이다. 필요한 정보를 빠르고 정확히 답한다.")
_LLM = ChatOpenAI(
    model=OPENAI_MODEL,
    temperature=OPENAI_TEMPERATURE,
    api_key=OPENAI_API_KEY,
    max_tokens=MAX_COMPLETION_TOKENS,
)

# 상단 정규식 부분만 교체
_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')            # [라벨](url)
_LABEL_PAREN = re.compile(r'([^\n()]+?)\((https?://[^\s)]+)\)')         # 라벨(url)
# href="..." 또는 href='...' 내부의 URL은 제외하고 순수 URL만 매칭
_PLAIN_URL = re.compile(
    r'(?<!href=")(?<!href=\')((?:https?://|www\.)[^\s<>"\')\]]+)',
    re.IGNORECASE
)

_DDG = DuckDuckGoSearchAPIWrapper()
_redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

def _normalize(q: str) -> str:
    return (q or "").strip()

def _cache_key(*parts: str) -> str:
    digest = hashlib.sha256("::".join(parts).encode()).hexdigest()
    return f"urc_cache:{digest}"

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
    return bool(re.match(r"^모르겠|^잘 알 수 없|^확인이 필요|^정보가 부족", s))

def _log(msg: str):
    if os.getenv("URC_DEBUG", "0") == "1":
        print(f"[URC] {msg}")

def _normalize_links(text: str) -> str:
    if not text:
        return ""
    s = html.unescape(str(text))

    # 1) 마크다운 링크
    s = _MD_LINK.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)

    # 2) 라벨(링크)
    s = _LABEL_PAREN.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)

    # 3) 맨땅 URL (http/https/www)
    def repl_url(m):
        raw = m.group(1)
        # 문장부호 꼬리 분리
        trailing = ""
        while raw and raw[-1] in ".,;:!?)":
            trailing = raw[-1] + trailing
            raw = raw[:-1]

        href = raw
        if raw.lower().startswith("www."):
            href = "http://" + raw  # 스킴 보정

        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{raw}</a>{trailing}'

    s = _PLAIN_URL.sub(repl_url, s)

    # 4) 줄바꿈 처리
    s = s.replace("\n", "<br>")
    return s

# -------------------- 단계 1: 로컬(홈페이지 인덱스) --------------------
def _local_ctx(q: str) -> Tuple[str, float, int]:
    docs = [d.page_content for d in get_retriever().get_relevant_documents(q)]
    nraw = len(docs)
    top_docs, best = rerank(q, docs)
    ctx = "\n\n".join(_shorten(top_docs))
    _log(f"retrieved={nraw}, rerank_top={len(top_docs)}, best={best:.4f}")
    return ctx, best, nraw

# -------------------- 단계 2: FAQ 룰(고정 문장 즉답) --------------------
def _faq_answer(q: str) -> Optional[str]:
    return find_faq_answer(q)

# -------------------- 단계 3: programs 룰(링크 즉답) --------------------
def _rule_answer(q: str) -> Optional[str]:
    info = classify_intent_and_entity(q)
    if info.get("intent") != "find_program_url":
        return None
    alias = info.get("program_name") or fuzzy_find_best_alias(q)
    if alias:
        prog = get_program_by_alias(alias)
        if prog:
            return (f"'{prog['name']}' 정보는 아래 링크에서 바로 확인할 수 있습니다:<br><br>"
                f'<a href="{prog["url"]}" target="_blank"><strong>{prog["name"]} 홈페이지 바로가기</strong></a><br><br>')
    tag = info.get("tag") or fuzzy_find_best_tag(q)
    if tag:
        progs = get_programs_by_tag(tag)
        if progs:
            lines = [f"- <a href='{p['url']}' target='_blank'>{p['name']}</a>" for p in progs]
            return f"'{tag}' 관련 페이지 목록입니다.<br><br>" + "<br>".join(lines)
    return None

# -------------------- 단계 4: 퍼지(로컬 코퍼스 부분일치) --------------------
def _fuzzy_ctx(q: str) -> Optional[str]:
    vs = get_vectorstore()
    texts = [d.page_content for d in vs.docstore._dict.values()]
    pairs = process.extract(q, texts, scorer=fuzz.partial_ratio, limit=FUZZ_LIMIT)
    chosen = [t for t, score, _ in pairs if score >= FUZZ_SCORE]
    if not chosen:
        return None
    return "\n\n".join(_shorten(chosen))

# -------------------- 단계 5: 웹검색(강화판) --------------------
def _format_hits(hits: List[dict], max_items: int) -> Optional[str]:
    """DuckDuckGo hits → 불릿 문자열"""
    if not hits:
        return None
    lines = []
    for h in hits[:max_items]:
        title = (h.get("title") or "").strip()
        body  = (h.get("snippet") or title or "").strip()
        url   = (h.get("link") or h.get("href") or "").strip()
        if not url:
            continue
        if not body:
            body = url
        lines.append(f"- {body} (출처: {url})")
    return "\n".join(lines) if lines else None

def _web_ctx(q: str) -> Optional[str]:
    """빈 결과일 때 쿼리 보강 재시도"""
    with contextlib.suppress(Exception):
        hits = _DDG.results(q, max_results=DDG_HITS)
        ctx = _format_hits(hits, DDG_HITS)
        if ctx:
            _log(f"web hits (q) = {len(hits)}")
            return ctx

        # 1차 보강: 기관명 추가
        q2 = f"{q} 천안 도시재생지원센터"
        hits2 = _DDG.results(q2, max_results=DDG_HITS)
        ctx2 = _format_hits(hits2, DDG_HITS)
        if ctx2:
            _log(f"web hits (q2) = {len(hits2)}")
            return ctx2

        # 2차 보강: 사이트 제한
        q3 = f"{q} site:cheonanurc.or.kr"
        hits3 = _DDG.results(q3, max_results=DDG_HITS)
        ctx3 = _format_hits(hits3, DDG_HITS)
        if ctx3:
            _log(f"web hits (q3) = {len(hits3)}")
            return ctx3
    _log("web hits = 0")
    return None

# -------------------- LLM 호출 --------------------
def _llm_single(q: str, ctx: str) -> str:
    msg = PROMPT_SINGLE.format(context=ctx or "없음", question=q)
    return _LLM.invoke([_SYS, HumanMessage(content=msg)]).content.strip()

def _llm_fusion(q: str, local_ctx: str, rule_ctx: str, web_ctx: str) -> str:
    msg = PROMPT_FUSION.format(local_ctx=local_ctx or "없음",
                               rule_ctx=rule_ctx or "없음",
                               web_ctx=web_ctx or "없음",
                               question=q)
    return _LLM.invoke([_SYS, HumanMessage(content=msg)]).content.strip()

# -------------------- 외부 API --------------------
async def ask_async(question: str) -> str:
    # 필수 키 점검
    with contextlib.suppress(Exception):
        validate_runtime_env()

    q = _normalize(question)
    if not q:
        return "질문이 비어 있습니다. 내용을 입력해 주세요."

    base_key = _cache_key(q)
    if (cached := await _get_cached(base_key)):
        return _normalize_links(cached)

    # 0) 로컬 인덱스 상태 진단 로그(선택)
    try:
        vs = get_vectorstore()
        _log(f"docstore_size={len(vs.docstore._dict)}")
    except Exception as e:
        _log(f"vectorstore load error: {e}")

    # 1) 로컬 컨텍스트: 임계치 상관 없이 '있으면' 한 번 시도
    local_ctx, best, nraw = _local_ctx(q)
    if local_ctx:
        ans_local = _llm_single(q, local_ctx)
        if ans_local and not _looks_like_idk(ans_local):
            asyncio.create_task(_set_cached(base_key, ans_local))
            return _normalize_links(ans_local)
        _log("local answer sounded like IDK → continue")

    # 2) FAQ 즉답
    if (faq_ans := _faq_answer(q)):
        asyncio.create_task(_set_cached(base_key, faq_ans))
        return _normalize_links(faq_ans)

    # 3) programs 룰(링크)
    if (rule_ans := _rule_answer(q)):
        asyncio.create_task(_set_cached(base_key, rule_ans))
        return _normalize_links(rule_ans)

    # 4) 퍼지 로컬 컨텍스트
    fuzzy_ctx = _fuzzy_ctx(q)
    if fuzzy_ctx:
        ans_fuzzy = _llm_single(q, fuzzy_ctx)
        if ans_fuzzy and not _looks_like_idk(ans_fuzzy):
            asyncio.create_task(_set_cached(base_key, ans_fuzzy))
            return _normalize_links(ans_fuzzy)
        _log("fuzzy answer sounded like IDK → continue")

    # 5) 웹검색(강제 사용) + 융합
    web_ctx = _web_ctx(q) or ""
    final = _llm_fusion(q, local_ctx or fuzzy_ctx or "", rule_ans or "", web_ctx)
    asyncio.create_task(_set_cached(base_key, final))
    return _normalize_links(final)
