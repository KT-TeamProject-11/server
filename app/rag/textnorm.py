# app/rag/textnorm.py
from __future__ import annotations
import re
import unicodedata
from typing import List

# 한국어/영문 질의 공통 정규화기

_ZWSP = "\u200b\u200c\u200d\u2060"
_PUNCS = r"""!"#$%&'()*+,./:;<=>?@[\]^_`{|}~“”‘’・·…"""

# '어디서봐', '주소좀' 처럼 붙여 쓰는 경우 방지용
_JOIN_PATTS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"(어디|어딘|어디임)\s*(서|에서)?\s*(봐|보|확인)"), "어디서 봐"),
    (re.compile(r"(확인)\s*(가능)"), "확인 가능"),
    (re.compile(r"(주소)\s*(좀|좀요|알려|알려줘)"), "주소 좀"),
    (re.compile(r"(링크)\s*(줘|달아|알려)"), "링크 줘"),
    (re.compile(r"(url)\s*(줘|달아|알려)", re.IGNORECASE), "URL 줘"),
]

def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")

def strip_noise(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    for ch in _ZWSP:
        s = s.replace(ch, " ")
    s = re.sub(rf"[{re.escape(_PUNCS)}]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def normalize_query(s: str) -> str:
    """질의 해석용: 대소문자/구두점/제로폭/붙임표 통일 + 흔한 붙여쓰기 복원"""
    s = nfkc(s)
    s = strip_noise(s.lower())
    for p, rep in _JOIN_PATTS:
        s = p.sub(rep, s)
    return s

def no_space(s: str) -> str:
    """비교용: 공백 완전 제거 버전(띄어쓰기 무시 매칭)"""
    return re.sub(r"\s+", "", s or "")

def make_alias_variants(phrase: str) -> List[str]:
    """별칭 하나로부터, 띄어쓰기·케이싱 다양한 변형을 만들어 풀에 넣는다."""
    if not phrase:
        return []
    base = nfkc(phrase)
    cand = {base, base.lower(), strip_noise(base), strip_noise(base.lower())}
    # 공백제거 버전도 추가
    cand.add(no_space(base))
    return list(cand)
