"""천안 도시재생지원센터 챗봇 – RAG + 룰 + 퍼지 + 웹 + 종합 컨텍스트 게이팅 + Redis 캐시"""

from __future__ import annotations

import os
import hashlib
import textwrap
import asyncio
import contextlib
from typing import Tuple, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun
from rapidfuzz import fuzz, process
from redis.asyncio import Redis

from .prompt import PROMPT, ALL_SOURCES_PROMPT
from .retriever import get_retriever
from .reranker import rerank
from .verifier import fact_check
from .programs import get_all_aliases, get_program_by_alias
from utils.intent_classifier import classify_intent_and_extract_entity

# ───────────── 환경변수 로드 ─────────────
OPENAI_MODEL   = os.environ["OPENAI_MODEL"]
LLAMA_API_URL  = os.environ["LLAMA_API"]
REDIS_URL      = os.environ["REDIS_URL"]
CACHE_TTL      = int(os.environ["CACHE_TTL_SEC"])
THRESH         = float(os.environ["THRESH"])
TOP_K          = int(os.environ["TOP_K"])
FUZZ_LIMIT     = int(os.environ["FUZZ_LIMIT"])
FUZZ_SCORE     = int(os.environ["FUZZ_SCORE"])
SEARCH_HITS    = int(os.environ["SEARCH_HITS"])

# ───────────── Redis 캐시 ─────────────
_redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

async def _get_cached(key: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        return await _redis.get(key)
    return None

async def _set_cached(key: str, val: str):
    with contextlib.suppress(Exception):
        await _redis.set(key, val, ex=CACHE_TTL)

def _cache_key(q: str, ctx: str) -> str:
    digest = hashlib.sha256(f"{q}::{ctx}".encode()).hexdigest()
    return f"llm_cache:{digest}"

# ───────────── LLM 인스턴스 ─────────────
_SYS = SystemMessage(
    content="너는 천안 도시재생지원센터 전용 챗봇이야. 필요한 정보를 찾아서 정확하게 답변해줘."
)
_LLM        = ChatOpenAI(model=OPENAI_MODEL, temperature=0.2, top_p=0.9)
_LLM_LOCAL  = ChatOpenAI(base_url=LLAMA_API_URL, api_key="none",
                         model="llama-3-8b-instruct-q4", temperature=0.2)
_LLM_BACKUP = _LLM
_SEARCH     = DuckDuckGoSearchRun(backend="auto")

def _normalize(q: str) -> str:
    return q.strip()

def _local_ctx(q: str) -> Tuple[str, float]:
    docs = [d.page_content for d in get_retriever().get_relevant_documents(q)]
    top_docs, best = rerank(q, docs, top_n=TOP_K) if docs else ([], 0.0)
    ctx = "\n\n".join(textwrap.shorten(d, 400) for d in top_docs)
    return ctx, best

def _fuzzy_ctx(q: str) -> str:
    vect = get_retriever().retrievers[0]
    texts = [d.page_content for d in vect.vectorstore.docstore._dict.values()]
    pairs = process.extract(q, texts, scorer=fuzz.partial_ratio, limit=FUZZ_LIMIT)
    chosen = [t for t, score, _ in pairs if score >= FUZZ_SCORE]
    return "\n\n".join(textwrap.shorten(t, 400) for t in chosen)

def _web_ctx(q: str) -> str:
    with contextlib.suppress(Exception):
        hits = _SEARCH.results(q, num_results=SEARCH_HITS)
        return "\n".join(
            f"- {h.get('body') or h.get('title','')} (출처: {h.get('url','')})"
            for h in hits
        )
    return ""

def _llm_call(llm: ChatOpenAI, q: str, ctx: str) -> str:
    prompt = PROMPT.format(context=ctx or "없음", question=q)
    return llm.invoke([_SYS, HumanMessage(content=prompt)]).content.strip()

async def _gate_llm(q: str, ctx: str) -> Tuple[str, str]:
    # 1) 로컬 llama 시도
    with contextlib.suppress(Exception):
        ans = _llm_call(_LLM_LOCAL, q, ctx)
        if fact_check(q, ans):
            return ans, "Local"
    # 2) OpenAI 백업
    ans = _llm_call(_LLM_BACKUP, q, ctx)
    return ans, "Backup"

def _ask_all_sources(q: str, local_ctx: str, rule_ctx: str, web_ctx: str) -> str:
    prompt = ALL_SOURCES_PROMPT.format(
        local_ctx=local_ctx or "없음",
        rule_ctx=rule_ctx or "없음",
        web_ctx=web_ctx or "없음",
        question=q,
    )
    return _LLM.invoke([_SYS, HumanMessage(content=prompt)]).content.strip()

# ───────────── 메인 비동기 엔드포인트 ─────────────
async def ask_async(question: str) -> str:
    q = _normalize(question)
    blank_key = _cache_key(q, "")

    # 0) 캐시 우선
    if (cached := await _get_cached(blank_key)):
        return f"{cached}\n\n▲confidence: Cached"

    # 1) 내부 RAG
    local_ctx, score = _local_ctx(q)
    if local_ctx and score >= THRESH:
        ans, src = await _gate_llm(q, local_ctx)
        if not ans.startswith("모르겠습니다"):
            asyncio.create_task(_set_cached(_cache_key(q, local_ctx), ans))
            return f"{ans}\n\n▲confidence: High ({src})"
        # “모르겠습니다” 면 다음 단계 진행

    # 2) 룰 기반 URL
    rule_ctx = ""
    intent = classify_intent_and_extract_entity(q)
    if intent.get("intent") == "find_program_url":
        name = intent.get("program_name") or ""
        best, s, _ = process.extractOne(name, get_all_aliases(), scorer=fuzz.WRatio)
        if s >= 75 and (info := get_program_by_alias(best)):
            rule_ctx = f"'{best}' 홈페이지: {info['url']}"
            ans = rule_ctx
            asyncio.create_task(_set_cached(blank_key, ans))
            return f"{ans}\n\n▲confidence: Rule (score={s:.0f})"

    # 3) 퍼지 매칭
    fuzzy_ctx = _fuzzy_ctx(q)
    if fuzzy_ctx:
        ans, src = await _gate_llm(q, fuzzy_ctx)
        if not ans.startswith("모르겠습니다") and fact_check(q, ans):
            asyncio.create_task(_set_cached(_cache_key(q, fuzzy_ctx), ans))
            return f"{ans}\n\n▲confidence: Mid ({src})"

    # 4) 웹 검색
    web_ctx = _web_ctx(q)
    if web_ctx:
        ans, src = await _gate_llm(q, web_ctx)
        if not ans.startswith("모르겠습니다"):
            asyncio.create_task(_set_cached(_cache_key(q, web_ctx), ans))
            return f"{ans}\n\n▲confidence: Mid ({src})"

    # 5) 종합 컨텍스트 물어보기 (최종 fallback)
    final_ans = _ask_all_sources(q, local_ctx, rule_ctx, web_ctx)
    asyncio.create_task(_set_cached(blank_key, final_ans))
    return f"{final_ans}\n\n▲confidence: Low (AllSources)"


'''
async def ask_async(question: str) -> str:
    q = _normalize(question)

    # 0) 캐시 키(컨텍스트 없음 단계에서는 질문만 사용)
    ckey_blank = _cache_key(q, "")
    if (cached := await _get_cached(ckey_blank)):
        return f"{cached}\n\n▲confidence: Cached"

    # 1) 내부 문서 RAG ★
    ctx, score = _local_ctx(q)
    if ctx and score >= THRESH:
        ans, src = await _gate_llm(q, ctx)
        asyncio.create_task(_set_cached(_cache_key(q, ctx), ans))
        return f"{ans}\n\n▲confidence: High ({src})"

    # 2) 룰 기반 프로그램 URL ★
    intent = classify_intent_and_extract_entity(q, _LLM_BACKUP)
    if intent.get("intent") == "find_program_url":
        name = intent.get("program_name") or ""
        best, s, _ = process.extractOne(name, get_all_aliases(), scorer=fuzz.WRatio)
        if s >= 75 and (info := get_program_by_alias(best)):
            ans = f"'{best}' 링크: [바로가기]({info['url']})"
            asyncio.create_task(_set_cached(ckey_blank, ans))
            return f"{ans}\n\n▲confidence: Rule (score={s:.0f})"

    # 3) 퍼지 매칭
    if (fctx := _fuzzy_ctx(q)):
        ans, src = await _gate_llm(q, fctx)
        if fact_check(q, ans):
            asyncio.create_task(_set_cached(_cache_key(q,fctx), ans))
            return f"{ans}\n\n▲confidence: Mid ({src})"

    # 4) 웹 검색
    if (wctx := _web_ctx(q)):
        ans, src = await _gate_llm(q, wctx)
        asyncio.create_task(_set_cached(_cache_key(q,wctx), ans))
        return f"{ans}\n\n▲confidence: Mid ({src})"

    # 5) 모델 온리
    ans, src = await _gate_llm(q, "")
    asyncio.create_task(_set_cached(ckey_blank, ans))
    return f"{ans}\n\n▲confidence: Low ({src})"

'''