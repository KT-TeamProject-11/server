from __future__ import annotations

import html, re, unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── 정규화 유틸
_POLITE_SUFFIX = re.compile(r"(좀|조금|구체적으로|자세히|정확히|빨리|빠르게|바로|지금|가능해\??|가능할까요\??|가능한가요\??|한번|한 번)$")
_ENDING_NOISE  = re.compile(r"(은|는|이|가|을|를|으로|에서|에|에게|한테|의|이[야요]?$|인가요\??$|인가요$|인가$|뭐[야요]?$|알려줘(요)?$|알려[ ]?주세요$|가르쳐줘(요)?$|보여줘(요)?$|찾아줘(요)?$)")
_PUNCT         = re.compile(r"[?!.,;:~…·/\\]+")
_WS            = re.compile(r"\s+")
# 문장 끝 '어디/확인/보'류 요청 꼬리 (정규화에서 제거용)
_REQ_TRAILER   = re.compile(
    r"(링크|url|주소|홈페이지|페이지|사이트|경로|바로가기|위치"
    r"|어디(서|에서)? ?(봐|보|확인|찾아|들어가|신청|하는지|가능|할 수)([는가요지]*)?"
    r"|어디(서|에서)?"
    r"|하는[가지요건]*"
    r"|알려[줘요]?"
    r"|확인[해]?[줘요]?"
    r"|신청[은가요]?"
    r")$",
    re.IGNORECASE,
)
_NUM_EXTRACT   = re.compile(
    r"\b(\d{2,3})\b|/(new|41|64|78|97|98|99|100|24|79|101|25|131|133|128|68|27|71|70|72|74|75|73|140|92|95|121|36|35|37|108)\b",
    re.IGNORECASE,
)

def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")

def _normalize(s: str, *, preserve_request: bool = False) -> str:
    """preserve_request=True면 '어디/확인/주소' 같은 요청어를 제거하지 않음."""
    if not s: return ""
    s = _nfkc(s).strip()
    s = _PUNCT.sub(" ", s)                          # 1) 문장부호 제거
    s = _POLITE_SUFFIX.sub("", s)                   # 2) 공손어미 제거
    if not preserve_request:
        s = _ENDING_NOISE.sub("", s)
        s = _REQ_TRAILER.sub("", s)                 # 3) 요청 꼬리 제거
    s = _WS.sub(" ", s).strip().lower()             # 4) 공백 정리
    return s

def _anchor(url: str, label: Optional[str] = None) -> str:
    u = url if url.startswith(("http://", "https://")) else f"https://{url}"
    return f'<a href="{html.escape(u)}" target="_blank" rel="noopener noreferrer">{html.escape(label or u)}</a>'

def _tokenize(s: str, *, preserve_request: bool = False) -> List[str]:
    s = _normalize(s, preserve_request=preserve_request)
    return s.split() if s else []

# ── 동의어 / 기본 사전
SYN: Dict[str, str] = {
    # 플랫폼
    "인스타": "instagram","인스타그램":"instagram","insta":"instagram","ig":"instagram",
    "sns":"instagram",
    "유튜브":"youtube","yt":"youtube","youtube":"youtube",
    "밴드":"band","band":"band",
    "블로그":"blog","blog":"blog","네이버":"blog","naver":"blog",
    # 섹션
    "센터소개":"센터소개","소개":"센터소개",
    "사업소개":"사업소개","사업":"사업소개",
    "도시재생+":"도시재생+","도시재생플러스":"도시재생+","재생+":"도시재생+",
    "아카이브":"아카이브","자료실":"아카이브","자료":"아카이브",
    "커뮤니티":"커뮤니티","커뮤":"커뮤니티",
    # 하위 기능
    "오시는길":"오시는길","오시는":"오시는길","찾아오시는길":"오시는길","찾아오는길":"오시는길",
    "위치":"오시는길","지도":"오시는길","약도":"오시는길",
    "프로그램":"프로그램","신청":"프로그램신청","접수":"프로그램신청","모집":"프로그램신청",
    "참가신청":"프로그램신청","신청페이지":"프로그램신청",
    "도시재생투어":"투어","투어":"투어","현장투어":"투어","tour":"투어",
    "일반코스":"일반코스","전문코스":"전문코스","코스":"코스",
    # 자연어 → 코스 동의어
    "전문투어":"전문코스","일반투어":"일반코스","투어코스":"코스",
    # 지명
    "센터":"센터","지원센터":"센터",
    "천안역세권":"역세권","역세권":"역세권",
    "오룡":"오룡지구","오룡지구":"오룡지구",
    "봉평":"봉평지구","봉평지구":"봉평지구","봉명":"봉평지구","봉명지구":"봉평지구",
    "남산지구":"남산지구","혁신지구":"혁신지구",
    "원성2지구":"원성2지구","원성2지규":"원성2지구","원성 2지구":"원성2지구",
}
KNUM = {"일":"1","이":"2","삼":"3","하나":"1","둘":"2","셋":"3"}

SECTION_KEYS = ["센터소개","사업소개","도시재생+","커뮤니티","아카이브"]
# 페이지 요구 힌트(브로드캐스트 트리거)
BROADCAST_HINTS = {
    "목록","전체","전부","정리","한번에","한눈에","한","목차","메뉴","링크","페이지","주소","url",
    "주소줄래", "링크줘",  # ← 쉼표 누락 버그 수정
    "어디","어디서","어디에서","어디서봐","어디서보","어디서확인","확인","확인해","확인하지","확인할까","찾아","찾아봐",
    # 보강
    "주소알려줘","주소요청","url줘","url좀","바로가기","접속경로"
}
GENERIC_IGNORE = {"센터","지원센터","도시재생","천안","천안시"}

def _canon_tokens(tokens: List[str]) -> List[str]:
    out=[]
    for t in tokens:
        if t in KNUM: out.append(KNUM[t]); continue
        out.append(SYN.get(t,t))
    return out

_COURSE_RE = re.compile(r"(일반|전문)?\s*코스\s*([0-9일이삼])", re.IGNORECASE)
def _extract_course(tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
    s = " ".join(tokens); m = _COURSE_RE.search(s)
    if not m: return None, None
    kind = (m.group(1) or "").replace(" ","")
    num  = KNUM.get(m.group(2), m.group(2))
    if kind and kind.lower() in ("일반","전문"):
        kind = "일반코스" if kind=="일반" else "전문코스"
    return kind, num

# ── 데이터 모델
@dataclass
class LinkItem:
    url: str
    label: Optional[str] = None

@dataclass
class UrlEntry:
    q: str
    title: str
    answer: str
    links: List[LinkItem]
    aliases: List[str] = field(default_factory=list)
    page_ids: List[str] = field(default_factory=list)
    _token_profiles: List[List[str]] = field(default_factory=list, repr=False)
    def to_html(self) -> str:
        parts=[]
        if self.title: parts.append(f"<strong>{html.escape(self.title)}</strong><br><br>")
        if self.answer: parts.append(html.escape(self.answer))
        if self.links:
            parts.append("<br><br><ul>")
            for li in self.links:
                parts.append(f"<li>{_anchor(li.url, li.label or li.url)}</li>")
            parts.append("</ul>")
        return "".join(parts)

@dataclass
class UrlResult:
    html: str
    hits: List[UrlEntry]

# ── 매핑
ENTRIES: List[UrlEntry] = [
    # 메인
    UrlEntry("메인","천안도시재생지원센터 메인","센터 메인 페이지입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/","메인 페이지")],
             aliases=["홈","홈페이지","센터 홈페이지","천안도시재생 홈페이지","메인 페이지","main"]),
    # Instagram
    UrlEntry("인스타그램 도시재생지원센터","Instagram — 천안시 도시재생지원센터","공식 인스타그램 계정입니다.",
             [LinkItem("https://www.instagram.com/cheonan_urc/?hl=ko","cheonan_urc")],
             aliases=["인스타 센터","센터 인스타","인스타그램 센터","cheonan_urc","인스타 도시재생지원센터","insta cheonan_urc","sns"]),
    UrlEntry("인스타그램 천안역세권 도시재생현장지원센터","Instagram — 천안역세권 도시재생현장지원센터","천안역세권 현장지원센터 인스타그램입니다.",
             [LinkItem("https://www.instagram.com/cheonan.want/?hl=ko","cheonan.want")],
             aliases=["인스타 역세권","역세권 인스타","천안역세권 인스타","cheonan.want", "sns"]),
    UrlEntry("인스타그램 오룡지구 도시재생현장지원센터","Instagram — 오룡지구 도시재생현장지원센터","오룡지구 현장지원센터 인스타그램입니다.",
             [LinkItem("https://www.instagram.com/cheonan_base/","cheonan_base")],
             aliases=["인스타 오룡","오룡 인스타","오룡지구 인스타","cheonan_base", "sns"]),
    # Blog
    UrlEntry("블로그 천안도시지원센터","블로그 — 천안도시지원센터","센터 네이버 블로그입니다.",
             [LinkItem("https://blog.naver.com/urc-cheonan","urc-cheonan")],
             aliases=["센터 블로그","천안도시재생 블로그","urc-cheonan 블로그","네이버 블로그 센터"]),
    UrlEntry("블로그 봉명지구 도시재생 현장 지원센터","블로그 — 봉명지구 도시재생 현장 지원센터","봉명지구 현장지원센터 네이버 블로그입니다.",
             [LinkItem("https://blog.naver.com/tongdol2020","tongdol2020")],
             aliases=["블로그 봉명지구","봉명 블로그","tongdol2020","봉명지구 블로그"]),
    # YouTube
    UrlEntry("유튜브 천안도시재생지원센터","YouTube — 천안도시재생지원센터","센터 공식 유튜브 채널입니다.",
             [LinkItem("https://www.youtube.com/channel/UCnmu-XM_ssRWVnwmCUVmFGg","YouTube 채널")],
             aliases=["유튜브 센터","센터 유튜브","youtube 센터","yt 센터"]),
    UrlEntry("유튜브 천안역세권 도시재생현장지원센터","YouTube — 천안역세권 도시재생현장지원센터","(요청 매핑 그대로) 해당 항목은 아래 링크로 연결됩니다.",
             [LinkItem("https://www.band.us/band/86255676","Band (제공된 링크)")],
             aliases=["유튜브 역세권","역세권 유튜브","youtube 천안역세권"]),
    # Band
    UrlEntry("밴드 천안도시재생지원센터","Band — 천안도시재생지원센터","센터 공식 밴드입니다.",
             [LinkItem("https://www.band.us/band/86255676","Band")],
             aliases=["밴드 센터","센터 밴드","band 센터","밴드"]),
    # ── 센터소개
    UrlEntry("센터소개 인사말", "센터소개 > 인사말", "센터 운영 철학과 환영 인사를 담은 인사말 페이지입니다.",
         [LinkItem("https://www.cheonanurc.or.kr/24", "인사말")],
         aliases=["인사말", "greeting"], page_ids=["24"]),

    UrlEntry("센터소개 목표와비전", "센터소개 > 목표와 비전", "천안시 도시재생의 비전과 센터의 핵심 목표를 안내합니다.",
         [LinkItem("https://www.cheonanurc.or.kr/79", "목표와 비전")],
         aliases=["목표와 비전", "비전", "목표"], page_ids=["79"]),

    UrlEntry("센터소개 센터 연혁", "센터소개 > 센터 연혁", "천안시 도시재생지원센터의 주요 연혁과 발전 과정을 소개합니다.",
         [LinkItem("https://www.cheonanurc.or.kr/101", "센터 연혁")],
         aliases=["연혁", "센터연혁"], page_ids=["101"]),

    UrlEntry("센터소개 조직 및 담당", "센터소개 > 조직 및 담당", "센터의 전체 조직 구성과 담당자 정보는 아래 링크에서 확인하실 수 있습니다.",
         [LinkItem("https://www.cheonanurc.or.kr/25", "조직 및 담당")],
         aliases=["조직도", "담당자", "조직", "센터조직", "구성", "팀", "조직구성", "인력", "부서", "센터장", "사무국장", "팀장", "책임"], page_ids=["25"]),

    UrlEntry("센터소개 오시는길 천안시 도시재생지원센터", "센터소개 > 오시는길 > 천안시 도시재생지원센터", "천안시 도시재생지원센터 방문을 위한 위치 안내입니다.",
         [LinkItem("https://www.cheonanurc.or.kr/131", "오시는길(센터)")],
         aliases=["오시는길 센터", "센터 오시는길", "주소 센터", "위치 센터", "찾아오시는길 센터", "주소"], page_ids=["131"]),

    UrlEntry("센터소개 오시는길 봉평지구 도시재생현장지원센터", "센터소개 > 오시는길 > 봉평지구 도시재생현장지원센터", "봉평지구 도시재생 현장지원센터 방문 위치 안내입니다.",
         [LinkItem("https://www.cheonanurc.or.kr/133", "오시는길(봉평지구)")],
         aliases=["오시는길 봉평지구", "봉평 오시는길", "봉명 오시는길", "위치 봉평", "주소 봉평"], page_ids=["133"]),

    UrlEntry("센터소개 오시는길 오룡지구 도시재생현장지원센터", "센터소개 > 오시는길 > 오룡지구 도시재생현장지원센터", "오룡지구 도시재생 현장지원센터 방문 위치 안내입니다.",
         [LinkItem("https://www.cheonanurc.or.kr/128", "오시는길(오룡지구)")],
         aliases=["오시는길 오룡지구", "오룡 오시는길", "위치 오룡", "주소 오룡"], page_ids=["128"]),
    # ── 사업소개
    UrlEntry("사업소개 천안 도시재생 총괄 사업현황","사업소개 > 천안 도시재생 총괄 사업현황","천안 도시재생 총괄 사업현황입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/68","총괄 사업현황")],
             aliases=["총괄 사업현황","도시재생 총괄"], page_ids=["68"]),
    UrlEntry("사업소개 도시재생선도사업","사업소개 > 도시재생선도사업","천안시의 도시재생 선도사업 추진 현황을 소개합니다.",
             [LinkItem("https://www.cheonanurc.or.kr/27","도시재생선도사업")],
             aliases=["선도사업"], page_ids=["27"]),
    UrlEntry("사업소개 천안역세권 도시재생사업","사업소개 > 천안역세권 도시재생사업","천안역세권 도시재생사업의 계획 및 주요 내용을 안내합니다.",
             [LinkItem("https://www.cheonanurc.or.kr/71","역세권 도시재생사업")],
             aliases=["천안역세권 사업","역세권 사업"], page_ids=["71"]),
    UrlEntry("사업소개 남산지구 도시재생사업","사업소개 > 남산지구 도시재생사업","남산지구 도시재생사업의 추진 내용과 대상지를 소개합니다.",
             [LinkItem("https://www.cheonanurc.or.kr/70","남산지구 도시재생사업")],
             aliases=["남산지구 사업"], page_ids=["70"]),
    UrlEntry("사업소개 봉평지구 도시재생사업","사업소개 > 봉평지구 도시재생사업","봉평지구 도시재생사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/72","봉평지구 도시재생사업")],
             aliases=["봉평지구 사업","봉명지구 사업"], page_ids=["72"]),
    UrlEntry("사업소개 오룡지구 도시재생사업","사업소개 > 오룡지구 도시재생사업","오룡지구 도시재생사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/74","오룡지구 도시재생사업")],
             aliases=["오룡지구 사업","오룡 사업"], page_ids=["74"]),
    UrlEntry("사업소개 천안역세권 혁신지구 도시재생사업","사업소개 > 천안역세권 혁신지구 도시재생사업","천안역세권 혁신지구 도시재생사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/75","역세권 혁신지구 도시재생사업")],
             aliases=["혁신지구 사업","천안역세권 혁신지구"], page_ids=["75"]),
    UrlEntry("사업소개 오룡지구 민-관 협력형 도시재생 리츠사업","사업소개 > 오룡지구 민-관 협력형 도시재생 리츠사업","오룡지구 민·관 협력형 도시재생 리츠사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/73","오룡지구 리츠사업")],
             aliases=["오룡 리츠사업","민관 협력형 리츠","리츠사업"], page_ids=["73"]),
    UrlEntry("사업소개 원성2지규 뉴:빌리지 사업","사업소개 > 원성2지규 뉴:빌리지 사업","원성2지규 뉴:빌리지 사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/140","원성2지규 뉴:빌리지")],
             aliases=["뉴빌리지","원성2지구 뉴빌리지","원성2지규","원성2지구"], page_ids=["140"]),
    # ── 커뮤니티
    UrlEntry("커뮤니티 천안시 도시재생지원센터","커뮤니티 > 천안시 도시재생지원센터","센터 커뮤니티 게시판입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/92","커뮤니티(센터)")],
             aliases=["커뮤니티 센터","커뮤 센터"], page_ids=["92"]),
    UrlEntry("커뮤니티 봉명지구 도시재생 현장지원센터","커뮤니티 > 봉명지구 도시재생 현장지원센터","봉명지구 커뮤니티 게시판입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/95","커뮤니티(봉명지구)")],
             aliases=["커뮤니티 봉명지구","봉명 커뮤니티","봉평 커뮤니티"], page_ids=["95"]),
    UrlEntry("커뮤니티 오룡지구 도시재생현장지원센터","커뮤니티 > 오룡지구 도시재생현장지원센터","오룡지구 커뮤니티 게시판입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/121","커뮤니티(오룡지구)")],
             aliases=["커뮤니티 오룡지구","오룡 커뮤니티"], page_ids=["121"]),
    # ── 도시재생+
    UrlEntry("도시재생플러스 공지사항","도시재생+ > 공지사항","센터의 공지사항, 채용, 기관소식 등 전체 알림 내용을 확인할 수 있습니다.",
             [LinkItem("https://www.cheonanurc.or.kr/new","공지사항(new)")],
             aliases=["도시재생+ 공지사항","공지사항","공지","채용공고","유관기관 공지"], page_ids=["new"]),
    UrlEntry("도시재생플러스 센터 프로그램 신청","도시재생+ > 센터 프로그램 신청","센터에서 운영하는 프로그램 신청과 모집 안내를 한눈에 확인하실 수 있습니다.",
             [LinkItem("https://www.cheonanurc.or.kr/41","센터 프로그램 신청")],
             aliases=["프로그램 신청","센터 프로그램","참여 프로그램","도시재생+ 프로그램 신청","신청 페이지","접수 페이지","모집 안내"], page_ids=["41"]),
    UrlEntry("도시재생플러스 도시재생투어","도시재생+ > 도시재생투어","천안시 도시재생에 관심 있는 분이라면 누구나 참여할 수 있는 투어입니다. 함께해보세요!",
             [LinkItem("https://www.cheonanurc.or.kr/64","도시재생투어")],
             aliases=["도시재생 투어","투어 안내","현장투어"], page_ids=["64"]),
    UrlEntry("도시재생플러스 도시재생투어 일반코스1","도시재생+ > 도시재생투어 > 일반코스1","도시재생의 기본 개념과 실제 현장을 둘러보는 일반코스 1 입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/78","일반코스1")],
             aliases=["일반코스 1","일반 코스 1","코스1 (일반)","투어 일반코스1"], page_ids=["78"]),
    UrlEntry("도시재생플러스 도시재생투어 일반코스2","도시재생+ > 도시재생투어 > 일반코스2","도시재생의 기본 개념과 실제 현장을 둘러보는 일반코스 2 입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/97","일반코스2")],
             aliases=["일반코스 2","일반 코스 2","코스2 (일반)","투어 일반코스2"], page_ids=["97"]),
    UrlEntry("도시재생플러스 도시재생투어 전문코스1","도시재생+ > 도시재생투어 > 전문코스1","천안 도시재생 주요 지구를 중심으로 구체적인 사례를 둘러보는 전문코스 1 입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/98","전문코스1")],
             aliases=["전문코스 1","전문 코스 1","코스1 (전문)","투어 전문코스1"], page_ids=["98"]),
    UrlEntry("도시재생플러스 도시재생투어 전문코스2","도시재생+ > 도시재생투어 > 전문코스2","천안 도시재생 주요 지구를 중심으로 구체적인 사례를 둘러보는 전문코스 2 입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/99","전문코스2")],
             aliases=["전문코스 2","전문 코스 2","코스2 (전문)","투어 전문코스2"], page_ids=["99"]),
    UrlEntry("도시재생플러스 도시재생투어 전문코스3","도시재생+ > 도시재생투어 > 전문코스3","천안 도시재생 주요 지구를 중심으로 구체적인 사례를 둘러보는 전문코스 3 입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/100","전문코스3")],
             aliases=["전문코스 3","전문 코스 3","코스3 (전문)","투어 전문코스3"], page_ids=["100"]),
    UrlEntry("아카이브 뉴스레터","아카이브 > 뉴스레터","센터 뉴스레터 모음입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/144","뉴스레터")],
             aliases=["뉴스레터","소식지","센터 뉴스레터","레터"], page_ids=["144"]),
    # ── 아카이브
    UrlEntry("아카이브 발간물","아카이브 > 발간물","천안시 도시재생지원센터에서 발행한 자료들을 열람하거나 다운로드할 수 있습니다.",
             [LinkItem("https://www.cheonanurc.or.kr/36","발간물")],
             aliases=["발간물","자료집","센터 발간물"], page_ids=["36"]),
    UrlEntry("아카이브 홍보 동영상","아카이브 > 홍보 동영상","센터 홍보 동영상 모음입니다.",
             [LinkItem("https://www.youtube.com/watch?v=ghzmqbIRJo0","홍보 동영상")],
             aliases=["홍보동영상","홍보 영상","동영상 자료"], page_ids=[]),
    UrlEntry("아카이브 도시재생 뉴스","아카이브 > 도시재생 뉴스","도시재생 관련 뉴스 모음입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/35","도시재생 뉴스")],
             aliases=["도시재생뉴스","뉴스","센터뉴스"], page_ids=["35"]),
    UrlEntry("아카이브 전문가 오피니언","아카이브 > 전문가 오피니언","도시재생 관련 전문가들의 시선과 해설을 담은 오피니언/칼럼 모음입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/37","전문가 오피니언")],
             aliases=["전문가오피니언","오피니언","전문가 칼럼"], page_ids=["37"]),
    UrlEntry("아카이브 마을기자단 및 인터뷰","아카이브 > 마을기자단 및 인터뷰","마을기자단의 시선으로 담은 이야기들과 인터뷰 자료 모음입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/108","마을기자단 및 인터뷰")],
             aliases=["마을기자단","인터뷰","마을기자단 및 인터뷰"], page_ids=["108"]),
    UrlEntry("사업소개 남산지구 도시재생뉴딜사업","사업소개 > 남산지구 도시재생사업","남산지구 도시재생사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/70","남산지구 도시재생뉴딜사업")],
             aliases=["남산지구 사업"], page_ids=["70"]),
    UrlEntry("사업소개 봉평지구 도시재생뉴딜사업","사업소개 > 봉평지구 도시재생사업","봉평지구 도시재생사업 안내입니다.",
             [LinkItem("https://www.cheonanurc.or.kr/72","봉평지구 도시재생뉴딜사업")],
             aliases=["봉평지구 사업","봉명지구 사업"], page_ids=["72"]),
]

# ── 인덱스/섹션
class _Index:
    def __init__(self, entries: List[UrlEntry]):
        self.entries = entries
        self.phrase_map: Dict[str, UrlEntry] = {}
        self.id_map: Dict[str, UrlEntry] = {}
        self.section_map: Dict[str, List[UrlEntry]] = {s: [] for s in SECTION_KEYS}
        for e in entries:
            for ph in [e.q] + e.aliases:
                k = _normalize(ph)
                if k:
                    self.phrase_map[k] = e
                    e._token_profiles.append(_canon_tokens(_tokenize(ph)))
            for pid in e.page_ids:
                self.id_map[str(pid).lower()] = e
            for extra in [e.title, e.answer]:
                if extra: e._token_profiles.append(_canon_tokens(_tokenize(extra)))
            for section in SECTION_KEYS:
                if e.title.startswith(f"{section} >"):
                    self.section_map[section].append(e)

    def by_phrase(self, query: str) -> Optional[UrlEntry]:
        return self.phrase_map.get(_normalize(query))

    def by_id(self, query: str) -> Optional[UrlEntry]:
        m = _NUM_EXTRACT.findall(query)
        if not m: return None
        for num, ident in m:
            key = (num or ident or "").lower()
            if key and key in self.id_map: return self.id_map[key]
        return None

    def entries_in_section(self, section: str) -> List[UrlEntry]:
        return list(self.section_map.get(section, []))

_INDEX = _Index(ENTRIES)

def _detect_section(tokens: List[str]) -> Optional[str]:
    tset = set(tokens)
    for s in SECTION_KEYS:
        if s in tset: return s
    return None

def _render_list(title: str, items: List[UrlEntry]) -> Optional[UrlResult]:
    if not items: return None
    parts=[f"<strong>{html.escape(title)}</strong><br><br><ul>"]
    for e in items:
        first = e.links[0] if e.links else None
        if first:
            parts.append(f"<li><strong>{html.escape(e.title)}</strong><br>{_anchor(first.url, first.label or first.url)}</li>")
    parts.append("</ul>")
    return UrlResult("".join(parts), hits=items)

def _entries_tour(kind: Optional[str]) -> List[UrlEntry]:
    if kind == "전문코스":
        return [e for e in ENTRIES if e.title.startswith("도시재생+ > 도시재생투어 > 전문코스")]
    if kind == "일반코스":
        return [e for e in ENTRIES if e.title.startswith("도시재생+ > 도시재생투어 > 일반코스")]
    # all
    return [e for e in ENTRIES if e.title.startswith("도시재생+ > 도시재생투어")]

def _should_broadcast_section(tokens_preserved: List[str], section: str) -> bool:
    """섹션만 물었거나 '어디/확인/주소/링크'가 보이면 링크 모음."""
    tset = set(tokens_preserved)
    if section not in tset: return False
    if tset & BROADCAST_HINTS: return True
    if any(tok.startswith("어디") for tok in tset): return True
    others = tset - {section} - GENERIC_IGNORE
    return len(others) == 0

# ── 스코어링
try:
    from rapidfuzz.fuzz import token_set_ratio as _rf_token_set_ratio
    _HAS_RF = True
except Exception:
    _HAS_RF = False

def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    return (len(sa & sb) / max(1, len(sa | sb))) if (sa or sb) else 0.0

def _score_tokens(qtoks: List[str], profiles: List[List[str]]) -> float:
    if not profiles: return 0.0
    if _HAS_RF:
        qs=" ".join(qtoks)
        return max(_rf_token_set_ratio(qs, " ".join(p)) for p in profiles)/100.0
    return max(_jaccard(qtoks, p) for p in profiles)

def _domain_boost(qtoks: List[str], e: UrlEntry) -> float:
    t=set(qtoks); boost=0.0
    if any(k in t for k in ("instagram","youtube","band","blog")) and any(p in _normalize(e.title) for p in ("instagram","youtube","band","blog")):
        boost+=0.15
    if "오시는길" in t and "오시는길" in _normalize(e.title): boost+=0.15
    if ({"투어","코스","일반코스","전문코스"} & t) and "투어" in _normalize(e.title): boost+=0.10
    if "프로그램신청" in t and "프로그램" in _normalize(e.title): boost+=0.10
    return boost

def _rule_match(qtoks: List[str]) -> Optional[UrlEntry]:
    toks=set(qtoks)
    # 오시는길
    if "오시는길" in toks:
        for e in ENTRIES:
            if e.page_ids==["131"] and ("센터" in toks or "천안시" in " ".join(qtoks)): return e
        for e in ENTRIES:
            if e.page_ids==["133"] and ("봉평지구" in toks or "봉명" in toks): return e
        for e in ENTRIES:
            if e.page_ids==["128"] and ("오룡지구" in toks or "오룡" in toks): return e
    # 프로그램 신청
    if "프로그램신청" in toks or ("프로그램" in toks and ({"신청","접수","모집"} & toks)):
        for e in ENTRIES:
            if e.page_ids==["41"]: return e
    # 투어 + (일반/전문)코스 + 번호
    kind, num = _extract_course(qtoks)
    if "투어" in toks:
        if kind and num:
            target = {("일반코스","1"):"78",("일반코스","2"):"97",
                      ("전문코스","1"):"98",("전문코스","2"):"99",("전문코스","3"):"100"}.get((kind,num))
            if target:
                for e in ENTRIES:
                    if target in e.page_ids: return e
        # 코스 미지정 → 안내
        for e in ENTRIES:
            if e.page_ids==["64"]: return e
    # 센터소개 조합
    if "센터소개" in toks and ({"인사말","greeting"} & toks):
        for e in ENTRIES:
            if e.page_ids==["24"]: return e
    if "센터소개" in toks and ({"조직도", "담당자", "조직", "센터조직", "구성", "팀", "조직구성", "인력", "부서","센터장", "사무국장", "팀장", "책임"} & toks):
        for e in ENTRIES:
            if e.page_ids==["25"]: return e
    # 아카이브 조합
    if "아카이브" in toks and ({"발간물"} & toks):
        for e in ENTRIES:
            if e.page_ids==["36"]: return e
    if "아카이브" in toks and ({"뉴스","도시재생뉴스"} & toks):
        for e in ENTRIES:
            if e.page_ids==["35"]: return e
    return None

def _best_candidates(query: str) -> List[Tuple[UrlEntry, float]]:
    hit = _INDEX.by_id(query)
    if hit: return [(hit,1.0)]
    hit = _INDEX.by_phrase(query)
    if hit: return [(hit,0.98)]
    qtoks = _canon_tokens(_tokenize(query))
    rule  = _rule_match(qtoks)
    if rule: return [(rule,0.95)]
    scored=[]
    for e in ENTRIES:
        s=_score_tokens(qtoks, e._token_profiles)+_domain_boost(qtoks,e)
        scored.append((e,s))
    scored.sort(key=lambda x:x[1], reverse=True)
    if not scored: return []
    top=scored[:3]; base=top[0][1]; TH=0.45 if _HAS_RF else 0.35
    return [(e,s) for e,s in top if s>=TH and s>=base-0.06]

# ── 공개 API
@dataclass
class UrlResult:
    html: str
    hits: List[UrlEntry]

def find_url_answer(query: str) -> Optional[UrlResult]:
    if not (query or "").strip():
        return None

    # ✅ 도시재생투어 코스 종류 질문 → 전체 코스 안내
    if "도시재생투어" in query and any(k in query for k in ["코스", "종류", "구성", "분류", "종류가", "어떤", "몇 개", "선택"]):
        course_links = [e for e in ENTRIES if e.title.startswith("도시재생+ > 도시재생투어 >")]
        if course_links:
            parts = ["<strong>도시재생투어는 다음과 같은 코스가 준비되어 있어요. 어떤 걸 원하시나요?</strong><br><br><ul>"]
            for e in course_links:
                if e.links:
                    parts.append(f"<li><strong>{html.escape(e.title)}</strong><br>{_anchor(e.links[0].url, e.links[0].label or e.links[0].url)}</li>")
            parts.append("</ul>")
            return UrlResult("".join(parts), hits=course_links)

    # 0) '페이지를 묻는' 의도 선판별(요청어 보존 토큰)
    ptoks = _canon_tokens(_tokenize(query, preserve_request=True))
    ptset = set(ptoks)   # ✅ set 변환 추가
    
    # A) 섹션 전체 브로드캐스트
    sec = _detect_section(ptoks)
    if sec and _should_broadcast_section(ptoks, sec):
        items = _INDEX.entries_in_section(sec)
        return _render_list(f"{sec} 섹션 링크 모음", items)

    # B) 투어 전용 브로드캐스트 (예: '전문투어 어디서 확인하지?')
    if "투어" in ptoks and (ptset & BROADCAST_HINTS or any(t.startswith("어디") for t in ptoks)):
        # 번호가 들어있다면 개별 매칭 단계로 넘김
        kind, num = _extract_course(ptoks)
        if not num:
            if "전문코스" in ptoks:
                return _render_list("도시재생투어 > 전문코스 링크 모음", _entries_tour("전문코스"))
            if "일반코스" in ptoks:
                return _render_list("도시재생투어 > 일반코스 링크 모음", _entries_tour("일반코스"))
            return _render_list("도시재생투어 링크 모음", _entries_tour(None))

    # 1) 일반 매칭
    cands = _best_candidates(query)
    if not cands:
        return None

    cands.sort(key=lambda x: x[1], reverse=True)
    best = cands[0][1]
    hits = [cands[0][0]]
    for e, s in cands[1:]:
        if s >= best - 0.03:
            hits.append(e)
        if len(hits) >= 3:
            break

    if len(hits) == 1:
        return UrlResult(html=hits[0].to_html(), hits=hits)

    parts = ["원하시는 항목에 가장 가까운 링크들입니다.<br><br><ul>"]
    for e in hits:
        first = e.links[0] if e.links else None
        if first:
            parts.append(
                f"<li><strong>{html.escape(e.title)}</strong><br>{_anchor(first.url, first.label or first.url)}</li>"
            )
    parts.append("</ul>")
    return UrlResult("".join(parts), hits=hits)


def list_registered_keys() -> List[str]:
    return [e.q for e in ENTRIES]

# ── 디버그 (다양한 사용자 질의 케이스)
if __name__ == "__main__":
    tests = [
        # 섹션/브로드캐스트
        "아카이브 어디서봐?", "센터소개 링크", "사업소개 전체", "도시재생+ 페이지",
        "커뮤니티 주소 알려줘", "도시재생플러스 어디서 확인해", "커뮤 링크 줘",

        # 투어 자연어
        "전문투어는 어디서 확인하지?", "일반투어 링크", "투어 코스 페이지 주소",
        "전문 투어 코스2 어디서 봐", "도시재생투어 어디?", "투어 코스 1 (일반)",

        # 특정 상세/ID/직접
        "센터소개 인사말", "아카이브 발간물", "도시재생+ 전문코스2", "투어 일반코스 1",
        "131", "/41", "new",

        # 플랫폼
        "인스타 센터", "유튜브 센터", "밴드 링크", "네이버 블로그 센터",

        # 오시는길
        "오시는길 센터", "봉명 오시는 길", "오룡 약도",
        "센터 주소 어디야", "봉명 주소좀", "오룡 위치 알려줘",

        "아카이브 뉴스레터", "뉴스레터 페이지", "센터 소식지", "레터 링크",

        # 기타 표현 변형
        "도시재생+ 프로그램 신청 어디서 확인함?", "프로그램 접수 페이지 URL 줄래?",
        "투어는 어디에서 볼 수 있어", "도시재생 플러스 공지사항 링크",
        "자료실 좀 보여줘", "아카이브 링크 목록 한눈에",
    ]
    for q in tests:
        r = find_url_answer(q)
        print(f"\nQ: {q}")
        print("HIT" if r else "MISS", "→", (r.html[:110] + "...") if r else "")
