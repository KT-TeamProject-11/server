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

# ─────────────────── LLM 설정 ───────────────────────────────────────
_LLM = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0.2,
    top_p=0.9,
)
_SYS = SystemMessage(
    content=(
        "너는 천안 도시재생지원센터 전용 챗봇이야. "
        "정확하지 않은 질문이라도 최대한 유추해서 답변하고, "
        "확실하지 않은 정보는 '제가 알고 있는 범위에서 말씀드릴게요'처럼 부드럽게 표현해. "
        "절대로 '모르겠습니다' 또는 '답변할 수 없습니다' 같은 말로 끝내지 마."
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

# ─────────────── 룰 기반 즉답 ────────────────────────────────
def rule_based_answer(user_input: str) -> str | None:
    q = user_input.lower()

    # ▶ 신청 자격 질문 (→ 나도 가능해?)
    if any(kw in q for kw in ["신청할 수", "참여할 수", "될까요", "신청 가능할까요", "나", "저"]) and "투어" not in q:
        return (
            "도시재생 프로그램은 천안시에 거주하거나 관심 있는 시민 누구나 신청하실 수 있어요. "
            "프로그램에 따라 조건이 다를 수 있으니 안내 문구를 꼭 확인해주세요!"
        )

    # ▶ 현재 프로그램 질문
    if any(kw in q for kw in ["현재", "진행", "프로그램", "세미나", "지금 하고", "참여 가능한", "신청 가능한"]) and "투어" not in q:
        return (
            "현재 진행 중인 프로그램은 '로컬브랜딩 활용과 확산전략 정책 세미나'가 있습니다."
        )

    # ▶ 투어 신청 자격 질문
    if "투어" in q and any(kw in q for kw in ["신청", "자격", "누가", "가능", "할 수"]):
        return (
            "도시재생 투어는 천안시 도시재생사업에 관심 있는 시민 누구나 신청하실 수 있어요. "
            "또한 천안시 선진지 답사를 희망하는 외부 센터도 가능합니다."
        )

    return None


# ─────────────────── 메인 엔드포인트 ────────────────────────────────
def ask(question: str) -> str:
    # 🔹 (0) 룰 기반 우선 응답
    rule_answer = rule_based_answer(question)
    if rule_answer:
        return f"{rule_answer}\n\n▲confidence: Exact (rule-based)"

    # 0) 질문 그대로 사용
    norm_q = _normalize_q(question)
    print(f"[DEBUG] raw='{question}' → norm='{norm_q}'")

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
