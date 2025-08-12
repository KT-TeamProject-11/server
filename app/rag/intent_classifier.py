# app/rag/intent_classifier.py
import re
from typing import Dict, Optional
from app.rag.programs import fuzzy_find_best_alias, fuzzy_find_best_tag

_RULE_FIND_URL = [
    re.compile(r"(어디|위치|오[는시]는?길|링크|바로가기|신청|참여|접수|가는 ?법)"),
    re.compile(r"(센터소개|사업소개|커뮤니티|투어|프로그램 ?신청|공지|아카이브|도시재생)"),
]

def _rule_match(text: str) -> bool:
    return all(r.search(text) for r in _RULE_FIND_URL)

def classify_intent_and_entity(q: str) -> Dict[str, Optional[str]]:
    q = (q or "").strip()
    if not q:
        return {"intent": "general_question", "program_name": None, "tag": None}
    # 1) 룰: 특정 페이지/링크 의도
    if _rule_match(q):
        return {
            "intent": "find_program_url",
            "program_name": fuzzy_find_best_alias(q) or "",
            "tag": fuzzy_find_best_tag(q)
        }
    # 2) 일반 질문
    return {"intent": "general_question", "program_name": None, "tag": None}
