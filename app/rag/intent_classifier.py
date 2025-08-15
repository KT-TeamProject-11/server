from __future__ import annotations
import re
from typing import Dict, Optional

from app.rag.textnorm import normalize_query, no_space
from app.rag.programs import (
    fuzzy_find_best_alias, fuzzy_find_best_tag, contains_program_keyword
)

# URL(페이지) 의도
_NAV_TRIGGER = re.compile(
    r"(어디서?\s*봐|어디서?\s*보|어디서?\s*확인|어디에\s*있|어딨|어디임|어딘지|URL|"
    r"주소\s*좀|주소\s*알려|URL\s*줘|url\s*줘|링크\s*줘|바로가기|페이지\s*주소|"
    r"홈페이지|사이트|페이지|경로|접속|다운로드|확인\s*가능|어디서\s*찾)",
    re.IGNORECASE,
)

# 설명/내용 의도
_INFO_TRIGGER = re.compile(
    r"(정의|무엇|뭐[야요]?|개요|내용|사업\s*내용|사업내용|목표|사업\s*목표|사업목표|"
    r"주요\s*사업|주요사업|구상도|절차|방법|신청\s*방법|모집|기간|일정|대상|자격|혜택|"
    r"장소|시간|수료|발표|심사|평가|운영|사업비|예산|비용|수강료|참가비|무료|유료)",
    re.IGNORECASE,
)

# 연락처/운영
_EMAIL_TRIGGER = re.compile(r"(이\s*메일|이멜|메일|e[-\s]*mail)", re.IGNORECASE)
_PHONE_TRIGGER = re.compile(
    r"(전화|번호|연락\s*처|연락처|문의\s*전화|콜센터|연락\s*하|연락\s*해야|연락\s*드리|"
    r"어디로\s*연락|문의는\s*어디로|문의\s*가능|문의\s*처|담당자|카카오톡|카톡|카톡\s*채널|kakao)",
    re.IGNORECASE,
)
_FAX_TRIGGER   = re.compile(r"(팩스|fax)", re.IGNORECASE)
_HOURS_TRIGGER = re.compile(r"(운영\s*시간|업무\s*시간|영업\s*시간|근무\s*시간|점심\s*시간)", re.IGNORECASE)

# 주소 키워드(명시적)
_ADDR_KEYWORDS = re.compile(r"(주소|위치|찾아오시는\s*길|오시는\s*길|지도|약도)", re.IGNORECASE)

# 숫자형 코스 별칭
_COURSE_NUM = re.compile(
    r"(?:(전문|일반)\s*코스\s*([0-9]+)|"
    r"(전문|일반)코스\s*([0-9]+)|"
    r"(전문|일반)\s*코스([0-9]+)|"
    r"코스\s*([0-9]+))",
    re.IGNORECASE,
)

def _extract_course_alias(q: str) -> Optional[str]:
    m = _COURSE_NUM.search(q)
    if not m:
        return None
    if m.group(1) and m.group(2):   kind, num = m.group(1), m.group(2)
    elif m.group(3) and m.group(4): kind, num = m.group(3), m.group(4)
    elif m.group(5) and m.group(6): kind, num = m.group(5), m.group(6)
    else:                           kind, num = None, m.group(7)
    kind = (kind or "").replace(" ", "")
    return f"{kind}코스 {num}".strip() if kind else None

def _detect_contact_type(q: str) -> Optional[str]:
    if _EMAIL_TRIGGER.search(q):   return "email"
    if _PHONE_TRIGGER.search(q):   return "phone"
    if _FAX_TRIGGER.search(q):     return "fax"
    if _HOURS_TRIGGER.search(q):   return "hours"
    # 주소/위치 계열 키워드가 있을 때만 address
    if _ADDR_KEYWORDS.search(q):   return "address"
    return None

def classify_intent_and_entity(text: str) -> Dict[str, Optional[str]]:
    """질문 → {intent, contact_type, program_name, tag}"""
    q = normalize_query(text)
    qns = no_space(q)

    alias_from_course = _extract_course_alias(q)
    alias = alias_from_course or (fuzzy_find_best_alias(q, min_score=80) or "")
    tag   = fuzzy_find_best_tag(q,   min_score=80)

    # 프로그램 + (주소/어디서/확인/링크/URL) → URL
    if contains_program_keyword(q) and (("주소" in q) or _NAV_TRIGGER.search(q)):
        return {"intent": "find_program_url", "contact_type": None, "program_name": alias or alias_from_course or "", "tag": tag}

    # 연락처(최우선)
    ctype = _detect_contact_type(q)
    if ctype:
        return {"intent": "ask_contact", "contact_type": ctype, "program_name": "", "tag": tag}

    # URL/내용
    wants_url  = bool(_NAV_TRIGGER.search(q) or _NAV_TRIGGER.search(qns))
    wants_info = bool(_INFO_TRIGGER.search(q))

    # 숫자 코스 패턴 + 주소/URL 힌트 → URL
    if alias_from_course and ("주소" in q or wants_url or "링크" in q.lower() or "url" in q.lower()):
        return {"intent": "find_program_url", "contact_type": None, "program_name": alias_from_course, "tag": tag}

    if wants_url or ("주소" in q and _ADDR_KEYWORDS.search(q)):
        return {"intent": "find_program_url", "contact_type": None, "program_name": alias or alias_from_course or "", "tag": tag}

    if wants_info:
        return {"intent": "ask_info", "contact_type": None, "program_name": alias or alias_from_course or "", "tag": tag}

    if (alias or alias_from_course) or tag:
        return {"intent": "ask_info", "contact_type": None, "program_name": alias or alias_from_course or "", "tag": tag}

    return {"intent": "general_question", "contact_type": None, "program_name": None, "tag": None}
