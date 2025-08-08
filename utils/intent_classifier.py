"""
룰 + KoBERT + (백업) LLM 하이브리드 의도·엔티티 분류기
----------------------------------------------------
- intent : {"find_program_url", "general_question"}
- program_name : 별칭(alias) 중 하나 또는 None
"""
from __future__ import annotations
import os, re, json
from functools import lru_cache
from typing import Dict, Optional, Tuple, List

import torch
from transformers import AutoTokenizer, BertForSequenceClassification  # ✅ 수정: AutoTokenizer 사용

from app.rag.programs import get_all_aliases
from .intent_prompt import INTENT_PROMPT_TEMPLATE  
from langchain_openai import ChatOpenAI            

# ───────────── 룰 기반 패턴 ─────────────
_RULE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "find_program_url": [
        re.compile(r"(어디|위치|오[는시]는? 길|링크|바로가기|신청|참여|접수|가는 ?법)"),
        re.compile(r"(센터소개|사업소개|커뮤니티|투어|프로그램 신청|공지|아카이브)"),
    ]
}
_ALIASES = sorted(get_all_aliases(), key=len, reverse=True)  # 긴 별칭 우선

def _rule_intent(text: str) -> Optional[str]:
    for intent, regs in _RULE_PATTERNS.items():
        if all(reg.search(text) for reg in regs):
            return intent
    return None

def _rule_program(text: str) -> Optional[str]:
    for alias in _ALIASES:
        if alias in text:
            return alias
    return None

# ───────────── KoBERT 분류기 ─────────────
@lru_cache(maxsize=1)
def _load_kobert():
    # HF 허브에 반드시 존재하는 기본 모델로 설정
    model_id = os.getenv("CLASSIFY_MODEL_ID", "skt/kobert-base-v1")
    tok = AutoTokenizer.from_pretrained(model_id)  # ✅ AutoTokenizer로 변경
    mdl = BertForSequenceClassification.from_pretrained(model_id, num_labels=2)  # 0:url,1:general
    device = "cuda" if torch.cuda.is_available() else "cpu"
    mdl.to(device).eval()
    return tok, mdl, device

def _kobert_intent(text: str) -> Tuple[Optional[str], float]:
    try:
        tok, mdl, device = _load_kobert()
    except Exception:
        # 모델 로드 실패 시 KoBERT 단계 건너뛰기
        return None, 0.0

    inputs = tok(text, return_tensors="pt", truncation=True, max_length=128)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.inference_mode():
        logits = mdl(**inputs).logits
    probs = torch.softmax(logits, dim=-1).squeeze().tolist()
    intent = "find_program_url" if probs[0] > probs[1] else "general_question"
    return intent, float(max(probs))

# ───────────── LLM 백업 ─────────────
_BACKUP_LLM = ChatOpenAI(model=os.getenv("OPENAI_MODEL"), temperature=0)

def _llm_intent_prog(text: str) -> Dict[str, Optional[str]]:
    from langchain_core.messages import SystemMessage, HumanMessage
    sys = SystemMessage(content=INTENT_PROMPT_TEMPLATE)
    resp = _BACKUP_LLM.invoke([sys, HumanMessage(content=text)])
    try:
        return json.loads(resp.content)
    except json.JSONDecodeError:
        return {"intent": "general_question", "program_name": None}

# ───────────── 페사드 함수 ─────────────
def classify_intent_and_extract_entity(text: str) -> Dict[str, Optional[str]]:
    """
    1) 룰 베이스
    2) KoBERT (확률 ≥ 0.65)
    3) LLM 백업
    """
    # 1) 룰
    intent = _rule_intent(text)
    prog   = _rule_program(text) if intent == "find_program_url" else None
    if intent:
        return {"intent": intent, "program_name": prog}

    # 2) KoBERT
    intent_kb, conf = _kobert_intent(text)
    if intent_kb == "find_program_url" and conf >= 0.65:
        prog = _rule_program(text)
        if prog:
            return {"intent": intent_kb, "program_name": prog}

    # 3) 최종 LLM 백업
    return _llm_intent_prog(text)
