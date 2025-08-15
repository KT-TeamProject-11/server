from __future__ import annotations
from typing import List, Optional, Tuple, Dict
import re
from rapidfuzz import fuzz

# === 1) 기존 FAQ 데이터 ===
FAQ_ENTRIES = [
    {
        "qs": [
            "천안시 도시재생지원센터는 어떤 곳인가요",
            "도시재생지원센터는 어떤 곳",
            "센터는 어떤 곳",
            "센터 역할",
            "센터 소개"
        ],
        "answer": (
            "저희 센터는 천안시의 도시재생 사업을 총괄 지원하는 중간지원조직입니다. "
            "주민과 행정기관 사이의 가교 역할을 하며, 주민 주도의 성공적인 도시재생이 이루어지도록 돕고 있습니다."
        ),
    },
    {
        "qs": [
            "센터 운영 시간과 위치가 궁금해요",
            "운영 시간",
            "운영시간",
            "위치",
            "주소",
        ],
        "answer": (
            "저희 센터는 평일 오전 9시부터 오후 6시까지 운영됩니다. "
            "주소는 천안시 은행길 15, 5층이며, 지도를 참고해 방문하실 수 있습니다."
        ),
    },
    {
        "qs": [
            "센터에 연락하려면 어떻게 해야 하나요",
            "연락처",
            "전화번호",
            "문의 방법",
        ],
        "answer": (
            "대표전화 041-417-4061~5로 연락 주시거나, 홈페이지 '온라인 문의' 게시판을 이용해 주시면 신속하게 답변드리겠습니다."
        ),
    },
    {
        "qs": [
            "도시재생이란 무엇인가요",
            "도시재생이 뭐야",
            "도시재생 쉽게 설명",
        ],
        "answer": (
            "도시재생은 낡고 쇠퇴한 구도심에 새로운 활력을 불어넣는 활동입니다. "
            "단순히 건물을 새로 짓는 재개발과 달리, 지역의 역사와 문화를 보존하면서 주민들의 삶의 질을 높이는 것을 목표로 합니다."
        ),
    },
    {
        "qs": [
            "천안시에서는 현재 어떤 도시재생 사업을 하고 있나요",
            "천안시 도시재생 사업 현황",
            "어떤 사업을 하나요",
        ],
        "answer": (
            "현재 천안시에서는 크게 오룡지구와 역세권지구를 중심으로 도시재생사업을 추진하고 있습니다. "
            "각 지역의 특성에 맞는 맞춤형 사업을 통해 원도심 활성화를 위해 노력하고 있습니다."
        ),
    },
    {
        "qs": [
            "우리 동네도 도시재생 사업 대상이 될 수 있나요",
            "우리동네 사업 대상",
            "도시재생 대상 되는지",
        ],
        "answer": (
            "도시재생 사업은 주민들의 적극적인 참여와 의지가 가장 중요합니다. "
            "사업 추진을 원하시면, 먼저 주민 공동체를 구성하고 저희 센터와 상담을 진행하시는 것을 추천합니다."
        ),
    },
    {
        "qs": [
            "사업 진행 상황은 어디서 확인할 수 있나요",
            "진행 상황 확인",
            "최신 소식 어디서 보나요",
        ],
        "answer": (
            "가장 최신 소식은 저희 센터 홈페이지 '도시재생+'의 공지사항(https://www.cheonanurc.or.kr/new)이나 "
            "아카이브 내 ‘도시재생뉴스’(https://www.cheonanurc.or.kr/35), 확인 하실 수 있습니다."
        ),
    },
    {
        "qs": [
            "도시재생 사업에 주민은 어떻게 참여할 수 있나요",
            "주민 참여 방법",
            "주민은 어떻게 참여",
        ],
        "answer": (
            "주민설명회, 공청회, 워크숍 등 다양한 프로그램에 직접 참여하여 의견을 제시하실 수 있습니다. "
            "또한, '주민공모사업'을 통해 직접 아이디어를 제안하고 사업을 실행해 볼 수도 있습니다."
        ),
    },
    {
        "qs": [
            "도시재생 투어는 누구나 신청할 수 있나요",
            "투어 대상",
            "투어 누구나 신청",
        ],
        "answer": (
            "네, 도시재생에 관심 있는 기관, 단체, 개인 누구나 신청 가능합니다. "
            "천안시 도시재생 사업 현장을 직접 둘러보며 생생한 이야기를 들을 수 있는 좋은 기회입니다."
        ),
    },
    {
        "qs": [
            "도시재생 투어 신청은 어떻게 하나요",
            "투어 신청 방법",
            "투어 신청",
        ],
        "answer": (
            "먼저 전화(041-417-4061~5)로 희망 날짜와 시간을 협의하신 후, 공문을 통해 공식 접수해 주시면 됩니다."
        ),
    },
    {
        "qs": [
            "공문은 어떻게 작성해야 하나요",
            "투어 공문 양식",
            "공문 작성",
        ],
        "answer": (
            "공문 수신자는 국립공주대학교 산학협력단으로, (경유) 천안시도시재생지원센터를 명시해주세요.\n"
            "제목: 천안시 도시재생지원센터 도시재생투어 신청\n"
            "본문 필수 기재 내용:\n"
            "- 1) 희망 일시\n"
            "- 2) 신청 투어 내용 (예: 특강, 현장투어[남산 or 역세권])\n"
            "- 3) 담당자 연락처\n"
            "- 4) 참가 인원 수\n"
            "붙임 문서: 현장 투어 계획서 1부"
        ),
    },
    {
        "qs": [
            "투어 비용은 어떻게 되나요",
            "투어 비용",
            "비용 안내",
        ],
        "answer": (
            "투어 비용은 참여 인원, 특강 포함 여부 등에 따라 달라질 수 있습니다. "
            "신청 접수 후 담당자와 협의를 통해 진행되며, 기관의 내부 규정에 따라 지급해주시면 됩니다."
        ),
    },
]

# === 2) 정규화 ===
_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")
_ENDING = re.compile(r"(인가요|인가|이란|이야|예요|에요|요|\?)$")

_SYNONYMS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"이\s*메일|e[-\s]*mail", re.IGNORECASE), "메일"),
    (re.compile(r"연락\s*처|전화\s*번호", re.IGNORECASE), "전화"),
    (re.compile(r"오시는\s*길|약도", re.IGNORECASE), "오시는길"),
    (re.compile(r"홈\s*페이지|누리집|사이트", re.IGNORECASE), "홈페이지"),
    (re.compile(r"도시재생\s*선도\s*사업", re.IGNORECASE), "도시재생선도사업"),
]

def _normalize(s: str) -> str:
    if not s:
        return ""
    t = s.strip().lower()
    t = _PUNCT.sub(" ", t)
    for pat, repl in _SYNONYMS:
        t = pat.sub(repl, t)
    t = _ENDING.sub("", t)
    t = _WS.sub(" ", t)
    return t.strip()

# === 3) intent 힌트 ===
_CONTACT_PAT  = re.compile(r"(연락|문의|전화|번호|메일|이메일)", re.IGNORECASE)
_COST_PAT     = re.compile(r"(비용|가격|요금|수강료|참가비|투어비)", re.IGNORECASE)
_SCHEDULE_PAT = re.compile(r"(일정|날짜|시간|기간|운영\s*시간|업무\s*시간)", re.IGNORECASE)
_ADDRESS_PAT  = re.compile(r"(주소|위치|오시는길|지도|약도|층|동)", re.IGNORECASE)

def _guess_intent_hint(texts: List[str], answer: str) -> str:
    blob = " ".join(texts + [answer or ""])
    if _CONTACT_PAT.search(blob):  return "contact"
    if _COST_PAT.search(blob):     return "cost"
    if _SCHEDULE_PAT.search(blob): return "schedule"
    if _ADDRESS_PAT.search(blob):  return "address"
    return "info"

# === 4) 인덱스 ===
_CANDS: List[Dict[str, str]] = []
for item in FAQ_ENTRIES:
    ans = str(item["answer"])
    intent_hint = _guess_intent_hint(item.get("qs", []), ans)
    for q in item["qs"]:
        _CANDS.append({
            "q_raw": q,
            "q_norm": _normalize(q),
            "answer": ans,
            "intent_hint": intent_hint,
        })

# === 5) 매칭 ===
def _score(a: str, b: str) -> int:
    ts = fuzz.token_set_ratio(a, b)
    pr = fuzz.partial_ratio(a, b)
    return int(0.6 * ts + 0.4 * pr)

def find_faq_answer(
    query: str,
    hard_threshold: int = 90,
    soft_threshold: int = 85,
    preferred_intent: Optional[str] = None,
    blocked_intents: Optional[List[str]] = None,
) -> Optional[str]:
    qn = _normalize(query or "")
    if not qn:
        return None

    pool = list(_CANDS)
    if preferred_intent:
        filtered = [c for c in pool if c.get("intent_hint") == preferred_intent]
        if filtered:
            pool = filtered

    if blocked_intents:
        blocked = set(blocked_intents)
        pool = [c for c in pool if c.get("intent_hint") not in blocked]

    if not pool:
        return None

    for c in pool:
        cn = c["q_norm"]
        if cn and (cn in qn or qn in cn):
            return c["answer"]

    best: Optional[Dict[str, str]] = None
    best_score = -1
    for c in pool:
        s = _score(qn, c["q_norm"])
        if s > best_score:
            best_score = s
            best = c

    if best and best_score >= hard_threshold:
        return best["answer"]
    if best and best_score >= soft_threshold:
        return best["answer"]

    return None
