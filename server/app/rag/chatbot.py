"""천안 도시재생지원센터 챗봇 – 로컬 문서 우선(data 디렉토리) → 퍼지 매칭 → 웹 검색 → LLM 기본 지식"""

from __future__ import annotations

import os
import textwrap
from typing import Tuple, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools import DuckDuckGoSearchRun

from rapidfuzz import fuzz, process            # 퍼지 검색 활용

from .prompt import PROMPT
from .retriever import get_retriever
from .reranker import rerank
from .verifier import fact_check

# ──────────────────── 프로그램 링크 추출 ─────────────────────────────
from .programs import get_all_aliases, get_program_by_alias
from .utils import classify_intent_and_extract_entity   

# ─────────────────── LLM 설정 ───────────────────────────────────────
_LLM = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0.2,
    top_p=0.9,
)
_SYS = SystemMessage(
    content=(
        "너는 천안 도시재생지원센터 전용 챗봇이야. "
        "모르는 내용은 최대한 찾아보고, 마지막까지 답을 만들어 줘. "
        "절대로 '모르겠습니다' 같은 말로 끝내지 마."
    )
)

# ─────────────── 환경 변수 파라미터 ────────────────────────────────
THRESH      = float(os.getenv("THRESH",      0.15))   # 로컬 재랭크 임계
TOP_K       = int(os.getenv("TOP_K",         4))      # 재랭크 후 사용할 문서 수
FUZZ_LIMIT  = int(os.getenv("FUZZ_LIMIT",    3))      # 퍼지 후보 개수
FUZZ_SCORE  = int(os.getenv("FUZZ_SCORE",    70))     # 퍼지 최소 점수(0~100)
SEARCH_HITS = int(os.getenv("SEARCH_HITS",   5))      # DuckDuckGo 결과 수

_SEARCH = DuckDuckGoSearchRun(backend="auto")

def _normalize_q(q: str) -> str:
    """질문 그대로 사용"""
    return q

def _local_ctx(q: str) -> Tuple[str, float]:
    raw = [d.page_content for d in get_retriever().get_relevant_documents(q)]
    docs, best = rerank(q, raw, top_n=TOP_K) if raw else ([], 0.0)
    ctx = "\n\n".join(textwrap.shorten(d, 400) for d in docs)
    return ctx, best

def _fuzzy_ctx(q: str) -> str:
    """편집거리 기반 유사 문서 추출 (RapidFuzz)"""
    vect_ret = get_retriever().retrievers[0]
    docs = vect_ret.vectorstore.docstore._dict.values()
    texts = [d.page_content for d in docs]
    pairs = process.extract(q, texts, scorer=fuzz.partial_ratio, limit=FUZZ_LIMIT)
    good = [item for item, score, _ in pairs if score >= FUZZ_SCORE]
    return "\n\n".join(textwrap.shorten(t, 400) for t in good)

def _web_ctx(q: str) -> str:
    """웹 검색 결과를 나열형 텍스트로 반환"""
    try:
        hits = _SEARCH.results(q, num_results=SEARCH_HITS)
    except Exception:
        return ""
    lines: list[str] = []
    for h in hits:
        txt = h.get("body") or h.get("snippet") or h.get("title", "")
        url = h.get("href") or h.get("url", "")
        lines.append(f"- {txt} (출처: {url})")
    return "\n".join(lines)


def _ask_llm(question: str, ctx: str | None) -> str:
    prompt = PROMPT.format(
        context=ctx or "해당 내용은 문서에 없음",
        question=question,
    )
    return _LLM.invoke([_SYS, HumanMessage(content=prompt)]).content.strip()

# def _program_link_ctx(q: str) -> Tuple[str | None, str | None]:
#     prog_name = extract_program_name(q)
#     if not prog_name:
#         return None, None
#     url = get_program_url(prog_name)
#     return prog_name, url

# ─────────────────── 메인 엔드포인트 ────────────────────────────────
def ask(question: str) -> str:
    # 0) 질문 그대로 사용
    norm_q = _normalize_q(question)
    print(f"[DEBUG] raw='{question}' → norm='{norm_q}'")

    # 1단계: LLM으로 의도와 핵심 키워드 추출
    intent_result = classify_intent_and_extract_entity(norm_q, _LLM)
    print(f"[DEBUG] intent_result={intent_result}")

    if intent_result.get("intent") == 'find_program_url':
        prog_name_keyword = intent_result.get("program_name")
        if prog_name_keyword:
            
            # 2단계: RapidFuzz로 가장 유사한 별칭(alias) 찾기
            all_aliases = get_all_aliases() # programs.py에서 모든 별칭 가져오기
            # extractOne이 (가장 비슷한 별칭, 유사도 점수, 인덱스)를 반환
            best_match, score, _ = process.extractOne(
                prog_name_keyword,
                all_aliases,
                scorer=fuzz.WRatio # WRatio가 유사도 계산에 효과적
            )

            print(f"[DEBUG] Keyword='{prog_name_keyword}', Best Match='{best_match}', Score={score:.2f}")

            # 3단계: 찾은 별칭으로 URL 가져오기 (유사도 75점 이상일 때만)
            if score >= 75:
                program_details = get_program_by_alias(best_match)
                if program_details:
                    url = program_details["url"]
                    # 정식 명칭을 찾기 위해 key를 역으로 탐색 (선택사항, 없어도 됨)
                    # 이 부분은 복잡하면 prog_name_keyword를 그대로 사용해도 괜찮습니다.
                    formal_name = best_match # 간단하게 일치한 별칭을 이름으로 사용

                    return (f"'{formal_name}' 정보는 아래 링크에서 바로 확인할 수 있습니다:\n\n"
                            f"[**{formal_name} 홈페이지 바로가기**]({url})\n\n"
                            f"▲confidence: Rule (program, score={score:.0f})")
            else:
                return (f"'{prog_name_keyword}'에 대한 정확한 프로그램 정보를 찾을 수 없습니다. "
                        f"조금 더 구체적인 이름으로 질문해주시겠어요?\n\n"
                        f"▲confidence: Rule (not found)")

    # --- 만약 위 `if` 문에서 아무것도 반환되지 않았다면, 아래 로직이 실행됨

    # 1) 로컬 벡터·BM25 검색 + Cross-Encoder 재랭크
    ctx, best = _local_ctx(norm_q)
    print(f"[DEBUG] local best={best:.3f}")

    # 1-a) 로컬 컨텍스트가 충분히 신뢰되면 바로 응답
    if ctx and best >= THRESH:
        ans = _ask_llm(norm_q, ctx)
        return f"{ans}\n\n▲confidence: High (local)"

    # 2) 퍼지 매칭 보강 (로컬 유사성)
    fuzzy = _fuzzy_ctx(norm_q)
    if fuzzy:
        ans = _ask_llm(norm_q, fuzzy)
        if fact_check(norm_q, ans):
            return f"{ans}\n\n▲confidence: Mid (fuzzy)"

    # 3) 웹 검색 보강 (로컬·퍼지 모두 없을 때)
    web_ctx = _web_ctx(norm_q)
    if web_ctx:
        # 웹 결과 전체를 이용해 상세하게 답변
        ans = _ask_llm(norm_q, web_ctx)
        return f"{ans}\n\n▲confidence: Mid (web)"

    # 4) LLM 자체 지식 (모두 실패 시)
    ans = _ask_llm(norm_q, "")
    return f"{ans}\n\n▲confidence: Low (model-only)"
